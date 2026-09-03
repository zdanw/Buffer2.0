import base64
import logging
from io import BytesIO
from typing import List, Optional
import requests

from bebcare.providers.generate_request import GenerateImageRequest, resolve_generate_image_request
from bebcare.providers.image_model_filter import (
    filter_aliyun_catalog_models,
    filter_image_models,
)

logger = logging.getLogger(__name__)


def _to_aliyun_size(size: str) -> str:
    """Convert 2048x2048 → 2048*2048 (DashScope format)."""
    if not size:
        return "2048*2048"
    return size.replace("x", "*").replace("X", "*")


def _image_url_to_data_url(url: str) -> str:
    """
    将参考图转为 data URL，避免阿里云侧无法拉取私有/外网受限 URL。
    已是 data: 则原样返回。
    """
    if not url:
        raise ValueError("empty reference image url")
    if url.startswith("data:"):
        return url

    from bebcare.utils.image_utils import download_image

    image = download_image(url)
    if image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


class AliyunMaasMultimodalProvider:
    """
    阿里云百炼 / MaaS 图生图（参考图 + prompt）：
    POST .../api/v1/services/aigc/multimodal-generation/generation

    content 结构：
      [{"image": "<url|data-url>"}, ..., {"text": "<prompt>"}]
    """

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
        }
        headers.update(self.extra_headers)
        return headers

    def _generation_url(self) -> str:
        marker = "/services/aigc/multimodal-generation/generation"
        if self.base_url.endswith(marker) or self.base_url.endswith("/generation"):
            return self.base_url
        return f"{self.base_url}/api/v1/services/aigc/multimodal-generation/generation"

    def _models_url(self) -> Optional[str]:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.base_url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}/compatible-mode/v1/models"
        except Exception:
            return None

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

        refs = [u for u in req.ordered_urls() if u]
        if not refs:
            raise ValueError(
                "阿里云图生图需要至少 1 张参考图；请确认产品已上传图片后再生成"
            )

        # 最多 3 张参考图（Qwen-Image I2I 上限）
        refs = refs[:3]
        content: List[dict] = []
        for url in refs:
            try:
                data_url = _image_url_to_data_url(url)
                content.append({"image": data_url})
            except Exception as e:
                logger.warning("Failed to prepare reference image %s: %s", url[:120], e)
                raise Exception(
                    f"参考图无法下载或转换，请检查产品图 URL 是否可访问: {e}"
                ) from e

        # prompt 注入：作为唯一 text 项，与参考图一起提交
        prompt_text = (req.prompt_with_role_labels() or "").strip()
        if not prompt_text:
            raise ValueError("图生图需要非空 prompt")
        content.append({"text": prompt_text})

        # prompt_extend=false：保留系统拼装/DeepSeek 生成的提示词，避免被阿里云改写冲掉
        parameters = {
            "size": _to_aliyun_size(req.size),
            "n": 1,
            "watermark": False,
            "prompt_extend": False,
        }
        if req.negative_prompt:
            parameters["negative_prompt"] = req.negative_prompt[:500]
        parameters.update(self.extra_params)

        payload = {
            "model": model_id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": parameters,
        }

        logger.info(
            "Aliyun I2I generate model=%s refs=%s prompt_len=%s size=%s",
            model_id,
            len(refs),
            len(prompt or ""),
            parameters.get("size"),
        )

        response = requests.post(
            self._generation_url(),
            headers=self._headers(),
            json=payload,
            timeout=600,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:800] if response.text else str(e)
            if "url error" in detail.lower():
                detail = (
                    f"{detail} | 提示：请使用支持图生图的模型 "
                    f"（如 qwen-image-2.0 / qwen-image-edit / wan2.7-image），"
                    f"不要用对话模型；当前 model={model_id}"
                )
            raise Exception(f"Aliyun MaaS HTTP error: {detail}") from e

        result = response.json()
        if result.get("code") and not (result.get("output") or {}).get("choices"):
            raise Exception(
                f"Aliyun MaaS error: {result.get('code')} — {result.get('message') or result}"
            )

        image_urls: List[str] = []
        choices = ((result.get("output") or {}).get("choices")) or []
        for choice in choices:
            message = choice.get("message") or {}
            for item in message.get("content") or []:
                if isinstance(item, dict) and item.get("image"):
                    image_urls.append(item["image"])

        if not image_urls:
            raise Exception(f"No images in Aliyun response: {str(result)[:500]}")
        return image_urls

    def verify_credentials(self) -> None:
        """Lightweight auth probe via GET compatible-mode /models. Raises on failure."""
        url = self._models_url()
        if not url:
            raise Exception("Aliyun connection test failed: cannot derive models URL from base_url")
        response = requests.get(url, headers=self._headers(), timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            detail = response.text[:500] if response.text else str(e)
            raise Exception(f"Aliyun connection test failed: {detail}") from e

    def _dashscope_catalog_url(self) -> str:
        return "https://dashscope.aliyuncs.com/api/v1/models"

    def list_models(self) -> List[dict]:
        if not self.supports_list_models:
            return []
        try:
            response = requests.get(
                self._dashscope_catalog_url(),
                headers=self._headers(),
                params={"capabilities": "IG"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            output = payload.get("output") if isinstance(payload, dict) else {}
            raw = []
            if isinstance(output, dict):
                raw = output.get("models") or []
            if not raw and isinstance(payload, dict):
                raw = payload.get("data") or []
            if not isinstance(raw, list):
                return []
            models = filter_aliyun_catalog_models(raw)
            if models:
                return models
        except Exception as e:
            logger.warning("Aliyun catalog list_models failed: %s", e)

        # Fallback: compatible-mode /models + keyword filter
        url = self._models_url()
        if not url:
            return []
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
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
            return filter_image_models(models)
        except Exception as e:
            logger.warning("Aliyun compatible list_models failed: %s", e)
            return []
