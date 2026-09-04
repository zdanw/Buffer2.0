from sqlalchemy.orm import Session

from bebcare.models.product import ProductImage


def next_sort_index(db: Session, product_id: str, image_type: str) -> int:
    from sqlalchemy import func

    current = (
        db.query(func.max(ProductImage.sort_index))
        .filter(
            ProductImage.product_id == product_id,
            ProductImage.image_type == image_type,
        )
        .scalar()
    )
    return (current if current is not None else -1) + 1


def set_preferred_image(db: Session, image: ProductImage, is_preferred: bool) -> None:
    """At most one preferred product and one preferred scene per product."""
    if is_preferred:
        db.query(ProductImage).filter(
            ProductImage.product_id == image.product_id,
            ProductImage.image_type == image.image_type,
            ProductImage.image_id != image.image_id,
            ProductImage.is_preferred.is_(True),
        ).update({ProductImage.is_preferred: False}, synchronize_session="fetch")
    image.is_preferred = bool(is_preferred)
    try:
        from bebcare.services.asset_metadata import link_near_duplicates

        link_near_duplicates(db, image)
    except Exception:
        pass
