"""Phase 2B versioned semantic asset analysis. Unknown stays unknown."""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SEMANTIC_SCHEMA_VERSION = "sem_v2"
OFFERING_CONTEXT_PREFIX = "offering_v1"
Presence = Literal["unknown", "absent", "present", "likely"]
Confidence = Literal["unknown", "low", "medium", "high"]
VisibilityEvidence = Literal["unknown", "absent", "partial", "complete"]
SuitabilityBand = Literal["unknown", "strong", "moderate", "weak", "unsuitable"]
ProminenceBand = Literal["unknown", "low", "medium", "high", "dominant"]
MatchBand = Literal["unknown", "match", "mismatch", "not_applicable"]
YesNoUnknown = Literal["unknown", "yes", "no"]
DominantSubjectKind = Literal[
    "unknown",
    "single_product",
    "product_group",
    "kit",
    "packaging",
    "person",
    "scene",
    "mixed",
]
AssetSourceType = Literal[
    "unknown",
    "product",
    "scene",
    "screenshot",
    "packaging",
    "person",
    "mixed",
]
SubjectOrScene = Literal["unknown", "subject", "scene", "mixed"]
BroadComposition = Literal["unknown", "centered", "close_up", "wide", "other"]
BroadLighting = Literal["unknown", "studio", "natural", "mixed", "other"]
GenerationSuitability = Literal[
    "unknown",
    "primary_subject",
    "supporting_subject",
    "scene",
    "avoid_as_primary",
]
DominantOffering = Literal[
    "unknown",
    "physical_product",
    "software",
    "saas",
    "service",
    "digital_product",
    "event_or_experience",
    "mixed",
]


class PhysicalModule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    observed_subject_count: Optional[int | Literal["unknown"]] = "unknown"
    broad_view_class: str = "unknown"
    support_surface: str = "unknown"
    packaging_role: str = "unknown"
    visible_display_orientation: str = "unknown"
    transparency_or_reflectivity_risk: str = "unknown"
    interaction_risk: str = "unknown"
    logo_product_region: str = "unknown"
    logo_visibility: str = "unknown"
    logo_confidence: str = "unknown"
    control_or_screen_visibility: VisibilityEvidence = "unknown"
    complete_silhouette_visible: VisibilityEvidence = "unknown"
    complete_original_base_visible: VisibilityEvidence = "unknown"
    major_component_relationships_visible: VisibilityEvidence = "unknown"
    major_occlusion: Presence = "unknown"
    fine_detail_visibility: VisibilityEvidence = "unknown"


class SoftwareSaasModule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    screenshot_or_mockup: str = "unknown"
    interface_region: str = "unknown"
    device_frame: str = "unknown"
    screen_orientation: str = "unknown"
    readable_text_risk: str = "unknown"
    sensitive_data_risk: str = "unknown"
    theme: str = "unknown"


class ServiceEventModule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    person_prominence: str = "unknown"
    activity_type: str = "unknown"
    setting_type: str = "unknown"
    documentary_or_conceptual: str = "unknown"
    identity_preservation_required: str = "unknown"
    scene_reuse_suitability: str = "unknown"


class AssetIntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_source_type: AssetSourceType = "unknown"
    subject_or_scene: SubjectOrScene = "unknown"
    people_or_hands_presence: Presence = "unknown"
    text_presence: Presence = "unknown"
    brand_mark_presence: Presence = "unknown"
    broad_composition: BroadComposition = "unknown"
    broad_lighting: BroadLighting = "unknown"
    screenshot_or_interface_presence: Presence = "unknown"
    packaging_presence: Presence = "unknown"
    dominant_offering_evidence: DominantOffering = "unknown"
    generation_suitability: GenerationSuitability = "unknown"
    confidence: Confidence = "unknown"
    dominant_subject_kind: DominantSubjectKind = "unknown"
    intended_component_match: MatchBand = "unknown"
    product_prominence: ProminenceBand = "unknown"
    packaging_prominence: ProminenceBand = "unknown"
    person_prominence: ProminenceBand = "unknown"
    lifestyle_context_dominance: ProminenceBand = "unknown"
    kit_or_group_image: YesNoUnknown = "unknown"
    geometry_reference_suitability: SuitabilityBand = "unknown"
    secondary_structure_suitability: SuitabilityBand = "unknown"
    interaction_reference_suitability: SuitabilityBand = "unknown"
    scene_reference_suitability: SuitabilityBand = "unknown"
    packaging_reference_suitability: SuitabilityBand = "unknown"
    evidence_confidence: Confidence = "unknown"
    warnings: list[str] = Field(default_factory=list)
    physical: Optional[PhysicalModule] = None
    software_saas: Optional[SoftwareSaasModule] = None
    service_event: Optional[ServiceEventModule] = None

    def compact_label(self, *, image_type: str | None = None) -> str:
        src = self.asset_source_type
        if src == "packaging" or self.packaging_presence in ("present", "likely"):
            return "Packaging"
        if src == "screenshot" or self.screenshot_or_interface_presence in (
            "present",
            "likely",
        ):
            return "Screenshot"
        if src == "person" or self.people_or_hands_presence in ("present", "likely"):
            return "Person"
        if src == "scene" or (image_type or "") == "scene":
            return "Scene"
        if src == "product":
            return "Product"
        if (image_type or "") == "scene":
            return "Scene"
        return "Product"

    def is_packaging(self) -> bool:
        return self.asset_source_type == "packaging" or self.packaging_presence in (
            "present",
            "likely",
        )

    def is_screenshot(self) -> bool:
        return self.asset_source_type == "screenshot" or (
            self.screenshot_or_interface_presence in ("present", "likely")
        )

    def usable(self) -> bool:
        return True


CATALOG_CATEGORY_CAP = 80
CATALOG_DESCRIPTION_CAP = 400
CATALOG_POINT_CAP = 80
CATALOG_POINT_MAX = 5


def _selling_point_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = [str(item) for item in raw]
    else:
        items = str(raw).split(",")
    points: list[str] = []
    for item in items:
        text = item.strip()[:CATALOG_POINT_CAP]
        if text:
            points.append(text)
        if len(points) >= CATALOG_POINT_MAX:
            break
    return points


def compact_catalog_context(
    category: str | None = None,
    description: str | None = None,
    selling_points: Any = None,
) -> str:
    """Capped catalog notes for vision analysis. User text is untrusted."""
    cat = (category or "").strip()[:CATALOG_CATEGORY_CAP]
    desc = (description or "").strip()[:CATALOG_DESCRIPTION_CAP]
    points = _selling_point_list(selling_points)
    return "\n".join(
        (
            f"category: {cat}" if cat else "category:",
            f"description: {desc}" if desc else "description:",
            f"selling_points: {'; '.join(points)}" if points else "selling_points:",
        )
    )


def catalog_context_digest(catalog_text: str) -> str:
    blob = (catalog_text or "").strip()
    useful = blob.replace("category:", "").replace("description:", "").replace(
        "selling_points:", ""
    )
    if not useful.strip():
        return "none"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def offering_context_version(
    offering_type: str | None,
    *,
    category: str | None = None,
    description: str | None = None,
    selling_points: Any = None,
) -> str:
    kind = (offering_type or "unknown").strip().lower() or "unknown"
    digest = catalog_context_digest(
        compact_catalog_context(category, description, selling_points)
    )
    return f"{OFFERING_CONTEXT_PREFIX}:{kind}:{digest}"


def offering_context_for_product(product: Any, offering_type: str | None = None) -> str:
    if product is None:
        return offering_context_version(offering_type)
    return offering_context_version(
        offering_type
        if offering_type is not None
        else getattr(product, "offering_type", None),
        category=getattr(product, "category", None),
        description=getattr(product, "description", None),
        selling_points=getattr(product, "selling_points", None),
    )


_CONFIDENCE_NUMERIC = (
    (0.8, "high"),
    (0.5, "medium"),
    (0.2, "low"),
    (0.0, "unknown"),
)


def _normalize_token(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if 0.0 <= number <= 1.0:
            for threshold, label in _CONFIDENCE_NUMERIC:
                if number >= threshold:
                    return label
        return value
    if not isinstance(value, str):
        return value
    text = value.strip().replace("-", "_").replace(" ", "_")
    return text.lower() if text else value


def normalize_intelligence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe formatting only: case, hyphen/underscore, numeric confidence, nested dicts."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            out[key] = normalize_intelligence_payload(value)
        elif isinstance(value, list):
            out[key] = value
        else:
            out[key] = _normalize_token(value)
    if not out.get("evidence_confidence") or out.get("evidence_confidence") == "unknown":
        if out.get("confidence") in ("low", "medium", "high"):
            out["evidence_confidence"] = out["confidence"]
    return out


def parse_intelligence_result(payload: Any) -> AssetIntelligenceResult:
    if isinstance(payload, AssetIntelligenceResult):
        return payload
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("intelligence_result_not_object")
    return AssetIntelligenceResult.model_validate(normalize_intelligence_payload(payload))
