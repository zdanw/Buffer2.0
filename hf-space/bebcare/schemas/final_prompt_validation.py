"""Typed result for the final provider-prompt contradiction guard."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

POLICY_VERSION = "prompt_contradiction_guard_v2"
AUTHORITY_POLICY_VERSION = "prompt_authority_v1"

CONFLICT_CATEGORIES = (
    "placement_conflict",
    "unsupported_mount_conflict",
    "unsupported_accessory_conflict",
    "cable_conflict",
    "vehicle_usage_conflict",
    "generated_branding_conflict",
    "subject_count_conflict",
    "reference_authority_conflict",
    "screen_content_conflict",
    "coverage_risk_conflict",
    "capture_style_conflict",
    "realism_conflict",
    "duplicate_policy_text",
    "malformed_prompt_text",
    "unsupported_geometry_conflict",
    "nonphysical_policy_mismatch",
    "unresolved_high_authority_conflict",
    "handheld_request_removed",
    "image_index_corrected",
)


class FinalPromptValidationResult(BaseModel):
    policy_version: str = POLICY_VERSION
    authority_policy_version: str = AUTHORITY_POLICY_VERSION
    original_prompt_hash: str = ""
    validated_prompt: str = ""
    validated_prompt_hash: str = ""
    offering_type: Optional[str] = None
    capture_mode: Optional[str] = None
    reference_coverage: Optional[str] = None
    detected_conflicts: list[str] = Field(default_factory=list)
    removed_fragments: list[str] = Field(default_factory=list)
    rewritten_fragments: list[str] = Field(default_factory=list)
    deduplicated_policy_categories: list[str] = Field(default_factory=list)
    applied_fallbacks: list[str] = Field(default_factory=list)
    unresolved_warnings: list[str] = Field(default_factory=list)
    hard_failures: list[str] = Field(default_factory=list)
    provider_request_allowed: bool = True
    changed: bool = False
    evaluated: bool = False
    diagnostics_summary: str = "prompt_contradiction_planned"
    safe_event_details: dict[str, Any] = Field(default_factory=dict)

    def capped(self, *, limit: int = 12) -> "FinalPromptValidationResult":
        return self.model_copy(
            update={
                "detected_conflicts": self.detected_conflicts[:limit],
                "removed_fragments": self.removed_fragments[:limit],
                "rewritten_fragments": self.rewritten_fragments[:limit],
                "deduplicated_policy_categories": self.deduplicated_policy_categories[:limit],
                "applied_fallbacks": self.applied_fallbacks[:limit],
                "unresolved_warnings": self.unresolved_warnings[:limit],
                "hard_failures": self.hard_failures[:limit],
            }
        )

    def persistable(self) -> dict[str, Any]:
        capped = self.capped()
        return {
            "policy_version": capped.policy_version,
            "authority_policy_version": capped.authority_policy_version,
            "original_prompt_hash": capped.original_prompt_hash,
            "validated_prompt_hash": capped.validated_prompt_hash,
            "offering_type": capped.offering_type,
            "capture_mode": capped.capture_mode,
            "reference_coverage": capped.reference_coverage,
            "detected_conflicts": capped.detected_conflicts,
            "removed_count": len(self.removed_fragments),
            "rewritten_count": len(self.rewritten_fragments),
            "applied_fallbacks": capped.applied_fallbacks,
            "hard_failures": capped.hard_failures,
            "provider_request_allowed": capped.provider_request_allowed,
            "changed": capped.changed,
            "evaluated": capped.evaluated,
            "diagnostics_summary": capped.diagnostics_summary,
        }
