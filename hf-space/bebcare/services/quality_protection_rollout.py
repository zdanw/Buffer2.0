"""Phase 3A deterministic quality-protection rollout. Server-resolved only.

QUALITY_PROTECTION_MODE:
  off — existing generation/publish behavior; no new blocking
  studio — QA for Studio outputs; automation unchanged
  manual_automation — QA for Studio and manual-review automation drafts;
                      automatic Buffer publishing is unchanged
  all — QA for Studio, manual automation, and automatic automation;
        only this mode may block automatic Buffer publication

Client requested mode is ignored.

Legacy GenerationRun rows with null quality_protection_mode are treated as off
so a later environment change cannot retroactively introduce blocking.
"""

from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO

VALID_MODES = ("off", "studio", "manual_automation", "all")
POLICY_VERSION = "quality_protection_v1"
LEGACY_NULL_MODE = "off"
_UNSET = object()


def normalize_quality_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    if not value:
        return LEGACY_NULL_MODE
    if value not in VALID_MODES:
        return LEGACY_NULL_MODE
    return value


def quality_protection_mode() -> str:
    return normalize_quality_mode(settings.quality_protection_mode)


def quality_protection_enabled(
    *,
    source: str,
    requested_mode: str | None = None,
    task_mode: str | None = None,
    persisted_mode: str | None | object = _UNSET,
) -> bool:
    del requested_mode
    mode = (
        normalize_quality_mode(persisted_mode if isinstance(persisted_mode, str) or persisted_mode is None else None)
        if persisted_mode is not _UNSET
        else quality_protection_mode()
    )
    if mode == "off":
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "manual_automation", "all")
    if source == SOURCE_AUTOMATION:
        tm = (task_mode or "").strip().lower()
        if tm == "auto":
            return mode == "all"
        return mode in ("manual_automation", "all")
    return False


def quality_blocks_auto_publish(
    *,
    source: str,
    task_mode: str | None = None,
    persisted_mode: str | None | object = _UNSET,
) -> bool:
    """Whether automatic Buffer publish may be blocked. Only persisted mode `all`."""
    mode = (
        normalize_quality_mode(persisted_mode if isinstance(persisted_mode, str) or persisted_mode is None else None)
        if persisted_mode is not _UNSET
        else quality_protection_mode()
    )
    if mode != "all":
        return False
    if source != SOURCE_AUTOMATION:
        return False
    if (task_mode or "").strip().lower() != "auto":
        return False
    return True
