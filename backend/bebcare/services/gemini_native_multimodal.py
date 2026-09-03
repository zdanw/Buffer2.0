"""Native Gemini multimodal adapter for local owner-BYOK analysis/QA.

Reuses GoogleGeminiImageProvider credentials. Prefers generateContent;
falls back once to /v1beta/interactions if generateContent returns 404.
Production default remains platform vision. Env-only; no OpenAI-compat chat.
"""

from __future__ import annotations

import base64
import copy
import logging
import os
import re
import subprocess
from io import BytesIO
from typing import Any, Optional

import requests
from PIL import Image

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.providers.google_gemini import GoogleGeminiImageProvider
from bebcare.providers.image_model_filter import (
    filter_gemini_vision_models,
    gemini_model_accepts_image_input,
    gemini_model_id,
)
from bebcare.providers.registry import _build_provider
from bebcare.services.asset_intelligence_policy import (
    FAILURE_PERMANENT,
    FAILURE_TRANSIENT,
    AnalysisFailure,
    classify_analysis_failure,
)
from bebcare.utils.crypto import decrypt_secret
from bebcare.utils.image_utils import image_to_jpeg_bytes

logger = logging.getLogger(__name__)

OWNER_GEMINI_PROVIDER = "owner_gemini_byok"
NATIVE_MODES = frozenset({"owner_gemini_byok", "google_openai_compat"})
_DATA_URL_RE = re.compile(
    r"^data:(image/[\w.+-]+);base64,(.+)$", flags=re.IGNORECASE | re.DOTALL
)
_resolved_model: str | None = None
_resolved_protocol: str | None = None
PROTOCOL_GENERATE_CONTENT = "generate_content"
PROTOCOL_INTERACTIONS = "interactions"
_MAX_INLINE_SIDE = 1024


def intelligence_transport() -> str:
    mode = str(getattr(settings, "asset_intelligence_transport", "platform") or "platform").strip().lower()
    if mode in NATIVE_MODES:
        return "owner_gemini_byok"
    return "platform"


def visual_qa_transport_mode() -> str:
    mode = str(getattr(settings, "visual_fidelity_qa_transport", "platform") or "platform").strip().lower()
    if mode in NATIVE_MODES:
        return "owner_gemini_byok"
    return "platform"


def owner_gemini_intelligence_enabled() -> bool:
    return intelligence_transport() == "owner_gemini_byok"


def owner_gemini_qa_enabled() -> bool:
    return visual_qa_transport_mode() == "owner_gemini_byok"


def cached_analysis_model() -> str | None:
    pinned = str(getattr(settings, "owner_gemini_analysis_model", None) or "").strip()
    if pinned:
        return pinned
    return _resolved_model


def set_cached_analysis_model(model_id: str | None) -> None:
    global _resolved_model
    _resolved_model = (model_id or "").strip() or None


def cached_native_protocol() -> str | None:
    return _resolved_protocol


def set_cached_native_protocol(protocol: str | None) -> None:
    global _resolved_protocol
    _resolved_protocol = (protocol or "").strip() or None


def assert_owner_gemini_vpn() -> None:
    profile = str(getattr(settings, "owner_gemini_byok_vpn_profile", None) or "").strip()
    if not profile:
        return
    if os.name != "nt":
        raise AnalysisFailure(FAILURE_PERMANENT, "vpn_required")
    try:
        completed = subprocess.run(
            ["rasdial"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AnalysisFailure(FAILURE_PERMANENT, "vpn_required") from exc
    blob = f"{completed.stdout or ''} {completed.stderr or ''}"
    if profile.lower() not in blob.lower():
        raise AnalysisFailure(FAILURE_PERMANENT, "vpn_required")


def load_owner_gemini_provider(*, owner_user_id: str | None) -> GoogleGeminiImageProvider:
    if not owner_user_id:
        raise AnalysisFailure(FAILURE_PERMANENT, "invalid_analysis_configuration")
    db = SessionLocal()
    try:
        config = (
            db.query(ImageProviderConfig)
            .filter(
                ImageProviderConfig.owner_user_id == owner_user_id,
                ImageProviderConfig.provider_type == "google_gemini",
                ImageProviderConfig.is_active == True,  # noqa: E712
            )
            .order_by(ImageProviderConfig.is_default.desc(), ImageProviderConfig.updated_at.desc())
            .first()
        )
        if config is None:
            raise AnalysisFailure(FAILURE_PERMANENT, "invalid_analysis_configuration")
        api_key = decrypt_secret(config.api_key_encrypted)
        provider = _build_provider(config, api_key)
        if not isinstance(provider, GoogleGeminiImageProvider):
            raise AnalysisFailure(FAILURE_PERMANENT, "invalid_analysis_configuration")
        return provider
    finally:
        db.close()


def select_vision_model(raw_models: list[dict[str, Any]], *, pinned: str | None = None) -> str:
    vision = filter_gemini_vision_models(raw_models)
    ids = [row["id"] for row in vision if row.get("id")]
    if pinned:
        want = pinned.strip()
        if want in ids:
            return want
        for item in raw_models:
            if gemini_model_id(item) == want and gemini_model_accepts_image_input(item):
                return want
        raise AnalysisFailure(FAILURE_PERMANENT, "analysis_model_not_vision_capable")
    if not ids:
        raise AnalysisFailure(FAILURE_PERMANENT, "analysis_model_not_vision_capable")
    return ids[0]


def discover_owner_gemini_analysis_model(*, owner_user_id: str | None) -> tuple[str, int]:
    """Non-billable GET /models. Returns (model_id, list_call_count)."""
    assert_owner_gemini_vpn()
    provider = load_owner_gemini_provider(owner_user_id=owner_user_id)
    raw = provider.list_raw_models()
    model_id = select_vision_model(
        raw, pinned=str(getattr(settings, "owner_gemini_analysis_model", None) or "").strip() or None
    )
    set_cached_analysis_model(model_id)
    return model_id, 1


def _resize_bytes(raw: bytes, *, max_side: int = _MAX_INLINE_SIDE) -> tuple[str, str]:
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
    jpeg = image_to_jpeg_bytes(image, quality=80)
    return "image/jpeg", base64.b64encode(jpeg).decode("ascii")


def inline_image_part(url: str) -> dict[str, Any]:
    text = (url or "").strip()
    if not text:
        raise AnalysisFailure(FAILURE_PERMANENT, "invalid_image_input")
    match = _DATA_URL_RE.match(text)
    if match:
        raw = base64.b64decode(match.group(2))
        mime, data = _resize_bytes(raw)
        return {"type": "image", "mime_type": mime, "data": data}
    if text.startswith("https://"):
        from bebcare.utils.image_utils import download_image_bytes

        raw = download_image_bytes(text, timeout=(5, 20), max_retries=1)
        mime, data = _resize_bytes(raw)
        return {"type": "image", "mime_type": mime, "data": data}
    raise AnalysisFailure(FAILURE_PERMANENT, "invalid_image_input")


def openai_messages_to_gemini(
    messages: list[dict[str, Any]], *, max_tokens: int = 1024
) -> dict[str, Any]:
    del max_tokens
    system_chunks: list[str] = []
    input_parts: list[dict[str, Any]] = []
    for message in messages:
        role = (message.get("role") or "user").strip().lower()
        content = message.get("content")
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_chunks.append(content.strip())
            continue
        if isinstance(content, str):
            if content.strip():
                input_parts.append({"type": "text", "text": content})
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                input_parts.append({"type": "text", "text": str(part["text"])})
            elif part.get("type") == "image_url":
                href = ((part.get("image_url") or {}).get("url") or "").strip()
                input_parts.append(inline_image_part(href))
    parts: list[dict[str, Any]] = []
    if system_chunks:
        parts.append({"type": "text", "text": "\n\n".join(system_chunks)})
    parts.extend(input_parts or [{"type": "text", "text": "Analyze the image."}])
    return {"input": parts}


def _generate_content_body(
    parts: list[dict[str, Any]],
    *,
    max_tokens: int,
    response_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gc_parts: list[dict[str, Any]] = []
    for part in parts:
        if part.get("type") == "text" and part.get("text"):
            gc_parts.append({"text": str(part["text"])})
        elif part.get("type") == "image" and part.get("data"):
            gc_parts.append(
                {
                    "inline_data": {
                        "mime_type": part.get("mime_type") or "image/jpeg",
                        "data": part["data"],
                    }
                }
            )
    cfg: dict[str, Any] = {
        "temperature": 0.0,
        "maxOutputTokens": max(32, int(max_tokens or 1024)),
        "responseMimeType": "application/json",
    }
    if response_schema:
        cfg["responseSchema"] = response_schema
    return {
        "contents": [{"role": "user", "parts": gc_parts or [{"text": "Analyze the image."}]}],
        "generationConfig": cfg,
    }


def gemini_response_schema(model_schema: dict[str, Any]) -> dict[str, Any]:
    """Dereference Pydantic JSON Schema into Gemini responseSchema."""
    schema = copy.deepcopy(model_schema)
    defs = schema.pop("$defs", None) or schema.pop("definitions", None) or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            if name in defs:
                return resolve(copy.deepcopy(defs[name]))
        any_of = node.get("anyOf") or node.get("oneOf")
        if any_of:
            variants = [resolve(item) for item in any_of]
            nulls = [item for item in variants if item.get("type") == "null"]
            rest = [item for item in variants if item.get("type") != "null"]
            if rest and nulls and len(rest) == 1:
                out = dict(rest[0])
                out["nullable"] = True
                return out
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in ("$ref", "anyOf", "oneOf", "title", "default", "$schema", "additionalProperties"):
                continue
            out[key] = resolve(value)
        if any_of and "anyOf" not in out:
            out["anyOf"] = variants
        return out

    return resolve(schema)


def _extract_generate_content_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") if isinstance(content, dict) else []
    texts = []
    for part in parts or []:
        if isinstance(part, dict) and part.get("text"):
            texts.append(str(part["text"]))
    return "\n".join(texts).strip()


def _extract_text(payload: dict[str, Any]) -> str:
    cached = payload.get("_text")
    if isinstance(cached, str) and cached.strip():
        return cached.strip()
    generate_text = _extract_generate_content_text(payload)
    if generate_text:
        return generate_text
    from bebcare.providers.google_gemini import _collect_text

    return _collect_text(payload)


def _normalize_usage(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("usageMetadata") or payload.get("usage_metadata") or payload.get("usage") or {}
    if not isinstance(meta, dict):
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    prompt = meta.get("promptTokenCount", meta.get("prompt_tokens"))
    completion = meta.get("candidatesTokenCount", meta.get("completion_tokens"))
    total = meta.get("totalTokenCount", meta.get("total_tokens"))
    return {
        "prompt_tokens": int(prompt) if isinstance(prompt, int) else None,
        "completion_tokens": int(completion) if isinstance(completion, int) else None,
        "total_tokens": int(total) if isinstance(total, int) else None,
    }


def _map_http_error(exc: requests.exceptions.HTTPError) -> AnalysisFailure:
    status = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
    if status in (401, 403):
        return AnalysisFailure(FAILURE_PERMANENT, "http_auth", http_status=status)
    if status >= 400:
        failure_type = FAILURE_TRANSIENT if status >= 500 or status == 429 else FAILURE_PERMANENT
        return AnalysisFailure(
            failure_type, f"http_{status}" if status else "http_error", http_status=status
        )
    failure_type, category = classify_analysis_failure(exc)
    return AnalysisFailure(failure_type, category)


def gemini_generate_content(
    *,
    owner_user_id: str | None,
    model_id: str,
    body: dict[str, Any],
    timeout: int = 90,
    protocol: str | None = None,
    max_tokens: int = 1024,
    response_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_owner_gemini_vpn()
    provider = load_owner_gemini_provider(owner_user_id=owner_user_id)
    chosen = protocol or cached_native_protocol() or PROTOCOL_GENERATE_CONTENT
    parts = list(body.get("input") or [])

    def _via_generate_content() -> dict[str, Any]:
        url = f"{provider._root()}/models/{model_id}:generateContent"
        if "/openai" in url or url.rstrip("/").endswith("/chat/completions"):
            raise AnalysisFailure(FAILURE_PERMANENT, "invalid_analysis_configuration")
        payload = provider.generate_content(
            model=model_id,
            body=_generate_content_body(
                parts, max_tokens=max_tokens, response_schema=response_schema
            ),
            timeout=timeout,
        )
        if not isinstance(payload, dict):
            raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_malformed")
        payload["usage"] = _normalize_usage(payload)
        return payload

    def _via_interactions() -> dict[str, Any]:
        url = provider._interactions_url()
        if "/openai" in url or url.rstrip("/").endswith("/chat/completions"):
            raise AnalysisFailure(FAILURE_PERMANENT, "invalid_analysis_configuration")
        payload = provider.complete_multimodal(
            model=model_id, input_parts=parts, timeout=timeout
        )
        if not isinstance(payload, dict):
            raise AnalysisFailure(FAILURE_TRANSIENT, "visual_qa_malformed")
        payload["usage"] = _normalize_usage(payload)
        return payload

    try:
        if chosen == PROTOCOL_INTERACTIONS:
            payload = _via_interactions()
            set_cached_native_protocol(PROTOCOL_INTERACTIONS)
            return payload
        try:
            payload = _via_generate_content()
            set_cached_native_protocol(PROTOCOL_GENERATE_CONTENT)
            return payload
        except requests.exceptions.HTTPError as exc:
            mapped = _map_http_error(exc)
            if mapped.error_category == "http_404" and cached_native_protocol() is None:
                from bebcare.services.provider_request_budget import provider_request_reason

                with provider_request_reason("fallback"):
                    payload = _via_interactions()
                set_cached_native_protocol(PROTOCOL_INTERACTIONS)
                return payload
            raise mapped from exc
    except AnalysisFailure:
        raise
    except requests.exceptions.HTTPError as exc:
        raise _map_http_error(exc) from exc
    except Exception as exc:
        failure_type, category = classify_analysis_failure(exc)
        raise AnalysisFailure(failure_type, category) from exc


def gemini_messages_complete(
    messages: list[dict[str, Any]],
    *,
    owner_user_id: str | None,
    max_tokens: int = 1024,
    response_schema: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    model_id = cached_analysis_model()
    if not model_id:
        model_id, _ = discover_owner_gemini_analysis_model(owner_user_id=owner_user_id)
    body = openai_messages_to_gemini(messages, max_tokens=max_tokens)
    payload = gemini_generate_content(
        owner_user_id=owner_user_id,
        model_id=model_id,
        body=body,
        max_tokens=max_tokens,
        response_schema=response_schema,
    )
    return _extract_text(payload), payload


def probe_multimodal(*, owner_user_id: str | None, model_id: str) -> dict[str, Any]:
    """Tiny native multimodal call with a 32px JPEG. Confirms image input works."""
    image = Image.new("RGB", (32, 32), (180, 180, 180))
    data = base64.b64encode(image_to_jpeg_bytes(image, quality=60)).decode("ascii")
    body = {
        "input": [
            {"type": "text", "text": "Return JSON {\"ok\": true} only."},
            {"type": "image", "mime_type": "image/jpeg", "data": data},
        ]
    }
    payload = gemini_generate_content(
        owner_user_id=owner_user_id, model_id=model_id, body=body, timeout=45
    )
    text = _extract_text(payload)
    return {"ok": "true" in text.lower() or "{" in text, "model": model_id}
