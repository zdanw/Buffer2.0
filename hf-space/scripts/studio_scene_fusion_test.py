"""One-shot Studio scene-fusion test (vision prompt + image generation).

Usage (from backend/):
  python scripts/studio_scene_fusion_test.py
  python scripts/studio_scene_fusion_test.py --vision-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from bebcare.database import SessionLocal
from bebcare.generator.content_generator import ContentGenerator
from bebcare.models import Product
from bebcare.schemas.generate import GenerateRequest
from bebcare.services.brand_context import enrich_product_info
from bebcare.utils.reference_selector import select_reference_images

DEFAULT_PRODUCT_ID = "6749b6e1-60ef-4b6f-a4c5-ae4af1bf425d"
DEFAULT_PROVIDER_ID = "1f61502d-abbe-4778-a005-591109d6b6cb"


def build_studio_product_info(db, product_id: str, provider_id: str) -> dict:
    product = db.query(Product).filter(Product.product_id == product_id).one()
    request = GenerateRequest(
        product_id=product_id,
        platform="instagram",
        reference_count=2,
        use_scene_reference=True,
        use_vision_image_prompt=True,
        realistic_placement=True,
        image_provider_id=provider_id,
        image_model="agnes-image-2.1-flash",
        image_size="1024x1024",
        locale="zh",
    )
    selected = select_reference_images(
        db, product_id, request.reference_count, request.use_scene_reference
    )
    base = {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points,
        "brand_voice": product.brand_voice,
        "reference_images": selected["reference_images"],
        "reference_product_images": selected["reference_product_images"],
        "reference_scene_images": selected["reference_scene_images"],
        "platform": request.platform,
        "use_scene_reference": selected["use_scene_reference"],
        "use_vision_image_prompt": True,
        "realistic_placement": True,
        "image_provider_id": provider_id,
        "image_model": request.image_model,
        "image_size": request.image_size,
        "owner_user_id": product.owner_user_id,
        "locale": "zh",
    }
    return enrich_product_info(db, product, base)


async def run(*, vision_only: bool) -> None:
    gen = ContentGenerator()
    db = SessionLocal()
    try:
        info = build_studio_product_info(db, DEFAULT_PRODUCT_ID, DEFAULT_PROVIDER_ID)
        refs = info["reference_images"]
        print("=== Studio scene-fusion test ===")
        print(f"Product: {info['product_name']} ({info['category']})")
        print(f"Scene refs: {len(info['reference_scene_images'])}")
        print(f"Product refs: {len(info['reference_product_images'])}")
        print(f"Total refs sent: {len(refs)}")

        user_content, system_prompt = gen._build_vision_user_content(info, refs)
        text_parts = [p["text"] for p in user_content if p.get("type") == "text"]
        print("\n--- Vision system prompt (first 400 chars) ---")
        print(system_prompt[:400], "...")
        print("\n--- Vision user text blocks ---")
        for i, t in enumerate(text_parts, 1):
            print(f"[{i}] {t[:500]}{'...' if len(t) > 500 else ''}")

        print("\n--- Calling vision model for image_prompt ... ---")
        image_prompt = await gen._call_vision_image_prompt_async(info, refs)
        print("\n=== Generated image_prompt ===")
        print(image_prompt)

        checks = [
            ("移除原产品", any(k in image_prompt for k in ("移除", "去掉", "清除", "删除"))),
            ("图一/场景", any(k in image_prompt for k in ("图一", "场景"))),
            ("图二/产品", any(k in image_prompt for k in ("图二", "产品", info["product_name"]))),
            ("摆放位置", any(k in image_prompt for k in ("放置", "摆放", "承托", "台面", "位置"))),
        ]
        print("\n--- Prompt quality checks ---")
        for label, ok in checks:
            mark = "OK" if ok else "MISS"
            print(f"  [{mark}] {label}")

        if vision_only:
            print("\n(vision-only mode; skipping image generation)")
            return

        print("\n--- Calling generate_image_async (full Studio path) ... ---")
        result = await gen.generate_image_async(
            info,
            platform="instagram",
            reference_images=refs,
            db=db,
            image_provider_id=DEFAULT_PROVIDER_ID,
            image_model="agnes-image-2.1-flash",
            image_size="1024x1024",
        )
        print("\n=== Result ===")
        image_urls = result.get("image_urls") or []
        print(json.dumps(
            {
                "image_prompt": result.get("image_prompt", "")[:800],
                "image_urls": image_urls,
                "warning": result.get("warning"),
                "dimensions": result.get("dimensions"),
            },
            ensure_ascii=False,
            indent=2,
        ))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vision-only",
        action="store_true",
        help="Only run vision prompt step (skip image API)",
    )
    args = parser.parse_args()
    asyncio.run(run(vision_only=args.vision_only))


if __name__ == "__main__":
    main()
