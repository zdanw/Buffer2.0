#!/usr/bin/env python3
"""
Export products (and optional categories) from a remote PulseForge deployment.

Usage:
  cd backend
  python scripts/export_remote_assets.py \\
    --base-url https://buffrer2-0.vercel.app \\
    --username admin \\
    --password "$ADMIN_PASSWORD"

Environment variables (optional):
  REMOTE_API_BASE_URL, REMOTE_API_USERNAME, REMOTE_API_PASSWORD

Output:
  bebcare/data/exports/<host>/products-export.json
  bebcare/data/exports/<host>/export-manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _host_slug(base_url: str) -> str:
    host = urlparse(base_url).netloc or base_url
    return host.replace(":", "-")


def login(client: httpx.Client, username: str, password: str) -> str:
    resp = client.post(
        "/v1/auth/login/",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Login succeeded but no access_token: {resp.text[:200]}")
    return token


def fetch_all_products(client: httpx.Client, page_size: int = 50) -> list[dict]:
    page = 1
    all_rows: list[dict] = []
    while True:
        resp = client.get("/v1/products/", params={"page": page, "page_size": page_size})
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") or []
        all_rows.extend(rows)
        pagination = payload.get("pagination") or {}
        total = pagination.get("total", len(all_rows))
        if len(all_rows) >= total or not rows:
            break
        page += 1
    return all_rows


def fetch_categories(client: httpx.Client) -> list[str]:
    resp = client.get("/v1/products/categories")
    resp.raise_for_status()
    return resp.json().get("categories") or []


def main() -> int:
    parser = argparse.ArgumentParser(description="Export remote PulseForge assets to local JSON")
    parser.add_argument(
        "--base-url",
        default=os.getenv("REMOTE_API_BASE_URL", "https://buffrer2-0.vercel.app"),
    )
    parser.add_argument("--username", default=os.getenv("REMOTE_API_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("REMOTE_API_PASSWORD"))
    parser.add_argument("--page-size", type=int, default=50)
    args = parser.parse_args()

    if not args.password:
        print(
            "ERROR: password required. Pass --password or set REMOTE_API_PASSWORD.",
            file=sys.stderr,
        )
        return 1

    base_url = args.base_url.rstrip("/")
    out_dir = _BACKEND_DIR / "bebcare" / "data" / "exports" / _host_slug(base_url)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_url": base_url,
        "status": "pending",
    }

    try:
        with httpx.Client(base_url=base_url, timeout=60.0, follow_redirects=True) as client:
            token = login(client, args.username, args.password)
            client.headers["Authorization"] = f"Bearer {token}"

            categories = fetch_categories(client)
            products = fetch_all_products(client, page_size=args.page_size)

            export_payload = {
                "exported_at": manifest["exported_at"],
                "source_url": base_url,
                "categories": categories,
                "product_count": len(products),
                "products": products,
            }

            products_path = out_dir / "products-export.json"
            products_path.write_text(
                json.dumps(export_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            manifest.update(
                {
                    "status": "success",
                    "product_count": len(products),
                    "categories": categories,
                    "products_file": str(products_path.relative_to(_BACKEND_DIR)),
                }
            )
            print(f"Exported {len(products)} products to {products_path}")
    except httpx.HTTPStatusError as exc:
        manifest.update(
            {
                "status": "http_error",
                "http_status": exc.response.status_code,
                "detail": exc.response.text[:500],
            }
        )
        print(f"HTTP error: {exc.response.status_code} {exc.response.text[:200]}", file=sys.stderr)
        return 2
    except Exception as exc:
        manifest.update({"status": "error", "detail": str(exc)})
        print(f"Export failed: {exc}", file=sys.stderr)
        return 2
    finally:
        manifest_path = out_dir / "export-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
