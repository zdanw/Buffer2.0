"""Final provider-prompt contradiction guard.

Deterministic. No extra model calls. Does not persist full prompts or secrets.
The validated prompt is the only text that may be bound onto GenerateImageRequest.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from bebcare.schemas.final_prompt_validation import (
    AUTHORITY_POLICY_VERSION,
    POLICY_VERSION,
    FinalPromptValidationResult,
)
from bebcare.schemas.generation_plan import NON_PHYSICAL_OFFERING_KINDS
from bebcare.services.grounded_rollout import SOURCE_STUDIO
from bebcare.services.product_fidelity_rollout import prevention_enabled

logger = logging.getLogger(__name__)

POLICY_NAME = "prompt_contradiction_guard"

PROHIBITION_RE = re.compile(
    r"\b(do not|don't|dont|never|avoid|prohibit|prohibited|must not|forbidden|"
    r"禁止|不要|勿)\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。；;])\s+")
IMAGE_ZERO_RE = re.compile(r"\bImage 0\b")
HANDHELD_REQUEST_RE = re.compile(
    r"hand-?held replacement|use hand-held replacement|"
    r"replace the product in (?:their|the|a) hands?|"
    r"swap the product in (?:their|the) hands?|"
    r"fingers must contact the product|"
    r"keep grip, arm pose|"
    r"手持替换|把手中的产品换",
    re.IGNORECASE,
)
CLOSEUP_REQUEST_RE = re.compile(
    r"\b(?:extreme\s+)?(?:macro shot|macro hero|tight crop|dutch angle|worm'?s eye|bird'?s eye)\b|"
    r"\bextreme close-?up\b|\bhero close-?up\b|\bproduct close-?up hero\b|"
    r"\bunsupported (?:rear|side) (?:view|reconstruction)\b",
    re.IGNORECASE,
)
BRANDING_REQUEST_RE = re.compile(
    r"preserve visible branding(?!=False)|"
    r"copy the logo(?: region)?|"
    r"recreate the (?:wordmark|logo|brand mark)|"
    r"the exact case-sensitive wordmark|"
    r"Logo placement must be copied|"
    r"printed letters on the product|"
    r"保留可见品牌(?!关系关闭)",
    re.IGNORECASE,
)
BRANDING_CONTRACT_RE = re.compile(
    r"Preserve identity-defining structure, proportions, branding, and visible relationships\.",
    re.IGNORECASE,
)
BRANDING_FLAG_RE = re.compile(r"preserve visible branding=True", re.IGNORECASE)
FLOATING_PRODUCT_RE = re.compile(
    r"\bfloating product\b|\bproduct floating in (?:mid-?)?air\b|\b悬空产品\b",
    re.IGNORECASE,
)
VARIETY_VS_COVERAGE_RE = re.compile(
    r"vary scene family, lighting, and palette",
    re.IGNORECASE,
)
REAR_SEAT_RE = re.compile(
    r"on (?:a |the )?(?:cushioned |soft )?(?:rear )?(?:car )?seat|"
    r"cushioned rear (?:car )?seat|back[- ]seat(?: placement)?",
    re.IGNORECASE,
)
CONSOLE_RE = re.compile(
    r"on (?:the |a )?cent(?:er|re) console|beside (?:the )?(?:steering|gear)|"
    r"within the driver'?s view|driver(?:'s)? (?:view|controls)",
    re.IGNORECASE,
)
COMMUTE_RE = re.compile(
    r"morning commute|during (?:a |the )?commute|while driving|"
    r"on the (?:road|highway)|active driving|in[- ]progress (?:road )?travel",
    re.IGNORECASE,
)
CABLE_RE = re.compile(
    r"charging cable|power cord|usb(?:-c)? cable|cable trailing|"
    r"trailing(?: toward| to) (?:the )?(?:console|seat|crib)",
    re.IGNORECASE,
)
ACCESSORY_RE = re.compile(
    r"\b(?:pouch|carry pouch|tray|dock|cradle|holder|clamp|bracket|clip mount|"
    r"shared plate|adapter|invented (?:stand|case))\b",
    re.IGNORECASE,
)
STROLLER_MOUNT_RE = re.compile(
    r"mounted on (?:the |a )?stroller|clip(?:ped)? to (?:the |a )?stroller frame|"
    r"on (?:the )?stroller fabric",
    re.IGNORECASE,
)
SCREEN_FEED_RE = re.compile(
    r"live nursery feed|live (?:video )?feed on the screen|readable (?:ui|interface)|"
    r"screen displaying a live|nursery feed on the (?:display|screen)|"
    r"status values on (?:the )?screen",
    re.IGNORECASE,
)
DUPLICATE_SUBJECT_RE = re.compile(
    r"two (?:identical )?(?:cameras|monitors|units|products)|"
    r"a pair of (?:cameras|monitors)|another (?:copy|unit|product) beside|"
    r"duplicate (?:hero )?devices?",
    re.IGNORECASE,
)
GOLDEN_RE = re.compile(
    r"warm golden cinematic|exaggerated golden(?:-|\s)?hour|golden cinematic styling|"
    r"dreamy (?:extreme )?(?:shallow )?depth of field|dreamy (?:extreme )?bokeh|"
    r"picture[- ]perfect symmetry|spotless showroom",
    re.IGNORECASE,
)
MALFORMED_WHITE_RE = re.compile(r"A lifestyle photograph\s+white the product", re.IGNORECASE)
ISOLATED_ZH_RE = re.compile(r"(?<![A-Za-z\u4e00-\u9fff])细腻质感(?![A-Za-z\u4e00-\u9fff])")
PARKED_OK_RE = re.compile(
    r"parked vehicle|stationary|visible through the window|outside the vehicle|"
    r"in the background",
    re.IGNORECASE,
)

STABLE_FALLBACK = (
    "Place the complete original product, including its original base, fully on a "
    "stable horizontal dresser, shelf, table, or counter."
)
PARKED_FALLBACK = (
    "If a vehicle appears, keep it parked and stationary. Keep the product away from "
    "driver controls and not presented for active operation."
)
SCREEN_FALLBACK = (
    "Keep the display dark, softly reflective, or visually nonprominent because detailed "
    "screen content is not supported by the references."
)
REALISM_FALLBACK = (
    "Use moderate depth of field, restrained scene-consistent light, ordinary asymmetry, "
    "and credible home or editorial photography."
)

EVENT_BY_CATEGORY = {
    "placement_conflict": "placement_conflict_resolved",
    "unsupported_mount_conflict": "placement_conflict_resolved",
    "vehicle_usage_conflict": "vehicle_usage_conflict_resolved",
    "unsupported_accessory_conflict": "unsupported_accessory_removed",
    "cable_conflict": "cable_instruction_removed",
    "screen_content_conflict": "screen_content_restricted",
    "generated_branding_conflict": "generated_branding_removed",
    "subject_count_conflict": "subject_count_conflict_resolved",
    "reference_authority_conflict": "reference_authority_conflict_resolved",
    "coverage_risk_conflict": "coverage_conflict_resolved",
    "realism_conflict": "realism_language_rewritten",
    "duplicate_policy_text": "duplicate_policy_removed",
    "malformed_prompt_text": "malformed_prompt_normalized",
}


def prompt_digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _source(info: dict) -> str:
    return (
        (info.get("generation_provenance") or {}).get("source")
        or info.get("source")
        or SOURCE_STUDIO
    )


def _plan(info: dict) -> dict[str, Any]:
    raw = info.get("generation_plan")
    return raw if isinstance(raw, dict) else {}


def _logo(plan: dict) -> dict[str, Any]:
    logo = plan.get("logo_policy")
    if isinstance(logo, dict):
        return logo
    nested = plan.get("fidelity")
    if isinstance(nested, dict) and isinstance(nested.get("logo"), dict):
        return nested["logo"]
    return {}


def guard_applies(product_info: dict | None) -> bool:
    info = product_info or {}
    if _plan(info):
        return True
    return prevention_enabled(source=_source(info))


def _physical(info: dict, texts: list[str]) -> bool:
    from bebcare.services.product_fidelity_prevention import physical_placement_sanitization_applies

    return physical_placement_sanitization_applies(info, texts)


def _coverage_restricted(plan: dict) -> bool:
    coverage = str(plan.get("reference_coverage") or "")
    constraints = plan.get("coverage_constraints") or []
    extra = plan.get("extra_constraints") or []
    if coverage in ("limited", "insufficient"):
        return True
    blob = " ".join(str(x) for x in list(constraints) + list(extra))
    return "no_macro" in blob or "no_handheld" in blob or "coverage_limited" in blob


def _branding_withheld(plan: dict, info: dict) -> bool:
    logo = _logo(plan)
    if logo.get("generated_branding_prohibited") is True:
        return True
    if logo.get("insert_wordmark_in_prompt") is False:
        return True
    overlay = info.get("fidelity_guard") if isinstance(info.get("fidelity_guard"), dict) else {}
    nested = overlay.get("logo_policy") if isinstance(overlay.get("logo_policy"), dict) else {}
    return bool(nested.get("generated_branding_prohibited")) or nested.get("insert_wordmark_in_prompt") is False


def _is_prohibition(chunk: str) -> bool:
    return bool(PROHIBITION_RE.search(chunk))


def _rewrite_positive(text: str, pattern: re.Pattern[str], replacement: str) -> tuple[str, bool]:
    if not text or not pattern.search(text):
        return text, False
    parts = SENTENCE_SPLIT_RE.split(text)
    kept: list[str] = []
    changed = False
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if pattern.search(chunk) and not _is_prohibition(chunk):
            if PARKED_OK_RE.search(chunk) and pattern in (COMMUTE_RE, CONSOLE_RE) and "console" not in chunk.lower():
                kept.append(chunk)
                continue
            kept.append(replacement.rstrip(".") + ".")
            changed = True
            continue
        kept.append(chunk)
    if not changed:
        return text, False
    return re.sub(r"\s+", " ", " ".join(kept)).strip(), True


def _drop_positive(text: str, pattern: re.Pattern[str]) -> tuple[str, bool]:
    if not text or not pattern.search(text):
        return text, False
    parts = SENTENCE_SPLIT_RE.split(text)
    kept: list[str] = []
    changed = False
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if pattern.search(chunk) and not _is_prohibition(chunk):
            changed = True
            continue
        kept.append(chunk)
    if not changed:
        return text, False
    return re.sub(r"\s+", " ", " ".join(kept)).strip(), True


def _dedupe_sentences(text: str) -> tuple[str, bool]:
    parts = SENTENCE_SPLIT_RE.split(text or "")
    seen: set[str] = set()
    kept: list[str] = []
    changed = False
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        key = re.sub(r"\s+", " ", chunk.lower())[:96]
        if key in seen:
            changed = True
            continue
        seen.add(key)
        kept.append(chunk)
    return (" ".join(kept).strip(), changed)


def _normalize(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    out = text or ""
    if MALFORMED_WHITE_RE.search(out):
        out = MALFORMED_WHITE_RE.sub("A lifestyle photograph of the product", out)
        flags.append("malformed_prompt_text")
    collapsed, n = re.subn(
        r"(lifestyle photograph[,\s]*){2,}",
        "lifestyle photograph, ",
        out,
        flags=re.IGNORECASE,
    )
    if n:
        out = collapsed
        flags.append("malformed_prompt_text")
    ascii_ratio = (sum(1 for ch in out if ord(ch) < 128) / max(len(out), 1))
    if ascii_ratio > 0.85 and ISOLATED_ZH_RE.search(out):
        out = ISOLATED_ZH_RE.sub("", out)
        flags.append("malformed_prompt_text")
    out = re.sub(r"\s+", " ", out).strip()
    return out, list(dict.fromkeys(flags))


def _remaining_positive(text: str, pattern: re.Pattern[str]) -> bool:
    for chunk in SENTENCE_SPLIT_RE.split(text or ""):
        if pattern.search(chunk) and not _is_prohibition(chunk):
            if PARKED_OK_RE.search(chunk) and pattern is COMMUTE_RE:
                continue
            return True
    return False


def _diagnostics_summary(result: FinalPromptValidationResult) -> str:
    if not result.evaluated:
        return "prompt_contradiction_planned"
    if not result.provider_request_allowed:
        return "final_prompt_blocked"
    cats = set(result.detected_conflicts)
    if "cable_conflict" in cats or "unsupported_accessory_conflict" in cats:
        return "prompt_cable_accessory_corrected"
    if "placement_conflict" in cats or "unsupported_mount_conflict" in cats or "vehicle_usage_conflict" in cats:
        return "prompt_placement_corrected"
    if "screen_content_conflict" in cats:
        return "prompt_screen_restricted"
    if "realism_conflict" in cats:
        return "prompt_realism_corrected"
    if result.changed:
        return "prompt_contradiction_resolved"
    return "prompt_contradiction_passed"


def validate_final_prompt(prompt: str, product_info: dict | None) -> FinalPromptValidationResult:
    info = product_info if isinstance(product_info, dict) else {}
    original = (prompt or "").strip()
    digest = prompt_digest(original)
    plan = _plan(info)
    offering = str(info.get("offering_type") or info.get("offering_kind") or plan.get("offering_type") or "")
    capture = str(plan.get("capture_style") or info.get("capture_style") or "")
    coverage = str(plan.get("reference_coverage") or "")
    if not guard_applies(info):
        return FinalPromptValidationResult(
            original_prompt_hash=digest,
            validated_prompt=original,
            validated_prompt_hash=digest,
            offering_type=offering or None,
            capture_mode=capture or None,
            reference_coverage=coverage or None,
            evaluated=False,
            diagnostics_summary="prompt_contradiction_off",
        )
    kind = offering.lower()
    software = kind in NON_PHYSICAL_OFFERING_KINDS
    packaging = "packaging" in kind or bool(info.get("packaging_is_the_offering"))
    graphic = "graphic" in capture or "illustrat" in capture
    physical = _physical(info, [original]) and not software and not packaging and not graphic

    text = original
    conflicts: list[str] = []
    removed: list[str] = []
    rewritten: list[str] = []
    fallbacks: list[str] = []

    if IMAGE_ZERO_RE.search(text):
        text = IMAGE_ZERO_RE.sub("Image 1", text)
        conflicts.append("reference_authority_conflict")
        rewritten.append("image_index_corrected")

    if plan and str(plan.get("handheld_physical_replacement") or "prohibited") == "prohibited":
        text, changed = _drop_positive(text, HANDHELD_REQUEST_RE)
        if changed:
            conflicts.append("unsupported_geometry_conflict")
            removed.append("handheld_request_removed")

    if physical:
        from bebcare.services.product_fidelity_prevention import (
            detect_unsupported_installations,
            evidence_installations,
            rewrite_vague_mount_language,
        )

        evidenced = evidence_installations(info)
        text = rewrite_vague_mount_language(text)
        text, changed = _rewrite_positive(text, REAR_SEAT_RE, STABLE_FALLBACK)
        if changed:
            conflicts.append("placement_conflict")
            rewritten.append("rear_seat_to_stable_surface")
            fallbacks.append("stable_surface")
        if "stroller_mount" not in evidenced:
            text, changed = _rewrite_positive(text, STROLLER_MOUNT_RE, STABLE_FALLBACK)
            if changed:
                conflicts.append("unsupported_mount_conflict")
                rewritten.append("stroller_mount_to_stable_surface")
                fallbacks.append("stable_surface")
        text, changed = _rewrite_positive(text, CONSOLE_RE, PARKED_FALLBACK)
        if changed:
            conflicts.append("vehicle_usage_conflict")
            rewritten.append("console_active_use_removed")
            fallbacks.append("parked_vehicle")
        text, changed = _rewrite_positive(text, COMMUTE_RE, PARKED_FALLBACK)
        if changed:
            conflicts.append("vehicle_usage_conflict")
            rewritten.append("commute_to_parked")
            fallbacks.append("parked_vehicle")
        text, changed = _drop_positive(text, CABLE_RE)
        if changed:
            conflicts.append("cable_conflict")
            removed.append("unsupported_cable")
        text, changed = _drop_positive(text, ACCESSORY_RE)
        if changed:
            conflicts.append("unsupported_accessory_conflict")
            removed.append("unsupported_accessory")
        if detect_unsupported_installations(text, evidenced, product_info=info):
            text, changed = _rewrite_positive(
                text,
                re.compile(
                    r"mounted on|clip(?:ped)? to|wall[-\s]?mount|crib[-\s]?rail|headrest",
                    re.IGNORECASE,
                ),
                STABLE_FALLBACK,
            )
            if changed:
                conflicts.append("unsupported_mount_conflict")
                rewritten.append("unsupported_mount_to_stable_surface")
                fallbacks.append("stable_surface")
        text, changed = _drop_positive(text, FLOATING_PRODUCT_RE)
        if changed:
            conflicts.append("placement_conflict")
            removed.append("floating_product")
            if "dresser, shelf, table" not in text.lower():
                text = f"{text} {STABLE_FALLBACK}".strip()
                fallbacks.append("stable_surface")

        if not software and not packaging:
            text, changed = _rewrite_positive(text, SCREEN_FEED_RE, SCREEN_FALLBACK)
            if changed:
                conflicts.append("screen_content_conflict")
                rewritten.append("live_feed_restricted")
                fallbacks.append("incidental_screen")

    if _coverage_restricted(plan):
        text, changed = _drop_positive(text, CLOSEUP_REQUEST_RE)
        if changed:
            conflicts.append("coverage_risk_conflict")
            removed.append("unsupported_closeup")
        text, changed = _drop_positive(text, VARIETY_VS_COVERAGE_RE)
        if changed:
            conflicts.append("coverage_risk_conflict")
            removed.append("variety_over_coverage")
        from bebcare.services.quality_diversity_policy import coverage_prompt

        extra = coverage_prompt(coverage or "limited")  # type: ignore[arg-type]
        if extra and extra.lower() not in text.lower():
            text = f"{text} {extra}".strip()
            conflicts.append("coverage_risk_conflict")
            fallbacks.append("coverage_constraints")
        if coverage == "insufficient" and _remaining_positive(text, CLOSEUP_REQUEST_RE):
            conflicts.append("unresolved_high_authority_conflict")

    if _branding_withheld(plan, info) and not software and not packaging and not graphic:
        from bebcare.services.product_fidelity_prevention import redact_prohibited_wordmark

        redacted = redact_prohibited_wordmark(text, info)
        if redacted != text:
            text = redacted
            conflicts.append("generated_branding_conflict")
            removed.append("brand_token")
        if BRANDING_CONTRACT_RE.search(text):
            text = BRANDING_CONTRACT_RE.sub(
                "Preserve identity-defining structure, proportions, and visible relationships. "
                "Do not generate branding.",
                text,
            )
            conflicts.append("generated_branding_conflict")
            rewritten.append("branding_contract_aligned")
        if BRANDING_FLAG_RE.search(text):
            text = BRANDING_FLAG_RE.sub("preserve visible branding=False", text)
            conflicts.append("generated_branding_conflict")
            rewritten.append("branding_flag_aligned")
        text, changed = _drop_positive(text, BRANDING_REQUEST_RE)
        if changed:
            conflicts.append("generated_branding_conflict")
            removed.append("generated_branding_request")

    subject = plan.get("subject") if isinstance(plan.get("subject"), dict) else {}
    if not subject and isinstance(plan.get("subject_spec"), dict):
        subject = plan["subject_spec"]
    if int(subject.get("primary_subject_count") or 1) == 1 and not subject.get("duplicate_primary_subjects_allowed"):
        text, changed = _drop_positive(text, DUPLICATE_SUBJECT_RE)
        if changed:
            conflicts.append("subject_count_conflict")
            removed.append("duplicate_primary")

    if physical and (not capture or "realistic" in capture or capture == ""):
        from bebcare.services.product_fidelity_prevention import sanitize_realistic_photo_report

        report = sanitize_realistic_photo_report(text)
        if report.get("categories_rewritten"):
            text = report["text"]
            conflicts.append("realism_conflict")
            rewritten.append("realistic_photo_sanitizer")
        text, changed = _rewrite_positive(text, GOLDEN_RE, REALISM_FALLBACK)
        if changed:
            conflicts.append("realism_conflict")
            rewritten.append("cinematic_styling_restrained")
            fallbacks.append("natural_photography")

    text, deduped = _dedupe_sentences(text)
    if deduped:
        conflicts.append("duplicate_policy_text")
        removed.append("duplicate_policy_sentence")
    text, norm_flags = _normalize(text)
    conflicts.extend(norm_flags)

    hard: list[str] = []
    if re.search(r"Image 1 \(primary", text, re.IGNORECASE) and re.search(
        r"Image 1 \(scene", text, re.IGNORECASE
    ):
        hard.append("reference_authority_conflict")
        conflicts.append("unresolved_high_authority_conflict")
    if physical:
        if _remaining_positive(text, REAR_SEAT_RE) or _remaining_positive(text, STROLLER_MOUNT_RE):
            hard.append("placement_conflict")
        if _remaining_positive(text, COMMUTE_RE):
            hard.append("vehicle_usage_conflict")
        if _remaining_positive(text, CABLE_RE):
            hard.append("cable_conflict")
        if _remaining_positive(text, SCREEN_FEED_RE):
            hard.append("screen_content_conflict")
    if _remaining_positive(text, IMAGE_ZERO_RE):
        hard.append("reference_authority_conflict")
    if coverage == "insufficient" and _remaining_positive(text, CLOSEUP_REQUEST_RE):
        hard.append("coverage_risk_conflict")
    if _branding_withheld(plan, info) and not software and not packaging and not graphic:
        if _remaining_positive(text, BRANDING_REQUEST_RE):
            hard.append("generated_branding_conflict")

    conflicts = list(dict.fromkeys(conflicts))
    allowed = not hard
    changed = prompt_digest(text) != digest
    result = FinalPromptValidationResult(
        original_prompt_hash=digest,
        validated_prompt=text.strip(),
        validated_prompt_hash=prompt_digest(text.strip()),
        offering_type=offering or None,
        capture_mode=capture or None,
        reference_coverage=coverage or None,
        detected_conflicts=conflicts,
        removed_fragments=removed[:12],
        rewritten_fragments=rewritten[:12],
        deduplicated_policy_categories=["duplicate_policy_text"] if "duplicate_policy_text" in conflicts else [],
        applied_fallbacks=list(dict.fromkeys(fallbacks))[:12],
        hard_failures=list(dict.fromkeys(hard)),
        provider_request_allowed=allowed,
        changed=changed,
        evaluated=True,
        safe_event_details={
            "conflict_categories": conflicts[:12],
            "removed_count": len(removed),
            "rewritten_count": len(rewritten),
            "provider_request_allowed": allowed,
            "validated_prompt_hash": prompt_digest(text.strip()),
            "coverage": coverage or None,
        },
    )
    result.diagnostics_summary = _diagnostics_summary(result)
    _stamp_info(info, result)
    _log_result(info, result)
    return result.capped()


def _stamp_info(info: dict, result: FinalPromptValidationResult) -> None:
    payload = result.persistable()
    payload["applied"] = result.changed
    payload["resolved"] = result.detected_conflicts[:12]
    if isinstance(info.get("generation_plan"), dict):
        info["generation_plan"]["prompt_contradiction"] = payload
        info["generation_plan"]["final_prompt_validation"] = payload
    provenance = info.setdefault("generation_provenance", {})
    if isinstance(provenance, dict):
        provenance["prompt_contradiction"] = payload
        provenance["validated_prompt_hash"] = result.validated_prompt_hash
    info["_validated_prompt_hash"] = result.validated_prompt_hash
    info["_validated_prompt"] = result.validated_prompt if result.provider_request_allowed else None


def _log_result(info: dict, result: FinalPromptValidationResult) -> None:
    try:
        logger.info(
            "generation_diagnostics",
            extra={
                "generation_run_id": info.get("generation_run_id"),
                "product_id": info.get("product_id"),
                "stage": "pre_provider",
                "event_code": (
                    "final_prompt_validation_blocked"
                    if not result.provider_request_allowed
                    else ("final_prompt_conflict_detected" if result.changed else "final_prompt_validation_passed")
                ),
                "outcome": "blocked" if not result.provider_request_allowed else ("applied" if result.changed else "clean"),
                "policy_version": POLICY_VERSION,
                "conflict_categories": result.detected_conflicts[:12],
                "removed_count": len(result.removed_fragments),
                "rewritten_count": len(result.rewritten_fragments),
                "provider_call_allowed": result.provider_request_allowed,
                "error_category": None if result.provider_request_allowed else "final_prompt_validation_blocked",
            },
        )
    except Exception:
        pass


def apply_prompt_contradiction_guard(prompt: str, product_info: dict | None) -> tuple[str, dict[str, Any]]:
    result = validate_final_prompt(prompt, product_info)
    report = {
        "policy_version": result.policy_version,
        "evaluated": result.evaluated,
        "applied": result.changed,
        "resolved": result.detected_conflicts[:12],
    }
    return result.validated_prompt, report


def bind_validated_request(request: Any, result: FinalPromptValidationResult) -> Any:
    """Freeze GenerateImageRequest onto the validated prompt. Role labels must already be in it."""
    frozen = request.model_copy(
        update={
            "prompt": result.validated_prompt,
            "annotate_roles": False,
            "validated_prompt_hash": result.validated_prompt_hash,
        }
    )
    bound = (frozen.prompt_with_role_labels() or "").strip()
    if prompt_digest(bound) != result.validated_prompt_hash:
        raise ValueError("provider_bound_prompt_hash_mismatch")
    return frozen


def prepare_validated_image_request(draft: Any, product_info: dict | None) -> tuple[Any, FinalPromptValidationResult]:
    cached = (product_info or {}).get("_validated_image_request")
    cached_result = (product_info or {}).get("_final_prompt_validation")
    if cached is not None and cached_result is not None:
        return cached, cached_result
    assembled = (draft.prompt_with_role_labels() or "").strip()
    result = validate_final_prompt(assembled, product_info)
    if product_info is not None:
        product_info["_final_prompt_validation"] = result
    if not result.provider_request_allowed:
        return draft, result
    frozen = bind_validated_request(draft, result)
    if product_info is not None:
        product_info["_validated_image_request"] = frozen
    return frozen, result


def persist_prompt_contradiction(db: Any, product_info: dict | None) -> None:
    """Best-effort events + plan merge. Must not raise."""
    info = product_info or {}
    run_id = info.get("generation_run_id")
    result: Optional[FinalPromptValidationResult] = info.get("_final_prompt_validation")
    report = None
    plan = info.get("generation_plan")
    if isinstance(result, FinalPromptValidationResult):
        report = result.persistable()
        report["applied"] = result.changed
        report["resolved"] = result.detected_conflicts[:12]
    elif isinstance(plan, dict) and isinstance(plan.get("prompt_contradiction"), dict):
        report = plan["prompt_contradiction"]
    provenance = info.get("generation_provenance") if isinstance(info.get("generation_provenance"), dict) else {}
    if report is None and isinstance(provenance.get("prompt_contradiction"), dict):
        report = provenance["prompt_contradiction"]
    if not run_id or not report or not report.get("evaluated"):
        return
    try:
        from bebcare.models.generation_qds import GenerationDecisionEvent
        from bebcare.models.generation_run import GenerationRun
        from bebcare.services.ownership import stamp_owner
        from bebcare.services.quality_diversity_events import _safe_details

        run = db.query(GenerationRun).filter(GenerationRun.run_id == str(run_id)).first()
        if run is None:
            return
        if run.owner_user_id and info.get("owner_user_id") and run.owner_user_id != info.get("owner_user_id"):
            return
        nested = db.begin_nested()
        stored = run.generation_plan if isinstance(run.generation_plan, dict) else {}
        merged = dict(stored)
        if isinstance(plan, dict):
            merged.update({k: v for k, v in plan.items() if k not in ("prompt",)})
        merged["prompt_contradiction"] = report
        merged["final_prompt_validation"] = report
        run.generation_plan = merged
        existing_types = {
            row[0]
            for row in db.query(GenerationDecisionEvent.event_type)
            .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
            .all()
        }
        max_seq = (
            db.query(GenerationDecisionEvent.sequence_number)
            .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
            .order_by(GenerationDecisionEvent.sequence_number.desc())
            .first()
        )
        sequence = int(max_seq[0]) + 1 if max_seq else 0
        events: list[dict[str, Any]] = []
        applied = bool(report.get("changed") or report.get("applied"))
        allowed = report.get("provider_request_allowed", True)
        if "final_prompt_validation_started" not in existing_types:
            events.append(
                {
                    "event_type": "final_prompt_validation_started",
                    "outcome": "active",
                    "summary": "Final prompt validation started",
                }
            )
        if applied and "final_prompt_conflict_detected" not in existing_types:
            events.append(
                {
                    "event_type": "final_prompt_conflict_detected",
                    "outcome": "applied",
                    "summary": "Final prompt conflicts detected",
                }
            )
        for category in list(report.get("detected_conflicts") or report.get("resolved") or [])[:8]:
            event_type = EVENT_BY_CATEGORY.get(str(category))
            if event_type and event_type not in existing_types:
                events.append({"event_type": event_type, "outcome": "applied", "summary": str(category)})
                existing_types.add(event_type)
        terminal = "final_prompt_validation_blocked" if not allowed else (
            "final_prompt_validation_passed"
        )
        if terminal not in existing_types:
            events.append(
                {
                    "event_type": terminal,
                    "outcome": "blocked" if not allowed else ("applied" if applied else "clean"),
                    "summary": "Final prompt blocked" if not allowed else "Final prompt validated",
                }
            )
        legacy = "prompt_contradiction_resolved" if applied else "prompt_contradiction_evaluated"
        if legacy not in existing_types:
            events.append(
                {
                    "event_type": legacy,
                    "outcome": "applied" if applied else "clean",
                    "summary": "Conflicting prompt instructions removed" if applied else "Final prompt checked",
                }
            )
        for event in events[:16]:
            rec = GenerationDecisionEvent(
                generation_run_id=run.run_id,
                sequence_number=sequence,
                event_type=event["event_type"],
                stage="pre_provider",
                outcome=event.get("outcome"),
                severity="warning" if not allowed else "info",
                policy_name=POLICY_NAME,
                policy_version=str(report.get("policy_version") or POLICY_VERSION),
                summary=(event.get("summary") or "")[:500],
                details=_safe_details(
                    {
                        "resolved": list(report.get("detected_conflicts") or report.get("resolved") or [])[:12],
                        "validated_prompt_hash": report.get("validated_prompt_hash"),
                        "provider_request_allowed": allowed,
                    }
                ),
            )
            stamp_owner(rec, type("Owner", (), {"user_id": run.owner_user_id})())
            db.add(rec)
            sequence += 1
        nested.commit()
    except Exception:
        logger.warning(
            "prompt_contradiction_persist_failed",
            extra={
                "generation_run_id": run_id,
                "event": "prompt_contradiction_persist_failed",
                "stage": "pre_provider",
                "outcome": "error",
                "policy_version": POLICY_VERSION,
                "product_id": info.get("product_id"),
                "error_category": "observability_persist",
            },
        )
