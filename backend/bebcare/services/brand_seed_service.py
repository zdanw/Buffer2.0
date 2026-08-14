"""Seed system brand kits from JSON files into the database."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from bebcare.models import Brand, Product, GENERIC_BRAND_ID, BEBCARE_BRAND_ID

logger = logging.getLogger(__name__)

_BRAND_KITS_DIR = Path(__file__).resolve().parent.parent / "data" / "brand_kits"


def _load_kit_files() -> List[Dict[str, Any]]:
    kits: List[Dict[str, Any]] = []
    if not _BRAND_KITS_DIR.is_dir():
        logger.warning("Brand kits directory missing: %s", _BRAND_KITS_DIR)
        return kits
    for path in sorted(_BRAND_KITS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            data["_source_file"] = path.name
            kits.append(data)
    return kits


def _kit_to_brand_fields(kit: Dict[str, Any]) -> Dict[str, Any]:
    fields = {
        "brand_id": kit["brand_id"],
        "slug": kit["slug"],
        "name": kit["name"],
        "is_generic": kit.get("is_generic", False),
        "is_system": kit.get("is_system", True),
        "voice": kit.get("voice"),
        "audience": kit.get("audience"),
        "tone_keywords": kit.get("tone_keywords"),
        "default_selling_points": kit.get("default_selling_points"),
        "default_hashtags": kit.get("default_hashtags"),
        "emoji_style": kit.get("emoji_style"),
        "words_to_avoid": kit.get("words_to_avoid"),
        "logo_font_rule": kit.get("logo_font_rule"),
        "vertical_pack": kit.get("vertical_pack"),
        "default_product_type": kit.get("default_product_type"),
        "copy_system_prompt": kit.get("copy_system_prompt"),
        "image_system_prompt": kit.get("image_system_prompt"),
        "vision_image_system_prompt": kit.get("vision_image_system_prompt"),
        "vision_scene_system_prompt": kit.get("vision_scene_system_prompt"),
        "narrative_perspectives": kit.get("narrative_perspectives"),
        "writing_styles": kit.get("writing_styles"),
        "copy_emoji_hints": kit.get("copy_emoji_hints"),
        "copy_example": kit.get("copy_example"),
        "image_fallback_selling_points": kit.get("image_fallback_selling_points"),
        "copy_fallback_selling_points": kit.get("copy_fallback_selling_points"),
        "extra": kit.get("extra"),
    }
    if kit.get("_source_file"):
        extra = dict(fields.get("extra") or {})
        extra["kit_file"] = kit["_source_file"]
        fields["extra"] = extra
    return fields


def upsert_brand_from_kit(db: Session, kit: Dict[str, Any]) -> Brand:
    brand_id = kit["brand_id"]
    existing = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    fields = _kit_to_brand_fields(kit)
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        brand = existing
        action = "updated"
    else:
        brand = Brand(**fields)
        db.add(brand)
        action = "created"
    db.flush()
    logger.info("Brand kit %s (%s)", action, brand.slug)
    return brand


def seed_system_brands(db: Session, force_update: bool = True) -> Dict[str, str]:
    """Insert or update Generic + Bebcare brand kits."""
    results: Dict[str, str] = {}
    for kit in _load_kit_files():
        slug = kit.get("slug", "unknown")
        existing = db.query(Brand).filter(Brand.brand_id == kit["brand_id"]).first()
        if existing and not force_update:
            results[slug] = "skipped"
            continue
        upsert_brand_from_kit(db, kit)
        results[slug] = "upserted"
    db.commit()
    return results


def assign_legacy_products_to_bebcare(db: Session) -> int:
    """
    Link products without brand_id to Bebcare when they look like legacy baby catalog,
    otherwise Generic.
    """
    bebcare = db.query(Brand).filter(Brand.brand_id == BEBCARE_BRAND_ID).first()
    generic = db.query(Brand).filter(Brand.brand_id == GENERIC_BRAND_ID).first()
    if not bebcare or not generic:
        return 0

    baby_categories = {
        "night lights",
        "audio monitor",
        "air purifiers",
        "video monitor",
    }
    updated = 0
    products = db.query(Product).filter(Product.brand_id.is_(None)).all()
    for product in products:
        cat = (product.category or "").strip().lower()
        has_baby_voice = bool((product.brand_voice or "").strip())
        if cat in baby_categories or has_baby_voice:
            product.brand_id = BEBCARE_BRAND_ID
        else:
            product.brand_id = GENERIC_BRAND_ID
        updated += 1
    if updated:
        db.commit()
    return updated


def initialize_brands(db: Session) -> None:
    seed_system_brands(db, force_update=True)
    count = assign_legacy_products_to_bebcare(db)
    if count:
        logger.info("Assigned brand_id on %s legacy products", count)
