"""Phase 2B semantic asset intelligence rollout. Server-resolved only."""

from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO

VALID_MODES = ("off", "studio", "all")


def asset_intelligence_mode() -> str:
    mode = (settings.asset_intelligence_mode or "off").strip().lower()
    if mode not in VALID_MODES:
        return "off"
    return mode


def semantic_analysis_enabled(*, source: str, requested_mode: str | None = None) -> bool:
    """Client requested_mode is ignored. Eligibility is env-only."""
    del requested_mode
    mode = asset_intelligence_mode()
    if mode == "off":
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "all")
    if source == SOURCE_AUTOMATION:
        return mode == "all"
    return False
