"""Resolve brand kit fields onto product_info for generation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from bebcare.models import Brand, Product, GENERIC_BRAND_ID


def _split_selling_points(raw) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return []


def _brand_to_context(brand: Brand) -> Dict[str, Any]:
    return {
        "brand_id": brand.brand_id,
        "brand_slug": brand.slug,
        "brand_name": brand.name,
        "is_generic_brand": bool(brand.is_generic),
        "brand_voice": brand.voice,
        "brand_audience": brand.audience,
        "vertical_pack": brand.vertical_pack or "general",
        "default_product_type": brand.default_product_type,
        "logo_font_rule": brand.logo_font_rule,
        "copy_system_prompt": brand.copy_system_prompt,
        "image_system_prompt": brand.image_system_prompt,
        "vision_image_system_prompt": brand.vision_image_system_prompt,
        "vision_scene_system_prompt": brand.vision_scene_system_prompt,
        "narrative_perspectives": brand.narrative_perspectives or [],
        "writing_styles": brand.writing_styles or [],
        "copy_emoji_hints": brand.copy_emoji_hints,
        "copy_example": brand.copy_example,
        "image_fallback_selling_points": brand.image_fallback_selling_points,
        "copy_fallback_selling_points": brand.copy_fallback_selling_points or [],
        "default_selling_points": brand.default_selling_points or [],
        "default_hashtags": brand.default_hashtags or [],
    }


def get_brand_for_product(db: Session, product: Product) -> Brand:
    brand_id = product.brand_id or GENERIC_BRAND_ID
    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if brand:
        return brand
    generic = db.query(Brand).filter(Brand.is_generic.is_(True)).first()
    if generic:
        return generic
    return db.query(Brand).filter(Brand.brand_id == GENERIC_BRAND_ID).first()


def resolve_product_brand_context(db: Session, product: Product) -> Dict[str, Any]:
    """Merge product facts with brand kit defaults (product wins when set)."""
    brand = get_brand_for_product(db, product)
    ctx = _brand_to_context(brand)

    product_points = _split_selling_points(product.selling_points)
    brand_points = _split_selling_points(ctx.get("default_selling_points"))
    selling_points = product_points or brand_points

    voice = ""
    if getattr(product, "use_brand_voice", True):
        voice = (product.brand_voice or "").strip() or (ctx.get("brand_voice") or "").strip()

    product_type = (product.category or "").strip() or (ctx.get("default_product_type") or "General")

    merged = {
        **ctx,
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "product_type": product_type,
        "description": product.description or "",
        "selling_points": selling_points,
        "brand_voice": voice,
        "use_brand_voice": bool(getattr(product, "use_brand_voice", True)),
    }
    return merged


def enrich_product_info(db: Session, product: Product, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attach brand-resolved fields to an existing product_info dict."""
    resolved = resolve_product_brand_context(db, product)
    if base:
        out = {**resolved, **base}
        # Re-resolve selling points / voice if base did not override meaningfully
        if not _split_selling_points(base.get("selling_points")):
            out["selling_points"] = resolved["selling_points"]
        if not (base.get("brand_voice") or "").strip():
            out["brand_voice"] = resolved["brand_voice"]
        return out
    return resolved
