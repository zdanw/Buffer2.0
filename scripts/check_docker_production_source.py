#!/usr/bin/env python3
"""Fail if the root Docker production source or build context is not backend/.

Production images must COPY application code from backend/, not drifted hf-space/.
The build context must still include those backend/ paths (root .dockerignore must
not exclude the backend/ tree). Rollback remains the previously deployed Hugging
Face image; this check does not delete hf-space/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"

APP_COPY = re.compile(
    r"^\s*COPY(?:\s+--chown=[^\s]+)?\s+(?P<src>\S+)\s+",
    re.IGNORECASE,
)

CANONICAL_RUNTIME_PATHS = (
    "backend/requirements.txt",
    "backend/bebcare/",
    "backend/migrations/",
    "backend/alembic.ini",
    "backend/app.py",
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


def _normalize_rel(value: str) -> str:
    text = value.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def dockerignore_patterns(text: str) -> list[tuple[bool, str]]:
    """Return (negated, pattern) pairs; comments and blanks omitted."""
    patterns: list[tuple[bool, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        if not line:
            continue
        patterns.append((negated, line))
    return patterns


def _glob_to_regex(pattern: str) -> str:
    """Convert a focused dockerignore glob (** / * / ?) to a regex body."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                i += 1
            continue
        char = pattern[i]
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        i += 1
    return "".join(out)


def ignore_pattern_matches(pattern: str, rel_path: str) -> bool:
    """Match a dockerignore pattern against a context-relative path.

    Covers this repository's patterns and the backend/ tree regression
    (backend/, /backend/, backend/**, backend). Not a full Docker parser.
    """
    pat = _normalize_rel(pattern)
    path = _normalize_rel(rel_path).rstrip("/")
    if not pat:
        return False

    if any(token in pat for token in "*?"):
        regex = "^" + _glob_to_regex(pat.rstrip("/")) + "(/.*)?$"
        return re.match(regex, path) is not None

    literal = pat.rstrip("/")
    return path == literal or path.startswith(literal + "/")


def path_excluded_by_dockerignore(rel_path: str, ignore_text: str) -> str | None:
    """Return the last matching excluding pattern, or None if the path is kept."""
    excluded_by: str | None = None
    for negated, pattern in dockerignore_patterns(ignore_text):
        if not ignore_pattern_matches(pattern, rel_path):
            continue
        if negated:
            excluded_by = None
        else:
            excluded_by = pattern
    return excluded_by


def required_runtime_paths(dockerfile_text: str) -> list[str]:
    required = list(CANONICAL_RUNTIME_PATHS)
    if any(
        src.replace("\\", "/").rstrip("/") == "backend/.env.example"
        or src.replace("\\", "/").startswith("backend/.env.example")
        for src in production_copy_sources(dockerfile_text)
    ):
        if "backend/.env.example" not in required:
            required.append("backend/.env.example")
    return required


def check_dockerignore(dockerignore_text: str, dockerfile_text: str) -> list[str]:
    errors: list[str] = []
    for rel_path in required_runtime_paths(dockerfile_text):
        matched = path_excluded_by_dockerignore(rel_path, dockerignore_text)
        if matched is None:
            continue
        errors.append(
            "root .dockerignore excludes required canonical path "
            f"{rel_path} (matched by pattern {matched!r}). "
            "Remove the backend/ tree exclusion so the root Dockerfile can "
            "COPY backend/ into the image."
        )
    return errors


def check(
    dockerfile: Path = DOCKERFILE,
    dockerignore: Path | None = None,
) -> list[str]:
    if not dockerfile.is_file():
        return [f"missing Dockerfile at {dockerfile}"]
    text = dockerfile.read_text(encoding="utf-8")
    sources = production_copy_sources(text)
    errors: list[str] = []
    if not any(src.startswith("backend/") for src in sources):
        errors.append("Dockerfile does not COPY any backend/ paths")
    if not any(
        src.rstrip("/") == "backend/bebcare" or src.startswith("backend/bebcare/")
        for src in sources
    ):
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

    ignore_path = dockerignore if dockerignore is not None else dockerfile.parent / ".dockerignore"
    if ignore_path.is_file():
        errors.extend(
            check_dockerignore(ignore_path.read_text(encoding="utf-8"), text)
        )
    elif dockerfile.resolve() == DOCKERFILE.resolve():
        errors.append(f"missing .dockerignore at {ignore_path}")
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
