import base64
import logging
import math
import re
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)

_DATA_URL_RE = re.compile(
    r"^data:(image/[\w.+-]+);base64,(.+)$", flags=re.IGNORECASE | re.DOTALL
)
_SIZE_RE = re.compile(r"^(\d{2,5})\s*[xX×*]\s*(\d{2,5})$")
_ASPECT_RE = re.compile(r"^(\d{1,2}):(\d{1,2})$")
_KNOWN_ASPECTS = (
    (1, 1),
    (16, 9),
    (9, 16),
    (4, 3),
    (3, 4),
    (3, 2),
    (2, 3),
    (4, 5),
    (5, 4),
    (21, 9),
)
_DROP_KEYS = ("negative_prompt", "image", "size", "n", "response_format")


def size_to_aspect(size: Optional[str]) -> str:
    raw = (size or "").strip()
    m = _ASPECT_RE.match(raw)
    if m:
        return f"{int(m.group(1))}:{int(m.group(2))}"
    m = _SIZE_RE.match(raw)
    if not m:
        return "1:1"
    w, h = int(m.group(1)), int(m.group(2))
    g = math.gcd(w, h) or 1
    exact = f"{w // g}:{h // g}"
    known = {f"{a}:{b}" for a, b in _KNOWN_ASPECTS}
    if exact in known:
        return exact
    ratio = w / h if h else 1.0
    best = min(_KNOWN_ASPECTS, key=lambda ab: abs(ab[0] / ab[1] - ratio))
    return f"{best[0]}:{best[1]}"


def _to_data_url(item: dict) -> str:
    mime = item.get("mime_type") or item.get("mimeType") or "image/png"
    return f"data:{mime};base64,{item['data']}"


def _reference_to_part(url: str) -> dict:
    if not url:
        raise ValueError("empty reference image url")
    match = _DATA_URL_RE.match(url.strip())
    if match:
        return {
            "type": "image",
            "data": match.group(2),
            "mime_type": match.group(1).lower(),
        }
    from bebcare.utils.image_utils import download_image_bytes

    raw = download_image_bytes(url)
    return {
        "type": "image",
        "data": base64.b64encode(raw).decode("ascii"),
        "mime_type": "image/jpeg",
    }


def _collect_images(payload: dict) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()

    def _add(item: dict):
        data = item.get("data")
        if not data:
            return
        data_url = _to_data_url(item)
        if data_url in seen:
            return
        seen.add(data_url)
        urls.append(data_url)

    out = payload.get("output_image")
    if isinstance(out, dict):
        _add(out)
    for step in payload.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for item in step.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "image":
                _add(item)
    return urls


class GoogleGeminiImageProvider:
    """Gemini Interactions API (Nano Banana image models)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        default_model: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        extra_params: Optional[dict] = None,
        supports_list_models: bool = True,
    ):
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}
        self.supports_list_models = supports_list_models

    def _root(self) -> str:
        root = self.base_url
        for suffix in ("/interactions", "/openai", "/models"):
            if root.endswith(suffix):
                root = root[: -len(suffix)]
        return root.rstrip("/")

    def _interactions_url(self) -> str:
        return f"{self._root()}/interactions"

    def _models_url(self) -> str:
        return f"{self._root()}/models"

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        headers.update(self.extra_headers)
        return headers

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "2048x2048",
        model: Optional[str] = None,
    ) -> List[str]:
        model_id = model or self.default_model
        if not model_id:
            raise ValueError("image model is required")

        text = (prompt or "").strip()
        if not text:
            raise ValueError("image prompt is required")
        if (negative_prompt or "").strip():
            text = f"{text}\n\nAvoid: {negative_prompt.strip()}"

        input_parts: List[dict] = [{"type": "text", "text": text}]
        for url in reference_images or []:
            if not url:
                continue
            try:
                input_parts.append(_reference_to_part(url))
            except Exception as e:
                raise Exception(f"参考图无法下载或转换: {e}") from e

        payload = {
            "model": model_id,
            "input": input_parts,
            "generation_config": {
                "image_config": {"aspect_ratio": size_to_aspect(size)},
            },
        }
        payload.update(self.extra_params)
        for key in _DROP_KEYS:
            payload.pop(key, None)

        response = requests.post(
            self._interactions_url(),
            headers=self._headers(),
            json=payload,
            timeout=180,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Google image generation HTTP error: {detail}") from e

        result = response.json()
        if not isinstance(result, dict):
            raise Exception("Google image generation returned a non-object payload")
        if result.get("error"):
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise Exception(f"Google image generation failed: {msg}")
        status = (result.get("status") or "").lower()
        if status and status not in ("completed", "complete"):
            raise Exception(f"Google image generation status={result.get('status')}")

        image_urls = _collect_images(result)
        if not image_urls:
            raise Exception("No images generated")
        return image_urls

    def list_models(self) -> List[dict]:
        if not self.supports_list_models:
            return []
        try:
            response = requests.get(
                self._models_url(), headers=self._headers(), timeout=30
            )
            response.raise_for_status()
            payload = response.json()
            raw = []
            if isinstance(payload, dict):
                raw = payload.get("models") or payload.get("data") or []
            elif isinstance(payload, list):
                raw = payload
            if not isinstance(raw, list):
                return []
            models = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("id") or item.get("model") or ""
                mid = str(name).split("/")[-1].strip()
                if not mid:
                    continue
                models.append({"id": mid, "owned_by": item.get("owned_by") or "google"})
            return [
                m
                for m in models
                if "image" in m["id"].lower() or "imagen" in m["id"].lower()
            ]
        except Exception as e:
            logger.warning("Google list_models failed for %s: %s", self._root(), e)
            return []
