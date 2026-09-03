"""Quality and Diversity Selector rollout. Server-resolved; client cannot enable.

QUALITY_DIVERSITY_SELECTOR_MODE:
  off | studio | manual_automation | all
  Default off. Requires grounded selection to already be enabled.
  studio — Studio generation and Studio comparison only
  manual_automation — Studio plus manual-review automation; auto-publish stays on the
                      existing grounded selector
  all — Studio, manual automation, and automatic publishing
"""

from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO, grounded_selection_enabled

VALID_MODES = ("off", "studio", "manual_automation", "all")
LEGACY_NULL = "off"
STRATEGY_OFF = "off"
STRATEGY_GROUNDED = "grounded_deterministic"
STRATEGY_QDS = "quality_diversity_weighted"
STRATEGY_FALLBACK = "selector_fallback"


def quality_diversity_selector_mode() -> str:
    mode = str(getattr(settings, "quality_diversity_selector_mode", "off") or "off").strip().lower()
    return mode if mode in VALID_MODES else LEGACY_NULL


def quality_diversity_enabled(
    *,
    source: str,
    task_mode: str | None = None,
    grounded: bool | None = None,
) -> bool:
    mode = quality_diversity_selector_mode()
    if mode == "off":
        return False
    if grounded is False:
        return False
    if grounded is None and not grounded_selection_enabled(source=source, task_mode=task_mode):
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "manual_automation", "all")
    if source == SOURCE_AUTOMATION:
        tm = (task_mode or "").strip().lower()
        if tm == "auto":
            return mode == "all"
        if tm == "manual":
            return mode in ("manual_automation", "all")
        return mode == "all"
    return False
