"""Agnes AI image generation (OpenAI-shaped /images/generations + LiteLLM extras)."""

import logging
from typing import List, Optional

import requests

from bebcare.providers.generate_request import GenerateImageRequest, resolve_generate_image_request
from bebcare.providers.image_model_filter import filter_image_models

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.agnes-ai.cn/v1"


class AgnesImageProvider:
    """Agnes images/generations: refs go in extra_body.image; no response_format."""

    def __init__(
        self,
        api_key: str,
        base_url: str = _DEFAULT_BASE,
        default_model: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        extra_params: Optional[dict] = None,
        supports_list_models: bool = True,
    ):
        self.api_key = api_key
        self.base_url = (base_url or _DEFAULT_BASE).rstrip("/")
        self.default_model = default_model or "agnes-image-2.1-flash"
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
        return f"{root}/models"

    def generate(
        self,
        prompt: str = "",
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "1024x1024",
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
        model_id = (req.model or self.default_model or "").strip()
        if not model_id:
            raise ValueError("image model is required")

        data: dict = {
            "model": model_id,
            "prompt": (req.prompt_with_role_labels() or "").strip(),
            "size": req.size,
        }
        if req.negative_prompt:
            data["negative_prompt"] = req.negative_prompt

        refs = [u.strip() for u in req.ordered_urls() if (u or "").strip()][:3]
        extra_body: dict = {}
        if refs:
            extra_body["image"] = refs
            logger.info(
                "Agnes image request with %s reference image(s), prompt_len=%s",
                len(refs),
                len(data["prompt"]),
            )

        user_extra = dict(self.extra_params or {})
        user_extra.pop("response_format", None)
        nested = user_extra.pop("extra_body", None)
        if isinstance(nested, dict):
            merged = {**nested, **extra_body}
            # Prefer our refs if both set
            if refs:
                merged["image"] = refs
            extra_body = merged
        data.update(user_extra)
        if extra_body:
            data["extra_body"] = extra_body
        data.pop("response_format", None)

        response = requests.post(
            self._images_url(), headers=self._headers(), json=data, timeout=180
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Agnes image generation HTTP error: {detail}") from e

        result = response.json()
        if isinstance(result, dict) and result.get("error"):
            err = result["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise Exception(msg or "Agnes image generation failed")

        image_urls: List[str] = []
        for item in result.get("data") or []:
            if isinstance(item, dict) and item.get("url"):
                image_urls.append(item["url"])
            elif isinstance(item, dict) and item.get("b64_json"):
                raise Exception("Agnes returned b64_json; URL response expected")
        if not image_urls:
            raise Exception("Agnes image API returned no image URLs")
        return image_urls

    def verify_credentials(self) -> None:
        response = requests.get(self._models_url(), headers=self._headers(), timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Agnes connection test failed: {detail}") from e

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
                if not mid:
                    continue
                models.append(
                    {
                        "id": mid,
                        "owned_by": item.get("owned_by"),
                        "description": item.get("description"),
                    }
                )
            return filter_image_models(models)
        except Exception as e:
            logger.warning("Agnes list_models failed: %s", e)
            return []
