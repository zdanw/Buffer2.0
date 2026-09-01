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
EXECUTED_GROUNDED_PROMPT_V1 = "grounded_prompt_v1"
EXECUTED_GROUNDED_PROMPT_TRANSPORT = "grounded_prompt_role_transport_v1"
EXPERIMENT_DETERMINISTIC = "deterministic_refs_only"
EXPERIMENT_BASELINE = "baseline_current"
EXPERIMENT_GROUNDED_PROMPT_V1 = "grounded_prompt_v1"
EXPERIMENT_GROUNDED_PROMPT_TRANSPORT = "grounded_prompt_role_transport_v1"
FALLBACK_PATH_LEGACY_RANDOM = "legacy_random_refs"
GROUNDED_EXECUTED_VERSIONS = (
    EXECUTED_DETERMINISTIC,
    EXECUTED_GROUNDED_PROMPT_V1,
    EXECUTED_GROUNDED_PROMPT_TRANSPORT,
)
PHASE1B_EXPERIMENT_TO_EXECUTED = {
    EXPERIMENT_GROUNDED_PROMPT_V1: EXECUTED_GROUNDED_PROMPT_V1,
    EXPERIMENT_GROUNDED_PROMPT_TRANSPORT: EXECUTED_GROUNDED_PROMPT_TRANSPORT,
}


def apply_phase1b_experiment(selection, requested_experiment: str | None = None):
    """Pin an allowed 1B variant after grounded selection already succeeded.

    Client experiment_variant is never an enable switch. Invalid/omitted pins
    use the default role-transport contract; eligibility comes only from
    grounded_selection_enabled + a successful grounded selector result.
    """
    if not getattr(selection, "grounded", False):
        return selection
    requested = (requested_experiment or "").strip() or None
    selection.requested_experiment_variant = requested
    if requested in PHASE1B_EXPERIMENT_TO_EXECUTED:
        selection.experiment_variant = requested
        selection.executed_pipeline_version = PHASE1B_EXPERIMENT_TO_EXECUTED[requested]
    else:
        selection.experiment_variant = EXPERIMENT_GROUNDED_PROMPT_TRANSPORT
        selection.executed_pipeline_version = EXECUTED_GROUNDED_PROMPT_TRANSPORT
    return selection


def selection_provenance(selection, *, source: str) -> dict:
    """Executed pipeline + eligibility stamp. Requested pins stay separate."""
    eligible = bool(getattr(selection, "grounded", False))
    return {
        "source": source,
        "rollout_mode_at_start": grounded_rollout_mode(),
        "experiment_variant": selection.experiment_variant,
        "requested_experiment_variant": getattr(
            selection, "requested_experiment_variant", None
        ),
        "requested_pipeline_version": selection.requested_pipeline_version,
        "executed_pipeline_version": selection.executed_pipeline_version,
        "fallback_reason": selection.fallback_reason,
        "fallback_path": selection.fallback_path,
        "reference_manifest": selection.manifest,
        "grounded_phase1b_enabled": eligible,
        "deterministic_metadata": getattr(selection, "deterministic_metadata", None),
        "asset_intelligence": getattr(selection, "asset_intelligence", None),
        "selector_trace": getattr(selection, "selector_trace", None),
    }


def _phase1b_eligible(product_info: dict | None) -> bool:
    info = product_info or {}
    provenance = info.get("generation_provenance") or {}
    return bool(
        info.get("grounded_phase1b_enabled")
        or provenance.get("grounded_phase1b_enabled")
    )


def grounded_prompt_contract_enabled(product_info: dict | None = None) -> bool:
    """Phase 1B prompts/contract. Requires the eligibility stamp, not a client pin."""
    return _phase1b_eligible(product_info)


def grounded_role_transport_enabled(product_info: dict | None = None) -> bool:
    if not _phase1b_eligible(product_info):
        return False
    info = product_info or {}
    provenance = info.get("generation_provenance") or {}
    executed = (
        info.get("executed_pipeline_version")
        or provenance.get("executed_pipeline_version")
        or ""
    )
    return executed == EXECUTED_GROUNDED_PROMPT_TRANSPORT


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
