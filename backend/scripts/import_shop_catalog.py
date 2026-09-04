#!/usr/bin/env python3
"""Scrape shop catalogs and import products into a PulseForge deployment.

Usage:
  cd backend
  python scripts/import_shop_catalog.py \\
    --base-url https://buffrer2-0.vercel.app \\
    --username catalogsetup \\
    --password "$PASSWORD" \\
    --phase all

Phases:
  scrape  - fetch product pages, write catalog-cache.json
  import  - create brands + products + images from cache
  all     - scrape then import
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

logger = logging.getLogger("import_shop_catalog")

EXPORT_HOST = "buffrer2-0.vercel.app"
OUT_DIR = _BACKEND_DIR / "bebcare" / "data" / "exports" / EXPORT_HOST
BRAND_KITS_DIR = _BACKEND_DIR / "bebcare" / "data" / "brand_kits"
CACHE_PATH = OUT_DIR / "catalog-cache.json"
MANIFEST_PATH = OUT_DIR / "import-manifest.json"

SKIP_SLUG_PARTS = ("gift-card", "gift_card", "copy-of-")

SITE_CONFIGS = [
    {"key": "bebcare", "sitemap": "https://bebcare.com/sitemap-0.xml", "base": "https://bebcare.com"},
    {"key": "boopkin", "sitemap": "https://www.boopkin.com/sitemap-0.xml", "base": "https://www.boopkin.com"},
    {"key": "babycommon", "sitemap": "https://babycommon.com/sitemap-0.xml", "base": "https://babycommon.com"},
    {"key": "burgdy", "sitemap": "https://www.burgdy.com/sitemap-0.xml", "base": "https://www.burgdy.com"},
]

BRAND_SLUGS = ("bebcare", "boopkin", "babycommon", "burgdy")

CATEGORY_MAP = {
    "feeding": "Feeding",
    "feed": "Feeding",
    "night-light": "Night Lights",
    "night light": "Night Lights",
    "night lights": "Night Lights",
    "baby-monitors": "Baby Monitors",
    "audio": "Audio Monitor",
    "video": "Video Monitor",
    "air-purifiers": "Air Purifiers",
    "air purifiers": "Air Purifiers",
    "champagne": "Champagne",
    "red": "Red Wine",
    "white": "White Wine",
    "whiskey": "Whiskey",
    "wine-accessories": "Wine Accessories",
    "strollers": "Strollers",
    "carriers": "Carriers",
    "high-chairs": "High Chairs",
    "balance-bikes": "Balance Bikes",
    "scooters": "Scooters",
    "play": "Play",
    "nursery": "Nursery",
    "health-safety": "Health & Safety",
    "diapering": "Diapering",
    "bags-carriers": "Bags & Carriers",
}


@dataclass
class ScrapedImage:
    url: str
    image_type: str  # product | scene


@dataclass
class ScrapedProduct:
    source_url: str
    source_site: str
    slug: str
    product_name: str
    category: str
    description: str
    selling_points: list[str]
    sku: str | None
    brand_slug: str
    product_images: list[str] = field(default_factory=list)
    scene_images: list[str] = field(default_factory=list)
    preferred_image: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if "/products/" not in path:
        return ""
    return path.split("/products/")[-1].split("/")[0]


def _should_skip_slug(slug: str) -> bool:
    low = slug.lower()
    return any(part in low for part in SKIP_SLUG_PARTS)


def _parse_sitemap_urls(xml_text: str, base: str) -> list[str]:
    urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml_text)
    product_urls = []
    for raw in urls:
        url = raw.strip()
        if "/products/" not in url:
            continue
        if _should_skip_slug(_slug_from_url(url)):
            continue
        product_urls.append(url)
    return sorted(set(product_urls))


def _discover_bebcare_fallback(client: httpx.Client) -> list[str]:
    """Bebcare may use locale paths; collect /products/ links from sitemap index."""
    urls: set[str] = set()
    for path in ("/sitemap-0.xml", "/sitemap.xml", "/sitemap-index.xml"):
        try:
            resp = client.get(f"https://bebcare.com{path}", timeout=60)
            if resp.status_code != 200:
                continue
            text = resp.text
            if "<sitemapindex" in text:
                for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text):
                    try:
                        sub = client.get(loc.strip(), timeout=60)
                        if sub.status_code == 200:
                            urls.update(_parse_sitemap_urls(sub.text, "https://bebcare.com"))
                    except Exception:
                        continue
            else:
                urls.update(_parse_sitemap_urls(text, "https://bebcare.com"))
        except Exception:
            continue
    return sorted(urls)


def discover_product_urls(client: httpx.Client) -> dict[str, list[str]]:
    discovered: dict[str, list[str]] = {}
    for cfg in SITE_CONFIGS:
        key = cfg["key"]
        urls: list[str] = []
        try:
            resp = client.get(cfg["sitemap"], timeout=60, follow_redirects=True)
            if resp.status_code == 200:
                urls = _parse_sitemap_urls(resp.text, cfg["base"])
        except Exception as exc:
            logger.warning("sitemap failed %s: %s", cfg["sitemap"], exc)
        if key == "bebcare" and not urls:
            urls = _discover_bebcare_fallback(client)
        discovered[key] = urls
        logger.info("discovered %s: %d product URLs", key, len(urls))
    return discovered


def _extract_json_ld(html: str) -> list[dict[str, Any]]:
    blocks = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                blocks.extend(data)
            else:
                blocks.append(data)
        except json.JSONDecodeError:
            continue
    return blocks


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _title_category(html: str, product: dict[str, Any] | None) -> str:
    for block in _extract_json_ld(html):
        if block.get("@type") == "BreadcrumbList":
            items = block.get("itemListElement") or []
            if len(items) >= 3:
                name = items[2].get("name") if isinstance(items[2], dict) else None
                if name and name.lower() not in ("shop", "home", "products"):
                    return CATEGORY_MAP.get(name.lower(), name)
    m = re.search(r'<p[^>]*class="[^"]*category[^"]*"[^>]*>([^<]+)</p>', html, re.I)
    if m:
        raw = _clean_text(m.group(1))
        return CATEGORY_MAP.get(raw.lower(), raw.title())
    if product and product.get("category"):
        return str(product["category"])
    return "General"


def _section_text(html: str, heading: str) -> str:
    pat = rf"<h2[^>]*>\s*{re.escape(heading)}\s*</h2>(.*?)(?:<h2|</section>|$)"
    m = re.search(pat, html, re.S | re.I)
    if not m:
        return ""
    return _clean_text(m.group(1))[:4000]


def _feature_bullets(html: str) -> list[str]:
    section = _section_text(html, "Features")
    if not section:
        feat = re.search(r"<h2[^>]*>\s*Features\s*</h2>(.*?)(?:<h2|$)", html, re.S | re.I)
        if not feat:
            return []
        section = feat.group(1)
    bullets = re.findall(r"<li[^>]*>(.*?)</li>", section, re.S)
    out = []
    for b in bullets:
        t = _clean_text(b)
        if t and len(t) < 300:
            out.append(t)
    return out[:12]


def _product_images_for_slug(html: str, base_url: str, slug: str) -> tuple[list[str], list[str]]:
    slug_key = slug.replace("%C2%AE", "").lower()
    slug_parts = [p for p in re.split(r"[-_]", slug_key) if len(p) > 2]
    paths = re.findall(r'(?:https?://[^"\']+)?(/assets/products/[^"\'>\s]+)', html)
    product_imgs: list[str] = []
    scene_imgs: list[str] = []
    for path in dict.fromkeys(paths):
        low = path.lower()
        if not any(part in low for part in slug_parts[:3]):
            # generated folders use slug
            if f"/generated/{slug_key}" not in low and f"/generated/{slug.replace('-', '')}" not in low:
                if slug_key not in low:
                    continue
        full = urljoin(base_url, path.split("?")[0])
        if "inline-" in low or "context" in low or "routine" in low or "care" in low:
            if "gallery" not in low:
                scene_imgs.append(full)
                continue
        if "gallery-context" in low:
            scene_imgs.append(full)
        else:
            product_imgs.append(full)
    # Shopify CDN fallback
    cdn = re.findall(r'(https://cdn\.shopify\.com/[^"\'>\s]+)', html)
    for url in cdn:
        if any(part in url.lower() for part in slug_parts[:2]):
            product_imgs.append(url.split("?")[0])
    return product_imgs[:8], scene_imgs[:4]


def assign_brand_slug(source_site: str, product_url: str) -> str:
    slug = _slug_from_url(product_url)
    if source_site == "bebcare":
        return "bebcare"
    if source_site == "boopkin":
        return "boopkin"
    if source_site == "burgdy":
        return "burgdy"
    if slug.startswith("bebcare-"):
        return "bebcare"
    if slug.startswith("boopkin-"):
        return "boopkin"
    return "babycommon"


def scrape_product_page(client: httpx.Client, url: str, source_site: str) -> ScrapedProduct | None:
    try:
        resp = client.get(url, timeout=60, follow_redirects=True)
        if resp.status_code != 200:
            return None
        html = resp.text
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        slug = _slug_from_url(url)
        if not slug:
            return None

        product_ld = None
        for block in _extract_json_ld(html):
            if block.get("@type") == "Product":
                product_ld = block
                break

        name = ""
        if product_ld:
            name = (product_ld.get("name") or "").strip().strip('"')
        if not name:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            name = _clean_text(m.group(1)) if m else slug.replace("-", " ").title()

        desc = ""
        if product_ld and product_ld.get("description"):
            desc = str(product_ld["description"]).strip()
        if not desc:
            desc = _section_text(html, "About this product")
        if not desc:
            meta = re.search(r'<meta name="description" content="([^"]+)"', html)
            desc = meta.group(1) if meta else ""

        sku = product_ld.get("sku") if product_ld else None
        category = _title_category(html, product_ld)
        selling_points = _feature_bullets(html)
        if not selling_points and desc:
            selling_points = [s.strip() for s in desc.split(".") if 20 < len(s.strip()) < 200][:5]

        product_imgs, scene_imgs = _product_images_for_slug(html, base, slug)
        if product_ld and product_ld.get("image"):
            img = product_ld["image"]
            hero = img[0] if isinstance(img, list) else img
            if hero and hero not in product_imgs:
                product_imgs.insert(0, hero.split("?")[0])

        preferred = product_imgs[0] if product_imgs else None
        if not product_imgs:
            meta = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if meta:
                product_imgs = [meta.group(1).split("?")[0]]
                preferred = product_imgs[0]
        brand_slug = assign_brand_slug(source_site, url)

        return ScrapedProduct(
            source_url=url,
            source_site=source_site,
            slug=slug,
            product_name=name,
            category=category,
            description=desc,
            selling_points=selling_points,
            sku=str(sku) if sku else None,
            brand_slug=brand_slug,
            product_images=product_imgs,
            scene_images=scene_imgs,
            preferred_image=preferred,
        )
    except Exception as exc:
        logger.warning("scrape failed %s: %s", url, exc)
        return None


def scrape_catalog(client: httpx.Client, workers: int = 8) -> list[dict[str, Any]]:
    discovered = discover_product_urls(client)
    primary_keys = {"bebcare", "boopkin"}
    tasks: list[tuple[str, str]] = []
    for site, urls in discovered.items():
        for url in urls:
            tasks.append((site, url))

    scraped: list[ScrapedProduct] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(scrape_product_page, client, url, site): (site, url)
            for site, url in tasks
        }
        for fut in as_completed(futures):
            item = fut.result()
            if item:
                scraped.append(item)

    # Dedup: primary sources win over babycommon duplicates
    seen: dict[tuple[str, str], ScrapedProduct] = {}
    order = []
    for item in scraped:
        key = (item.brand_slug, _normalize_name(item.product_name))
        site_prio = 0 if item.source_site in primary_keys else 1
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
            order.append(key)
        else:
            exist_prio = 0 if existing.source_site in primary_keys else 1
            if site_prio < exist_prio:
                seen[key] = item

    # Skip babycommon bebcare/boopkin slugs when we have primary
    final: list[ScrapedProduct] = []
    for key in order:
        item = seen[key]
        if item.source_site == "babycommon" and item.brand_slug in ("bebcare", "boopkin"):
            continue
        final.append(item)

    logger.info("scraped %d unique products after dedup", len(final))
    return [asdict(p) for p in final]


def load_brand_kit(slug: str) -> dict[str, Any]:
    path = BRAND_KITS_DIR / f"{slug}.json"
    if slug == "bebcare":
        path = BRAND_KITS_DIR / "bebcare.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class PulseForgeClient:
    def __init__(self, base_url: str, username: str, password: str, delay: float = 0.2):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.username = username
        self.password = password
        self.client = httpx.Client(base_url=self.base_url, timeout=120.0, follow_redirects=True)
        self._set_token(self._login(username, password))
        self.brand_ids: dict[str, str] = {}
        self._product_index: dict[tuple[str, str], str] = {}

    def _set_token(self, token: str) -> None:
        self.client.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._sleep()
        resp = self.client.request(method, url, **kwargs)
        if resp.status_code == 401:
            logger.warning("token expired, re-authenticating")
            self._set_token(self._login(self.username, self.password))
            self._sleep()
            resp = self.client.request(method, url, **kwargs)
        return resp

    def _login(self, username: str, password: str) -> str:
        resp = self.client.post(
            "/v1/auth/login/",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("login missing token")
        return token

    def _sleep(self):
        time.sleep(self.delay)

    def list_brands(self) -> list[dict]:
        return self._request("GET", "/v1/brands/").json().get("data") or []

    def ensure_brands(self) -> dict[str, str]:
        existing = {b["slug"]: b["brand_id"] for b in self.list_brands()}
        for slug in BRAND_SLUGS:
            kit = load_brand_kit(slug)
            if slug in existing:
                brand_id = existing[slug]
                self._update_brand(brand_id, kit)
            else:
                brand_id = self._create_brand(kit)
            self.brand_ids[slug] = brand_id
            logger.info("brand ready %s -> %s", slug, brand_id)
        return self.brand_ids

    def _create_brand(self, kit: dict[str, Any]) -> str:
        payload = {
            "name": kit["name"],
            "slug": kit["slug"],
            "voice": kit.get("voice"),
            "audience": kit.get("audience"),
            "tone_keywords": kit.get("tone_keywords"),
            "default_selling_points": kit.get("default_selling_points") or [],
            "default_hashtags": kit.get("default_hashtags") or [],
            "emoji_style": kit.get("emoji_style", "moderate"),
            "words_to_avoid": kit.get("words_to_avoid"),
            "logo_font_rule": kit.get("logo_font_rule"),
            "logo_in_images": kit.get("logo_in_images", "preserve"),
            "vertical_pack": kit.get("vertical_pack", "general"),
            "default_product_type": kit.get("default_product_type", "General"),
            "logo_url": kit.get("logo_url"),
        }
        resp = self._request("POST", "/v1/brands/", json=payload)
        resp.raise_for_status()
        brand_id = resp.json()["brand_id"]
        self._update_brand(brand_id, kit)
        return brand_id

    def _update_brand(self, brand_id: str, kit: dict[str, Any]) -> None:
        payload = {
            "voice": kit.get("voice"),
            "audience": kit.get("audience"),
            "tone_keywords": kit.get("tone_keywords"),
            "default_selling_points": kit.get("default_selling_points"),
            "default_hashtags": kit.get("default_hashtags"),
            "emoji_style": kit.get("emoji_style"),
            "words_to_avoid": kit.get("words_to_avoid"),
            "logo_font_rule": kit.get("logo_font_rule"),
            "logo_in_images": kit.get("logo_in_images"),
            "vertical_pack": kit.get("vertical_pack"),
            "default_product_type": kit.get("default_product_type"),
            "logo_url": kit.get("logo_url"),
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
        }
        resp = self._request("PUT", f"/v1/brands/{brand_id}", json=payload)
        if resp.status_code >= 400:
            logger.warning("brand update %s: %s", brand_id, resp.text[:200])

    def initialize_packs(self) -> None:
        for slug, brand_id in self.brand_ids.items():
            resp = self._request("POST", f"/v1/brands/{brand_id}/initialize-pack")
            if resp.status_code >= 400:
                logger.warning("init pack %s: %s", slug, resp.text[:200])
            else:
                logger.info("initialized pack for %s", slug)

    def _build_product_index(self) -> None:
        for brand_id in self.brand_ids.values():
            page = 1
            while page <= 100:
                resp = self._request(
                    "GET",
                    "/v1/products/",
                    params={"page": page, "page_size": 100, "brand_id": brand_id},
                )
                resp.raise_for_status()
                data = resp.json()
                rows = data.get("data") or []
                for row in rows:
                    key = (brand_id, _normalize_name(row.get("product_name", "")))
                    self._product_index[key] = row["product_id"]
                pagination = data.get("pagination") or {}
                if page * 100 >= pagination.get("total", 0) or not rows:
                    break
                page += 1

    def find_product_by_name(self, name: str, brand_id: str) -> dict | None:
        product_id = self._product_index.get((brand_id, _normalize_name(name)))
        if not product_id:
            return None
        return {"product_id": product_id, "product_name": name}

    def create_or_update_product(self, item: dict[str, Any], brand_id: str) -> str:
        has_branding = item["brand_slug"] in ("bebcare", "boopkin")
        payload = {
            "product_name": item["product_name"],
            "category": item.get("category") or "General",
            "description": item.get("description") or "",
            "selling_points": item.get("selling_points") or [],
            "brand_id": brand_id,
            "use_brand_voice": True,
            "has_on_body_branding": has_branding,
            "offering_type": "physical_product",
        }
        existing = self.find_product_by_name(item["product_name"], brand_id)
        if existing:
            product_id = existing["product_id"]
            self._request("PUT", f"/v1/products/{product_id}", json=payload).raise_for_status()
            return product_id
        resp = self._request("POST", "/v1/products/", json=payload)
        resp.raise_for_status()
        product_id = resp.json()["product_id"]
        self._product_index[(brand_id, _normalize_name(item["product_name"]))] = product_id
        return product_id

    def _validate_image(self, content: bytes) -> tuple[int, int] | None:
        try:
            img = Image.open(BytesIO(content))
            img.load()
            w, h = img.size
            if w < 300 or h < 300:
                return None
            return w, h
        except Exception:
            return None

    def upload_image(self, product_id: str, url: str, image_type: str) -> dict | None:
        try:
            self._sleep()
            img_resp = httpx.get(url, timeout=90, follow_redirects=True)
            img_resp.raise_for_status()
            content = img_resp.content
            dims = self._validate_image(content)
            if not dims:
                return None
            filename = urlparse(url).path.split("/")[-1] or "image.png"
            if "." not in filename:
                filename += ".png"
            self._sleep()
            files = {"files": (filename, content, img_resp.headers.get("content-type", "image/png"))}
            resp = self._request(
                "POST",
                f"/v1/products/{product_id}/images",
                params={"image_type": image_type},
                files=files,
            )
            if resp.status_code >= 400:
                logger.warning("upload failed %s: %s", url, resp.text[:150])
                return None
            uploaded = resp.json().get("uploaded") or []
            return uploaded[0] if uploaded else None
        except Exception as exc:
            logger.warning("image error %s: %s", url, exc)
            return None

    def set_preferred(self, product_id: str, image_id: str) -> None:
        self._request(
            "PATCH",
            f"/v1/products/{product_id}/images/{image_id}",
            json={"is_preferred": True},
        )


def import_catalog(
    pf: PulseForgeClient,
    catalog: list[dict[str, Any]],
    manifest: dict[str, Any],
    max_products: int | None = None,
) -> None:
    pf.ensure_brands()
    pf._build_product_index()
    done_urls = {
        e["source_url"]: e
        for e in manifest.get("products", [])
        if e.get("status") == "ok" and e.get("images_uploaded", 0) > 0
    }

    items = catalog[:max_products] if max_products else catalog
    for idx, item in enumerate(items, 1):
        url = item["source_url"]
        if url in done_urls:
            continue
        brand_id = pf.brand_ids[item["brand_slug"]]
        entry = {
            "source_url": url,
            "brand_slug": item["brand_slug"],
            "product_name": item["product_name"],
            "status": "pending",
            "product_id": None,
            "images_uploaded": 0,
            "errors": [],
        }
        try:
            product_id = pf.create_or_update_product(item, brand_id)
            entry["product_id"] = product_id
            preferred_id = None
            for img_url in item.get("product_images") or []:
                uploaded = pf.upload_image(product_id, img_url, "product")
                if uploaded:
                    entry["images_uploaded"] += 1
                    if preferred_id is None or img_url == item.get("preferred_image"):
                        preferred_id = uploaded.get("image_id")
            for img_url in item.get("scene_images") or []:
                if pf.upload_image(product_id, img_url, "scene"):
                    entry["images_uploaded"] += 1
            if preferred_id:
                pf.set_preferred(product_id, preferred_id)
            entry["status"] = "ok" if entry["images_uploaded"] > 0 else "no_images"
        except Exception as exc:
            entry["status"] = "error"
            entry["errors"].append(str(exc))
            logger.exception("import failed %s", url)

        manifest["products"] = [e for e in manifest.get("products", []) if e.get("source_url") != url]
        manifest["products"].append(entry)
        manifest["updated_at"] = _now_iso()
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if idx % 10 == 0:
            logger.info("import progress %d/%d", idx, len(items))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import shop catalogs into PulseForge")
    parser.add_argument("--base-url", default=f"https://{EXPORT_HOST}")
    parser.add_argument("--username", default="catalogsetup")
    parser.add_argument("--password", required=True)
    parser.add_argument("--phase", choices=("scrape", "import", "all"), default="all")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--init-packs-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.init_packs_only:
        pf = PulseForgeClient(args.base_url, args.username, args.password)
        pf.ensure_brands()
        pf.initialize_packs()
        return 0

    if args.phase in ("scrape", "all"):
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            catalog = scrape_catalog(client, workers=args.workers)
        CACHE_PATH.write_text(
            json.dumps({"scraped_at": _now_iso(), "products": catalog}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("wrote cache %s (%d products)", CACHE_PATH, len(catalog))

    if args.phase in ("import", "all"):
        if not CACHE_PATH.exists():
            logger.error("missing cache %s — run --phase scrape first", CACHE_PATH)
            return 1
        catalog = json.loads(CACHE_PATH.read_text(encoding="utf-8")).get("products") or []
        manifest = {"started_at": _now_iso(), "products": []}
        if MANIFEST_PATH.exists():
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        pf = PulseForgeClient(args.base_url, args.username, args.password)
        import_catalog(pf, catalog, manifest, max_products=args.max_products)
        pf.initialize_packs()
        ok = sum(1 for p in manifest.get("products", []) if p.get("status") == "ok")
        logger.info("import complete: %d ok / %d total in manifest", ok, len(manifest.get("products", [])))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
