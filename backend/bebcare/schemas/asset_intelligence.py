"""Phase 2B versioned semantic asset analysis. Unknown stays unknown."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SEMANTIC_SCHEMA_VERSION = "sem_v1"
OFFERING_CONTEXT_PREFIX = "offering_v1"
Presence = Literal["unknown", "absent", "present", "likely"]
Confidence = Literal["unknown", "low", "medium", "high"]
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


def offering_context_version(offering_type: str | None) -> str:
    kind = (offering_type or "unknown").strip().lower() or "unknown"
    return f"{OFFERING_CONTEXT_PREFIX}:{kind}"


def parse_intelligence_result(payload: Any) -> AssetIntelligenceResult:
    if isinstance(payload, AssetIntelligenceResult):
        return payload
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("intelligence_result_not_object")
    return AssetIntelligenceResult.model_validate(payload)
