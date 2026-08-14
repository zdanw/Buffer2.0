#!/usr/bin/env python3
"""Seed system brand kits (Generic + Bebcare) into the database."""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from bebcare.database import SessionLocal
from bebcare.services.brand_seed_service import initialize_brands


def main() -> int:
    db = SessionLocal()
    try:
        initialize_brands(db)
        print("Brand kits seeded successfully.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
