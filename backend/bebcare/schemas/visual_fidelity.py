"""Versioned visual product-fidelity QA result. No unexplained scalar score."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "visual_fidelity_v1"
CheckStatus = Literal["pass", "warning", "hard_fail", "not_verifiable"]
Confidence = Literal["unknown", "low", "medium", "high"]
PublicationDecision = Literal["eligible", "eligible_with_warnings", "blocked"]

UNIVERSAL_CODES = (
    "unexpected_primary_duplicate",
    "prominent_generated_text_corruption",
    "total_reference_identity_loss",
    "severe_scene_mismatch",
)
PHYSICAL_CODES = (
    "product_silhouette_mismatch",
    "major_proportion_mismatch",
    "missing_major_component",
    "invented_major_component",
    "control_layout_mismatch",
    "lens_or_sensor_layout_mismatch",
    "base_or_housing_redesign",
    "antenna_or_major_feature_missing",
    "unsupported_mount_or_attachment",
    "unsupported_packaging_or_accessory",
    "unsupported_accessory",
    "implausible_support_or_contact",
    "implausible_cable_routing",
    "unsafe_or_misleading_usage_setup",
    "display_orientation_mismatch",
    "prominent_screen_corruption",
    "logo_spelling_or_case_mismatch",
    "logo_shape_or_placement_mismatch",
    "logo_shape_mismatch",
    "logo_placement_mismatch",
    "invented_logo",
    "duplicated_logo",
    "mirrored_logo",
    "unexpected_product_text",
    "logo_on_unsupported_surface",
    "expected_logo_not_verifiable",
)
SOFTWARE_CODES = (
    "primary_interface_corruption",
    "device_frame_mismatch",
    "interface_orientation_mismatch",
    "prominent_ui_text_corruption",
    "sensitive_information_visible",
)
SERVICE_CODES = (
    "representation_mismatch",
    "irrelevant_literal_product",
    "supplied_person_preservation_failure",
)
STYLE_WARNING_CODES = (
    "strong_cgi_render_appearance",
    "excessive_golden_or_magical_lighting",
    "generic_ai_lifestyle_staging",
    "excessive_bokeh",
    "material_response_mismatch",
    "product_scene_sharpness_mismatch",
    "overdesigned_marketing_symbols",
)
ALL_CHECK_CODES = (
    UNIVERSAL_CODES + PHYSICAL_CODES + SOFTWARE_CODES + SERVICE_CODES + STYLE_WARNING_CODES
)

LOGO_CHECK_CODES = frozenset(
    {
        "logo_spelling_or_case_mismatch",
        "logo_shape_or_placement_mismatch",
        "logo_shape_mismatch",
        "logo_placement_mismatch",
        "invented_logo",
        "duplicated_logo",
        "mirrored_logo",
        "unexpected_product_text",
        "logo_on_unsupported_surface",
        "expected_logo_not_verifiable",
    }
)
GENERATED_BRANDING_HARD_CODES = frozenset(
    {
        "invented_logo",
        "logo_on_unsupported_surface",
        "duplicated_logo",
        "mirrored_logo",
        "unexpected_product_text",
        "logo_shape_mismatch",
        "logo_placement_mismatch",
        "logo_spelling_or_case_mismatch",
    }
)
HIGH_CERTAINTY = frozenset({"high", "medium"})
HARD_FAIL_CODES = frozenset(
    {
        "product_silhouette_mismatch",
        "base_or_housing_redesign",
        "invented_major_component",
        "missing_major_component",
        "control_layout_mismatch",
        "major_proportion_mismatch",
        "logo_spelling_or_case_mismatch",
        "invented_logo",
        "duplicated_logo",
        "mirrored_logo",
        "unexpected_product_text",
        "logo_on_unsupported_surface",
        "logo_shape_mismatch",
        "logo_placement_mismatch",
        "unsupported_mount_or_attachment",
        "unsupported_packaging_or_accessory",
        "unsupported_accessory",
        "unsafe_or_misleading_usage_setup",
        "display_orientation_mismatch",
        "implausible_support_or_contact",
        "unexpected_primary_duplicate",
        "primary_interface_corruption",
        "total_reference_identity_loss",
        "antenna_or_major_feature_missing",
        "lens_or_sensor_layout_mismatch",
        "prominent_screen_corruption",
        "implausible_cable_routing",
        "logo_shape_or_placement_mismatch",
        "severe_scene_mismatch",
        "prominent_generated_text_corruption",
        "device_frame_mismatch",
        "interface_orientation_mismatch",
        "prominent_ui_text_corruption",
        "sensitive_information_visible",
        "representation_mismatch",
        "irrelevant_literal_product",
        "supplied_person_preservation_failure",
    }
)

USER_MESSAGE = {
    "unsupported_mount_or_attachment": "Unsupported product placement detected",
    "unsupported_packaging_or_accessory": "Unsupported product placement detected",
    "unsupported_accessory": "Unsupported product placement detected",
    "unsafe_or_misleading_usage_setup": "Product setup may not match the references",
    "implausible_support_or_contact": "Unsupported product placement detected",
    "implausible_cable_routing": "Unsupported product placement detected",
    "logo_spelling_or_case_mismatch": "Branding could not be verified",
    "logo_shape_or_placement_mismatch": "Branding could not be verified",
    "logo_shape_mismatch": "Branding could not be verified",
    "logo_placement_mismatch": "Branding appeared in an unsupported location",
    "invented_logo": "Branding appeared in an unsupported location",
    "duplicated_logo": "Branding appeared in an unsupported location",
    "mirrored_logo": "Branding appeared in an unsupported location",
    "unexpected_product_text": "Branding appeared in an unsupported location",
    "logo_on_unsupported_surface": "Branding appeared in an unsupported location",
    "expected_logo_not_verifiable": "Branding could not be verified",
    "approved_logo_unavailable": "Approved logo placement was unavailable",
    "strong_cgi_render_appearance": "Image appears heavily rendered",
    "excessive_golden_or_magical_lighting": "Image appears heavily rendered",
    "publish_blocked": "Automatic publishing paused",
    "default": "Product details may differ from the reference",
}


class VisualFidelityCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    check_code: str
    status: CheckStatus
    confidence: Confidence = "unknown"
    short_reason: str = ""
    observed_evidence: str = ""
    reference_evidence: str = ""
    affected_region: str = ""
    publication_effect: Literal["none", "warn", "block"] = "none"


class VisualFidelityAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: Literal["visual_fidelity_v1"] = SCHEMA_VERSION
    candidate_index: int = 0
    offering_type: str = "unknown"
    reference_coverage: str = "primary"
    checks: list[VisualFidelityCheck] = Field(default_factory=list)
    overall_publication_decision: PublicationDecision = "eligible"
    confidence: Confidence = "unknown"
    model_version: str = "unknown"
    cache_hit: bool = False
    correction_used: bool = False
    latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    provider: str = "platform_vision"


def publication_decision_from_checks(checks: list[VisualFidelityCheck]) -> PublicationDecision:
    hard = any(c.status == "hard_fail" for c in checks)
    warn = any(c.status == "warning" for c in checks)
    if hard:
        return "blocked"
    if warn:
        return "eligible_with_warnings"
    return "eligible"


WARNING_CODE_BY_CHECK = {
    "unsupported_mount_or_attachment": "fidelity_placement",
    "unsupported_packaging_or_accessory": "fidelity_placement",
    "unsupported_accessory": "fidelity_placement",
    "unsafe_or_misleading_usage_setup": "fidelity_usage",
    "implausible_support_or_contact": "fidelity_placement",
    "implausible_cable_routing": "fidelity_placement",
    "logo_spelling_or_case_mismatch": "fidelity_branding",
    "logo_shape_or_placement_mismatch": "fidelity_branding",
    "logo_shape_mismatch": "fidelity_branding",
    "logo_placement_mismatch": "fidelity_branding",
    "invented_logo": "fidelity_branding",
    "duplicated_logo": "fidelity_branding",
    "mirrored_logo": "fidelity_branding",
    "unexpected_product_text": "fidelity_branding",
    "logo_on_unsupported_surface": "fidelity_branding",
    "expected_logo_not_verifiable": "fidelity_branding",
    "approved_logo_unavailable": "fidelity_branding",
    "strong_cgi_render_appearance": "fidelity_rendered",
    "excessive_golden_or_magical_lighting": "fidelity_rendered",
    "publish_blocked": "fidelity_publish_paused",
}


def warning_code_for_visual(check_code: str) -> str:
    return WARNING_CODE_BY_CHECK.get(check_code, "fidelity_product")


def user_message_for_visual(check_code: str) -> str:
    return USER_MESSAGE.get(check_code, USER_MESSAGE["default"])


def normalize_check(
    check: VisualFidelityCheck,
    *,
    composite_logo: bool = False,
) -> VisualFidelityCheck:
    """Style/logo-composite/low/unknown cannot hard-fail. not_verifiable never hard-fails."""
    if check.check_code in STYLE_WARNING_CODES and check.status == "hard_fail":
        check.status = "warning"
        check.publication_effect = "warn"
    if check.status == "not_verifiable":
        check.publication_effect = "none"
        return check
    if check.check_code == "expected_logo_not_verifiable" and check.status == "hard_fail":
        check.status = "not_verifiable"
        check.publication_effect = "none"
        return check
    if (
        composite_logo
        and check.check_code in LOGO_CHECK_CODES
        and check.check_code not in GENERATED_BRANDING_HARD_CODES
        and check.status == "hard_fail"
    ):
        check.status = "warning"
        check.publication_effect = "warn"
        check.short_reason = (
            (check.short_reason or "") + " logo composite pending; not a publication block"
        ).strip()
        return check
    if check.status == "hard_fail" and check.confidence not in HIGH_CERTAINTY:
        check.status = "warning"
        check.publication_effect = "warn"
        return check
    if check.status == "hard_fail":
        check.publication_effect = "block"
    elif check.status == "warning":
        check.publication_effect = "warn"
    return check
