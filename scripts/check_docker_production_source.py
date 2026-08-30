#!/usr/bin/env python3
"""Fail if the root Dockerfile's production application source is not backend/.

Production images must copy application code from backend/, not drifted hf-space/.
Rollback remains the previously deployed Hugging Face image; this check does not delete hf-space/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"

APP_COPY = re.compile(
    r"^\s*COPY(?:\s+--chown=[^\s]+)?\s+(?P<src>\S+)\s+",
    re.IGNORECASE,
)


def production_copy_sources(text: str) -> list[str]:
    sources: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = APP_COPY.match(stripped)
        if not match:
            continue
        src = match.group("src").replace("\\", "/")
        sources.append(src)
    return sources


def check(dockerfile: Path = DOCKERFILE) -> list[str]:
    if not dockerfile.is_file():
        return [f"missing Dockerfile at {dockerfile}"]
    text = dockerfile.read_text(encoding="utf-8")
    sources = production_copy_sources(text)
    errors: list[str] = []
    if not any(src.startswith("backend/") for src in sources):
        errors.append("Dockerfile does not COPY any backend/ paths")
    if not any(src.rstrip("/") == "backend/bebcare" or src.startswith("backend/bebcare/") for src in sources):
        errors.append("Dockerfile must COPY backend/bebcare/ as the application package")
    hf_app = [
        src
        for src in sources
        if src.startswith("hf-space/")
        and any(
            part in src
            for part in ("bebcare", "migrations", "app.py", "alembic.ini", "requirements.txt")
        )
    ]
    if hf_app:
        errors.append(
            "Dockerfile copies production application paths from hf-space/: " + ", ".join(hf_app)
        )
    cmd_ok = "bebcare.main:app" in text or "uvicorn" in text
    if not cmd_ok:
        errors.append("Dockerfile should keep uvicorn bebcare.main:app entrypoint")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("[docker-source] FAIL")
        for err in errors:
            print(f"  {err}")
        return 1
    print("[docker-source] OK production application source is backend/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
