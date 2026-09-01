"""Quality and Diversity Selector rollout. Server-resolved; client cannot enable.

QUALITY_DIVERSITY_SELECTOR_MODE:
  off | studio | all
  Default off. Requires grounded selection to already be enabled.
"""

from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO, grounded_selection_enabled

VALID_MODES = ("off", "studio", "all")
LEGACY_NULL = "off"


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
        return mode in ("studio", "all")
    if source == SOURCE_AUTOMATION:
        return mode == "all"
    return False
