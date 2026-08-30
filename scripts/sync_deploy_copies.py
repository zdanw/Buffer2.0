#!/usr/bin/env python3
"""Optional archive sync: backend/ → hf-space/.

Production Docker builds copy application code from backend/, not hf-space/.
This script does not define the live application source. CI gates production
source with scripts/check_docker_production_source.py.

Usage:
  python scripts/sync_deploy_copies.py          # optional archive sync
  python scripts/sync_deploy_copies.py --check  # report archive drift (not a production gate)

Preserves deploy-only files (Dockerfile, README, …).
Does not copy backend-only artifacts (tests, Long-CLIP, railway, …).
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend"
TARGETS = (ROOT / "hf-space",)

# Relative paths under backend/ to mirror into each deploy copy.
SYNC_PATHS = (
    "bebcare",
    "migrations",
    "scripts",
    "app.py",
    "alembic.ini",
    "requirements.txt",
    "requirements-clip.txt",
    ".gitignore",
)

# Deploy copies may keep their own comments/ports; update DeepSeek notes separately if needed.
# Not synced: .env.example, Dockerfile, README.md, ms_deploy.json


# Backend-only scripts (not shipped to deploy copies).
SKIP_SCRIPT_NAMES = frozenset(
    {
        "migrate_sqlite_to_supabase.py",
    }
)

# Never delete these from a deploy target (even if absent in backend sync set).
PRESERVE_NAMES = frozenset(
    {
        "Dockerfile",
        "README.md",
        ".dockerignore",
        ".gitattributes",
        "ms_deploy.json",
        ".git",
        ".env",
        "chroma_data",
        "__pycache__",
        ".pytest_cache",
    }
)


def _should_skip_file(rel: Path) -> bool:
    parts = rel.parts
    if "__pycache__" in parts or parts and parts[-1].endswith(".pyc"):
        return True
    if parts[:1] == ("scripts",) and parts[-1] in SKIP_SCRIPT_NAMES:
        return True
    return False


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for name in SYNC_PATHS:
        path = SRC / name
        if not path.exists():
            raise FileNotFoundError(f"missing sync source: {path}")
        if path.is_file():
            if not _should_skip_file(Path(name)):
                files.append(Path(name))
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            rel = child.relative_to(SRC)
            if _should_skip_file(rel):
                continue
            files.append(rel)
    return files


def _synced_rel_set(files: list[Path]) -> set[Path]:
    return set(files)


def check_drift(target: Path, files: list[Path]) -> list[str]:
    problems: list[str] = []
    synced = _synced_rel_set(files)

    for rel in files:
        src_f = SRC / rel
        dst_f = target / rel
        if not dst_f.exists():
            problems.append(f"missing: {rel.as_posix()}")
            continue
        if not filecmp.cmp(src_f, dst_f, shallow=False):
            problems.append(f"differ:  {rel.as_posix()}")

    # Extra files under synced trees that are not in backend (e.g. dead dashscope_wan).
    for top in ("bebcare", "migrations", "scripts"):
        dst_top = target / top
        if not dst_top.is_dir():
            continue
        for child in dst_top.rglob("*"):
            if not child.is_file():
                continue
            rel = child.relative_to(target)
            if _should_skip_file(rel):
                continue
            if rel not in synced:
                problems.append(f"extra:   {rel.as_posix()}")

    for name in ("app.py", "alembic.ini", "requirements.txt", "requirements-clip.txt"):
        # already covered via files list
        _ = name

    return problems


def _clear_synced_tree(target: Path, top: str) -> None:
    dst = target / top
    if dst.exists():
        shutil.rmtree(dst)


def apply_sync(target: Path, files: list[Path]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    # Rebuild mirrored trees so extras (e.g. unregistered providers) disappear.
    for top in ("bebcare", "migrations", "scripts"):
        _clear_synced_tree(target, top)

    for rel in files:
        src_f = SRC / rel
        dst_f = target / rel
        dst_f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_f, dst_f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optional archive sync backend → hf-space (not the production app source)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report archive drift vs backend; does not gate production deploys",
    )
    parser.add_argument(
        "--target",
        choices=("hf-space", "all"),
        default="all",
        help="Which deploy copy to sync (default: all)",
    )
    args = parser.parse_args()

    files = _iter_source_files()
    targets = TARGETS if args.target == "all" else (ROOT / args.target,)

    if args.check:
        print(
            "[check] NOTICE: production Docker copies backend/; "
            "hf-space/ is an archive copy, not the active application source."
        )
        any_drift = False
        for target in targets:
            if not target.is_dir():
                print(f"[check] SKIP missing target {target.name}")
                continue
            problems = check_drift(target, files)
            if problems:
                any_drift = True
                print(f"[check] DRIFT in {target.name} ({len(problems)}):")
                for p in problems:
                    print(f"  {p}")
            else:
                print(f"[check] OK {target.name}")
        return 1 if any_drift else 0

    for target in targets:
        apply_sync(target, files)
        problems = check_drift(target, files)
        if problems:
            print(f"[sync] FAILED verify {target.name}:")
            for p in problems:
                print(f"  {p}")
            return 1
        print(f"[sync] OK {target.name} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
