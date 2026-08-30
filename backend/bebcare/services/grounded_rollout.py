"""Centralized Phase 1A grounded-selection rollout.

GROUNDED_ROLLOUT_MODE:
  off — current random scene-first selection everywhere
  studio — grounded selection only for Studio image / full-content generation
  manual_automation — Studio plus scheduled tasks with mode=manual
  all — Studio, manual automation, and auto-publish automation

Recommended first enablement: studio. Default in settings is off so existing
deployments keep current behavior until the env var is set.
"""

from bebcare.config.settings import settings

VALID_MODES = ("off", "studio", "manual_automation", "all")
SOURCE_STUDIO = "studio"
SOURCE_AUTOMATION = "automation"

PIPELINE_GROUNDED_V1 = "grounded_refs_v1"
PIPELINE_BASELINE = "baseline_current"
EXECUTED_DETERMINISTIC = "deterministic_refs_only"
EXECUTED_LEGACY_RANDOM = "legacy_random_refs"
EXPERIMENT_DETERMINISTIC = "deterministic_refs_only"
EXPERIMENT_BASELINE = "baseline_current"
FALLBACK_PATH_LEGACY_RANDOM = "legacy_random_refs"


def grounded_rollout_mode() -> str:
    mode = (settings.grounded_rollout_mode or "off").strip().lower()
    if mode not in VALID_MODES:
        return "off"
    return mode


def grounded_selection_enabled(*, source: str, task_mode: str | None = None) -> bool:
    mode = grounded_rollout_mode()
    if mode == "off":
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "manual_automation", "all")
    if source == SOURCE_AUTOMATION:
        if mode == "all":
            return True
        if mode == "manual_automation":
            return (task_mode or "").strip().lower() == "manual"
        return False
    return False
