#!/usr/bin/env python3
"""Deploy frontend to Vercel production without Git metadata.

Hobby teams block CLI deploys when the local commit author is not a team member.
This script copies frontend/ into a temp dir (no .git), then runs `vercel --prod`.

Usage (from repo root, PowerShell):
  $env:NODE_OPTIONS="--use-system-ca"
  python scripts/deploy_vercel_frontend.py

Options:
  python scripts/deploy_vercel_frontend.py --wait          # poll until Ready
  python scripts/deploy_vercel_frontend.py --no-wait       # default; exit after create
  python scripts/deploy_vercel_frontend.py --keep-temp     # keep temp deploy dir
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PROJECT_JSON = ROOT / ".vercel" / "project.json"
VERCELIGNORE = ROOT / ".vercelignore"
SCOPE = "bebacre-s-projects"
PROD_URL = "https://buffrer2-0.vercel.app"

SKIP_DIR_NAMES = frozenset({"node_modules", "dist", ".vercel", ".git"})
SKIP_FILE_NAMES = frozenset({".env.local"})


def _require_files() -> None:
    missing = [p for p in (FRONTEND, PROJECT_JSON, VERCELIGNORE) if not p.exists()]
    if missing:
        paths = ", ".join(str(p.relative_to(ROOT)) for p in missing)
        sys.exit(f"Missing required path(s): {paths}")


def _which_vercel() -> str:
    vercel = shutil.which("vercel")
    if not vercel:
        sys.exit("vercel CLI not found. Install with: npm i -g vercel")
    return vercel


def _copy_frontend(dst_frontend: Path) -> None:
    def ignore(dirpath: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if name in SKIP_DIR_NAMES or name in SKIP_FILE_NAMES:
                ignored.add(name)
        return ignored

    shutil.copytree(FRONTEND, dst_frontend, ignore=ignore)


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=False,
    )


def _run_capture(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def _parse_deployment_id(text: str) -> str | None:
    # Prefer explicit dpl_ id, then inspector URL slug.
    m = re.search(r"\bdpl_([A-Za-z0-9]+)\b", text)
    if m:
        return f"dpl_{m.group(1)}"
    m = re.search(
        r"https://vercel\.com/bebacre-s-projects/buffrer2-0/([A-Za-z0-9]+)",
        text,
    )
    if m:
        return m.group(1)
    return None


def _wait_ready(vercel: str, deployment_id: str, env: dict[str, str], timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = _run_capture(
            [vercel, "inspect", deployment_id, "--scope", SCOPE],
            cwd=ROOT,
            env=env,
        )
        out = (result.stdout or "") + (result.stderr or "")
        print(out, end="" if out.endswith("\n") else "\n", flush=True)
        if "● Ready" in out or re.search(r"\bstatus\s+●\s+Ready\b", out):
            print(f"\nProduction: {PROD_URL}", flush=True)
            return
        if "● Error" in out or "BLOCKED" in out:
            sys.exit("Deployment failed or blocked. See inspect output above.")
        time.sleep(5)
    sys.exit(f"Timed out after {timeout_s}s waiting for Ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll vercel inspect until Ready (default: --no-wait)",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Exit after creating the deployment (default)",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Do not delete the temp deploy directory",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Seconds to wait when --wait is set (default: 180)",
    )
    args = parser.parse_args()
    do_wait = bool(args.wait) and not args.no_wait

    _require_files()
    vercel = _which_vercel()

    env = os.environ.copy()
    # Help Node trust corporate / antivirus TLS interception on Windows.
    opts = env.get("NODE_OPTIONS", "")
    if "--use-system-ca" not in opts:
        env["NODE_OPTIONS"] = (opts + " --use-system-ca").strip()

    tmp_root = Path(tempfile.mkdtemp(prefix="buffrer2-vercel-deploy-"))
    print(f"Temp deploy dir: {tmp_root}", flush=True)

    try:
        dst_frontend = tmp_root / "frontend"
        dst_vercel = tmp_root / ".vercel"
        dst_vercel.mkdir(parents=True, exist_ok=True)

        print("Copying frontend (no node_modules/dist/.git)...", flush=True)
        _copy_frontend(dst_frontend)
        shutil.copy2(PROJECT_JSON, dst_vercel / "project.json")
        shutil.copy2(VERCELIGNORE, tmp_root / ".vercelignore")

        # Deploy must run inside the temp tree so CLI does not attach repo Git author.
        deploy = _run_capture(
            [vercel, "--prod", "--yes", "--no-wait"],
            cwd=tmp_root,
            env=env,
        )
        combined = (deploy.stdout or "") + (deploy.stderr or "")
        print(combined, end="" if combined.endswith("\n") else "\n", flush=True)

        # Node 20 deprecation may print as Error while deploy still succeeds.
        deployment_id = _parse_deployment_id(combined)
        if deploy.returncode != 0 and not deployment_id:
            # Fallback: try parsing JSON blob if present.
            try:
                data = json.loads(combined[combined.index("{") : combined.rindex("}") + 1])
                deployment_id = data.get("deployment", {}).get("id")
            except (ValueError, json.JSONDecodeError, AttributeError):
                deployment_id = None

        if not deployment_id:
            sys.exit(
                "Deploy failed (no deployment id). "
                "If you saw 'Not authorized', ensure you run this script "
                "and that vercel whoami is the project owner."
            )

        print(f"Deployment: {deployment_id}", flush=True)
        if do_wait:
            _wait_ready(vercel, deployment_id, env, args.timeout)
        else:
            print(
                f"Created. Check with:\n"
                f"  vercel inspect {deployment_id} --scope {SCOPE}\n"
                f"Production alias: {PROD_URL}",
                flush=True,
            )
    finally:
        if args.keep_temp:
            print(f"Kept temp dir: {tmp_root}", flush=True)
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
