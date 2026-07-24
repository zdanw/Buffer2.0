from sqlalchemy import func


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
