"""Demand-triggered semantic asset intelligence. Short-lived DB sessions for writes."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.product_image_analysis import ProductImageAnalysis
from bebcare.schemas.asset_intelligence import (
    SEMANTIC_SCHEMA_VERSION,
    AssetIntelligenceResult,
    offering_context_version,
    parse_intelligence_result,
)
from bebcare.services.asset_intelligence_adapter import (
    ANALYSIS_PROVIDER,
    ANALYSIS_PURPOSE,
    analysis_model_version,
    analyze_reference_image,
)
from bebcare.services.asset_intelligence_policy import (
    FAILURE_PERMANENT,
    FAILURE_TRANSIENT,
    MAX_ANALYSIS_ATTEMPTS,
    AnalysisFailure,
    classify_analysis_failure,
    is_retry_eligible,
    is_usable_cache_hit,
    next_retry_at_for_attempt,
)
from bebcare.services.asset_intelligence_rollout import (
    asset_intelligence_mode,
    semantic_analysis_enabled,
)
from bebcare.services.ownership import stamp_owner

logger = logging.getLogger(__name__)


def _model_version() -> str:
    return analysis_model_version()


def load_usable_analyses(
    session: Session,
    *,
    owner_user_id: str,
    product_id: str,
) -> dict[str, AssetIntelligenceResult]:
    if not owner_user_id or not product_id:
        return {}
    images = (
        session.query(ProductImage)
        .join(Product, Product.product_id == ProductImage.product_id)
        .filter(
            ProductImage.product_id == product_id,
            Product.owner_user_id == owner_user_id,
        )
        .all()
    )
    hashes = [img.content_hash for img in images if img.content_hash]
    if not hashes:
        return {}
    product = session.query(Product).filter(Product.product_id == product_id).first()
    context = offering_context_version(getattr(product, "offering_type", None) if product else None)
    rows = (
        session.query(ProductImageAnalysis)
        .filter(
            ProductImageAnalysis.owner_user_id == owner_user_id,
            ProductImageAnalysis.content_hash.in_(hashes),
            ProductImageAnalysis.schema_version == SEMANTIC_SCHEMA_VERSION,
            ProductImageAnalysis.model_version == _model_version(),
            ProductImageAnalysis.offering_context_version == context,
        )
        .all()
    )
    by_hash = {}
    for row in rows:
        if not is_usable_cache_hit(row):
            continue
        try:
            by_hash[row.content_hash] = parse_intelligence_result(row.normalized_result)
        except Exception:
            continue
    mapping: dict[str, AssetIntelligenceResult] = {}
    for img in images:
        if img.content_hash and img.content_hash in by_hash:
            mapping[img.image_id] = by_hash[img.content_hash]
    return mapping


def analysis_for_image(
    session: Session,
    *,
    owner_user_id: str,
    image: ProductImage,
    offering_type: str | None,
) -> Optional[ProductImageAnalysis]:
    if not image.content_hash:
        return None
    return (
        session.query(ProductImageAnalysis)
        .filter(
            ProductImageAnalysis.owner_user_id == owner_user_id,
            ProductImageAnalysis.content_hash == image.content_hash,
            ProductImageAnalysis.schema_version == SEMANTIC_SCHEMA_VERSION,
            ProductImageAnalysis.model_version == _model_version(),
            ProductImageAnalysis.offering_context_version == offering_context_version(offering_type),
        )
        .first()
    )


def compact_labels_for_product(
    session: Session,
    *,
    owner_user_id: str,
    product: Product,
) -> dict[str, dict[str, Any]]:
    mapping = load_usable_analyses(
        session, owner_user_id=owner_user_id, product_id=product.product_id
    )
    labels: dict[str, dict[str, Any]] = {}
    suggestion = None
    for img in product.images or []:
        result = mapping.get(img.image_id)
        if not result:
            continue
        labels[img.image_id] = {
            "label": result.compact_label(image_type=img.image_type),
            "status": "ready",
        }
        evidence = result.dominant_offering_evidence
        if evidence and evidence != "unknown" and suggestion is None:
            suggestion = evidence
    return {"by_image": labels, "offering_type_suggestion": suggestion}


def provenance_summary(
    *,
    source: str,
    selected_ids: list[str],
    by_image: dict[str, AssetIntelligenceResult],
    scheduled_ids: list[str],
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    used = [iid for iid in selected_ids if iid in by_image]
    results = []
    for iid in selected_ids:
        result = by_image.get(iid)
        if result is None:
            continue
        results.append(
            {
                "image_id": iid,
                "is_packaging": result.is_packaging(),
                "is_screenshot": result.is_screenshot(),
                "label": result.compact_label(),
                "generation_suitability": result.generation_suitability,
            }
        )
    return {
        "mode": asset_intelligence_mode(),
        "enabled": semantic_analysis_enabled(source=source),
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "model_version": _model_version(),
        "cache_hit": bool(used),
        "cached_image_ids": used,
        "scheduled_image_ids": scheduled_ids,
        "fallback_reason": fallback_reason,
        "provider": ANALYSIS_PROVIDER if semantic_analysis_enabled(source=source) else None,
        "results": results,
    }


def enqueue_selected_intelligence(
    *,
    image_ids: list[str],
    owner_user_id: str,
    product_id: str,
    source: str,
    requested_mode: str | None = None,
    complete: Optional[Callable] = None,
) -> list[str]:
    if not semantic_analysis_enabled(source=source, requested_mode=requested_mode):
        return []
    ids = [iid for iid in image_ids if iid]
    if not ids:
        return []

    def _run():
        try:
            run_intelligence_job(
                image_ids=ids,
                owner_user_id=owner_user_id,
                product_id=product_id,
                source=source,
                complete=complete,
            )
        except Exception:
            logger.exception("asset intelligence job failed product_id=%s", product_id)

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return ids
    threading.Thread(target=_run, daemon=True).start()
    return ids


def run_intelligence_job(
    *,
    image_ids: list[str],
    owner_user_id: str,
    product_id: str,
    source: str,
    complete: Optional[Callable] = None,
) -> dict[str, Any]:
    """Process selected assets in a dedicated session. At most one vision call per job."""
    db = SessionLocal()
    outcomes: dict[str, Any] = {"processed": [], "skipped": [], "errors": []}
    try:
        if not semantic_analysis_enabled(source=source):
            return outcomes
        product = (
            db.query(Product)
            .filter(
                Product.product_id == product_id,
                Product.owner_user_id == owner_user_id,
            )
            .first()
        )
        if not product:
            return outcomes
        offering = getattr(product, "offering_type", None) or "unknown"
        context = offering_context_version(offering)
        images = (
            db.query(ProductImage)
            .filter(
                ProductImage.image_id.in_(image_ids),
                ProductImage.product_id == product_id,
            )
            .all()
        )
        seen_hashes: set[str] = set()
        called = False
        for image in images:
            if not image.content_hash:
                outcomes["skipped"].append({"image_id": image.image_id, "reason": "missing_content_hash"})
                continue
            existing = analysis_for_image(
                db, owner_user_id=owner_user_id, image=image, offering_type=offering
            )
            if is_usable_cache_hit(existing):
                existing.product_image_id = existing.product_image_id or image.image_id
                outcomes["skipped"].append({"image_id": image.image_id, "reason": "cache_hit"})
                continue
            if existing and not is_retry_eligible(existing):
                reason = "retry_wait"
                if (existing.failure_type or "") == FAILURE_PERMANENT:
                    reason = "permanent_failure"
                elif int(existing.attempt_count or 0) >= MAX_ANALYSIS_ATTEMPTS:
                    reason = "max_attempts"
                elif (existing.status or "") == "analyzing":
                    reason = "already_scheduled"
                outcomes["skipped"].append({"image_id": image.image_id, "reason": reason})
                continue
            if image.content_hash in seen_hashes:
                outcomes["skipped"].append({"image_id": image.image_id, "reason": "same_hash_batch"})
                continue
            if called:
                outcomes["skipped"].append({"image_id": image.image_id, "reason": "bounded_one_call"})
                continue
            seen_hashes.add(image.content_hash)
            called = True
            _analyze_one(
                db,
                image=image,
                product=product,
                owner_user_id=owner_user_id,
                offering=offering,
                context=context,
                existing=existing,
                complete=complete,
                outcomes=outcomes,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("asset intel unique cache race product_id=%s", product_id)
        outcomes["skipped"].append({"reason": "unique_constraint_race"})
    except Exception:
        db.rollback()
        logger.exception("asset intelligence job rollback")
        raise
    finally:
        db.close()
    return outcomes


def _reload_cache_row(
    db: Session,
    *,
    owner_user_id: str,
    image: ProductImage,
    offering: str,
) -> Optional[ProductImageAnalysis]:
    db.expire_all()
    return analysis_for_image(
        db, owner_user_id=owner_user_id, image=image, offering_type=offering
    )


def _analyze_one(
    db: Session,
    *,
    image: ProductImage,
    product: Product,
    owner_user_id: str,
    offering: str,
    context: str,
    existing: Optional[ProductImageAnalysis],
    complete: Optional[Callable],
    outcomes: dict[str, Any],
) -> None:
    row = existing
    now = datetime.utcnow()
    if row is None:
        row = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version=SEMANTIC_SCHEMA_VERSION,
            model_version=_model_version(),
            offering_context_version=context,
            status="analyzing",
            attempt_count=0,
            product_image_id=image.image_id,
        )
        stamp_owner(row, type("Owner", (), {"user_id": owner_user_id})())
        db.add(row)
    else:
        row.status = "analyzing"
        row.product_image_id = image.image_id
        row.updated_at = now
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.last_attempt_at = now
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        recovered = _reload_cache_row(
            db, owner_user_id=owner_user_id, image=image, offering=offering
        )
        if is_usable_cache_hit(recovered):
            outcomes["skipped"].append({"image_id": image.image_id, "reason": "cache_hit"})
            return
        outcomes["skipped"].append({"image_id": image.image_id, "reason": "unique_constraint_race"})
        return
    try:
        payload = analyze_reference_image(
            image_url=image.cdn_url,
            offering_type=offering,
            complete=complete,
        )
        result: AssetIntelligenceResult = payload["result"]
        row.normalized_result = result.model_dump()
        row.raw_response = payload.get("raw")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        usage = dict(usage)
        usage.setdefault("purpose", ANALYSIS_PURPOSE)
        usage.setdefault("provider", payload.get("provider") or ANALYSIS_PROVIDER)
        usage.setdefault("model", payload.get("model") or _model_version())
        usage["attempt_count"] = row.attempt_count
        usage["cache_hit"] = False
        usage["status"] = "ready"
        row.usage = usage
        row.status = "ready"
        row.failure_type = None
        row.error_category = None
        row.next_retry_at = None
        row.analyzed_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        outcomes["processed"].append(image.image_id)
        logger.info(
            "asset_intel image_id=%s purpose=%s provider=%s model=%s "
            "tokens_in=%s tokens_out=%s request_count=%s correction_used=%s "
            "latency_ms=%s attempt_count=%s status=%s",
            image.image_id,
            ANALYSIS_PURPOSE,
            usage.get("provider"),
            usage.get("model"),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("request_count"),
            usage.get("correction_used"),
            usage.get("latency_ms"),
            row.attempt_count,
            row.status,
        )
    except Exception as exc:
        if isinstance(exc, AnalysisFailure):
            failure_type, category = exc.failure_type, exc.error_category
            usage = dict(exc.usage or {})
            raw = (exc.raw or "")[:8000]
        else:
            failure_type, category = classify_analysis_failure(exc)
            usage = {}
            raw = None
        if failure_type == FAILURE_TRANSIENT and row.attempt_count >= MAX_ANALYSIS_ATTEMPTS:
            failure_type = FAILURE_PERMANENT
            category = "transient_retry_exhausted"
        row.status = "failed"
        row.failure_type = failure_type
        row.error_category = category
        row.raw_response = raw
        usage.update(
            {
                "purpose": ANALYSIS_PURPOSE,
                "provider": ANALYSIS_PROVIDER,
                "model": _model_version(),
                "cache_hit": False,
                "status": "failed",
                "error_category": category,
                "failure_type": failure_type,
                "attempt_count": row.attempt_count,
            }
        )
        row.usage = usage
        row.next_retry_at = (
            next_retry_at_for_attempt(row.attempt_count)
            if failure_type == FAILURE_TRANSIENT
            else None
        )
        row.updated_at = datetime.utcnow()
        outcomes["errors"].append(
            {"image_id": image.image_id, "error": category, "failure_type": failure_type}
        )
        logger.warning(
            "asset_intel failed image_id=%s category=%s failure_type=%s attempts=%s",
            image.image_id,
            category,
            failure_type,
            row.attempt_count,
        )


def selected_image_ids(manifest: Optional[dict]) -> list[str]:
    items = (manifest or {}).get("items") or []
    return [item.get("image_id") for item in items if item.get("image_id")]
