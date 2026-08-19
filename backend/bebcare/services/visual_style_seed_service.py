"""Auto-seed global visual style presets on startup (idempotent)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from bebcare.config.settings import settings
from bebcare.models.prompt_dimension import PromptDimension
from bebcare.models.user import User
from bebcare.services.vertical_pack_service import initialize_pack

logger = logging.getLogger(__name__)


def _earliest_admin(db: Session) -> User:
    admin = (
        db.query(User)
        .filter(User.is_admin.is_(True))
        .order_by(User.created_at.asc())
        .first()
    )
    if not admin:
        raise RuntimeError("Cannot seed visual styles without an admin user")
    return admin


def seed_visual_styles_if_needed(db: Session) -> List[Dict[str, Any]]:
    """Seed General pack for earliest admin when empty; optionally seed baby pack."""
    results: List[Dict[str, Any]] = []
    admin = _earliest_admin(db)
    count = (
        db.query(PromptDimension)
        .filter(PromptDimension.owner_user_id == admin.user_id)
        .count()
    )

    if count == 0:
        logger.info("No visual style presets found — seeding general pack")
        results.append(initialize_pack("general", db, owner=admin))
    else:
        logger.info("Visual style presets already present (%s rows), skipping general seed", count)

    if settings.seed_baby_dimensions:
        logger.info("SEED_BABY_DIMENSIONS=true — importing baby_family pack (additive)")
        results.append(initialize_pack("baby_family", db, owner=admin))

    return results
