#!/usr/bin/env python3
"""Apply brands schema + seed kits using only stdlib (no venv required)."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND / "bebcare.db"
KITS_DIR = BACKEND / "bebcare" / "data" / "brand_kits"

GENERIC_ID = "00000000-0000-0000-0000-000000000001"
BEBCARE_ID = "00000000-0000-0000-0000-000000000002"

CREATE_BRANDS = """
CREATE TABLE IF NOT EXISTS brands (
    brand_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_generic INTEGER NOT NULL DEFAULT 0,
    is_system INTEGER NOT NULL DEFAULT 0,
    voice TEXT,
    audience TEXT,
    tone_keywords TEXT,
    default_selling_points TEXT,
    default_hashtags TEXT,
    emoji_style TEXT,
    words_to_avoid TEXT,
    logo_font_rule TEXT,
    vertical_pack TEXT,
    default_product_type TEXT,
    copy_system_prompt TEXT,
    image_system_prompt TEXT,
    vision_image_system_prompt TEXT,
    vision_scene_system_prompt TEXT,
    narrative_perspectives TEXT,
    writing_styles TEXT,
    copy_emoji_hints TEXT,
    copy_example TEXT,
    image_fallback_selling_points TEXT,
    copy_fallback_selling_points TEXT,
    extra TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""

ADD_BRAND_ID = """
ALTER TABLE products ADD COLUMN brand_id TEXT REFERENCES brands(brand_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_BRANDS)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    if "brand_id" not in cols:
        try:
            conn.execute("ALTER TABLE products ADD COLUMN brand_id TEXT")
        except sqlite3.OperationalError:
            pass


def _upsert_brand(conn: sqlite3.Connection, kit: dict) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO brands (
            brand_id, slug, name, is_generic, is_system,
            voice, audience, tone_keywords, default_selling_points, default_hashtags,
            emoji_style, words_to_avoid, logo_font_rule, vertical_pack, default_product_type,
            copy_system_prompt, image_system_prompt, vision_image_system_prompt,
            vision_scene_system_prompt, narrative_perspectives, writing_styles,
            copy_emoji_hints, copy_example, image_fallback_selling_points,
            copy_fallback_selling_points, extra, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(brand_id) DO UPDATE SET
            slug=excluded.slug,
            name=excluded.name,
            is_generic=excluded.is_generic,
            is_system=excluded.is_system,
            voice=excluded.voice,
            audience=excluded.audience,
            tone_keywords=excluded.tone_keywords,
            default_selling_points=excluded.default_selling_points,
            default_hashtags=excluded.default_hashtags,
            emoji_style=excluded.emoji_style,
            words_to_avoid=excluded.words_to_avoid,
            logo_font_rule=excluded.logo_font_rule,
            vertical_pack=excluded.vertical_pack,
            default_product_type=excluded.default_product_type,
            copy_system_prompt=excluded.copy_system_prompt,
            image_system_prompt=excluded.image_system_prompt,
            vision_image_system_prompt=excluded.vision_image_system_prompt,
            vision_scene_system_prompt=excluded.vision_scene_system_prompt,
            narrative_perspectives=excluded.narrative_perspectives,
            writing_styles=excluded.writing_styles,
            copy_emoji_hints=excluded.copy_emoji_hints,
            copy_example=excluded.copy_example,
            image_fallback_selling_points=excluded.image_fallback_selling_points,
            copy_fallback_selling_points=excluded.copy_fallback_selling_points,
            extra=excluded.extra,
            updated_at=excluded.updated_at
        """,
        (
            kit["brand_id"],
            kit["slug"],
            kit["name"],
            1 if kit.get("is_generic") else 0,
            1 if kit.get("is_system", True) else 0,
            kit.get("voice"),
            kit.get("audience"),
            kit.get("tone_keywords"),
            json.dumps(kit.get("default_selling_points") or [], ensure_ascii=False),
            json.dumps(kit.get("default_hashtags") or [], ensure_ascii=False),
            kit.get("emoji_style"),
            kit.get("words_to_avoid"),
            kit.get("logo_font_rule"),
            kit.get("vertical_pack"),
            kit.get("default_product_type"),
            kit.get("copy_system_prompt"),
            kit.get("image_system_prompt"),
            kit.get("vision_image_system_prompt"),
            kit.get("vision_scene_system_prompt"),
            json.dumps(kit.get("narrative_perspectives") or [], ensure_ascii=False),
            json.dumps(kit.get("writing_styles") or [], ensure_ascii=False),
            kit.get("copy_emoji_hints"),
            kit.get("copy_example"),
            kit.get("image_fallback_selling_points"),
            json.dumps(kit.get("copy_fallback_selling_points") or [], ensure_ascii=False),
            json.dumps(kit.get("extra") or {}, ensure_ascii=False),
            now,
            now,
        ),
    )


def _assign_legacy_products(conn: sqlite3.Connection) -> int:
    baby_categories = {
        "night lights",
        "audio monitor",
        "air purifiers",
        "video monitor",
    }
    rows = conn.execute(
        "SELECT product_id, category, brand_voice FROM products WHERE brand_id IS NULL"
    ).fetchall()
    updated = 0
    for product_id, category, brand_voice in rows:
        cat = (category or "").strip().lower()
        brand_id = BEBCARE_ID if cat in baby_categories or (brand_voice or "").strip() else GENERIC_ID
        conn.execute(
            "UPDATE products SET brand_id = ? WHERE product_id = ?",
            (brand_id, product_id),
        )
        updated += 1
    return updated


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(conn)
        for path in sorted(KITS_DIR.glob("*.json")):
            kit = json.loads(path.read_text(encoding="utf-8"))
            _upsert_brand(conn, kit)
            print(f"Upserted brand: {kit['slug']} ({path.name})")
        assigned = _assign_legacy_products(conn)
        if assigned:
            print(f"Assigned brand_id on {assigned} products")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        print(f"brands table row count: {count}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
