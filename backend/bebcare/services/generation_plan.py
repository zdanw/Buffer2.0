"""Attach compact GenerationPlan onto product_info / provenance."""

from __future__ import annotations

import logging

from bebcare.schemas.generation_plan import (
    GenerationPlan,
    build_generation_plan,
    dump_generation_plan,
    load_generation_plan,
    render_generation_plan_contract,
)
from bebcare.schemas.reference_manifest import ReferenceManifest
from bebcare.services.grounded_rollout import grounded_prompt_contract_enabled

logger = logging.getLogger(__name__)


def plan_from_product_info(product_info: dict | None) -> GenerationPlan | None:
    info = product_info or {}
    return load_generation_plan(info.get("generation_plan"))


def executed_plan_contract(product_info: dict | None, locale: str = "en") -> str:
    plan = plan_from_product_info(product_info)
    if plan is None:
        return ""
    from bebcare.schemas.generation_plan import render_fidelity_contract_suffix

    extra = render_fidelity_contract_suffix(product_info, locale)
    return f"{render_generation_plan_contract(plan, locale)} {extra}".strip()


def attach_generation_plan(product_info: dict) -> GenerationPlan | None:
    provenance = product_info.get("generation_provenance") or {}
    product_info["use_grounded_prompt_contract"] = grounded_prompt_contract_enabled(
        product_info
    )
    if not product_info["use_grounded_prompt_contract"]:
        product_info.pop("generation_plan", None)
        provenance.pop("generation_plan", None)
        product_info["generation_provenance"] = provenance
        return None
    raw = provenance.get("reference_manifest") or product_info.get("reference_manifest")
    if not raw:
        return None
    try:
        manifest = ReferenceManifest.model_validate(raw)
        plan = build_generation_plan(
            manifest,
            structured_group=product_info.get("structured_group"),
            product_info=product_info,
        )
    except Exception:
        logger.exception("Failed to build GenerationPlan")
        return None
    dumped = dump_generation_plan(plan)
    trace = provenance.get("selector_trace") if isinstance(provenance.get("selector_trace"), dict) else None
    if trace:
        dumped["diversity_fingerprint"] = trace.get("fingerprint")
        dumped["reference_coverage"] = trace.get("coverage")
        dumped["selector_policy_version"] = trace.get("selector_policy_version")
        dumped["selection_seed"] = trace.get("selection_seed")
        dumped["selector_trace"] = trace
        coverage = str(trace.get("coverage") or "")
        from bebcare.services.quality_diversity_policy import apply_coverage_to_plan_dict

        dumped = apply_coverage_to_plan_dict(dumped, coverage)
        from bebcare.services.quality_diversity_policy import user_facing_selector_reason

        product_info["reference_diagnostics"] = {
            "coverage": coverage or None,
            "reason": user_facing_selector_reason(trace),
            "diversity_applied": bool(trace.get("weighted_rotation_enabled")),
        }
        if coverage in ("limited", "insufficient"):
            product_info["reference_quality_notice"] = True
    product_info["generation_plan"] = dumped
    provenance["generation_plan"] = dumped
    product_info["generation_provenance"] = provenance
    from bebcare.services.product_fidelity_prevention import apply_product_fidelity_prevention

    apply_product_fidelity_prevention(product_info)
    return plan_from_product_info(product_info) or plan
