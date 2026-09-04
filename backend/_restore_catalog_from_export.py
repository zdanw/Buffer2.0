"""Restore local brands/products from committed export + chat-known brand names. Do not commit."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bebcare.database import SessionLocal
from bebcare.models.brand import BEBCARE_BRAND_ID, Brand
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.services.brand_seed_service import initialize_brands
from bebcare.services.ownership import stamp_owner

EXPORT = (
    Path(__file__).resolve().parent
    / "bebcare"
    / "data"
    / "exports"
    / "buffrer2-0.vercel.app"
    / "products-export.json"
)

CHAT_BRANDS = (
    {"slug": "boopkin", "name": "Boopkin"},
    {"slug": "baby-common", "name": "Baby Common"},
)


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def _selling(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(str(x) for x in value if x) or None
    text = str(value).strip()
    return text or None


def main() -> None:
    payload = json.loads(EXPORT.read_text(encoding="utf-8"))
    products = payload.get("products") or []
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin.is_(True)).order_by(User.created_at.asc()).first()
        if not admin:
            raise SystemExit("no admin user")
        initialize_brands(db)
        for spec in CHAT_BRANDS:
            existing = (
                db.query(Brand)
                .filter(Brand.owner_user_id == admin.user_id, Brand.slug == spec["slug"])
                .first()
            )
            if existing:
                continue
            brand = Brand(
                slug=spec["slug"],
                name=spec["name"],
                is_generic=False,
                is_system=False,
                vertical_pack="baby_family",
            )
            stamp_owner(brand, admin)
            db.add(brand)
        for row in db.query(Product).filter(Product.product_name == "QDS enable-test").all():
            db.delete(row)
        db.flush()
        imported = 0
        images_n = 0
        for raw in products:
            product_id = raw["product_id"]
            product = db.query(Product).filter(Product.product_id == product_id).first()
            selling = _selling(raw.get("selling_points"))
            if product is None:
                product = Product(product_id=product_id)
                stamp_owner(product, admin)
                db.add(product)
            product.product_name = (raw.get("product_name") or "Unnamed").strip()
            product.brand_id = BEBCARE_BRAND_ID
            product.category = raw.get("category") or "General"
            product.description = raw.get("description")
            product.selling_points = selling
            product.brand_voice = raw.get("brand_voice")
            product.use_brand_voice = True
            product.has_on_body_branding = True
            product.offering_type = "physical_product"
            product.created_at = _parse_dt(raw.get("created_at"))
            product.updated_at = _parse_dt(raw.get("updated_at"))
            db.flush()
            imported += 1
            ordered = list(raw.get("product_images") or []) + list(raw.get("scene_images") or [])
            for index, img in enumerate(ordered):
                image_id = img.get("image_id")
                if not image_id:
                    continue
                row_img = db.query(ProductImage).filter(ProductImage.image_id == image_id).first()
                if row_img is None:
                    row_img = ProductImage(image_id=image_id)
                    db.add(row_img)
                row_img.product_id = product_id
                row_img.cdn_url = img["cdn_url"]
                row_img.phash = img.get("phash")
                row_img.width = img.get("width")
                row_img.height = img.get("height")
                row_img.image_type = img.get("image_type") or "product"
                row_img.uploaded_at = _parse_dt(img.get("uploaded_at"))
                row_img.sort_index = index
                images_n += 1
        db.commit()
        names = [p.product_name for p in db.query(Product).order_by(Product.product_name).all()]
        brands = [b.name for b in db.query(Brand).order_by(Brand.name).all()]
        print("brands", brands)
        print("products", names)
        print("imported", imported, "images", images_n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
