"""Deterministic no-model grounded reference selection.

Does not download CDN bytes. Replaces func.random() only when rollout is on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from bebcare.models.generation_run import GenerationRun
from bebcare.models.product import Product, ProductImage
from bebcare.schemas.reference_manifest import (
    ManifestItem,
    ReferenceManifest,
    assert_canonical_grounded_order,
)
from bebcare.services.grounded_rollout import (
    EXECUTED_DETERMINISTIC,
    EXECUTED_LEGACY_RANDOM,
    EXPERIMENT_DETERMINISTIC,
    FALLBACK_PATH_LEGACY_RANDOM,
    PIPELINE_GROUNDED_V1,
)
from bebcare.utils.reference_selector import select_reference_images
from bebcare.utils.reference_suitability import (
    has_valid_dimensions,
    is_near_duplicate,
    parse_target_aspect,
    suitability_score,
    tie_break_key,
)

DIVERSITY_LOOKBACK = 8


class InvalidReferencePinError(ValueError):
    pass


@dataclass
class GroundedSelection:
    reference_images: list[str]
    reference_product_images: list[str]
    reference_scene_images: list[str]
    use_scene_reference: bool
    manifest: dict
    requested_pipeline_version: str
    executed_pipeline_version: str
    fallback_reason: Optional[str]
    fallback_path: Optional[str]
    experiment_variant: str
    grounded: bool


def _legacy_manifest_from_urls(
    product_urls: list[str],
    scene_urls: list[str],
    *,
    image_id_by_url: dict[str, str] | None = None,
) -> ReferenceManifest:
    """Scene-first URL list matching current provider order on the baseline path."""
    items: list[ManifestItem] = []
    order = 1
    lookup = image_id_by_url or {}
    for url in scene_urls:
        items.append(
            ManifestItem(
                order=order,
                role="scene",
                image_id=lookup.get(url),
                cdn_url=url,
                image_type="scene",
                authority="legacy_url",
            )
        )
        order += 1
    for index, url in enumerate(product_urls):
        items.append(
            ManifestItem(
                order=order,
                role="primary_subject" if index == 0 else "supporting_subject",
                image_id=lookup.get(url),
                cdn_url=url,
                image_type="product",
                authority="legacy_url",
            )
        )
        order += 1
    return ReferenceManifest(items=items)


def _url_lookup(images: list[ProductImage]) -> dict[str, str]:
    return {img.cdn_url: img.image_id for img in images if img.cdn_url}


def recent_primary_counts(session: Session, product_id: str) -> dict[str, int]:
    rows = (
        session.query(GenerationRun.reference_manifest)
        .filter(
            GenerationRun.product_id == product_id,
            GenerationRun.executed_pipeline_version == EXECUTED_DETERMINISTIC,
        )
        .order_by(GenerationRun.created_at.desc())
        .limit(DIVERSITY_LOOKBACK)
        .all()
    )
    counts: dict[str, int] = {}
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        try:
            manifest = ReferenceManifest.model_validate(payload)
        except Exception:
            continue
        primary = manifest.primary_image_id()
        if primary:
            counts[primary] = counts.get(primary, 0) + 1
    return counts


def _owned_images(
    session: Session,
    product_id: str,
    owner_user_id: str,
    image_type: str,
) -> list[ProductImage]:
    product = (
        session.query(Product)
        .filter(
            Product.product_id == product_id,
            Product.owner_user_id == owner_user_id,
        )
        .first()
    )
    if not product:
        return []
    return (
        session.query(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == image_type,
        )
        .all()
    )


def _valid_candidate(image: ProductImage) -> bool:
    if not image or not image.cdn_url:
        return False
    return has_valid_dimensions(image.width, image.height)


def _rank_key(image: ProductImage, score: float):
    return (
        -score,
        *tie_break_key(image.sort_index, image.uploaded_at, image.image_id),
    )


def _pin_images(
    session: Session,
    *,
    product_id: str,
    owner_user_id: str,
    image_ids: list[str],
    image_type: str,
) -> list[ProductImage]:
    if not image_ids:
        return []
    allowed = {img.image_id: img for img in _owned_images(session, product_id, owner_user_id, image_type)}
    ordered: list[ProductImage] = []
    for image_id in image_ids:
        iid = (image_id or "").strip()
        if not iid:
            continue
        image = allowed.get(iid)
        if image is None:
            raise InvalidReferencePinError(f"Invalid {image_type} reference image id")
        if image.product_id != product_id:
            raise InvalidReferencePinError(f"Invalid {image_type} reference image id")
        if image.image_type != image_type:
            raise InvalidReferencePinError(f"Invalid {image_type} reference image id")
        ordered.append(image)
    return ordered


def _exclude_near_duplicates(
    chosen: ProductImage,
    pool: list[ProductImage],
) -> list[ProductImage]:
    remaining = []
    for image in pool:
        if image.image_id == chosen.image_id:
            continue
        if is_near_duplicate(chosen.phash, image.phash):
            continue
        remaining.append(image)
    return remaining


def select_grounded_references(
    session: Session,
    product_id: str,
    reference_count: int,
    use_scene_reference: bool = False,
    *,
    owner_user_id: str,
    image_size: str | None = None,
    pinned_product_image_ids: list[str] | None = None,
    pinned_scene_image_ids: list[str] | None = None,
) -> GroundedSelection:
    count = max(int(reference_count or 1), 1)
    products = [img for img in _owned_images(session, product_id, owner_user_id, "product") if _valid_candidate(img)]
    scenes = [img for img in _owned_images(session, product_id, owner_user_id, "scene") if _valid_candidate(img)]
    repeats = recent_primary_counts(session, product_id)

    try:
        pinned_products = (
            _pin_images(
                session,
                product_id=product_id,
                owner_user_id=owner_user_id,
                image_ids=pinned_product_image_ids or [],
                image_type="product",
            )
            if pinned_product_image_ids is not None
            else None
        )
        pinned_scenes = (
            _pin_images(
                session,
                product_id=product_id,
                owner_user_id=owner_user_id,
                image_ids=pinned_scene_image_ids or [],
                image_type="scene",
            )
            if pinned_scene_image_ids is not None
            else None
        )
        if pinned_products is not None:
            pinned_products = [img for img in pinned_products if _valid_candidate(img)]
        if pinned_scenes is not None:
            pinned_scenes = [img for img in pinned_scenes if _valid_candidate(img)]
    except InvalidReferencePinError:
        raise

    if not products and not pinned_products:
        raise RuntimeError("no_valid_product_references")

    items: list[ManifestItem] = []
    selected_products: list[tuple[ProductImage, str, dict]] = []

    if pinned_products is not None:
        for index, image in enumerate(pinned_products[:count]):
            role = "primary_subject" if index == 0 else "supporting_subject"
            selected_products.append((image, "explicit_pin", {"score": None, "pin_order": index}))
    else:
        preferred = next(
            (
                img
                for img in products
                if img.is_preferred and img.image_type == "product" and _valid_candidate(img)
            ),
            None,
        )
        pool = list(products)
        if preferred:
            selected_products.append(
                (
                    preferred,
                    "preferred",
                    {
                        "score": suitability_score(
                            width=preferred.width,
                            height=preferred.height,
                            target_aspect=None,
                            image_type="product",
                            apply_diversity=False,
                        ),
                        "diversity_skipped": True,
                    },
                )
            )
            pool = _exclude_near_duplicates(preferred, pool)
        else:
            target_aspect = parse_target_aspect(image_size)
            ranked = sorted(
                pool,
                key=lambda img: _rank_key(
                    img,
                    suitability_score(
                        width=img.width,
                        height=img.height,
                        target_aspect=target_aspect,
                        image_type="product",
                        primary_repeat_count=repeats.get(img.image_id, 0),
                        apply_diversity=True,
                    ),
                ),
            )
            if not ranked:
                raise RuntimeError("no_valid_product_references")
            primary = ranked[0]
            selected_products.append(
                (
                    primary,
                    "suitability",
                    {
                        "score": suitability_score(
                            width=primary.width,
                            height=primary.height,
                            target_aspect=target_aspect,
                            image_type="product",
                            primary_repeat_count=repeats.get(primary.image_id, 0),
                        )
                    },
                )
            )
            pool = _exclude_near_duplicates(primary, ranked[1:])

        target = parse_target_aspect(image_size)
        while len(selected_products) < count and pool:
            ranked_support = sorted(
                pool,
                key=lambda img: _rank_key(
                    img,
                    suitability_score(
                        width=img.width,
                        height=img.height,
                        target_aspect=target,
                        image_type="product",
                        apply_diversity=False,
                    ),
                ),
            )
            nxt = ranked_support[0]
            selected_products.append(
                (
                    nxt,
                    "suitability",
                    {
                        "score": suitability_score(
                            width=nxt.width,
                            height=nxt.height,
                            target_aspect=target,
                            image_type="product",
                            apply_diversity=False,
                        )
                    },
                )
            )
            pool = _exclude_near_duplicates(nxt, ranked_support[1:])

    target = parse_target_aspect(image_size)
    scene_choice: tuple[ProductImage, str, dict] | None = None
    effective_scene = bool(use_scene_reference)
    if use_scene_reference:
        if pinned_scenes is not None:
            if pinned_scenes:
                scene = pinned_scenes[0]
                scene_choice = (scene, "explicit_pin", {"pin_order": 0})
            else:
                effective_scene = False
        else:
            preferred_scene = next(
                (img for img in scenes if img.is_preferred and _valid_candidate(img)),
                None,
            )
            if preferred_scene:
                scene_choice = (
                    preferred_scene,
                    "preferred",
                    {
                        "score": suitability_score(
                            width=preferred_scene.width,
                            height=preferred_scene.height,
                            target_aspect=target,
                            image_type="scene",
                            apply_diversity=False,
                        )
                    },
                )
            elif scenes:
                ranked_scenes = sorted(
                    scenes,
                    key=lambda img: _rank_key(
                        img,
                        suitability_score(
                            width=img.width,
                            height=img.height,
                            target_aspect=target,
                            image_type="scene",
                            apply_diversity=False,
                        ),
                    ),
                )
                scene = ranked_scenes[0]
                scene_choice = (
                    scene,
                    "suitability",
                    {
                        "score": suitability_score(
                            width=scene.width,
                            height=scene.height,
                            target_aspect=target,
                            image_type="scene",
                            apply_diversity=False,
                        )
                    },
                )
            else:
                effective_scene = False

    order = 1
    for index, (image, authority, meta) in enumerate(selected_products):
        items.append(
            ManifestItem(
                order=order,
                role="primary_subject" if index == 0 else "supporting_subject",
                image_id=image.image_id,
                cdn_url=image.cdn_url,
                image_type="product",
                authority=authority,  # type: ignore[arg-type]
                suitability=meta,
            )
        )
        order += 1
    if scene_choice:
        image, authority, meta = scene_choice
        items.append(
            ManifestItem(
                order=order,
                role="scene",
                image_id=image.image_id,
                cdn_url=image.cdn_url,
                image_type="scene",
                authority=authority,  # type: ignore[arg-type]
                suitability=meta,
            )
        )

    if not items or items[0].role != "primary_subject":
        raise RuntimeError("no_valid_product_references")

    manifest = ReferenceManifest(items=items)
    assert_canonical_grounded_order(manifest)
    return GroundedSelection(
        reference_images=manifest.ordered_urls(),
        reference_product_images=manifest.product_urls(),
        reference_scene_images=manifest.scene_urls(),
        use_scene_reference=effective_scene,
        manifest=manifest.model_dump(),
        requested_pipeline_version=PIPELINE_GROUNDED_V1,
        executed_pipeline_version=EXECUTED_DETERMINISTIC,
        fallback_reason=None,
        fallback_path=None,
        experiment_variant=EXPERIMENT_DETERMINISTIC,
        grounded=True,
    )


def fallback_legacy_selection(
    session: Session,
    product_id: str,
    reference_count: int,
    use_scene_reference: bool,
    *,
    reason: str,
) -> GroundedSelection:
    selected = select_reference_images(
        session, product_id, reference_count, use_scene_reference
    )
    images = (
        session.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .all()
    )
    manifest = _legacy_manifest_from_urls(
        selected["reference_product_images"],
        selected["reference_scene_images"],
        image_id_by_url=_url_lookup(images),
    )
    return GroundedSelection(
        reference_images=selected["reference_images"],
        reference_product_images=selected["reference_product_images"],
        reference_scene_images=selected["reference_scene_images"],
        use_scene_reference=selected["use_scene_reference"],
        manifest=manifest.model_dump(),
        requested_pipeline_version=PIPELINE_GROUNDED_V1,
        executed_pipeline_version=EXECUTED_LEGACY_RANDOM,
        fallback_reason=reason,
        fallback_path=FALLBACK_PATH_LEGACY_RANDOM,
        experiment_variant=EXPERIMENT_DETERMINISTIC,
        grounded=False,
    )
