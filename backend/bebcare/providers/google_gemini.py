import base64
import logging
import math
import re
from typing import List, Optional
import requests

from bebcare.providers.generate_request import GenerateImageRequest, resolve_generate_image_request

from bebcare.providers.image_model_filter import filter_gemini_image_models

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


def _collect_text(payload: dict) -> str:
    texts: List[str] = []
    seen: set[str] = set()

    def _add(text: object) -> None:
        value = str(text or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        texts.append(value)

    output = payload.get("output")
    if isinstance(output, str):
        _add(output)
    elif isinstance(output, dict):
        _add(output.get("text"))
        for item in output.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                _add(item.get("text"))
    for step in payload.get("steps") or []:
        if not isinstance(step, dict):
            continue
        _add(step.get("text"))
        for item in step.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                _add(item.get("text"))
    return "\n".join(texts).strip()


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
        prompt: str = "",
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "2048x2048",
        model: Optional[str] = None,
        request: Optional[GenerateImageRequest] = None,
    ) -> List[str]:
        req = resolve_generate_image_request(
            prompt=prompt,
            negative_prompt=negative_prompt,
            reference_images=reference_images,
            size=size,
            model=model,
            request=request,
        )
        model_id = req.model or self.default_model
        if not model_id:
            raise ValueError("image model is required")

        text = (req.prompt_with_role_labels() or "").strip()
        if not text:
            raise ValueError("image prompt is required")
        if (req.negative_prompt or "").strip():
            text = f"{text}\n\nAvoid: {req.negative_prompt.strip()}"

        input_parts: List[dict] = [{"type": "text", "text": text}]
        for url in req.ordered_urls():
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
                "image_config": {"aspect_ratio": size_to_aspect(req.size)},
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

    def complete_multimodal(
        self,
        *,
        model: str,
        input_parts: List[dict],
        timeout: int = 90,
    ) -> dict:
        """Native Interactions API text+image completion. Not OpenAI-compat chat."""
        model_id = (model or "").strip()
        if not model_id:
            raise ValueError("analysis model is required")
        url = self._interactions_url()
        if "/openai" in url or url.rstrip("/").endswith("/chat/completions"):
            raise ValueError("refusing OpenAI-compatible Gemini URL")
        payload = {"model": model_id, "input": input_parts}
        response = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise Exception("Google multimodal returned a non-object payload")
        if result.get("error"):
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise Exception(f"Google multimodal failed: {msg}")
        result["_text"] = _collect_text(result)
        return result

    def generate_content(
        self,
        *,
        model: str,
        body: dict,
        timeout: int = 90,
    ) -> dict:
        """Native models/{id}:generateContent. Not OpenAI-compat chat."""
        model_id = (model or "").strip()
        if not model_id:
            raise ValueError("analysis model is required")
        url = f"{self._root()}/models/{model_id}:generateContent"
        if "/openai" in url or url.rstrip("/").endswith("/chat/completions"):
            raise ValueError("refusing OpenAI-compatible Gemini URL")
        response = requests.post(
            url,
            headers=self._headers(),
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise Exception("Google generateContent returned a non-object payload")
        if result.get("error"):
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise Exception(f"Google generateContent failed: {msg}")
        return result

    def verify_credentials(self) -> None:
        """Lightweight auth probe via GET /models. Raises on auth / HTTP failure."""
        response = requests.get(
            self._models_url(), headers=self._headers(), timeout=30
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Google Gemini connection test failed: {detail}") from e

    def list_raw_models(self) -> List[dict]:
        """Unfiltered GET /models payload items. Non-billable capability listing."""
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
            return [item for item in raw if isinstance(item, dict)]
        except Exception as e:
            logger.warning("Google list_raw_models failed for %s: %s", self._root(), e)
            return []

    def list_models(self) -> List[dict]:
        return filter_gemini_image_models(self.list_raw_models())
