from sqlalchemy import func


def _allowed_urls(session, product_id: str, image_type: str) -> set[str]:
    from bebcare.models import ProductImage

    rows = (
        session.query(ProductImage.cdn_url)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == image_type,
        )
        .all()
    )
    return {row[0] for row in rows if row[0]}


def _random_product_urls(session, product_id: str, reference_count: int) -> list[str]:
    from bebcare.models import ProductImage

    product_images = (
        session.query(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == "product",
        )
        .order_by(func.random())
        .limit(reference_count)
        .all()
    )
    return [img.cdn_url for img in product_images]


def _random_scene_urls(session, product_id: str) -> list[str]:
    from bebcare.models import ProductImage

    scene_images = (
        session.query(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == "scene",
        )
        .order_by(func.random())
        .limit(1)
        .all()
    )
    return [scene_images[0].cdn_url] if scene_images else []


def _validate_pinned_urls(urls, allowed: set[str], *, label: str) -> list[str]:
    validated: list[str] = []
    for url in urls or []:
        u = (url or "").strip()
        if not u:
            continue
        if u not in allowed:
            raise ValueError(f"Invalid {label} reference URL")
        validated.append(u)
    return validated


def resolve_reference_images(
    session,
    product_id,
    reference_count,
    use_scene_reference=False,
    *,
    pinned_product_images=None,
    pinned_scene_images=None,
):
    """Pick references; optional pinned lists lock the same URLs across parallel runs."""
    if pinned_product_images is None and pinned_scene_images is None:
        return select_reference_images(
            session, product_id, reference_count, use_scene_reference
        )

    allowed_product = _allowed_urls(session, product_id, "product")
    allowed_scene = _allowed_urls(session, product_id, "scene")

    if pinned_product_images is not None:
        product_urls = _validate_pinned_urls(
            pinned_product_images, allowed_product, label="product"
        )
    else:
        product_urls = _random_product_urls(session, product_id, reference_count)

    scene_urls: list[str] = []
    effective_scene = bool(use_scene_reference)
    if use_scene_reference:
        if pinned_scene_images is not None:
            scene_urls = _validate_pinned_urls(
                pinned_scene_images, allowed_scene, label="scene"
            )
        else:
            scene_urls = _random_scene_urls(session, product_id)
        if not scene_urls:
            effective_scene = False

    return {
        "reference_images": scene_urls + product_urls,
        "reference_product_images": product_urls,
        "reference_scene_images": scene_urls,
        "use_scene_reference": effective_scene,
    }


def select_reference_images(session, product_id, reference_count, use_scene_reference=False):
    """Pick reference images and split by type for display/traceability.

    Returns dict with:
      reference_images, reference_product_images, reference_scene_images, use_scene_reference
    """
    from bebcare.models import ProductImage

    product_urls = []
    scene_urls = []
    effective_scene = bool(use_scene_reference)

    if use_scene_reference:
        scene_images = (
            session.query(ProductImage)
            .filter(
                ProductImage.product_id == product_id,
                ProductImage.image_type == "scene",
            )
            .order_by(func.random())
            .limit(1)
            .all()
        )
        product_images = (
            session.query(ProductImage)
            .filter(
                ProductImage.product_id == product_id,
                ProductImage.image_type == "product",
            )
            .order_by(func.random())
            .limit(reference_count)
            .all()
        )
        if scene_images:
            scene_urls = [scene_images[0].cdn_url]
        else:
            effective_scene = False
        product_urls = [img.cdn_url for img in product_images]
    else:
        # 未启用场景参考时只选产品图，避免场景图混入参考集
        product_images = (
            session.query(ProductImage)
            .filter(
                ProductImage.product_id == product_id,
                ProductImage.image_type == "product",
            )
            .order_by(func.random())
            .limit(reference_count)
            .all()
        )
        product_urls = [img.cdn_url for img in product_images]

    return {
        "reference_images": scene_urls + product_urls,
        "reference_product_images": product_urls,
        "reference_scene_images": scene_urls,
        "use_scene_reference": effective_scene,
    }


def ids_for_urls(session, product_id: str, urls: list[str] | None, image_type: str) -> list[str] | None:
    if urls is None:
        return None
    from bebcare.models import ProductImage

    rows = (
        session.query(ProductImage)
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == image_type,
        )
        .all()
    )
    by_url = {row.cdn_url: row.image_id for row in rows if row.cdn_url}
    ids = []
    for url in urls:
        u = (url or "").strip()
        if not u:
            continue
        image_id = by_url.get(u)
        if image_id:
            ids.append(image_id)
    return ids


def resolve_generate_references(
    session,
    *,
    product_id: str,
    owner_user_id: str,
    reference_count: int,
    use_scene_reference: bool,
    source: str,
    task_mode: str | None = None,
    image_size: str | None = None,
    pinned_product_images: list[str] | None = None,
    pinned_scene_images: list[str] | None = None,
    pinned_product_image_ids: list[str] | None = None,
    pinned_scene_image_ids: list[str] | None = None,
    requested_experiment: str | None = None,
):
    """Single selection entry for Studio and automation.

    Grounded path never uses func.random(). Rollout-off keeps current random
    scene-first behavior.
    """
    from bebcare.models import ProductImage
    from bebcare.services.grounded_rollout import (
        EXECUTED_LEGACY_RANDOM,
        EXPERIMENT_BASELINE,
        PIPELINE_BASELINE,
        apply_phase1b_experiment,
        grounded_selection_enabled,
    )
    from bebcare.utils.grounded_reference_selector import (
        GroundedSelection,
        InvalidReferencePinError,
        _legacy_manifest_from_urls,
        _url_lookup,
        fallback_legacy_selection,
        select_grounded_references,
    )

    from bebcare.services.asset_metadata import (
        ensure_product_deterministic_metadata,
        provenance_for_manifest,
    )
    from bebcare.services.asset_intelligence import (
        enqueue_selected_intelligence,
        load_usable_analyses,
        provenance_summary,
        selected_image_ids,
    )

    try:
        ensure_product_deterministic_metadata(
            session,
            product_id=product_id,
            owner_user_id=owner_user_id,
            trigger="generate",
        )
        # Release SQLite write locks before generate_task_store opens another session.
        session.commit()
    except Exception:
        pass

    intelligence_by_image = {}
    try:
        intelligence_by_image = load_usable_analyses(
            session, owner_user_id=owner_user_id, product_id=product_id
        )
    except Exception:
        intelligence_by_image = {}

    def _stamp(selection):
        try:
            selection.deterministic_metadata = provenance_for_manifest(
                session, selection.manifest
            )
        except Exception:
            selection.deterministic_metadata = None
        ids = selected_image_ids(selection.manifest)
        scheduled: list[str] = []
        fallback_reason = None
        try:
            scheduled = enqueue_selected_intelligence(
                image_ids=ids,
                owner_user_id=owner_user_id,
                product_id=product_id,
                source=source,
            )
        except Exception:
            fallback_reason = "intelligence_enqueue_failed"
        try:
            selection.asset_intelligence = provenance_summary(
                source=source,
                selected_ids=ids,
                by_image=intelligence_by_image,
                scheduled_ids=scheduled,
                fallback_reason=fallback_reason,
            )
        except Exception:
            selection.asset_intelligence = None
        return selection

    grounded = grounded_selection_enabled(source=source, task_mode=task_mode)
    requested = (requested_experiment or "").strip() or None
    if not grounded:
        selected = resolve_reference_images(
            session,
            product_id,
            reference_count,
            use_scene_reference,
            pinned_product_images=pinned_product_images,
            pinned_scene_images=pinned_scene_images,
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
        return _stamp(GroundedSelection(
            reference_images=selected["reference_images"],
            reference_product_images=selected["reference_product_images"],
            reference_scene_images=selected["reference_scene_images"],
            use_scene_reference=selected["use_scene_reference"],
            manifest=manifest.model_dump(),
            requested_pipeline_version=PIPELINE_BASELINE,
            executed_pipeline_version=EXECUTED_LEGACY_RANDOM,
            fallback_reason=None,
            fallback_path=None,
            experiment_variant=EXPERIMENT_BASELINE,
            grounded=False,
            requested_experiment_variant=requested,
        ))

    product_ids = pinned_product_image_ids
    scene_ids = pinned_scene_image_ids
    if product_ids is None and pinned_product_images is not None:
        product_ids = ids_for_urls(session, product_id, pinned_product_images, "product")
    if scene_ids is None and pinned_scene_images is not None:
        scene_ids = ids_for_urls(session, product_id, pinned_scene_images, "scene")

    try:
        return _stamp(
            apply_phase1b_experiment(
                select_grounded_references(
                    session,
                    product_id,
                    reference_count,
                    use_scene_reference,
                    owner_user_id=owner_user_id,
                    image_size=image_size,
                    pinned_product_image_ids=product_ids,
                    pinned_scene_image_ids=scene_ids,
                    intelligence_by_image=intelligence_by_image,
                ),
                requested_experiment=requested,
            )
        )
    except InvalidReferencePinError:
        raise
    except Exception as exc:
        fallback = fallback_legacy_selection(
            session,
            product_id,
            reference_count,
            use_scene_reference,
            reason=str(exc) or "grounded_selection_failed",
        )
        fallback.requested_experiment_variant = requested
        return _stamp(fallback)
