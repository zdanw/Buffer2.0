"""Internal QDS data contracts. Never sent to ordinary clients as a control surface."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CoverageClass = Literal["strong", "moderate", "limited", "insufficient"]
RiskProfile = Literal["conservative", "balanced", "exploratory"]
ReferenceRole = Literal[
    "primary_geometry",
    "secondary_structure",
    "logo_reference",
    "interaction_reference",
    "scene_reference",
    "style_reference",
    "software_interface_reference",
    "packaging_reference",
]


class RoleScore(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    raw_score: float
    quality_floor: float
    eligible: bool
    exclusion_codes: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class QDSCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    image_id: str
    cdn_url: str = ""
    image_type: str = "product"
    source_type: str = "unknown"
    is_preferred: bool = False
    is_explicit_pin: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = None
    phash: Optional[str] = None
    deterministic_metadata_status: str = "unknown"
    semantic_analysis_status: str = "unknown"
    universal_evidence: dict[str, Any] = Field(default_factory=dict)
    physical_evidence: Optional[dict[str, Any]] = None
    software_evidence: Optional[dict[str, Any]] = None
    service_event_evidence: Optional[dict[str, Any]] = None
    recent_usage: dict[str, Any] = Field(default_factory=dict)
    role_scores: list[RoleScore] = Field(default_factory=list)
    disqualifications: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QDSRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    owner_user_id: str
    product_id: str
    generation_run_id: Optional[str] = None
    source: str
    task_mode: Optional[str] = None
    generation_plan: dict[str, Any] = Field(default_factory=dict)
    desired_reference_count: int = 1
    target_aspect_ratio: Optional[str] = None
    intended_subject_hint: Optional[str] = None
    intended_component_hint: Optional[str] = None
    risk_profile: Optional[RiskProfile] = None
    provider_type: Optional[str] = None
    provider_reference_limit: Optional[int] = None
    explicit_pinned_image_ids: list[str] = Field(default_factory=list)
    preferred_image_id: Optional[str] = None
    selection_seed: Optional[str] = None
    policy_version: Optional[str] = None


class QDSSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    selector_version: str
    selection_seed: str
    strategy: str
    exploration_level: RiskProfile = "balanced"
    required_roles: list[str] = Field(default_factory=list)
    eligible_pool_by_role: dict[str, list[str]] = Field(default_factory=dict)
    excluded_candidates: list[dict[str, Any]] = Field(default_factory=list)
    primary_reference: Optional[str] = None
    supporting_references: list[str] = Field(default_factory=list)
    scene_reference: Optional[str] = None
    effective_weights: dict[str, float] = Field(default_factory=dict)
    selected_reference_manifest: dict[str, Any] = Field(default_factory=dict)
    reference_coverage: CoverageClass = "moderate"
    coverage_reasons: list[str] = Field(default_factory=list)
    applied_history_penalties: dict[str, float] = Field(default_factory=dict)
    diversity_fingerprint: dict[str, str] = Field(default_factory=dict)
    fallback_reason: Optional[str] = None
    requested_strategy: str = "off"
    executed_strategy: str = "off"
    history_snapshot: dict[str, Any] = Field(default_factory=dict)
