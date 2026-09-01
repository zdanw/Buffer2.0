from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GenerationHistoryUserSummary(BaseModel):
    user_id: str
    username: str
    email: str


class GenerationHistoryProductSummary(BaseModel):
    product_id: str
    name: str


class GenerationHistoryQaSummary(BaseModel):
    hard_fail_count: int = 0
    warning_count: int = 0


class GenerationHistoryListItem(BaseModel):
    run_id: str
    created_at: datetime
    status: str
    source: str
    user: GenerationHistoryUserSummary
    product: Optional[GenerationHistoryProductSummary] = None
    thumbnail_url: Optional[str] = None
    credits_charged: int = 0
    latency_ms: Optional[int] = None
    provider_summary: Optional[str] = None
    qa_summary: GenerationHistoryQaSummary = Field(default_factory=GenerationHistoryQaSummary)
    diagnosis_line: str = ""


class GenerationHistoryListResponse(BaseModel):
    items: list[GenerationHistoryListItem]
    total: int
    page: int
    page_size: int
    pages: int


class GenerationHistoryArtifact(BaseModel):
    artifact_id: str
    cdn_url: str
    selected: bool
    persistence_warning: Optional[str] = None
    candidate_index: int


class GenerationHistoryFinding(BaseModel):
    finding_id: str
    stage: str
    check_code: str
    check_label: str
    severity: str
    passed: bool
    details: Optional[dict[str, Any]] = None
    qa_kind: str = "deterministic"
    confidence: Optional[str] = None
    created_at: datetime


class GenerationHistoryCreditInfo(BaseModel):
    charged: int = 0
    reservation_status: Optional[str] = None
    grant_source: Optional[str] = None
    grant_note: Optional[str] = None


class GenerationHistoryGenerateTask(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    stage: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    expired: bool = False


class GenerationHistoryCompareSibling(BaseModel):
    run_id: str
    status: str
    image_prompt_pipeline: Optional[str] = None
    thumbnail_url: Optional[str] = None
    selected: bool = False
    created_at: datetime


class GenerationHistoryDetail(BaseModel):
    run_id: str
    owner_user_id: str
    source: str
    product_id: Optional[str] = None
    scheduled_task_id: Optional[str] = None
    generate_task_id: Optional[str] = None
    rollout_mode_at_start: str
    experiment_variant: Optional[str] = None
    requested_pipeline_version: str
    executed_pipeline_version: str
    fallback_reason: Optional[str] = None
    fallback_path: Optional[str] = None
    image_prompt_pipeline: Optional[str] = None
    compare_group_id: Optional[str] = None
    provider_type: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None
    image_size: Optional[str] = None
    image_provider_mode: Optional[str] = None
    status: str
    error_category: Optional[str] = None
    latency_ms: Optional[int] = None
    retry_count: Optional[int] = None
    credits_charged: int = 0
    provider_usage: Optional[dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    quality_protection_mode: Optional[str] = None
    quality_policy_version: Optional[str] = None
    product_fidelity_prevention_mode: Optional[str] = None
    visual_fidelity_qa_mode: Optional[str] = None
    visual_fidelity_policy_version: Optional[str] = None
    requested_selector_strategy: Optional[str] = None
    executed_selector_strategy: Optional[str] = None
    selection_seed: Optional[str] = None
    user: GenerationHistoryUserSummary
    product: Optional[GenerationHistoryProductSummary] = None
    output_snapshot: Optional[dict[str, Any]] = None
    generate_task: Optional[GenerationHistoryGenerateTask] = None
    artifacts: list[GenerationHistoryArtifact] = Field(default_factory=list)
    quality_findings: list[GenerationHistoryFinding] = Field(default_factory=list)
    credit: GenerationHistoryCreditInfo = Field(default_factory=GenerationHistoryCreditInfo)
    generation_plan: Optional[dict[str, Any]] = None
    reference_manifest: Optional[dict[str, Any]] = None
    qa_summary: GenerationHistoryQaSummary = Field(default_factory=GenerationHistoryQaSummary)
    diagnosis_line: str = ""
    compare_siblings: list[GenerationHistoryCompareSibling] = Field(default_factory=list)
    generation_diagnostics: Optional[dict[str, Any]] = None
