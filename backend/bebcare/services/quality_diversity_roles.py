"""Role-specific reference suitability. Unknown stays unknown; no hidden geometry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from bebcare.schemas.asset_intelligence import AssetIntelligenceResult, parse_intelligence_result
from bebcare.services.quality_diversity_policy import (
    FAILED_INTEL_STATUSES,
    GEOMETRY_ROLES,
    USABLE_INTEL_CONFIDENCE,
    ReferenceRole,
    coverage_from_score,
)
from bebcare.utils.reference_suitability import suitability_score

PRESENT = frozenset({"present", "likely"})
PERSON_DOMINANT = frozenset({"high", "dominant", "primary", "person_dominant"})
PACKAGING_DOMINANT = frozenset({"primary", "dominant", "hero", "packaging_primary"})


@dataclass
class RoleVerdict:
    role: str
    score: float
    eligible: bool
    exclusion_reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)
    evidence_class: str = "missing"
    evidence_complete: bool = False
    score_confidence: str = "resolution_only"

    @property
    def coverage(self) -> str:
        return coverage_from_score(self.score, eligible=self.eligible)

    @property
    def semantic(self) -> bool:
        return self.evidence_class in {"usable", "partial_useful"}


def _intel(raw: Any) -> Optional[AssetIntelligenceResult]:
    if raw is None:
        return None
    try:
        return parse_intelligence_result(raw)
    except Exception:
        return None


def _physical(intel: AssetIntelligenceResult | None) -> dict[str, Any]:
    if intel is None or intel.physical is None:
        return {}
    return intel.physical.model_dump()


def _service(intel: AssetIntelligenceResult | None) -> dict[str, Any]:
    if intel is None or intel.service_event is None:
        return {}
    return intel.service_event.model_dump()


def base_quality_01(
    *,
    width: Optional[int],
    height: Optional[int],
    image_type: str,
    target_aspect: Optional[float] = None,
) -> float:
    raw = suitability_score(
        width=width,
        height=height,
        target_aspect=target_aspect,
        image_type=image_type,
        apply_diversity=False,
    )
    return max(0.0, min(1.0, raw / 10.0))


def classify_intelligence(intel: Any, *, analysis_status: str | None = None) -> str:
    status = (analysis_status or "").strip().lower()
    if status in FAILED_INTEL_STATUSES:
        return "failed" if status == "failed" else "stale"
    result = _intel(intel)
    if result is None:
        return "missing"
    conf = str(result.confidence or "unknown").strip().lower()
    discriminating = (
        result.generation_suitability not in ("", "unknown")
        or result.asset_source_type not in ("", "unknown")
        or result.is_packaging()
        or result.people_or_hands_presence in PRESENT
    )
    if conf in USABLE_INTEL_CONFIDENCE and discriminating:
        return "usable"
    if conf in USABLE_INTEL_CONFIDENCE:
        return "partial_useful"
    if conf == "low" and discriminating:
        return "partial_useful"
    if conf == "low":
        return "low_confidence"
    if discriminating:
        return "partial_useful"
    return "missing"


def evaluate_role(
    role: ReferenceRole | str,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    image_type: str = "product",
    intel: Any = None,
    target_aspect: Optional[float] = None,
    intended_component: str | None = None,
    packaging_required: bool = False,
    observed_component: str | None = None,
    warnings: list[str] | None = None,
    analysis_status: str | None = None,
) -> RoleVerdict:
    """Score one asset for one role. Does not infer unseen structure."""
    result = _intel(intel)
    evidence_class = classify_intelligence(intel, analysis_status=analysis_status)
    semantic = evidence_class in {"usable", "partial_useful"}
    physical = _physical(result)
    service = _service(result)
    score = base_quality_01(
        width=width, height=height, image_type=image_type, target_aspect=target_aspect
    )
    reasons: list[str] = []
    signals: dict[str, Any] = {
        "base_quality": round(score, 4),
        "asset_source_type": getattr(result, "asset_source_type", "unknown") if result else "unknown",
        "generation_suitability": getattr(result, "generation_suitability", "unknown") if result else "unknown",
        "view_class": physical.get("broad_view_class") or "unknown",
        "support_surface": physical.get("support_surface") or "unknown",
        "packaging_role": physical.get("packaging_role") or "unknown",
        "composition": getattr(result, "broad_composition", "unknown") if result else "unknown",
        "people": getattr(result, "people_or_hands_presence", "unknown") if result else "unknown",
        "brand_mark": getattr(result, "brand_mark_presence", "unknown") if result else "unknown",
        "packaging_presence": getattr(result, "packaging_presence", "unknown") if result else "unknown",
    }

    edge = min(int(width or 0), int(height or 0))
    if int(width or 0) <= 0 or int(height or 0) <= 0:
        reasons.append("zero_dimensions")
        signals["zero_dimensions"] = True
    severe_crop = edge < 256 and "zero_dimensions" not in reasons
    if severe_crop:
        signals["severe_crop"] = True
        if role in GEOMETRY_ROLES:
            reasons.append("severe_crop")

    packaging_dom = False
    if result is not None:
        packaging_dom = result.is_packaging() or str(physical.get("packaging_role") or "").lower() in PACKAGING_DOMINANT
    signals["packaging_dominated"] = packaging_dom

    person_dom = False
    if result is not None:
        prominence = str(service.get("person_prominence") or "").lower()
        person_dom = result.asset_source_type == "person" or (
            result.people_or_hands_presence in PRESENT and prominence in PERSON_DOMINANT
        ) or prominence in PERSON_DOMINANT
        if not person_dom and result.asset_source_type == "person":
            person_dom = True
        if (
            not person_dom
            and result.people_or_hands_presence in PRESENT
            and result.generation_suitability == "avoid_as_primary"
            and role in GEOMETRY_ROLES
        ):
            person_dom = True
    signals["person_dominated"] = person_dom

    lifestyle_dom = False
    if result is not None:
        lifestyle_dom = (
            result.subject_or_scene == "scene"
            and result.broad_composition in ("wide", "other")
            and result.generation_suitability in ("scene", "avoid_as_primary")
        )
    signals["lifestyle_context_dominated"] = lifestyle_dom

    occluded = False
    warn_list = list(warnings or [])
    if result is not None:
        warn_list.extend(result.warnings or [])
    joined = " ".join(str(w) for w in warn_list).lower()
    if "occlu" in joined or str(physical.get("interaction_risk") or "").lower() in (
        "major_occlusion",
        "occluded",
        "high",
    ):
        occluded = True
    signals["major_occlusion"] = occluded

    wrong_component = False
    intended = (intended_component or "").strip().lower()
    observed = (observed_component or physical.get("component_id") or "").strip().lower()
    if intended and observed and intended != observed:
        wrong_component = True
        reasons.append("wrong_component")
    signals["wrong_component"] = wrong_component

    if role in GEOMETRY_ROLES:
        if image_type == "scene":
            reasons.append("scene_not_geometry")
        if packaging_dom and not packaging_required:
            reasons.append("packaging_dominated")
        if person_dom:
            reasons.append("person_dominated")
        if occluded:
            reasons.append("major_occlusion")
        if result is not None and result.generation_suitability == "avoid_as_primary" and role == "primary_geometry":
            if not packaging_required:
                reasons.append("avoid_as_primary")
        if (
            role == "secondary_structure"
            and result is not None
            and result.generation_suitability in ("scene", "avoid_as_primary")
            and not packaging_required
        ):
            reasons.append("not_structure_evidence")
        if result is not None and result.broad_composition == "wide" and role == "primary_geometry":
            score -= 0.12
            signals["subject_too_small"] = True
        if result is not None and result.broad_composition == "close_up" and edge < 512:
            score -= 0.08
            signals["insufficient_detail"] = True
        if result is not None and result.generation_suitability == "primary_subject":
            score += 0.06
        if str(physical.get("support_surface") or "") not in ("", "unknown", "absent"):
            score += 0.04
            signals["complete_base"] = True
        # unknown support is not treated as missing — do not infer hidden geometry
        if lifestyle_dom:
            score -= 0.10
            if role == "primary_geometry":
                reasons.append("lifestyle_context_dominated")

    if role == "logo_reference":
        if result is not None and result.brand_mark_presence in PRESENT:
            score += 0.12
        elif result is not None and result.brand_mark_presence == "absent":
            score -= 0.18
            if score < 0.58:
                reasons.append("logo_not_visible")

    if role == "interaction_reference":
        if person_dom:
            score += 0.10
        if packaging_dom and not packaging_required:
            score -= 0.08
        if result is not None and result.generation_suitability == "primary_subject":
            score -= 0.04

    if role == "scene_reference":
        if image_type != "scene" and result is not None and result.subject_or_scene != "scene":
            score -= 0.15
        if lifestyle_dom:
            score += 0.08

    if role == "style_reference":
        if result is not None and result.broad_lighting not in ("unknown",):
            score += 0.05

    if role == "packaging_reference":
        if image_type == "scene":
            reasons.append("scene_not_packaging")
        if packaging_dom:
            score += 0.12
        elif result is not None and not packaging_dom:
            score -= 0.10

    if role == "software_interface_reference":
        if image_type == "scene":
            reasons.append("scene_not_interface")
        if result is not None and (
            getattr(result, "is_screenshot", lambda: False)()
            or str(getattr(result, "asset_source_type", "") or "") == "screenshot"
        ):
            score += 0.10
        if severe_crop:
            reasons.append("interface_cropped")
        if result is not None and "sensitive" in " ".join(str(w) for w in (result.warnings or [])).lower():
            reasons.append("sensitive_information")

    if packaging_required and role in GEOMETRY_ROLES and not packaging_dom:
        score -= 0.06

    score = max(0.0, min(1.0, score))
    # Logo-not-visible is a limiter, not always a hard exclude
    hard = [r for r in reasons if r != "logo_not_visible"]
    if role == "logo_reference" and "logo_not_visible" in reasons and score < 0.58:
        hard.append("logo_not_visible")
    eligible = not hard
    if not semantic:
        # Resolution is technical usability, not role suitability.
        signals["role_suitability_unavailable"] = True
    return RoleVerdict(
        role=str(role),
        score=round(score, 4),
        eligible=eligible,
        exclusion_reasons=hard,
        signals=signals,
        evidence_class=evidence_class,
        evidence_complete=semantic and not hard,
        score_confidence="semantic" if semantic else "resolution_only",
    )
