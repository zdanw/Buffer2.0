"""Typed pre-selection context. Server-derived; no secrets; cannot enable QDS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO
from bebcare.services.quality_diversity_policy import (
    CLOSEUP_HINTS,
    LOGO_HINTS,
    PERSPECTIVE_HINTS,
    SAFETY_PLACE_HINTS,
    SCREEN_HINTS,
    TRANSPARENT_HINTS,
    _blob,
)

PRESENT = frozenset({"present", "likely"})


@dataclass
class SelectorContext:
    source: str = SOURCE_STUDIO
    task_mode: str | None = None
    auto_publish: bool = False
    aspect_ratio: str | None = None
    use_scene_reference: bool = False
    realistic_placement: bool = True
    style_hint: str | None = None
    offering_type: str | None = None
    logo_mode: str | None = None
    logo_fidelity_required: bool = False
    has_on_body_branding: bool = False
    content_purpose: str | None = None
    dimension_text: str = ""
    explore_requested: bool = False
    safety_placement_risk: bool = False
    reference_count: int = 1
    screenshot_risk: bool = False
    transparent_risk: bool = False
    reflective_risk: bool = False
    display_risk: bool = False
    close_up_risk: bool = False
    capture_style: str | None = None

    def to_risk_hint(self) -> dict[str, Any]:
        return {
            "capture_style": self.capture_style or self.style_hint,
            "offering_kind": self.offering_type,
            "dimension_text": self.dimension_text,
            "content_purpose": self.content_purpose,
            "camera_distance": "close" if self.close_up_risk else None,
            "explore_requested": self.explore_requested,
            "aspect_ratio": self.aspect_ratio,
            "auto_publish": self.auto_publish,
            "logo_fidelity_required": self.logo_fidelity_required,
            "screenshot_risk": self.screenshot_risk,
            "transparent_risk": self.transparent_risk,
            "display_risk": self.display_risk,
            "safety_placement_risk": self.safety_placement_risk,
            "close_up_risk": self.close_up_risk,
        }

    def to_trace(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("style_hint", None)
        if self.style_hint:
            payload["style_hint_present"] = True
        return payload


def _intel_risks(intel_by_image: dict | None) -> dict[str, bool]:
    screenshot = transparent = reflective = display = close_up = False
    for result in (intel_by_image or {}).values():
        if result is None:
            continue
        src = str(getattr(result, "asset_source_type", "") or "")
        if getattr(result, "is_screenshot", lambda: False)() or src == "screenshot":
            screenshot = True
            display = True
        physical = getattr(result, "physical", None)
        risk = ""
        if physical is not None:
            risk = str(getattr(physical, "transparency_or_reflectivity_risk", "") or "").lower()
        if risk in ("high", "present", "likely", "transparent", "reflective"):
            if "reflect" in risk:
                reflective = True
            else:
                transparent = True
        composition = str(getattr(result, "broad_composition", "") or "")
        if composition == "close_up":
            close_up = True
        if getattr(result, "screenshot_or_interface_presence", None) in PRESENT:
            display = True
    return {
        "screenshot_risk": screenshot,
        "transparent_risk": transparent,
        "reflective_risk": reflective,
        "display_risk": display,
        "close_up_risk": close_up,
    }


def build_selector_context(
    *,
    source: str,
    product: Any = None,
    task_mode: str | None = None,
    image_size: str | None = None,
    use_scene_reference: bool = False,
    realistic_placement: bool = True,
    style_hint: str | None = None,
    reference_count: int = 1,
    content_purpose: str | None = None,
    selected_dimensions: dict | None = None,
    logo_mode: str | None = None,
    explore_requested: bool = False,
    intelligence_by_image: dict | None = None,
) -> SelectorContext:
    """Compact context from objects already available before reference selection."""
    src = (source or SOURCE_STUDIO).strip().lower() or SOURCE_STUDIO
    mode = (task_mode or "").strip().lower() or None
    auto = src == SOURCE_AUTOMATION and mode in ("auto", "auto_publish", "automatic")
    offering = None
    on_body = False
    if product is not None:
        offering = str(getattr(product, "offering_type", None) or "").strip() or None
        on_body = bool(getattr(product, "has_on_body_branding", False))
    dims = selected_dimensions if isinstance(selected_dimensions, dict) else {}
    dim_text = " ".join(str(v) for v in dims.values() if v)
    blob = _blob([style_hint, dim_text, content_purpose, offering])
    risks = _intel_risks(intelligence_by_image)
    close_up = risks["close_up_risk"] or any(h in blob for h in CLOSEUP_HINTS)
    safety = any(h in blob for h in SAFETY_PLACE_HINTS)
    logo_fid = (logo_mode or "preserve").strip().lower() == "preserve" and on_body
    if any(h in blob for h in LOGO_HINTS):
        logo_fid = True
    capture = None
    if style_hint:
        low = style_hint.lower()
        if any(k in low for k in ("illustration", "illustrated", "graphic", "conceptual")):
            capture = "graphic_or_illustrated"
        elif "photo" in low or "lifestyle" in low:
            capture = "realistic_photography"
    return SelectorContext(
        source=src,
        task_mode=mode,
        auto_publish=auto,
        aspect_ratio=image_size,
        use_scene_reference=bool(use_scene_reference),
        realistic_placement=bool(realistic_placement),
        style_hint=(style_hint or None),
        offering_type=offering,
        logo_mode=logo_mode,
        logo_fidelity_required=logo_fid,
        has_on_body_branding=on_body,
        content_purpose=content_purpose,
        dimension_text=dim_text,
        explore_requested=bool(explore_requested),
        safety_placement_risk=safety,
        reference_count=max(int(reference_count or 1), 1),
        screenshot_risk=risks["screenshot_risk"] or any(h in blob for h in SCREEN_HINTS),
        transparent_risk=risks["transparent_risk"] or any(h in blob for h in TRANSPARENT_HINTS),
        reflective_risk=risks["reflective_risk"],
        display_risk=risks["display_risk"] or any(h in blob for h in SCREEN_HINTS),
        close_up_risk=close_up,
        capture_style=capture,
    )
