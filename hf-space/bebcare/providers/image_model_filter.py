"""Filter GET /models listings down to image-generation models."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence
from urllib.parse import urlparse

_IMAGE_KEYWORDS = (
    "dall-e",
    "dalle",
    "gpt-image",
    "imagen",
    "flux",
    "seedream",
    "seededit",
    "stable-diffusion",
    "sdxl",
    "midjourney",
    "wanx",
    "wan2.",
    "qwen-image",
    "image-edit",
    "cogview",
    "kolors",
    "dreamina",
    "agnes",
    "t2i",
    "i2i",
    "image",
)

_NON_IMAGE_KEYWORDS = (
    "embed",
    "embedding",
    "whisper",
    "tts",
    "asr",
    "speech",
    "audio",
    "chat",
    "instruct",
    "coder",
    "code-",
    "-code",
    "rerank",
    "moderation",
    "deepseek",
    "doubao-pro",
    "doubao-lite",
    "skylark",
    "moonshot",
    "glm-4",
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-long",
    "text-embedding",
    "vision-preview",
)

_GEMINI_IMAGE_NAME_HINTS = ("-image", "imagen", "banana")


def looks_like_image_model(
    model_id: str,
    *,
    extra_text: str = "",
    trust_ep_prefix: bool = False,
) -> bool:
    mid = (model_id or "").strip()
    text = f"{mid} {extra_text}".lower()
    if any(k in text for k in _IMAGE_KEYWORDS):
        return True
    if any(k in text for k in _NON_IMAGE_KEYWORDS):
        return False
    if trust_ep_prefix and mid.startswith("ep-"):
        return True
    return False


def _modalities_include_image(modalities: object) -> bool:
    if not modalities:
        return False
    if isinstance(modalities, str):
        modalities = [modalities]
    if not isinstance(modalities, Sequence):
        return False
    return any(str(m).lower() == "image" for m in modalities)


def openrouter_models_query(base_url: str) -> dict[str, str]:
    host = (urlparse(base_url).netloc or base_url).lower()
    if "openrouter.ai" in host:
        return {"output_modalities": "image"}
    return {}


def is_openrouter_base_url(base_url: str) -> bool:
    return bool(openrouter_models_query(base_url))


def model_item_output_modalities(item: Mapping[str, object]) -> list[str]:
    raw = item.get("output_modalities")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    arch = item.get("architecture")
    if isinstance(arch, dict) and isinstance(arch.get("output_modalities"), list):
        return [str(x) for x in arch["output_modalities"]]
    return []


def filter_openai_compatible_models(
    models: Iterable[Mapping[str, object]],
    *,
    server_prefiltered: bool = False,
) -> List[dict]:
    out: List[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or item.get("model") or "").strip()
        if not mid:
            continue
        modalities = model_item_output_modalities(item)
        if modalities and not _modalities_include_image(modalities):
            continue
        if server_prefiltered or modalities:
            out.append(_model_entry(item, mid))
            continue
        extra = _extra_text(item)
        if looks_like_image_model(mid, extra_text=extra):
            out.append(_model_entry(item, mid))
    return out


def filter_gemini_image_models(models: Iterable[Mapping[str, object]]) -> List[dict]:
    out: List[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or item.get("model") or ""
        mid = str(name).split("/")[-1].strip()
        if not mid:
            continue
        low = mid.lower()
        desc = str(item.get("description") or "").lower()
        methods = item.get("supportedGenerationMethods") or item.get(
            "supported_actions"
        ) or []
        method_text = " ".join(str(m) for m in methods).lower()
        if any(h in low for h in _GEMINI_IMAGE_NAME_HINTS):
            out.append(_model_entry(item, mid, owned_by="google"))
            continue
        if "image" in desc and "generate" in method_text:
            out.append(_model_entry(item, mid, owned_by="google"))
    return out


def filter_doubao_ark_models(models: Iterable[Mapping[str, object]]) -> List[dict]:
    """Ark ep-* ids are opaque — require underlying model/name metadata."""
    out: List[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or item.get("model") or "").strip()
        if not mid:
            continue
        extra = _extra_text(item)
        if mid.startswith("ep-"):
            if not extra.strip():
                continue
            if not looks_like_image_model("", extra_text=extra):
                continue
        elif not looks_like_image_model(mid, extra_text=extra):
            continue
        out.append(_model_entry(item, mid))
    return out


def filter_aliyun_catalog_models(models: Iterable[Mapping[str, object]]) -> List[dict]:
    """Models from DashScope GET /api/v1/models?capabilities=IG."""
    out: List[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        mid = (
            item.get("model_id")
            or item.get("model")
            or item.get("name")
            or item.get("id")
        )
        mid = str(mid or "").strip()
        if not mid:
            continue
        meta = item.get("inference_metadata")
        if isinstance(meta, dict):
            response_modality = meta.get("response_modality") or []
            if isinstance(response_modality, list) and response_modality:
                if not _modalities_include_image(response_modality):
                    continue
        out.append(_model_entry(item, mid))
    return out


def filter_image_models(models: Iterable[Mapping[str, object]]) -> List[dict]:
    """Generic keyword fallback for providers without richer metadata."""
    out: List[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or item.get("model") or "").strip()
        if not mid:
            continue
        extra = _extra_text(item)
        if looks_like_image_model(mid, extra_text=extra):
            out.append(_model_entry(item, mid))
    return out


def _extra_text(item: Mapping[str, object]) -> str:
    return " ".join(
        str(item.get(k) or "")
        for k in ("model", "name", "display_name", "owned_by", "description")
    )


def _model_entry(
    item: Mapping[str, object],
    model_id: str,
    *,
    owned_by: object | None = None,
) -> dict:
    return {
        "id": model_id,
        "owned_by": owned_by if owned_by is not None else item.get("owned_by"),
        "description": item.get("description"),
    }
