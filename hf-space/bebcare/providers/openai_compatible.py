import logging
from typing import List, Optional
import requests

from bebcare.providers.image_model_filter import (
    filter_openai_compatible_models,
    is_openrouter_base_url,
    openrouter_models_query,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleImageProvider:
    """OpenAI-style /images/generations + optional GET /models."""

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
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}
        self.supports_list_models = supports_list_models

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
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
        if root.endswith("/v1"):
            return f"{root}/models"
        if root.endswith("/v3"):
            return f"{root}/models"
        return f"{root}/models"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "1024x1024",
        model: Optional[str] = None,
    ) -> List[str]:
        model_id = model or self.default_model
        if not model_id:
            raise ValueError("image model is required")

        data = {
            "model": model_id,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if reference_images:
            # Best-effort: many OpenAI-compatible gateways accept `image` as URL(s)
            data["image"] = reference_images if len(reference_images) > 1 else reference_images[0]
        data.update(self.extra_params)
        # Agnes / LiteLLM rejects response_format for some models (e.g. agnes-t2i-*).
        # Default to URL responses; opt in via extra_params only for non-Agnes gateways.
        mid = (model_id or "").lower()
        host = (self.base_url or "").lower()
        if data.get("response_format") is None or "agnes" in host or mid.startswith("agnes"):
            data.pop("response_format", None)

        response = requests.post(self._images_url(), headers=self._headers(), json=data, timeout=120)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Image generation HTTP error: {detail}") from e

        result = response.json()
        if result.get("error"):
            raise Exception(result["error"].get("message", str(result["error"])))

        image_urls: List[str] = []
        for item in result.get("data") or []:
            if isinstance(item, dict):
                if item.get("url"):
                    image_urls.append(item["url"])
                elif item.get("b64_json"):
                    raise Exception("Provider returned b64_json; URL response_format required")
        if not image_urls:
            raise Exception("No images generated")
        return image_urls

    def verify_credentials(self) -> None:
        """Lightweight auth probe via GET /models. Raises on auth / HTTP failure."""
        response = requests.get(self._models_url(), headers=self._headers(), timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"OpenAI-compatible connection test failed: {detail}") from e

    def list_models(self) -> List[dict]:
        if not self.supports_list_models:
            return []
        try:
            query = openrouter_models_query(self.base_url)
            response = requests.get(
                self._models_url(),
                headers=self._headers(),
                params=query or None,
                timeout=30,
            )
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
                if not mid:
                    continue
                models.append(item)
            return filter_openai_compatible_models(
                models,
                server_prefiltered=is_openrouter_base_url(self.base_url),
            )
        except Exception as e:
            logger.warning("list_models failed for %s: %s", self.base_url, e)
            return []
