import logging
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)


class DoubaoArkImageProvider:
    """Volcengine Ark images/generations (existing Bebcare Doubao path)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        default_model: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        extra_params: Optional[dict] = None,
        supports_list_models: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}
        self.supports_list_models = supports_list_models

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Ark-Sdk-Version": "v1.0.0",
        }
        headers.update(self.extra_headers)
        return headers

    def _images_url(self) -> str:
        if self.base_url.endswith("/images/generations"):
            return self.base_url
        return f"{self.base_url}/images/generations"

    def _models_url(self) -> str:
        root = self.base_url
        if root.endswith("/images/generations"):
            root = root[: -len("/images/generations")]
        return f"{root}/models"

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

        data = {
            "model": model_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt or "",
            "size": size,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "watermark": False,
        }
        if reference_images:
            data["image"] = reference_images
        data.update(self.extra_params)

        response = requests.post(self._images_url(), headers=self._headers(), json=data, timeout=600)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Doubao image generation HTTP error: {detail}") from e

        result = response.json()
        if result.get("error"):
            msg = result["error"].get("message", "Unknown error")
            if "Timeout while downloading" in msg:
                raise Exception(f"Download timeout: {msg}")
            raise Exception(f"Image generation failed: {msg}")

        image_urls: List[str] = []
        for item in result.get("data") or []:
            if isinstance(item, dict) and item.get("url"):
                image_urls.append(item["url"])
        if not image_urls:
            raise Exception("No images generated")
        return image_urls

    def list_models(self) -> List[dict]:
        if not self.supports_list_models:
            return []
        try:
            response = requests.get(self._models_url(), headers=self._headers(), timeout=30)
            response.raise_for_status()
            payload = response.json()
            raw = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(raw, list):
                return []
            models = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                mid = item.get("id") or item.get("model")
                if mid:
                    models.append({"id": mid, "owned_by": item.get("owned_by")})
            return models
        except Exception as e:
            logger.warning("Doubao list_models failed: %s", e)
            return []
