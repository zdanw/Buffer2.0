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
