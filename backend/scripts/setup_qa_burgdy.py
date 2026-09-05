#!/usr/bin/env python3
"""Push Bebcare brand kit updates and create Burgdy automations on QA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

_BACKEND = Path(__file__).resolve().parents[1]
_KITS = _BACKEND / "bebcare" / "data" / "brand_kits"
_EXPORT = _BACKEND / "bebcare" / "data" / "exports" / "buffrer2-0.vercel.app" / "products-export.json"

# 11:59 AM US Eastern (EDT, Mar–Nov) = 23:59 Asia/Shanghai (scheduler timezone)
DAILY_CRON = "59 23 * * *"


def login(base_url: str, username: str, password: str) -> dict[str, str]:
    r = httpx.post(
        f"{base_url}/v1/auth/login/",
        data={"username": username, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def load_kit(slug: str) -> dict[str, Any]:
    path = _KITS / f"{slug}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def brand_by_slug(headers: dict[str, str], base_url: str, slug: str) -> dict[str, Any]:
    brands = httpx.get(f"{base_url}/v1/brands/", headers=headers, timeout=120).json().get("data", [])
    for brand in brands:
        if brand.get("slug") == slug:
            return brand
    raise RuntimeError(f"Brand not found: {slug}")


def update_brand_from_kit(headers: dict[str, str], base_url: str, slug: str) -> None:
    kit = load_kit(slug)
    brand = brand_by_slug(headers, base_url, slug)
    brand_id = brand["brand_id"]
    payload = {
        "voice": kit.get("voice"),
        "audience": kit.get("audience"),
        "tone_keywords": kit.get("tone_keywords"),
        "default_selling_points": kit.get("default_selling_points"),
        "default_hashtags": kit.get("default_hashtags"),
        "emoji_style": kit.get("emoji_style"),
        "words_to_avoid": kit.get("words_to_avoid"),
        "logo_url": kit.get("logo_url"),
        "logo_font_rule": kit.get("logo_font_rule"),
        "logo_in_images": kit.get("logo_in_images", "preserve"),
        "copy_system_prompt": kit.get("copy_system_prompt"),
        "image_system_prompt": kit.get("image_system_prompt"),
        "vision_image_system_prompt": kit.get("vision_image_system_prompt"),
        "narrative_perspectives": kit.get("narrative_perspectives"),
        "writing_styles": kit.get("writing_styles"),
        "copy_emoji_hints": kit.get("copy_emoji_hints"),
        "copy_example": kit.get("copy_example"),
        "image_fallback_selling_points": kit.get("image_fallback_selling_points"),
        "copy_fallback_selling_points": kit.get("copy_fallback_selling_points"),
    }
    r = httpx.put(f"{base_url}/v1/brands/{brand_id}", headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    print(f"Updated brand kit: {slug}")


def load_burgdy_products(headers: dict[str, str], base_url: str) -> list[dict[str, Any]]:
    burgdy_id = brand_by_slug(headers, base_url, "burgdy")["brand_id"]
    if _EXPORT.is_file():
        data = json.loads(_EXPORT.read_text(encoding="utf-8"))
        exported = [p for p in data.get("products", []) if p.get("brand_id") == burgdy_id]
        if exported:
            print(f"Loaded {len(exported)} Burgdy products from export snapshot")
            return exported

    products: list[dict[str, Any]] = []
    page = 1
    page_size = 20
    while True:
        res = None
        for attempt in range(4):
            try:
                res = httpx.get(
                    f"{base_url}/v1/products/",
                    headers=headers,
                    params={"page": page, "page_size": page_size, "brand_id": burgdy_id},
                    timeout=120,
                )
                if res.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
        if res is None or res.status_code != 200:
            print(f"Warning: products page {page} failed ({getattr(res, 'status_code', 'error')})")
            break
        payload = res.json()
        batch = payload.get("data") or []
        products.extend(batch)
        pagination = payload.get("pagination") or {}
        if page >= pagination.get("pages", 1):
            break
        page += 1
    return products


def filter_products(products: list[dict[str, Any]], keyword: str) -> list[str]:
    keyword = keyword.lower()
    ids: list[str] = []
    for product in products:
        blob = " ".join(
            [
                product.get("product_name") or "",
                product.get("category") or "",
                product.get("description") or "",
            ]
        ).lower()
        if keyword in blob:
            ids.append(product["product_id"])
    return ids


def existing_task_names(headers: dict[str, str], base_url: str) -> set[str]:
    names: set[str] = set()
    page = 1
    while True:
        res = httpx.get(
            f"{base_url}/v1/tasks/",
            headers=headers,
            params={"page": page, "page_size": 50},
            timeout=60,
        ).json()
        for task in res.get("data", []):
            names.add(task.get("name", ""))
        pagination = res.get("pagination") or {}
        if page >= pagination.get("pages", 1):
            break
        page += 1
    return names


def create_task(headers: dict[str, str], base_url: str, payload: dict[str, Any]) -> None:
    r = httpx.post(f"{base_url}/v1/tasks/", headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    print(f"Created task: {payload['name']}")


def setup_automations(headers: dict[str, str], base_url: str) -> None:
    burgdy_products = load_burgdy_products(headers, base_url)
    burgundy_ids = filter_products(burgdy_products, "burgundy")
    bordeaux_ids = filter_products(burgdy_products, "bordeaux")
    champagne_ids = [p["product_id"] for p in burgdy_products if (p.get("category") or "").lower() == "champagne"]
    meme_ids = filter_products(burgdy_products, "champagne")[:15] + filter_products(burgdy_products, "burgundy")[:10] + filter_products(burgdy_products, "bordeaux")[:5]

    specs = [
        {
            "name": "Burgdy | Burgundy Daily Sales",
            "target_products": burgundy_ids,
            "target_categories": [],
            "mode": "auto",
            "use_scene_reference": True,
            "realistic_placement": True,
            "use_vision_image_prompt": False,
        },
        {
            "name": "Burgdy | Bordeaux Daily Sales",
            "target_products": bordeaux_ids,
            "target_categories": [],
            "mode": "auto",
            "use_scene_reference": True,
            "realistic_placement": True,
            "use_vision_image_prompt": False,
        },
        {
            "name": "Burgdy | Champagne Daily Sales",
            "target_products": champagne_ids,
            "target_categories": [],
            "mode": "auto",
            "use_scene_reference": True,
            "realistic_placement": True,
            "use_vision_image_prompt": False,
        },
        {
            "name": "Burgdy | Wine Meme Daily",
            "target_products": meme_ids,
            "target_categories": [],
            "mode": "manual",
            "use_scene_reference": False,
            "realistic_placement": False,
            "use_vision_image_prompt": True,
            "generate_image_count": 3,
            "generate_copy_count": 3,
        },
    ]

    existing = existing_task_names(headers, base_url)
    for spec in specs:
        if spec["name"] in existing:
            print(f"Skip existing task: {spec['name']}")
            continue
        if not spec["target_products"]:
            print(f"Skip {spec['name']}: no matching products")
            continue
        payload = {
            "name": spec["name"],
            "cron": DAILY_CRON,
            "mode": spec["mode"],
            "target_categories": spec["target_categories"],
            "target_products": spec["target_products"],
            "platforms": ["instagram", "facebook"],
            "reference_image_count": 2,
            "run_count_per_execution": 1,
            "generate_image_count": spec.get("generate_image_count", 2),
            "generate_copy_count": spec.get("generate_copy_count", 2),
            "enabled": True,
            "use_scene_reference": spec["use_scene_reference"],
            "use_vision_image_prompt": spec["use_vision_image_prompt"],
            "realistic_placement": spec["realistic_placement"],
            "notify_on_publish": spec["mode"] == "auto",
        }
        create_task(headers, base_url, payload)
        print(f"  -> {len(spec['target_products'])} products in rotation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure QA Bebcare brand + Burgdy automations")
    parser.add_argument("--base-url", default="https://buffrer2-0.vercel.app")
    parser.add_argument("--username", default="catalogsetup")
    parser.add_argument("--password", required=True)
    parser.add_argument("--skip-brands", action="store_true")
    parser.add_argument("--skip-automations", action="store_true")
    args = parser.parse_args()

    headers = login(args.base_url.rstrip("/"), args.username, args.password)
    if not args.skip_brands:
        update_brand_from_kit(headers, args.base_url.rstrip("/"), "bebcare")
        update_brand_from_kit(headers, args.base_url.rstrip("/"), "burgdy")
    if not args.skip_automations:
        setup_automations(headers, args.base_url.rstrip("/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
