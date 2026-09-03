"""Studio Visual QA executed-policy builder.

Benchmark and Studio generation must call this module rather than assembling a
reduced QA payload by hand. Wordmark is comparison-only for QA and is not added
to image-generation prompts here.
"""

from __future__ import annotations

from typing import Any

REQUIRED_QA_CHECK_CODES: tuple[str, ...] = (
    "unexpected_product_text",
    "invented_logo",
    "logo_spelling_or_case_mismatch",
    "logo_placement_mismatch",
    "logo_on_unsupported_surface",
    "prominent_screen_corruption",
    "prominent_ui_text_corruption",
    "unsupported_accessory",
    "unsupported_mount_or_attachment",
    "base_or_housing_redesign",
    "unexpected_primary_duplicate",
)

POLICY_BUILDER_ID = "studio_visual_qa_policy_v1"


def _screen_fields(product_info: dict, plan: dict) -> tuple[str, str]:
    intel = product_info.get("asset_intelligence_results") or []
    strength = "unknown"
    has_display = False
    for row in intel:
        if not isinstance(row, dict):
            continue
        physical = row.get("physical") if isinstance(row.get("physical"), dict) else {}
        display = physical.get("display") or physical.get("screen") or {}
        if isinstance(display, dict) and display:
            has_display = True
            evidence = str(display.get("evidence_strength") or display.get("visibility") or "").lower()
            if evidence in ("strong", "high", "clear"):
                strength = "strong"
            elif evidence in ("moderate", "medium"):
                strength = "moderate"
            elif evidence in ("weak", "incidental", "dark", "off", "low"):
                strength = "weak"
        elif display:
            has_display = True
    contract = plan.get("identity_contract") if isinstance(plan.get("identity_contract"), dict) else {}
    physical_visible = contract.get("physical_visible") or []
    if strength == "unknown" and physical_visible:
        blob = str(physical_visible).lower()
        if "screen" in blob or "display" in blob:
            has_display = True
            strength = "weak"
    if not has_display and strength == "unknown":
        strength = "weak"
    policy = "unsupported_invented_live_ui"
    usage = plan.get("usage_policy") if isinstance(plan.get("usage_policy"), dict) else {}
    if usage.get("active_driving_presentation") == "prohibited":
        policy = "unsupported_invented_live_ui"
    contradiction = plan.get("prompt_contradiction") if isinstance(plan.get("prompt_contradiction"), dict) else {}
    if "screen_content_restricted" in str(contradiction.get("applied") or contradiction.get("codes") or ""):
        policy = "unsupported_invented_live_ui"
    return strength, policy


def build_visual_qa_policy(product_info: dict | None) -> dict[str, Any]:
    """Return the executed Visual QA policy Studio generation uses."""
    from bebcare.schemas.generation_plan import dump_generation_plan
    from bebcare.services.generation_plan import plan_from_product_info
    from bebcare.services.product_fidelity_prevention import (
        apply_product_fidelity_prevention,
        identity_contract_from_evidence,
        logo_protection_contract,
    )

    info = dict(product_info or {})
    prevented = apply_product_fidelity_prevention(dict(info))
    plan = prevented.get("generation_plan") if isinstance(prevented.get("generation_plan"), dict) else {}
    plan = dict(plan or {})
    if not plan.get("logo_policy"):
        plan["logo_policy"] = logo_protection_contract(prevented)
    if not plan.get("identity_contract"):
        plan["identity_contract"] = identity_contract_from_evidence(prevented)
    if not plan.get("reference_manifest"):
        built = plan_from_product_info(prevented)
        dumped = dump_generation_plan(built) if built else {}
        dumped.update(plan)
        plan = dumped
    logo = plan.get("logo_policy") if isinstance(plan.get("logo_policy"), dict) else {}
    identity = logo.get("logo_identity") if isinstance(logo.get("logo_identity"), dict) else {}
    wordmark = logo.get("wordmark_authority") or identity.get("wordmark")
    placement = plan.get("placement") if isinstance(plan.get("placement"), dict) else {}
    subject = plan.get("subject") if isinstance(plan.get("subject"), dict) else {}
    screen_strength, screen_policy = _screen_fields(prevented, plan)
    coverage = plan.get("reference_coverage") or info.get("reference_coverage") or "primary"
    return {
        "policy_builder": POLICY_BUILDER_ID,
        "executed_generation_plan": plan,
        "reference_manifest": plan.get("reference_manifest") or prevented.get("reference_manifest"),
        "validated_final_prompt_hash": (
            prevented.get("_sanitized_prompt_hash") or info.get("_sanitized_prompt_hash")
        ),
        "reference_coverage": coverage,
        "offering_type": prevented.get("offering_type") or info.get("offering_type") or "unknown",
        "subject_count_policy": subject.get("count_policy")
        or subject.get("policy")
        or "single_primary_unless_kit",
        "generated_branding_prohibited": bool(logo.get("generated_branding_prohibited")),
        "logo_mode": logo.get("logo_mode"),
        "approved_wordmark_for_comparison": wordmark,
        "logo_placement_evidence": logo.get("logo_placement") or plan.get("logo_placement"),
        "screen_evidence_strength": screen_strength,
        "screen_content_policy": screen_policy,
        "unsupported_mount_accessory_cable_policy": {
            "unsupported_codes": list(placement.get("unsupported_codes") or []),
            "instruction": placement.get("instruction"),
            "usage_policy": plan.get("usage_policy") or {},
        },
        "compositing_state": "planned" if logo.get("use_controlled_compositing") else "none",
        "qa_stage": "pre_composite",
        "provider_image_labels": plan.get("provider_image_order") or [],
        "required_check_codes": list(REQUIRED_QA_CHECK_CODES),
        "insert_wordmark_in_generation_prompt": bool(logo.get("insert_wordmark_in_prompt")),
    }


def qa_payload_from_policy(
    *,
    policy: dict[str, Any],
    candidate_index: int,
    candidate_url: str | None,
    primary: dict | None,
    supporting: list[dict],
    reference_labels: dict,
    composite_logo: bool,
    owner_user_id: str | None,
    approved_logo_url: str | None,
    asset_intelligence: list | None,
) -> dict[str, Any]:
    plan = policy.get("executed_generation_plan") or {}
    return {
        "candidate_index": candidate_index,
        "candidate_url": candidate_url,
        "primary_reference_url": (primary or {}).get("cdn_url"),
        "supporting_reference_urls": [s.get("cdn_url") for s in supporting if s.get("cdn_url")],
        "approved_logo_url": approved_logo_url,
        "reference_labels": reference_labels,
        "executed_qa_policy": policy,
        "executed_generation_plan": plan,
        "generation_plan": plan,
        "reference_manifest": policy.get("reference_manifest"),
        "validated_final_prompt_hash": policy.get("validated_final_prompt_hash"),
        "reference_coverage": policy.get("reference_coverage"),
        "offering_type": policy.get("offering_type"),
        "subject_count_policy": policy.get("subject_count_policy"),
        "generated_branding_prohibited": policy.get("generated_branding_prohibited"),
        "logo_mode": policy.get("logo_mode"),
        "approved_wordmark_for_comparison": policy.get("approved_wordmark_for_comparison"),
        "logo_placement_evidence": policy.get("logo_placement_evidence"),
        "screen_evidence_strength": policy.get("screen_evidence_strength"),
        "screen_content_policy": policy.get("screen_content_policy"),
        "unsupported_mount_accessory_cable_policy": policy.get(
            "unsupported_mount_accessory_cable_policy"
        ),
        "compositing_state": policy.get("compositing_state"),
        "qa_stage": policy.get("qa_stage"),
        "provider_image_labels": policy.get("provider_image_labels"),
        "required_check_codes": policy.get("required_check_codes"),
        "plan_summary": {
            "placement": plan.get("placement"),
            "subject": plan.get("subject"),
            "capture_style": plan.get("capture_style"),
            "constraints": plan.get("constraints"),
            "identity_contract": plan.get("identity_contract"),
            "usage_policy": plan.get("usage_policy"),
            "provider_image_order": plan.get("provider_image_order"),
            "reference_coverage": plan.get("reference_coverage"),
        },
        "logo_policy": plan.get("logo_policy") or {},
        "placement_policy": plan.get("placement"),
        "asset_intelligence": asset_intelligence or [],
        "composite_logo": composite_logo,
        "owner_user_id": owner_user_id,
        "policy_builder": POLICY_BUILDER_ID,
        "insert_wordmark_in_generation_prompt": policy.get("insert_wordmark_in_generation_prompt"),
    }
