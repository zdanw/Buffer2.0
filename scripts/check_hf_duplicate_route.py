#!/usr/bin/env python3
"""Check whether the production HF Space exposes POST /v1/products/{id}/duplicate."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_HOST = os.getenv("HF_SPACE_HOST", "zongsechenai-bebcare-buffer.hf.space").strip()
DEFAULT_HOST = DEFAULT_HOST.replace("https://", "").replace("http://", "").split("/")[0]


def main() -> int:
    host = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST).strip()
    url = f"https://{host}/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.URLError as e:
        print(f"Failed to fetch {url}: {e}")
        return 1

    paths = data.get("paths", {})
    duplicate_paths = [p for p in paths if p.endswith("/duplicate")]
    product_duplicate = "/v1/products/{product_id}/duplicate"

    if product_duplicate in paths:
        print(f"OK: {host} has {product_duplicate}")
        return 0

    print(f"MISSING: {host} does not expose {product_duplicate}")
    if duplicate_paths:
        print("Other duplicate paths:", duplicate_paths)
    print(
        "Rebuild the Hugging Face Space from latest main, then Factory reboot:\n"
        "  https://huggingface.co/spaces/zongsechenai/bebcare-buffer"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
