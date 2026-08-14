#!/usr/bin/env python3
"""Import products (and images) from products-export.json into local SQLite."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND / "bebcare.db"
DEFAULT_EXPORT = (
    BACKEND
    / "bebcare"
    / "data"
    / "exports"
    / "buffrer2-0.vercel.app"
    / "products-export.json"
)
GENERIC_ID = "00000000-0000-0000-0000-000000000001"
BEBCARE_ID = "00000000-0000-0000-0000-000000000002"

BABY_CATEGORIES = {
    "night lights",
    "audio monitor",
    "air purifiers",
    "video monitor",
    "bottle warmer",
    "wearable breast pump",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_brand(product: dict) -> str:
    name = (product.get("product_name") or "").lower()
    cat = (product.get("category") or "").strip().lower()
    voice = (product.get("brand_voice") or "").strip()
    if "bebcare" in name or cat in BABY_CATEGORIES or voice:
        return BEBCARE_ID
    return GENERIC_ID


def _upsert_images(conn: sqlite3.Connection, product_id: str, images: list[dict]) -> int:
    count = 0
    for img in images:
        image_id = img.get("image_id") or str(uuid.uuid4())
        exists = conn.execute(
            "SELECT 1 FROM product_images WHERE image_id = ?", (image_id,)
        ).fetchone()
        row = (
            image_id,
            product_id,
            img.get("cdn_url"),
            img.get("phash"),
            img.get("width"),
            img.get("height"),
            img.get("image_type") or "product",
            img.get("uploaded_at") or _now(),
        )
        if exists:
            conn.execute(
                """
                UPDATE product_images SET
                  product_id=?, cdn_url=?, phash=?, width=?, height=?,
                  image_type=?, uploaded_at=?
                WHERE image_id=?
                """,
                (*row[1:], image_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO product_images (
                  image_id, product_id, cdn_url, phash, width, height,
                  image_type, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        count += 1
    return count


def import_products(export_path: Path) -> tuple[int, int]:
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    products = payload.get("products") or []
    if not products:
        print("No products in export file.")
        return 0, 0

    conn = sqlite3.connect(DB_PATH)
    try:
        imported = 0
        images_imported = 0
        for p in products:
            product_id = p.get("product_id") or str(uuid.uuid4())
            existing = conn.execute(
                "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            selling = p.get("selling_points") or []
            if isinstance(selling, list):
                selling_str = ",".join([x for x in selling if x])
            else:
                selling_str = str(selling or "")

            brand_id = _pick_brand(p)
            created = p.get("created_at") or _now()
            updated = p.get("updated_at") or created
            fields = (
                product_id,
                p.get("product_name", "Unnamed"),
                brand_id,
                p.get("category", "General"),
                p.get("description"),
                selling_str or None,
                p.get("brand_voice"),
                created,
                updated,
            )
            if existing:
                conn.execute(
                    """
                    UPDATE products SET
                      product_name=?, brand_id=?, category=?, description=?,
                      selling_points=?, brand_voice=?, updated_at=?
                    WHERE product_id=?
                    """,
                    (
                        fields[1],
                        fields[2],
                        fields[3],
                        fields[4],
                        fields[5],
                        fields[6],
                        updated,
                        product_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO products (
                      product_id, product_name, brand_id, category, description,
                      selling_points, brand_voice, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    fields,
                )
            all_images = (p.get("product_images") or []) + (p.get("scene_images") or [])
            images_imported += _upsert_images(conn, product_id, all_images)
            imported += 1
        conn.commit()
        return imported, images_imported
    finally:
        conn.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_EXPORT)
    args = parser.parse_args()
    if not args.file.exists():
        print(f"Export file not found: {args.file}")
        return 1
    count, img_count = import_products(args.file)
    print(f"Imported/updated {count} products and {img_count} images from {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
