"""Vision adapter for product-fidelity QA. Production default is platform vision."""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from io import BytesIO
from typing import Any, Callable, Optional

import httpx
from pydantic import ValidationError

from bebcare.config.settings import settings
from bebcare.generator.content_generator import deepseek_chat_completions_url
from bebcare.schemas.visual_fidelity import (
    ALL_CHECK_CODES,
    SCHEMA_VERSION,
    VisualFidelityAssessment,
    VisualFidelityCheck,
    normalize_check,
    publication_decision_from_checks,
)
from bebcare.services.asset_intelligence_adapter import (
    ANALYSIS_PROVIDER,
    MAX_RESPONSE_BYTES,
    assert_analysis_image_url,
)
from bebcare.services.asset_intelligence_policy import (
    FAILURE_PERMANENT,
    FAILURE_TRANSIENT,
    AnalysisFailure,
)
from bebcare.services.provider_request_budget import (
    KIND_QA,
    provider_request_context,
    reserved_provider_call,
)
from bebcare.services.visual_qa_policy import POLICY_BUILDER_ID, build_visual_qa_policy, qa_payload_from_policy

logger = logging.getLogger(__name__)
RAW_CAP = 8000
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
QA_PURPOSE = "visual_fidelity_qa"
PLATFORM_PROVIDER = ANALYSIS_PROVIDER

SYSTEM_PROMPT = """You compare a generated marketing image to product reference images.
Return ONLY JSON. No markdown. Schema version visual_fidelity_v1.
The first image is the Candidate image, not a numbered reference.
Primary reference is Image 1. Supporting references start at Image 2. Logo is Approved logo asset.
check_code MUST be exactly one of the provided codes. Never invent a new code.
status must be pass, warning, hard_fail, or not_verifiable.
confidence must be unknown, low, medium, or high.
Use not_verifiable rather than guess. Do not promote missing evidence or low confidence to hard_fail.
Scene contents such as a crib, child seat, stroller, vehicle, or person are not failures by themselves.
Style concerns cannot become identity hard-fails.
Hard-fail only when candidate evidence clearly conflicts with reference evidence at medium or high confidence.
If a logo, antenna, or screen is hidden, distant, off, reflective, or not in view, use not_verifiable.
Invented mounts, brackets, pouches, or cables are hard-fails when clearly present.
Active-driving presentation of a control or display is a usage failure; a parked vehicle is allowed.
If generated_branding_prohibited is true, visible product letters, wordmarks, or brand icons on the candidate are invented_logo or unexpected_product_text hard-fails even when they match a reference. Absence of branding is pass. Correct spelling does not rescue unsupported placement or generated branding.
Dark or incidental screens with weak screen evidence are pass. Invented live feeds, readable UI, or unsupported on-screen controls are prominent_ui_text_corruption or prominent_screen_corruption hard-fails at medium or high confidence.
Include a checks array covering at least these codes:
unexpected_product_text, invented_logo, logo_spelling_or_case_mismatch, logo_placement_mismatch,
logo_on_unsupported_surface, prominent_screen_corruption, prominent_ui_text_corruption,
unsupported_accessory, unsupported_mount_or_attachment, base_or_housing_redesign,
unexpected_primary_duplicate, product_silhouette_mismatch, implausible_cable_routing,
strong_cgi_render_appearance.
Example:
{"schema_version":"visual_fidelity_v1","candidate_index":0,"checks":[{"check_code":"product_silhouette_mismatch","status":"pass","confidence":"medium","short_reason":"outline matches"}],"overall_publication_decision":"eligible","confidence":"medium"}
"""


def visual_qa_response_schema() -> dict[str, Any]:
    """Compact Gemini responseSchema. Check-code validation remains strict after parse."""
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "candidate_index": {"type": "integer"},
            "confidence": {"type": "string", "enum": ["unknown", "low", "medium", "high"]},
            "overall_publication_decision": {
                "type": "string",
                "enum": ["eligible", "eligible_with_warnings", "blocked"],
            },
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "check_code": {"type": "string", "enum": list(ALL_CHECK_CODES)},
                        "status": {
                            "type": "string",
                            "enum": ["pass", "warning", "hard_fail", "not_verifiable"],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["unknown", "low", "medium", "high"],
                        },
                        "short_reason": {"type": "string"},
                    },
                    "required": ["check_code", "status", "confidence"],
                },
            },
        },
        "required": ["checks"],
    }


def visual_qa_model_version() -> str:
    transport = resolve_visual_qa_transport()
    return transport["model"]


def resolve_visual_qa_transport() -> dict[str, str]:
    """HTTP target for visual QA. Default remains platform vision, not owner BYOK."""
    from bebcare.services.gemini_native_multimodal import (
        OWNER_GEMINI_PROVIDER,
        cached_analysis_model,
        visual_qa_transport_mode,
    )

    if visual_qa_transport_mode() == "owner_gemini_byok":
        return {
            "mode": "owner_gemini_byok",
            "url": "native:gemini-multimodal",
            "key": "owner_byok",
            "model": cached_analysis_model()
            or (getattr(settings, "owner_gemini_analysis_model", None) or "owner_gemini_byok"),
            "provider": OWNER_GEMINI_PROVIDER,
        }
    vision_key = (settings.vision_api_key or "").strip()
    if vision_key:
        base = settings.vision_api_url or settings.deepseek_api_url
        return {
            "mode": "platform",
            "url": deepseek_chat_completions_url(base or ""),
            "key": vision_key,
            "model": (settings.vision_model or "unknown").strip() or "unknown",
            "provider": PLATFORM_PROVIDER,
        }
    # Do not send the DeepSeek key to a different default host (e.g. Agnes).
    return {
        "mode": "platform",
        "url": deepseek_chat_completions_url(settings.deepseek_api_url or ""),
        "key": (settings.deepseek_api_key or "").strip(),
        "model": (settings.deepseek_model or "unknown").strip() or "unknown",
        "provider": PLATFORM_PROVIDER,
    }


def _strip_fence(text: str) -> str:
    return _FENCE.sub("", (text or "").strip()).strip()


def _extract_json_text(raw: str) -> str:
    text = _strip_fence(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


_STATUS_ALIASES = {
    "ok": "pass",
    "passed": "pass",
    "fail": "hard_fail",
    "failed": "hard_fail",
    "hardfail": "hard_fail",
    "hard-fail": "hard_fail",
    "warn": "warning",
    "unverifiable": "not_verifiable",
    "notverifiable": "not_verifiable",
    "n/a": "not_verifiable",
    "na": "not_verifiable",
}
_CONF_ALIASES = {"med": "medium", "mid": "medium"}
_CODE_ALIASES = {
    "silhouette_mismatch": "product_silhouette_mismatch",
    "proportion_mismatch": "major_proportion_mismatch",
    "housing_redesign": "base_or_housing_redesign",
    "base_redesign": "base_or_housing_redesign",
    "cgi": "strong_cgi_render_appearance",
    "cgi_render": "strong_cgi_render_appearance",
}


def _norm_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_visual_qa_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic QA JSON cleanup. Unknown check codes are dropped, never remapped loosely."""
    data = dict(payload)
    nested = data.get("assessment") or data.get("result")
    if isinstance(nested, dict) and ("checks" in nested or "check_code" in str(nested)):
        data = {**data, **nested}
    raw_checks = data.get("checks") or data.get("findings") or []
    if isinstance(raw_checks, dict):
        raw_checks = [raw_checks]
    seen: set[str] = set()
    checks: list[dict[str, Any]] = []
    for row in raw_checks:
        if not isinstance(row, dict):
            continue
        code = _CODE_ALIASES.get(_norm_token(row.get("check_code") or row.get("code")), "")
        if not code:
            token = _norm_token(row.get("check_code") or row.get("code"))
            code = token if token in ALL_CHECK_CODES else ""
        if not code or code in seen:
            continue
        status = _STATUS_ALIASES.get(_norm_token(row.get("status")), _norm_token(row.get("status")))
        if status not in ("pass", "warning", "hard_fail", "not_verifiable"):
            status = "not_verifiable"
        conf = row.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            conf = "high" if conf >= 0.8 else "medium" if conf >= 0.5 else "low" if conf >= 0.2 else "unknown"
        else:
            conf = _CONF_ALIASES.get(_norm_token(conf), _norm_token(conf) or "unknown")
        if conf not in ("unknown", "low", "medium", "high"):
            conf = "unknown"
        seen.add(code)
        checks.append(
            {
                "check_code": code,
                "status": status,
                "confidence": conf,
                "short_reason": str(row.get("short_reason") or "")[:400],
                "observed_evidence": str(row.get("observed_evidence") or "")[:400],
                "reference_evidence": str(row.get("reference_evidence") or "")[:400],
                "affected_region": str(row.get("affected_region") or "")[:120],
            }
        )
    data["checks"] = checks
    decision = _norm_token(data.get("overall_publication_decision") or data.get("publication_decision"))
    if decision in ("pass", "ok", "eligible"):
        data["overall_publication_decision"] = "eligible"
    elif decision in ("warn", "warning", "eligible_with_warnings"):
        data["overall_publication_decision"] = "eligible_with_warnings"
    elif decision in ("block", "blocked", "hard_fail"):
        data["overall_publication_decision"] = "blocked"
    return data


def _require_known_checks(parsed: dict[str, Any]) -> None:
    rows = parsed.get("checks") or []
    if not any(
        isinstance(row, dict) and str(row.get("check_code") or "") in ALL_CHECK_CODES
        for row in rows
    ):
        raise ValueError("visual_qa_checks_missing")


def _compact_data_image(url: str, *, max_side: int = 1024, quality: int = 80) -> str:
    """Shrink data-URL images so multimodal QA uploads do not write-timeout."""
    match = re.match(r"^data:image/[\w.+-]+;base64,(.*)$", (url or "").strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        return url
    try:
        from PIL import Image
        from bebcare.utils.image_utils import image_to_jpeg_bytes

        raw = base64.b64decode(match.group(1))
        image = Image.open(BytesIO(raw))
        image.load()
        width, height = image.size
        longest = max(width, height) or 1
        if longest > max_side:
            scale = max_side / longest
            image = image.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )
        jpeg = image_to_jpeg_bytes(image, quality=quality)
        return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    except Exception:
        logger.warning("visual QA data-url compact failed; sending original")
        return url


def _safe_vision_url(url: str) -> str | None:
    text = (url or "").strip()
    if not text:
        return None
    if text.startswith("data:image/"):
        return _compact_data_image(text)
    return assert_analysis_image_url(text)


def _vision_user_content(payload: dict[str, Any]) -> list[dict[str, Any]]:
    labels = payload.get("reference_labels") or {}
    candidate_label = labels.get("candidate") or "Candidate image"
    primary_label = labels.get("primary") or "Primary reference, Image 1"
    logo_label = labels.get("approved_logo") or "Approved logo asset"
    supporting_labels = list(labels.get("supporting") or [])
    image_roles = [candidate_label, primary_label, *supporting_labels, logo_label]
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": json.dumps({
            "task": "Compare generated candidate to primary product reference. "
            "Candidate image is not a provider reference number. "
            "Use executed_qa_policy as the complete production policy. "
            "approved_wordmark_for_comparison is for QA comparison only.",
            "executed_qa_policy": payload.get("executed_qa_policy") or {},
            "generation_plan": payload.get("generation_plan") or payload.get("plan_summary") or {},
            "reference_manifest": payload.get("reference_manifest") or {},
            "validated_final_prompt_hash": payload.get("validated_final_prompt_hash"),
            "reference_coverage": payload.get("reference_coverage"),
            "offering_type": payload.get("offering_type") or "unknown",
            "subject_count_policy": payload.get("subject_count_policy"),
            "generated_branding_prohibited": payload.get("generated_branding_prohibited"),
            "logo_mode": payload.get("logo_mode"),
            "approved_wordmark_for_comparison": payload.get("approved_wordmark_for_comparison"),
            "logo_placement_evidence": payload.get("logo_placement_evidence"),
            "screen_evidence_strength": payload.get("screen_evidence_strength"),
            "screen_content_policy": payload.get("screen_content_policy"),
            "unsupported_mount_accessory_cable_policy": payload.get(
                "unsupported_mount_accessory_cable_policy"
            ),
            "compositing_state": payload.get("compositing_state"),
            "qa_stage": payload.get("qa_stage"),
            "provider_image_labels": payload.get("provider_image_labels"),
            "required_check_codes": payload.get("required_check_codes") or list(ALL_CHECK_CODES),
            "generation_plan_summary": payload.get("plan_summary") or {},
            "logo_policy": payload.get("logo_policy") or {},
            "placement_policy": payload.get("placement_policy") or {},
            "check_codes": list(ALL_CHECK_CODES),
            "asset_intelligence": payload.get("asset_intelligence") or [],
            "image_roles": image_roles,
            "reference_labels": labels,
            "policy_builder": payload.get("policy_builder"),
        }, ensure_ascii=False)[:16000]}
    ]
    labeled = [
        (candidate_label, payload.get("candidate_url")),
        (primary_label, payload.get("primary_reference_url")),
        (logo_label, payload.get("approved_logo_url")),
    ]
    for label, url in labeled:
        safe = _safe_vision_url(str(url or ""))
        if not safe:
            continue
        parts.append({"type": "text", "text": f"Image role: {label}"})
        parts.append({"type": "image_url", "image_url": {"url": safe}})
    for index, url in enumerate(payload.get("supporting_reference_urls") or []):
        safe = _safe_vision_url(str(url or ""))
        if not safe:
            continue
        label = (
            supporting_labels[index]
            if index < len(supporting_labels)
            else f"Supporting reference, Image {index + 2}"
        )
        parts.append({"type": "text", "text": f"Image role: {label}"})
        parts.append({"type": "image_url", "image_url": {"url": safe}})
    return parts


def _parse_usage(raw: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not isinstance(raw, dict):
        return None, None
    pt = raw.get("prompt_tokens")
    ct = raw.get("completion_tokens")
    try:
        prompt_tokens = int(pt) if pt is not None else None
    except (TypeError, ValueError):
        prompt_tokens = None
    try:
        completion_tokens = int(ct) if ct is not None else None
    except (TypeError, ValueError):
        completion_tokens = None
    return prompt_tokens, completion_tokens


def _coerce_assessment(
    data: dict[str, Any],
    *,
    candidate_index: int,
    correction_used: bool,
    composite_logo: bool = False,
    provider: str | None = None,
    policy: dict[str, Any] | None = None,
) -> VisualFidelityAssessment:
    checks = []
    for row in data.get("checks") or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("check_code") or "")
        if code not in ALL_CHECK_CODES:
            continue
        check = normalize_check(
            VisualFidelityCheck.model_validate(row),
            composite_logo=composite_logo,
            policy=policy,
        )
        checks.append(check)
    assessment = VisualFidelityAssessment.model_validate(
        {
            **data,
            "schema_version": SCHEMA_VERSION,
            "candidate_index": candidate_index,
            "checks": [c.model_dump() for c in checks],
            "correction_used": correction_used,
            "provider": data.get("provider") or provider or ANALYSIS_PROVIDER,
            "model_version": visual_qa_model_version(),
        }
    )
    assessment.overall_publication_decision = publication_decision_from_checks(assessment.checks)
    return assessment


_http_post: Callable[..., Any] | None = None


def _with_production_qa_policy(payload: dict[str, Any]) -> dict[str, Any]:
    existing = payload.get("executed_qa_policy")
    if isinstance(existing, dict) and existing.get("policy_builder") == POLICY_BUILDER_ID:
        return payload
    policy = build_visual_qa_policy(payload)
    supporting = [{"cdn_url": url} for url in (payload.get("supporting_reference_urls") or []) if url]
    built = qa_payload_from_policy(
        policy=policy,
        candidate_index=int(payload.get("candidate_index") or 0),
        candidate_url=payload.get("candidate_url"),
        primary={"cdn_url": payload.get("primary_reference_url")},
        supporting=supporting,
        reference_labels=payload.get("reference_labels") or {},
        composite_logo=bool(payload.get("composite_logo")),
        owner_user_id=payload.get("owner_user_id"),
        approved_logo_url=payload.get("approved_logo_url"),
        asset_intelligence=payload.get("asset_intelligence") or [],
    )
    merged = {**built, **payload}
    merged["executed_qa_policy"] = policy
    merged["policy_builder"] = POLICY_BUILDER_ID
    return merged


def assess_visual_fidelity(payload: dict[str, Any]) -> VisualFidelityAssessment:
    """One QA call + at most one JSON-correction call. Tests may patch this function."""
    payload = _with_production_qa_policy(payload)
    candidate_index = int(payload.get("candidate_index") or 0)
    transport = resolve_visual_qa_transport()
    key = transport["key"]
    if not key:
        raise AnalysisFailure(FAILURE_PERMANENT, "vision_unconfigured")
    vision_content = _vision_user_content(payload)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": vision_content},
    ]
    started = time.monotonic()
    correction_used = False
    parsed: dict[str, Any] | None = None
    usage = None
    last_error: Exception | None = None

    def _post_platform(body: dict[str, Any]):
        poster = _http_post
        if poster is None:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:

                def _post():
                    return client.post(
                        transport["url"],
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )

                return reserved_provider_call(_post, kind=KIND_QA)
        return reserved_provider_call(lambda: poster(body), kind=KIND_QA)

    qa_policy = payload.get("executed_qa_policy") if isinstance(payload.get("executed_qa_policy"), dict) else {}
    for attempt in range(2):
        try:
            reason = "correction" if attempt else "initial"
            with provider_request_context(KIND_QA, reason=reason):
                if transport["mode"] == "owner_gemini_byok":
                    from bebcare.services.gemini_native_multimodal import gemini_messages_complete

                    content, payload_json = gemini_messages_complete(
                        messages,
                        owner_user_id=payload.get("owner_user_id"),
                        max_tokens=2048,
                        response_schema=visual_qa_response_schema(),
                    )
                    usage = payload_json.get("usage")
                    parsed = json.loads(_extract_json_text(content))
                    if not isinstance(parsed, dict):
                        raise ValueError("not an object")
                    parsed = normalize_visual_qa_payload(parsed)
                    _require_known_checks(parsed)
                    break
                body = {
                    "model": transport["model"],
                    "messages": messages,
                    "temperature": 0,
                }
                response = _post_platform(body)
            status = int(getattr(response, "status_code", 200) or 200)
            if status in (401, 403):
                logger.warning("visual fidelity QA HTTP auth status=%s", status)
                raise AnalysisFailure(FAILURE_PERMANENT, "visual_qa_http")
            if status >= 400:
                logger.warning("visual fidelity QA HTTP status=%s", status)
                raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_http")
            raw_bytes = getattr(response, "content", None)
            if raw_bytes is None:
                raw_bytes = (response.text or "").encode("utf-8")
            if len(raw_bytes) > MAX_RESPONSE_BYTES:
                raise AnalysisFailure(FAILURE_PERMANENT, "visual_qa_response_too_large")
            payload_json = json.loads(raw_bytes.decode("utf-8", errors="replace"))
            usage = payload_json.get("usage")
            content = (
                ((payload_json.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            )
            parsed = json.loads(_extract_json_text(content))
            if not isinstance(parsed, dict):
                raise ValueError("not an object")
            parsed = normalize_visual_qa_payload(parsed)
            _require_known_checks(parsed)
            break
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            if attempt == 0:
                correction_used = True
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": vision_content
                        + [
                            {
                                "type": "text",
                                "text": (
                                    "Previous reply was invalid VisualFidelityAssessment JSON. "
                                    "Return only JSON with a checks array using exact check_code values. "
                                    f"Error (capped): {str(exc)[:400]}"
                                ),
                            }
                        ],
                    },
                ]
                continue
            raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_malformed") from exc
        except AnalysisFailure:
            raise
        except Exception as exc:
            raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_transport") from exc
    if parsed is None:
        raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_malformed") from last_error
    assessment = _coerce_assessment(
        parsed,
        candidate_index=candidate_index,
        correction_used=correction_used,
        composite_logo=bool(payload.get("composite_logo")),
        provider=transport.get("provider"),
        policy=qa_policy if isinstance(qa_policy, dict) else None,
    )
    assessment.latency_ms = int((time.monotonic() - started) * 1000)
    pt, ct = _parse_usage(usage if isinstance(usage, dict) else None)
    assessment.prompt_tokens = pt
    assessment.completion_tokens = ct
    assessment.provider = transport["provider"]
    return assessment
