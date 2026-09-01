"""Logo identity vs placement. Placement is never inferred from the wordmark string."""

from __future__ import annotations

from typing import Any, Optional

from bebcare.schemas.logo_placement import (
    LOGO_PLACE_VERSION,
    MIRROR_REGION,
    UNSUPPORTED_OVERLAY_REGIONS,
    LogoIdentity,
    LogoObservation,
    LogoPlacementEvidence,
    normalize_region,
)
from bebcare.schemas.visual_fidelity import VisualFidelityCheck
from bebcare.services.logo_policy import (
    LOGO_IN_IMAGES_COMPOSITE,
    LOGO_IN_IMAGES_OMIT,
    resolve_effective_logo_mode,
)

NO_GENERATE_BRANDING = (
    "Do not render, redraw, restyle, relocate, or invent letters, wordmarks, "
    "symbols, labels, or branding on the product. Leave product surfaces clean "
    "and consistent with the references. Branding may be added later using an "
    "approved asset only on an evidenced product region."
)
HIGH = frozenset({"high", "medium"})
STRONG_VISIBILITY = frozenset({"clearly_visible"})


def _item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def provider_ordered_items(items: list | None) -> list:
    return sorted(
        list(items or []),
        key=lambda item: int(_item_value(item, "order", 0) or 0),
    )


def model_facing_provider_labels(items: list | None) -> list[tuple[int, Any]]:
    """1-based Image N in actual provider payload order (first product/scene part)."""
    return [(index, item) for index, item in enumerate(provider_ordered_items(items), start=1)]


def stored_role_line(items: list | None) -> str:
    parts = []
    for index, item in model_facing_provider_labels(items):
        role = _item_value(item, "role")
        if role:
            parts.append(f"Image {index}: {role}")
    return "; ".join(parts)


def model_facing_provider_index(target: Any, items: list | None) -> int:
    tid = _item_value(target, "image_id")
    turl = _item_value(target, "cdn_url")
    for index, item in model_facing_provider_labels(items):
        if tid and _item_value(item, "image_id") == tid:
            return index
        if turl and _item_value(item, "cdn_url") == turl:
            return index
    return 1


def identity_from_product_info(product_info: dict | None) -> LogoIdentity:
    info = product_info or {}
    url = (info.get("logo_url") or info.get("brand_logo_url") or "").strip() or None
    return LogoIdentity(
        approved_logo_asset_id=info.get("logo_asset_id") or info.get("brand_logo_id"),
        approved_logo_url=url,
        owner_user_id=info.get("logo_owner_user_id") or info.get("brand_owner_user_id"),
        wordmark=str(info.get("brand_wordmark") or info.get("brand_name") or "").strip() or None,
        version=info.get("brand_logo_version") or info.get("logo_version"),
    )


def placement_from_product_info(product_info: dict | None) -> LogoPlacementEvidence:
    info = product_info or {}
    stored = info.get("logo_placement") or (info.get("generation_plan") or {}).get("logo_placement")
    if isinstance(stored, dict) and stored:
        try:
            return LogoPlacementEvidence.model_validate(stored)
        except Exception:
            pass
    region = "unknown"
    visibility = "unknown"
    confidence = "unknown"
    present = "unknown"
    ref_id = None
    for row in info.get("asset_intelligence_results") or []:
        if not isinstance(row, dict):
            continue
        physical = row.get("physical") if isinstance(row.get("physical"), dict) else {}
        region = normalize_region(physical.get("logo_product_region") or physical.get("logo_region"))
        vis = str(physical.get("logo_visibility") or row.get("brand_mark_presence") or "unknown").lower()
        if vis in ("present", "likely"):
            present = vis if vis in ("present", "likely") else "present"
            visibility = "clearly_visible" if vis == "present" else "partially_visible"
        elif vis in ("absent",):
            present = "absent"
            visibility = "absent"
        conf = str(row.get("confidence") or physical.get("logo_confidence") or "unknown").lower()
        if conf in ("high", "medium", "low", "unknown"):
            confidence = conf  # type: ignore[assignment]
        ref_id = row.get("image_id") or row.get("product_image_id") or ref_id
        if region != "unknown" or present in ("present", "likely"):
            break
    supports = region not in UNSUPPORTED_OVERLAY_REGIONS and visibility in STRONG_VISIBILITY
    return LogoPlacementEvidence(
        version=LOGO_PLACE_VERSION,
        logo_present=present,  # type: ignore[arg-type]
        approved_logo_asset_id=(info.get("logo_asset_id") or None),
        reference_image_id=ref_id,
        product_region=region,  # type: ignore[arg-type]
        visibility_class=visibility if visibility in (
            "clearly_visible", "partially_visible", "tiny_or_unverifiable",
            "naturally_hidden", "absent", "unknown",
        ) else "unknown",  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        candidate_view_supports_region=supports,
    )


def placement_strongly_evidenced(evidence: LogoPlacementEvidence) -> bool:
    if evidence.confidence not in HIGH:
        return False
    if evidence.visibility_class not in STRONG_VISIBILITY:
        return False
    if evidence.product_region in UNSUPPORTED_OVERLAY_REGIONS:
        return False
    return bool(evidence.candidate_view_supports_region)


def include_wordmark_in_generation_prompt(product_info: dict | None) -> bool:
    info = product_info or {}
    offering = str(info.get("offering_type") or info.get("offering_kind") or "").lower()
    if offering in ("software", "saas", "service", "event", "events", "book", "sign"):
        return True
    if "packaging" in offering or info.get("packaging_is_offering") is True:
        return True
    capture = str(
        (info.get("generation_plan") or {}).get("capture_style")
        or info.get("capture_style")
        or "realistic_photography"
    ).lower()
    if "graphic" in capture or "illustrat" in capture:
        return True
    mode = resolve_effective_logo_mode(info)
    if mode in (LOGO_IN_IMAGES_COMPOSITE, LOGO_IN_IMAGES_OMIT):
        return False
    evidence = placement_from_product_info(info)
    return placement_strongly_evidenced(evidence)


def approved_logo_usable(product_info: dict | None) -> bool:
    info = product_info or {}
    identity = identity_from_product_info(info)
    if not identity.approved_logo_url:
        return False
    owner = (info.get("owner_user_id") or "").strip()
    logo_owner = (identity.owner_user_id or owner).strip()
    if owner and identity.owner_user_id and identity.owner_user_id != owner:
        return False
    return bool(logo_owner == owner or not identity.owner_user_id)


def should_overlay_approved_logo(
    product_info: dict | None,
    *,
    generated_branding_conflict: bool = False,
) -> tuple[bool, str]:
    info = product_info or {}
    if resolve_effective_logo_mode(info) != LOGO_IN_IMAGES_COMPOSITE:
        return False, "not_composite"
    if generated_branding_conflict:
        return False, "pre_composite_generated_mark"
    if not approved_logo_usable(info):
        return False, "unapproved_or_foreign_logo"
    evidence = placement_from_product_info(info)
    if not placement_strongly_evidenced(evidence):
        return False, "placement_unreliable"
    return True, "evidenced_region"


def evaluate_logo_observation(
    *,
    observation: LogoObservation,
    evidence: LogoPlacementEvidence,
    identity: LogoIdentity | None = None,
    intrinsic_text_subject: bool = False,
) -> list[VisualFidelityCheck]:
    """Deterministic placement conflicts. Does not call a model."""
    if intrinsic_text_subject:
        return []
    checks: list[VisualFidelityCheck] = []

    def _check(code: str, status: str, confidence: str, reason: str, region: str = "") -> VisualFidelityCheck:
        return VisualFidelityCheck(
            check_code=code,
            status=status,  # type: ignore[arg-type]
            confidence=confidence,  # type: ignore[arg-type]
            short_reason=reason,
            observed_evidence=observation.product_region,
            reference_evidence=evidence.product_region,
            affected_region=region or observation.product_region,
        )

    if observation.count > 1 or (observation.present and observation.count >= 2):
        checks.append(_check("duplicated_logo", "hard_fail", "high", "more than one brand mark"))
    if observation.mirrored:
        checks.append(_check("mirrored_logo", "hard_fail", "high", "logo appears mirrored"))
    if observation.overlaps_lens_or_control and observation.present:
        checks.append(_check("logo_on_unsupported_surface", "hard_fail", "high", "logo overlaps lens or control"))

    wordmark = (identity.wordmark if identity else None) or ""
    if observation.present and wordmark and observation.spelling:
        if observation.spelling != wordmark:
            checks.append(_check("logo_spelling_or_case_mismatch", "hard_fail", "high", "spelling or case mismatch"))

    evidenced_region = evidence.product_region
    observed_region = observation.product_region
    if observation.present and evidenced_region not in ("unknown",) and observed_region not in ("unknown",):
        if observed_region == MIRROR_REGION.get(evidenced_region):
            checks.append(_check("mirrored_logo", "hard_fail", "high", "opposite/mirrored surface is not inherited"))
        elif observed_region != evidenced_region:
            checks.append(
                _check(
                    "logo_on_unsupported_surface",
                    "hard_fail",
                    "high",
                    "logo on a surface that is not evidenced",
                    observed_region,
                )
            )
            if observation.generated_mark or evidenced_region == "absent" or evidence.visibility_class == "absent":
                checks.append(_check("invented_logo", "hard_fail", "high", "branding invented on unsupported surface"))

    if observation.present and evidence.visibility_class in ("absent",) and evidenced_region in ("unknown", "absent"):
        checks.append(_check("invented_logo", "hard_fail", "high", "no brand mark evidenced"))

    if not observation.present:
        if evidence.visibility_class in ("naturally_hidden", "tiny_or_unverifiable"):
            checks.append(_check("expected_logo_not_verifiable", "not_verifiable", "low", "naturally hidden or tiny"))
        elif evidence.visibility_class == "clearly_visible" and evidence.confidence in HIGH:
            checks.append(_check("expected_logo_not_verifiable", "warning", "low", "expected mark not visible"))

    if observation.present and evidence.visibility_class == "tiny_or_unverifiable":
        checks.append(_check("expected_logo_not_verifiable", "warning", "low", "too small to verify"))

    # Correct spelling never rescues a placement fail
    return checks


def generated_branding_blocks_overlay(checks: list[VisualFidelityCheck]) -> bool:
    blocking = {
        "invented_logo",
        "logo_on_unsupported_surface",
        "duplicated_logo",
        "mirrored_logo",
        "unexpected_product_text",
        "logo_spelling_or_case_mismatch",
        "logo_shape_mismatch",
    }
    return any(c.check_code in blocking and c.status == "hard_fail" for c in checks)
