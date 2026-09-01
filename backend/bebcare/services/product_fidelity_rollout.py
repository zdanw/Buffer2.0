"""Product Fidelity Guard v1 rollouts. Server-resolved; client cannot enable.

PRODUCT_FIDELITY_PREVENTION_MODE:
  off | studio | all
  Default off. Studio applies prevention on Studio generates; all includes automation.

VISUAL_FIDELITY_QA_MODE:
  off | studio | auto_publish | all
  Default off. Client requested mode is ignored.
  Legacy GenerationRun null visual_fidelity_qa_mode is treated as off.
"""

from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO

PREVENTION_MODES = ("off", "studio", "all")
VISUAL_MODES = ("off", "studio", "auto_publish", "all")
PREVENTION_POLICY_VERSION = "product_fidelity_prevention_v3"
VISUAL_POLICY_VERSION = "visual_fidelity_qa_v3"
LEGACY_NULL = "off"
_UNSET = object()


def normalize_prevention_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    return value if value in PREVENTION_MODES else LEGACY_NULL


def normalize_visual_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    return value if value in VISUAL_MODES else LEGACY_NULL


def product_fidelity_prevention_mode() -> str:
    return normalize_prevention_mode(getattr(settings, "product_fidelity_prevention_mode", "off"))


def visual_fidelity_qa_mode() -> str:
    return normalize_visual_mode(getattr(settings, "visual_fidelity_qa_mode", "off"))


def prevention_enabled(
    *,
    source: str,
    requested_mode: str | None = None,
    persisted_mode: str | None | object = _UNSET,
) -> bool:
    del requested_mode
    mode = (
        normalize_prevention_mode(persisted_mode if isinstance(persisted_mode, str) or persisted_mode is None else None)
        if persisted_mode is not _UNSET
        else product_fidelity_prevention_mode()
    )
    if mode == "off":
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "all")
    if source == SOURCE_AUTOMATION:
        return mode == "all"
    return False


def visual_fidelity_enabled(
    *,
    source: str,
    requested_mode: str | None = None,
    task_mode: str | None = None,
    persisted_mode: str | None | object = _UNSET,
) -> bool:
    del requested_mode
    mode = (
        normalize_visual_mode(persisted_mode if isinstance(persisted_mode, str) or persisted_mode is None else None)
        if persisted_mode is not _UNSET
        else visual_fidelity_qa_mode()
    )
    if mode == "off":
        return False
    if source == SOURCE_STUDIO:
        return mode in ("studio", "all")
    if source == SOURCE_AUTOMATION:
        tm = (task_mode or "").strip().lower()
        if tm == "auto":
            return mode in ("auto_publish", "all")
        return mode == "all"
    return False


def visual_qa_entitled(owner_user_id: str | None) -> bool:
    """Later commercial-tier hook. v1: any owner is entitled when the server mode is on."""
    del owner_user_id
    return True


def visual_fidelity_blocks_auto_publish(
    *,
    source: str,
    task_mode: str | None = None,
    persisted_mode: str | None | object = _UNSET,
) -> bool:
    mode = (
        normalize_visual_mode(persisted_mode if isinstance(persisted_mode, str) or persisted_mode is None else None)
        if persisted_mode is not _UNSET
        else visual_fidelity_qa_mode()
    )
    if mode not in ("auto_publish", "all"):
        return False
    if source != SOURCE_AUTOMATION:
        return False
    return (task_mode or "").strip().lower() == "auto"
