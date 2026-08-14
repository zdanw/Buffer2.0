"""Auto-seed global visual style presets on startup (idempotent)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from bebcare.config.settings import settings
from bebcare.models.prompt_dimension import PromptDimension
from bebcare.services.vertical_pack_service import initialize_pack

logger = logging.getLogger(__name__)


def seed_visual_styles_if_needed(db: Session) -> List[Dict[str, Any]]:
    """Seed General pack when empty; optionally seed baby pack via SEED_BABY_DIMENSIONS."""
    results: List[Dict[str, Any]] = []
    count = db.query(PromptDimension).count()

    if count == 0:
        logger.info("No visual style presets found — seeding general pack")
        results.append(initialize_pack("general", db))
    else:
        logger.info("Visual style presets already present (%s rows), skipping general seed", count)

    if settings.seed_baby_dimensions:
        logger.info("SEED_BABY_DIMENSIONS=true — importing baby_family pack (additive)")
        results.append(initialize_pack("baby_family", db))

    return results
