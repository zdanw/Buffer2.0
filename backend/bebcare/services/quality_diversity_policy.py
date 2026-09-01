"""Single configuration module for Quality and Diversity Selector.

Scores are 0–1 role-suitability values (not the 10-point resolution helper).
Existing 10-point suitability typically lands ~0.50 (severe undersize) to 1.00
(≥1024px). Floors are set against that observed range, not the 0.88 / 0.70
examples in the iteration brief.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal

SELECTOR_POLICY_VERSION = "quality_diversity_selector_v2"

ReferenceRole = Literal[
    "primary_geometry",
    "secondary_structure",
    "logo_reference",
    "interaction_reference",
    "scene_reference",
    "style_reference",
]

ROLES: tuple[ReferenceRole, ...] = (
    "primary_geometry",
    "secondary_structure",
    "logo_reference",
    "interaction_reference",
    "scene_reference",
    "style_reference",
)

CoverageClass = Literal["strong", "moderate", "limited", "insufficient"]
RiskBand = Literal["conservative", "balanced", "exploratory"]
SelectorMode = Literal["current", "quality_floor_top_one", "quality_floor_weighted"]

# Absolute eligibility on 0–1 *semantic* role scores. Severe undersize (~0.50) fails.
# Do not apply this floor to resolution-only scores; those are technical usability.
ABSOLUTE_MIN_SCORE = 0.58
RELATIVE_BAND = 0.22
NOVELTY_QUALITY_GAP = 0.12
NOVELTY_WEIGHT_CAP = 0.85
MIN_USABLE_SEMANTIC_FOR_WEIGHTED_PRIMARY = 2
MIN_ROLE_SCORE_SPREAD = 0.08
MAX_WEIGHTED_PRIMARY_POOL = 3
USABLE_INTEL_CONFIDENCE = frozenset({"medium", "high"})
SEMANTIC_EVIDENCE_CLASSES = frozenset({"usable", "partial_useful"})
FAILED_INTEL_STATUSES = frozenset({"failed", "stale"})
SCENE_FINGERPRINT_KEYS = (
    "scene_family",
    "capture_style",
    "camera_distance",
    "composition",
    "lighting_family",
    "subject_scale",
    "prop_family",
    "aspect_ratio",
)

COVERAGE_STRONG = 0.80
COVERAGE_MODERATE = 0.65
COVERAGE_LIMITED = 0.52

LOOKBACK_RUNS = 12
COOLDOWN_DECAY = 0.72
COOLDOWN_FLOOR = 0.38
AUTO_PUBLISH_QUALITY_MIX = 0.94
STUDIO_QUALITY_MIX = 0.82
EXPLORATORY_QUALITY_MIX = 0.68

TEMPERATURE = {
    "conservative": 6.0,
    "balanced": 2.2,
    "exploratory": 1.15,
}

FINGERPRINT_KEYS = (
    "primary_reference_id",
    "primary_view_class",
    "display_configuration",
    "content_purpose",
    "scene_family",
    "capture_style",
    "camera_distance",
    "composition",
    "lighting_family",
    "subject_scale",
    "prop_family",
    "aspect_ratio",
)

FINGERPRINT_NEAR = 0.85
FINGERPRINT_PARTIAL = 0.70
FINGERPRINT_NEAR_FACTOR = 0.45
FINGERPRINT_PARTIAL_FACTOR = 0.72

GEOMETRY_ROLES = frozenset({"primary_geometry", "secondary_structure"})

COVERAGE_CONSTRAINTS: dict[str, list[str]] = {
    "strong": ["moderate_viewpoint_ok", "close_framing_when_supported"],
    "moderate": ["small_viewpoint_ok", "stable_placement", "ordinary_framing"],
    "limited": [
        "stay_near_source_angle",
        "no_macro",
        "no_mounting",
        "no_handheld",
        "no_extreme_perspective",
        "smaller_in_frame",
        "hide_uncertain_details",
    ],
    "insufficient": [
        "avoid_literal_close_product",
        "safer_non_literal_if_supported",
    ],
}

LIMITED_PROMPT = (
    "Stay close to the source camera angle. Do not use macro, mounting, handheld "
    "replacement, or extreme perspective. Keep the product smaller in the frame. "
    "Hide uncertain details instead of inventing them."
)
INSUFFICIENT_PROMPT = (
    "Avoid literal close product reproduction. Prefer safer non-literal lifestyle "
    "or brand context where the offering supports it."
)
VARIETY_PROMPT = (
    "Credible lifestyle photograph: do not perfectly centre the product every time; "
    "vary scene family, lighting, and palette; do not mirror decorative props on both "
    "sides; not every prop must communicate a product feature; allow ordinary negative "
    "space and incidental background objects; use moderate rather than extreme bokeh; "
    "surfaces need not be spotless; do not add floating symbols unless graphic campaign "
    "art is requested."
)

USER_LIMITED_REFERENCE = (
    "Some product details may be hard to match from the available photos."
)

USER_REASON_LIMITED = "limited_references"
USER_REASON_STABLE = "stable_primary"
USER_REASON_ROTATION = "safe_rotation"


def user_facing_selector_reason(trace: dict | None) -> str:
    payload = trace if isinstance(trace, dict) else {}
    coverage = str(payload.get("coverage") or "")
    if coverage in ("limited", "insufficient"):
        return USER_REASON_LIMITED
    if payload.get("weighted_rotation_enabled"):
        return USER_REASON_ROTATION
    return USER_REASON_STABLE

CLOSEUP_HINTS = (
    "macro",
    "close-up",
    "close up",
    "closeup",
    "tight crop",
    "product framing",
)
LOGO_HINTS = ("prominent logo", "logo close", "wordmark hero", "pack shot logo")
TRANSPARENT_HINTS = ("transparent", "glass body", "clear plastic", "translucent")
SCREEN_HINTS = ("screen close", "interface close", "display close-up", "ui close")
PERSPECTIVE_HINTS = (
    "major perspective",
    "extreme angle",
    "worm's eye",
    "bird's eye",
    "dutch angle",
)
WIDE_HINTS = ("wide environmental", "establishing shot", "environment wide", "wide scene")
SAFETY_PLACE_HINTS = ("mount", "clip", "strap", "dock", "crib-rail", "wall-mount")


def coverage_from_score(score: float, *, eligible: bool) -> CoverageClass:
    if not eligible or score < COVERAGE_LIMITED:
        return "insufficient"
    if score >= COVERAGE_STRONG:
        return "strong"
    if score >= COVERAGE_MODERATE:
        return "moderate"
    return "limited"


def _blob(texts: Iterable[str | None]) -> str:
    return " ".join(str(t) for t in texts if t).lower()


def resolve_risk_band(
    *,
    source: str,
    task_mode: str | None,
    coverage: CoverageClass,
    capture_style: str | None = None,
    offering_kind: str | None = None,
    dimension_text: str = "",
    content_purpose: str | None = None,
    camera_distance: str | None = None,
    explore_requested: bool = False,
    auto_publish: bool = False,
    logo_fidelity_required: bool = False,
    screenshot_risk: bool = False,
    transparent_risk: bool = False,
    display_risk: bool = False,
    close_up_risk: bool = False,
    safety_placement_risk: bool = False,
    insufficient_role_intelligence: bool = False,
) -> tuple[RiskBand, list[str]]:
    reasons: list[str] = []
    if coverage in ("limited", "insufficient"):
        reasons.append("limited_coverage")
    src = (source or "").strip().lower()
    mode = (task_mode or "").strip().lower()
    if auto_publish or (src == "automation" and mode in ("auto", "auto_publish", "automatic")):
        reasons.append("auto_publish")
    if insufficient_role_intelligence:
        reasons.append("insufficient_role_intelligence")
    blob = _blob(
        [dimension_text, content_purpose, camera_distance, capture_style, offering_kind]
    )
    if close_up_risk or any(h in blob for h in CLOSEUP_HINTS):
        reasons.append("close_up")
    if logo_fidelity_required or any(h in blob for h in LOGO_HINTS):
        reasons.append("logo_fidelity")
    if transparent_risk or any(h in blob for h in TRANSPARENT_HINTS):
        reasons.append("transparent_or_reflective")
    if screenshot_risk or display_risk or any(h in blob for h in SCREEN_HINTS):
        reasons.append("screen_or_interface")
    if any(h in blob for h in PERSPECTIVE_HINTS):
        reasons.append("major_perspective")
    if safety_placement_risk or any(h in blob for h in SAFETY_PLACE_HINTS):
        reasons.append("safety_placement")
    if reasons:
        return "conservative", reasons
    style = (capture_style or "").strip().lower()
    kind = (offering_kind or "").strip().lower()
    purpose = (content_purpose or "").strip().lower()
    exploratory = (
        explore_requested
        or any(h in blob for h in WIDE_HINTS)
        or "small product" in blob
        or "brand lifestyle" in purpose
        or style in ("graphic_or_illustrated", "graphic", "illustrated", "conceptual")
        or kind in ("service", "services", "event", "events", "saas", "software")
        or purpose in ("service", "event", "brand_lifestyle", "conceptual")
    )
    if exploratory and src != "automation":
        return "exploratory", ["exploratory_intent"]
    if exploratory and mode == "manual":
        return "exploratory", ["exploratory_manual"]
    return "balanced", ["ordinary_studio"]


def quality_mix_for(risk: RiskBand, *, source: str, task_mode: str | None) -> float:
    src = (source or "").strip().lower()
    mode = (task_mode or "").strip().lower()
    if src == "automation" and mode in ("auto", "auto_publish", "automatic"):
        return AUTO_PUBLISH_QUALITY_MIX
    if risk == "conservative":
        return AUTO_PUBLISH_QUALITY_MIX
    if risk == "exploratory":
        return EXPLORATORY_QUALITY_MIX
    return STUDIO_QUALITY_MIX


def fingerprint_from_parts(parts: dict[str, Any] | None) -> dict[str, str]:
    raw = parts or {}
    return {key: str(raw.get(key) or "") for key in FINGERPRINT_KEYS}


def fingerprint_similarity(a: dict[str, str], b: dict[str, str]) -> float:
    if not FINGERPRINT_KEYS:
        return 0.0
    matched = 0
    for key in FINGERPRINT_KEYS:
        left = (a or {}).get(key) or ""
        right = (b or {}).get(key) or ""
        if left and left == right:
            matched += 1
    return matched / len(FINGERPRINT_KEYS)


def coverage_prompt(coverage: CoverageClass) -> str:
    if coverage == "limited":
        return LIMITED_PROMPT
    if coverage == "insufficient":
        return INSUFFICIENT_PROMPT
    return ""


def apply_coverage_to_plan_dict(dumped: dict[str, Any], coverage: str | None) -> dict[str, Any]:
    """Tighten GenerationPlan transformation freedom. Independent of prevention mode."""
    plan = dumped if isinstance(dumped, dict) else {}
    cov = str(coverage or "")
    if cov not in ("limited", "insufficient"):
        return plan
    allowed = [c for c in (plan.get("allowed_changes") or []) if c != "scene_consistent_perspective"]
    if cov == "insufficient":
        allowed = [c for c in allowed if c not in ("focus",)]
    plan["allowed_changes"] = allowed
    forbidden = list(plan.get("forbidden_changes") or [])
    for item in (
        "invented_mounts",
        "unsupported_faces_or_views",
        "identity_structure_change",
        "invented_accessories",
        "invented_packaging",
    ):
        if item not in forbidden:
            forbidden.append(item)
    plan["forbidden_changes"] = forbidden
    constraints = list(plan.get("constraints") or [])
    tag = "coverage_" + cov
    if tag not in constraints:
        constraints.append(tag)
    plan["constraints"] = constraints
    plan["coverage_constraints"] = list(COVERAGE_CONSTRAINTS.get(cov) or [])
    plan["reference_coverage"] = cov
    return plan


def scene_fingerprint_similarity(a: dict[str, str], b: dict[str, str]) -> float:
    if not SCENE_FINGERPRINT_KEYS:
        return 0.0
    matched = 0
    for key in SCENE_FINGERPRINT_KEYS:
        left = (a or {}).get(key) or ""
        right = (b or {}).get(key) or ""
        if left and left == right:
            matched += 1
    return matched / len(SCENE_FINGERPRINT_KEYS)
