"""Deterministic asset metadata lifecycle, cache, and lazy refresh (Phase 2A)."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from bebcare.models.product import Product, ProductImage
from bebcare.services.deterministic_metadata import (
    DET_META_VERSION,
    cache_identity,
    extract_deterministic_metadata,
)
from bebcare.utils.reference_suitability import is_near_duplicate

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_ANALYZING = "analyzing"
STATUS_READY = "ready"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"
VALID_STATUSES = (
    STATUS_PENDING,
    STATUS_ANALYZING,
    STATUS_READY,
    STATUS_PARTIAL,
    STATUS_FAILED,
    STATUS_STALE,
)
LAZY_CDN_TIMEOUT_SECONDS = 5


def needs_deterministic_refresh(image: ProductImage, *, current_version: str = DET_META_VERSION) -> bool:
    status = (image.analysis_status or "").strip() or None
    version = (image.deterministic_metadata_version or "").strip() or None
    if status == STATUS_READY and version == current_version and image.content_hash:
        return False
    if version and version != current_version:
        return True
    # Terminal deterministic outcomes are not retried until version/schema changes
    # or an explicit force refresh. Failed/partial images stay usable for generation.
    if status in (STATUS_FAILED, STATUS_PARTIAL) and version == current_version:
        return False
    if status in (STATUS_STALE, STATUS_PENDING, STATUS_ANALYZING, None, ""):
        return True
    if not image.content_hash:
        return True
    return status != STATUS_READY


def _processing_record(
    *,
    trigger: str,
    cache_hit: bool,
    duration_ms: int,
    status: str,
    error_category: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "metadata_version": DET_META_VERSION,
        "trigger": trigger,
        "cache_hit": cache_hit,
        "duration_ms": duration_ms,
        "status": status,
        "error_category": error_category,
    }


def _merge_quality(base: Optional[dict], processing: dict) -> dict:
    payload = dict(base or {})
    payload["processing"] = processing
    return payload


def _log_telemetry(image: ProductImage, processing: dict) -> None:
    logger.info(
        "det_meta image_id=%s product_id=%s version=%s trigger=%s cache_hit=%s "
        "duration_ms=%s status=%s error_category=%s",
        image.image_id,
        image.product_id,
        processing.get("metadata_version"),
        processing.get("trigger"),
        processing.get("cache_hit"),
        processing.get("duration_ms"),
        processing.get("status"),
        processing.get("error_category"),
    )


def find_owner_cache_hit(
    session: Session,
    *,
    owner_user_id: str,
    content_hash: str,
    exclude_image_id: Optional[str] = None,
) -> Optional[ProductImage]:
    query = (
        session.query(ProductImage)
        .join(Product, Product.product_id == ProductImage.product_id)
        .filter(
            Product.owner_user_id == owner_user_id,
            ProductImage.content_hash == content_hash,
            ProductImage.deterministic_metadata_version == DET_META_VERSION,
            ProductImage.analysis_status == STATUS_READY,
        )
    )
    if exclude_image_id:
        query = query.filter(ProductImage.image_id != exclude_image_id)
    return query.first()


def _copy_cached_fields(target: ProductImage, source: ProductImage) -> None:
    target.detected_mime_type = source.detected_mime_type
    target.has_alpha = source.has_alpha
    target.exif_orientation = source.exif_orientation
    target.content_hash = source.content_hash
    if source.width and source.height:
        target.width = source.width
        target.height = source.height
    if source.phash:
        target.phash = source.phash
    quality = dict(source.basic_quality_json or {})
    quality.pop("processing", None)
    target.basic_quality_json = quality
    target.deterministic_metadata_version = DET_META_VERSION
    target.analysis_status = STATUS_READY
    target.deterministic_metadata_at = datetime.utcnow()


def _related_duplicate(left: ProductImage, right: ProductImage) -> bool:
    if is_near_duplicate(left.phash, right.phash):
        return True
    return bool(
        left.content_hash
        and right.content_hash
        and left.content_hash == right.content_hash
    )


def link_near_duplicates(session: Session, image: ProductImage) -> None:
    if not image.product_id:
        return
    if not image.phash and not image.content_hash:
        return
    siblings = (
        session.query(ProductImage)
        .filter(
            ProductImage.product_id == image.product_id,
            ProductImage.image_id != image.image_id,
            ProductImage.image_type == image.image_type,
        )
        .all()
    )
    if image.is_preferred:
        image.near_duplicate_of_image_id = None
        for sibling in siblings:
            if _related_duplicate(image, sibling) and not sibling.is_preferred:
                sibling.near_duplicate_of_image_id = image.image_id
        return
    preferred = [
        sibling
        for sibling in siblings
        if sibling.is_preferred and _related_duplicate(image, sibling)
    ]
    if preferred:
        image.near_duplicate_of_image_id = preferred[0].image_id
        return
    matches = [sibling for sibling in siblings if _related_duplicate(image, sibling)]
    if not matches:
        image.near_duplicate_of_image_id = None
        return
    anchor = sorted(
        matches,
        key=lambda row: (row.uploaded_at or datetime.min, row.image_id or ""),
    )[0]
    image.near_duplicate_of_image_id = anchor.image_id


def clear_near_duplicate_refs(session: Session, image_id: str) -> None:
    (
        session.query(ProductImage)
        .filter(ProductImage.near_duplicate_of_image_id == image_id)
        .update({ProductImage.near_duplicate_of_image_id: None}, synchronize_session=False)
    )


def apply_extracted(
    image: ProductImage,
    extracted: dict[str, Any],
    *,
    processing: dict[str, Any],
    status: str = STATUS_READY,
) -> None:
    image.content_hash = extracted["content_hash"]
    image.detected_mime_type = extracted["detected_mime_type"]
    image.has_alpha = extracted["has_alpha"]
    image.exif_orientation = extracted.get("exif_orientation")
    if extracted.get("width"):
        image.width = extracted["width"]
    if extracted.get("height"):
        image.height = extracted["height"]
    if extracted.get("phash"):
        image.phash = extracted["phash"]
    image.deterministic_metadata_version = DET_META_VERSION
    image.analysis_status = status
    image.deterministic_metadata_at = datetime.utcnow()
    image.basic_quality_json = _merge_quality(extracted.get("basic_quality_json"), processing)


def refresh_deterministic_metadata(
    session: Session,
    image: ProductImage,
    *,
    owner_user_id: str,
    raw_bytes: Optional[bytes] = None,
    trigger: str = "refresh",
    force: bool = False,
) -> ProductImage:
    """Idempotent refresh. Never overwrites original stored bytes (there are none locally)."""
    started = time.perf_counter()
    if not force and not needs_deterministic_refresh(image):
        duration_ms = int((time.perf_counter() - started) * 1000)
        processing = _processing_record(
            trigger=trigger,
            cache_hit=True,
            duration_ms=duration_ms,
            status=image.analysis_status or STATUS_READY,
        )
        image.basic_quality_json = _merge_quality(image.basic_quality_json, processing)
        _log_telemetry(image, processing)
        session.flush()
        return image

    previous = image.deterministic_metadata_version
    if previous and previous != DET_META_VERSION:
        image.analysis_status = STATUS_STALE
    else:
        image.analysis_status = STATUS_ANALYZING
    # Do not flush analyzing: holding a write lock across CDN/IO deadlocks SQLite
    # when generate_task_store opens a second session.

    try:
        if raw_bytes is None:
            raw_bytes = _download_legacy_bytes(image)
        if not raw_bytes:
            raise ValueError("missing_image_bytes")
        extracted = extract_deterministic_metadata(raw_bytes)
        cached = find_owner_cache_hit(
            session,
            owner_user_id=owner_user_id,
            content_hash=extracted["content_hash"],
            exclude_image_id=image.image_id,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        if cached is not None:
            _copy_cached_fields(image, cached)
            processing = _processing_record(
                trigger=trigger,
                cache_hit=True,
                duration_ms=duration_ms,
                status=STATUS_READY,
            )
            image.basic_quality_json = _merge_quality(image.basic_quality_json, processing)
            link_near_duplicates(session, image)
            _log_telemetry(image, processing)
            session.flush()
            return image
        processing = _processing_record(
            trigger=trigger,
            cache_hit=False,
            duration_ms=duration_ms,
            status=STATUS_READY,
        )
        apply_extracted(image, extracted, processing=processing)
        link_near_duplicates(session, image)
        _log_telemetry(image, processing)
        session.flush()
        return image
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        category = type(exc).__name__
        status = STATUS_PARTIAL if image.width and image.height else STATUS_FAILED
        processing = _processing_record(
            trigger=trigger,
            cache_hit=False,
            duration_ms=duration_ms,
            status=status,
            error_category=category,
        )
        image.analysis_status = status
        image.deterministic_metadata_version = DET_META_VERSION
        image.deterministic_metadata_at = datetime.utcnow()
        image.basic_quality_json = _merge_quality(image.basic_quality_json, processing)
        _log_telemetry(image, processing)
        logger.warning(
            "det_meta failed image_id=%s category=%s err=%s",
            image.image_id,
            category,
            str(exc)[:200],
        )
        session.flush()
        return image


def _download_legacy_bytes(image: ProductImage) -> Optional[bytes]:
    url = (image.cdn_url or "").strip()
    if not url:
        return None
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".test") or host.endswith(".invalid") or host in ("localhost", "127.0.0.1"):
        raise ValueError("non_fetchable_url")
    from bebcare.utils.image_utils import _DOWNLOAD_HEADERS
    import requests

    response = requests.get(url, timeout=LAZY_CDN_TIMEOUT_SECONDS, headers=_DOWNLOAD_HEADERS)
    response.raise_for_status()
    return response.content or None


def ensure_product_deterministic_metadata(
    session: Session,
    *,
    product_id: str,
    owner_user_id: str,
    trigger: str = "generate",
) -> dict[str, Any]:
    """Lazy, non-blocking. Failures are recorded; generation must continue."""
    images = (
        session.query(ProductImage)
        .join(Product, Product.product_id == ProductImage.product_id)
        .filter(
            ProductImage.product_id == product_id,
            Product.owner_user_id == owner_user_id,
        )
        .all()
    )
    summaries = []
    for image in images:
        try:
            if needs_deterministic_refresh(image):
                refresh_deterministic_metadata(
                    session,
                    image,
                    owner_user_id=owner_user_id,
                    trigger=trigger,
                )
        except Exception:
            logger.exception("det_meta ensure skipped image_id=%s", image.image_id)
        summaries.append(summarize_image(image))
    return {"images": summaries, "trigger": trigger, "metadata_version": DET_META_VERSION}


def summarize_image(image: ProductImage) -> dict[str, Any]:
    digest = image.content_hash
    version = image.deterministic_metadata_version
    identity = cache_identity(digest, version) if digest and version else None
    quality = image.basic_quality_json or {}
    return {
        "image_id": image.image_id,
        "analysis_status": image.analysis_status,
        "cache_identity": identity,
        "has_alpha": image.has_alpha,
        "detected_mime_type": image.detected_mime_type,
        "quality_warning": quality.get("warning"),
        "metadata_usable": image.analysis_status == STATUS_READY
        and version == DET_META_VERSION,
    }


def provenance_for_manifest(session: Session, manifest: Optional[dict]) -> dict[str, Any]:
    items = (manifest or {}).get("items") or []
    ids = [item.get("image_id") for item in items if item.get("image_id")]
    if not ids:
        return {"metadata_version": DET_META_VERSION, "images": []}
    rows = session.query(ProductImage).filter(ProductImage.image_id.in_(ids)).all()
    by_id = {row.image_id: row for row in rows}
    return {
        "metadata_version": DET_META_VERSION,
        "images": [summarize_image(by_id[iid]) for iid in ids if iid in by_id],
    }


def is_exact_duplicate(left: ProductImage, right: ProductImage) -> bool:
    if left.analysis_status != STATUS_READY or right.analysis_status != STATUS_READY:
        return False
    if not left.content_hash or not right.content_hash:
        return False
    if left.deterministic_metadata_version != DET_META_VERSION:
        return False
    if right.deterministic_metadata_version != DET_META_VERSION:
        return False
    return left.content_hash == right.content_hash
