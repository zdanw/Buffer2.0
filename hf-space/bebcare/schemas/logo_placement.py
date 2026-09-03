"""Versioned logo identity vs placement evidence. No 3D reconstruction."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LOGO_PLACE_VERSION = "logo_place_v1"
LogoRegion = Literal[
    "front",
    "rear",
    "left_side",
    "right_side",
    "top",
    "base_front",
    "base_side",
    "screen_bezel",
    "packaging",
    "unknown",
]
VisibilityClass = Literal[
    "clearly_visible",
    "partially_visible",
    "tiny_or_unverifiable",
    "naturally_hidden",
    "absent",
    "unknown",
]
Presence = Literal["unknown", "absent", "present", "likely"]
Confidence = Literal["unknown", "low", "medium", "high"]
VALID_REGIONS = frozenset(
    {
        "front",
        "rear",
        "left_side",
        "right_side",
        "top",
        "base_front",
        "base_side",
        "screen_bezel",
        "packaging",
        "unknown",
    }
)
MIRROR_REGION = {"left_side": "right_side", "right_side": "left_side"}
UNSUPPORTED_OVERLAY_REGIONS = frozenset({"unknown", "screen_bezel"})


class LogoIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approved_logo_asset_id: Optional[str] = None
    approved_logo_url: Optional[str] = None
    owner_user_id: Optional[str] = None
    wordmark: Optional[str] = None
    version: Optional[str] = None


class LogoPlacementEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: Literal["logo_place_v1"] = LOGO_PLACE_VERSION
    logo_present: Presence = "unknown"
    approved_logo_asset_id: Optional[str] = None
    reference_image_id: Optional[str] = None
    product_region: LogoRegion = "unknown"
    bbox_norm: Optional[list[float]] = None
    visible_surface: str = "unknown"
    orientation: str = "unknown"
    visibility_class: VisibilityClass = "unknown"
    confidence: Confidence = "unknown"
    candidate_view_supports_region: bool = False


class LogoObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    present: bool = False
    product_region: LogoRegion = "unknown"
    count: int = 0
    spelling: Optional[str] = None
    mirrored: bool = False
    overlaps_lens_or_control: bool = False
    generated_mark: bool = False


def normalize_region(value: Any) -> str:
    raw = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "base": "base_front",
        "front_base": "base_front",
        "side": "left_side",
        "camera_head": "left_side",
        "camera_head_side": "left_side",
        "housing_side": "left_side",
        "bezel": "screen_bezel",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in VALID_REGIONS else "unknown"
