#!/usr/bin/env python3
"""Reset docs-demo sandbox and regenerate demo placeholder assets."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

runpy.run_path(str(ROOT / "scripts" / "generate_demo_assets.py"), run_name="__main__")

from bebcare.services.docs_sandbox_service import seed_docs_sandbox

if __name__ == "__main__":
    seed_docs_sandbox()
    print("Docs sandbox seeded successfully.")
