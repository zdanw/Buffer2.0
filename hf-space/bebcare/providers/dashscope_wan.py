import logging
import re
import time
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)

_COMMON_WAN_MODELS = [
    {"id": "wan2.6-t2i", "owned_by": "dashscope"},
    {"id": "wan2.5-t2i-preview", "owned_by": "dashscope"},
    {"id": "wan2.2-t2i-flash", "owned_by": "dashscope"},
    {"id": "wan2.2-t2i-plus", "owned_by": "dashscope"},
    {"id": "wanx2.1-t2i-turbo", "owned_by": "dashscope"},
    {"id": "wanx2.1-t2i-plus", "owned_by": "dashscope"},
]


def _normalize_api_root(base_url: str) -> str:
    """
    Accepts:
      - https://xxx.maas.aliyuncs.com/compatible-mode/v1
      - https://xxx.maas.aliyuncs.com/api/v1
      - https://dashscope.aliyuncs.com/api/v1
      - host without path
    Returns root ending with /api/v1 (no trailing slash after v1 extras).
    """
    url = (base_url or "").strip().rstrip("/")
    url = re.sub(r"/compatible-mode/v1(?:/.*)?$", "/api/v1", url)
    if url.endswith("/images/generations"):
        url = url[: -len("/images/generations")]
    if "/api/v1" not in url:
        url = f"{url}/api/v1"
    # keep only up to /api/v1
    idx = url.find("/api/v1")
    if idx >= 0:
        url = url[: idx + len("/api/v1")]
    return url.rstrip("/")


def _to_dashscope_size(size: str, model: str) -> str:
    """OpenAI-style 1024x1024 → DashScope 1024*1024; clamp oversized for Wan."""
    raw = (size or "1280*1280").replace("x", "*").replace("X", "*")
    parts = raw.split("*")
    try:
        w, h = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return "1280*1280"

    # Wan 2.6 / 2.5 prefer ~1280; 2048 exceeds typical limits
    max_side = 1440
    if "wan2.2" in model or "wan2.1" in model or "wanx2.0" in model:
        max_side = 1440
        default = 1024
    else:
        default = 1280

    if w > max_side or h > max_side or w * h > 1440 * 1440:
        return f"{default}*{default}"
    return f"{w}*{h}"


def _is_wan26(model: str) -> bool:
    return (model or "").lower().startswith("wan2.6")


class DashScopeWanImageProvider:
    """
    Alibaba Cloud DashScope / Model Studio Wan (万相) native image generation.

    Does NOT use OpenAI /images/generations.
    - wan2.6: sync multimodal-generation (preferred)
    - wan2.5 and below: async text2image/image-synthesis + task poll
    """

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
        self.api_root = _normalize_api_root(base_url)
        self.default_model = default_model or "wan2.6-t2i"
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}
        self.supports_list_models = supports_list_models

    def _headers(self, async_enable: bool = False) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if async_enable:
            headers["X-DashScope-Async"] = "enable"
        headers.update(self.extra_headers)
        return headers

    def _host_compatible_models_url(self) -> Optional[str]:
        # Derive .../compatible-mode/v1/models from api root host
        root = self.api_root
        if "/api/v1" in root:
            return root.replace("/api/v1", "/compatible-mode/v1") + "/models"
        return None

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        reference_images: Optional[List[str]] = None,
        size: str = "1280x1280",
        model: Optional[str] = None,
    ) -> List[str]:
        model_id = model or self.default_model
        if not model_id:
            raise ValueError("image model is required")
        if reference_images:
            logger.info(
                "DashScope Wan text-to-image ignores reference_images (%s urls)",
                len(reference_images),
            )

        ds_size = _to_dashscope_size(size, model_id)
        if _is_wan26(model_id):
            return self._generate_wan26_sync(prompt, negative_prompt, ds_size, model_id)
        return self._generate_legacy_async(prompt, negative_prompt, ds_size, model_id)

    def _generate_wan26_sync(
        self, prompt: str, negative_prompt: str, size: str, model: str
    ) -> List[str]:
        url = f"{self.api_root}/services/aigc/multimodal-generation/generation"
        body = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": {
                "prompt_extend": True,
                "watermark": False,
                "n": 1,
                "negative_prompt": negative_prompt or "",
                "size": size,
            },
        }
        if isinstance(self.extra_params.get("parameters"), dict):
            body["parameters"].update(self.extra_params["parameters"])

        response = requests.post(url, headers=self._headers(False), json=body, timeout=180)
        if response.status_code >= 400:
            detail = response.text[:800]
            raise Exception(f"DashScope wan2.6 sync HTTP {response.status_code}: {detail}")

        result = response.json()
        if result.get("code"):
            raise Exception(
                f"DashScope error {result.get('code')}: {result.get('message', result)}"
            )

        urls = self._extract_urls_from_output(result.get("output") or {})
        if not urls:
            raise Exception(f"DashScope returned no image URL: {str(result)[:500]}")
        return urls

    def _generate_legacy_async(
        self, prompt: str, negative_prompt: str, size: str, model: str
    ) -> List[str]:
        url = f"{self.api_root}/services/aigc/text2image/image-synthesis"
        body = {
            "model": model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": size,
                "n": 1,
                "prompt_extend": True,
                "watermark": False,
            },
        }
        if negative_prompt:
            body["input"]["negative_prompt"] = negative_prompt
        body["parameters"].update(self.extra_params.get("parameters", {}))

        response = requests.post(
            url, headers=self._headers(async_enable=True), json=body, timeout=60
        )
        if response.status_code >= 400:
            detail = response.text[:800]
            raise Exception(f"DashScope async submit HTTP {response.status_code}: {detail}")

        result = response.json()
        if result.get("code"):
            raise Exception(
                f"DashScope submit error {result.get('code')}: {result.get('message', result)}"
            )

        task_id = (result.get("output") or {}).get("task_id")
        if not task_id:
            raise Exception(f"DashScope submit missing task_id: {str(result)[:500]}")

        return self._poll_task(task_id)

    def _poll_task(self, task_id: str, timeout_sec: float = 180.0, interval: float = 3.0) -> List[str]:
        url = f"{self.api_root}/tasks/{task_id}"
        deadline = time.time() + timeout_sec
        last_status = "UNKNOWN"

        while time.time() < deadline:
            time.sleep(interval)
            response = requests.get(url, headers=self._headers(False), timeout=30)
            if response.status_code >= 400:
                raise Exception(
                    f"DashScope poll HTTP {response.status_code}: {response.text[:500]}"
                )
            payload = response.json()
            output = payload.get("output") or {}
            last_status = output.get("task_status") or last_status

            if last_status == "SUCCEEDED":
                urls = self._extract_urls_from_output(output)
                if not urls:
                    raise Exception(f"Task succeeded but no image URL: {str(output)[:500]}")
                return urls
            if last_status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise Exception(
                    f"DashScope task {last_status}: {output.get('message') or str(output)[:500]}"
                )
            # PENDING / RUNNING

        raise Exception(f"DashScope task timeout after {timeout_sec}s (last_status={last_status})")

    def _extract_urls_from_output(self, output: dict) -> List[str]:
        urls: List[str] = []
        # wan2.6 style: choices[].message.content[].image
        for choice in output.get("choices") or []:
            message = choice.get("message") or {}
            for item in message.get("content") or []:
                if isinstance(item, dict) and item.get("image"):
                    urls.append(item["image"])
        # legacy: results[].url
        for item in output.get("results") or []:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
        return urls

    def list_models(self) -> List[dict]:
        if not self.supports_list_models:
            return list(_COMMON_WAN_MODELS)

        models_url = self._host_compatible_models_url()
        fetched: List[dict] = []
        if models_url:
            try:
                response = requests.get(
                    models_url, headers=self._headers(False), timeout=30
                )
                response.raise_for_status()
                payload = response.json()
                raw = payload.get("data") if isinstance(payload, dict) else payload
                if isinstance(raw, list):
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        mid = item.get("id") or item.get("model")
                        if not mid:
                            continue
                        low = mid.lower()
                        if any(k in low for k in ("wan", "wanx", "t2i", "image", "flux")):
                            fetched.append({"id": mid, "owned_by": item.get("owned_by") or "dashscope"})
            except Exception as e:
                logger.warning("DashScope list_models via compatible-mode failed: %s", e)

        if fetched:
            # merge with common ids (dedupe)
            seen = {m["id"] for m in fetched}
            for m in _COMMON_WAN_MODELS:
                if m["id"] not in seen:
                    fetched.append(m)
            return fetched
        return list(_COMMON_WAN_MODELS)
