import asyncio
import logging
import time
from typing import Dict, List, Optional

import httpx

from bebcare.config.settings import settings
from bebcare.prompt_builder.prompt_engine import prompt_engine
from bebcare.utils.image_utils import persist_image_url_to_cdn

logger = logging.getLogger(__name__)


def deepseek_chat_completions_url(base_url: str) -> str:
    """Accept base (…/v1) or full …/chat/completions; always return the chat endpoint."""
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def _run_sync(coro):
    """Run async API from sync callers (APScheduler threads, tests)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside an event loop — must not nest asyncio.run
    raise RuntimeError(
        "Sync ContentGenerator method called from a running event loop; "
        "use the async_* variant instead"
    )


class ContentGenerator:
    def __init__(self):
        self.deepseek_api_key = settings.deepseek_api_key
        self.deepseek_api_url = deepseek_chat_completions_url(settings.deepseek_api_url)
        self.doubao_api_key = settings.doubao_api_key
        self.doubao_api_url = settings.doubao_api_url
        self.doubao_model_id = settings.doubao_model_id

        self.image_prompt_system_prompt = """
You are a professional AI image prompt engineer for a premium baby-product brand (Bebcare).
Convert the product info and dimension choices into ONE detailed English image prompt for an AI image generator.

Output rules:
1. Output ONLY the final English image prompt — no Chinese, no titles, no explanation
2. Lead with product fidelity: describe the product first, then scene, lighting, composition, style, and details
3. Hard constraints (never violate; weave them into the prompt, do not list them as a checklist):
   - Keep product shape, structure, part count, and relative layout exactly as described (and as in reference images if any)
   - Keep product color, materials, textures, and any on-product print/logo unchanged
   - Do NOT invent extra products, missing/extra parts, warped geometry, or recolored surfaces
   - Do NOT add text, watermarks, QR codes, URLs, captions, or brand names in the scene (on-product print only if specified)
4. Soft quality guidance (only after fidelity is satisfied):
   - Rich sensory detail: light direction, quality, color temperature; material finish (matte, soft-touch, rounded edges)
   - Lifestyle narrative suited to baby products: calm, safe, warm, companion-like mood
   - Commercial product photography with clear foreground-to-background depth
   - Precise color language (e.g. cream knitted cotton, soft pastel accents, warm golden key light)
5. Naturally fuse scene, viewpoint, composition, style, quality, props, and lighting into one coherent paragraph or short continuous prompt
"""

    async def _retry_request_async(
        self, func, max_retries=3, initial_delay=2.0, backoff_factor=2.0
    ):
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

        raise last_exception

    async def _call_deepseek_async(
        self, prompt: str, system_prompt: str = None, max_tokens: int = 300
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}",
        }

        async def request_once(token_limit: int):
            data = {
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": system_prompt or prompt_engine.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": token_limit,
                # 对齐旧 deepseek-chat（非 thinking）；V4 默认开启 thinking
                "thinking": {"type": "disabled"},
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.deepseek_api_url, headers=headers, json=data
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.error(
                    "DeepSeek API %s: %s",
                    response.status_code,
                    (response.text or "")[:2000],
                )
                raise
            choice = response.json()["choices"][0]
            return choice["message"]["content"].strip(), choice.get("finish_reason")

        async def make_request():
            content, finish_reason = await request_once(max_tokens)
            retry_limit = max_tokens
            if finish_reason == "length":
                retry_limit = min(max(max_tokens * 2, 1024), 4096)
                if retry_limit > max_tokens:
                    content, finish_reason = await request_once(retry_limit)
            if finish_reason == "length":
                raise Exception(f"DeepSeek output truncated after max_tokens={retry_limit}")
            return content

        return await self._retry_request_async(make_request, max_retries=3, initial_delay=2.0)

    def _call_deepseek(self, prompt: str, system_prompt: str = None, max_tokens: int = 300) -> str:
        return _run_sync(self._call_deepseek_async(prompt, system_prompt, max_tokens))

    def _db_session(self, db=None):
        """短生命周期 Session：调用方未传入时自建，用完即关。"""
        from bebcare.database import SessionLocal

        if db is not None:
            return db, False
        return SessionLocal(), True

    async def generate_copywriting_async(self, product_info: Dict, platform: str, db=None) -> str:
        session, own = self._db_session(db)
        try:
            prompt = await asyncio.to_thread(
                prompt_engine.build_copywriting_prompt, product_info, platform, session
            )
        finally:
            if own:
                session.close()
        return await self._call_deepseek_async(prompt, prompt_engine.system_prompt, 500)

    def generate_copywriting(self, product_info: Dict, platform: str, db=None) -> str:
        return _run_sync(self.generate_copywriting_async(product_info, platform, db))

    async def generate_image_async(
        self,
        product_info: Dict,
        platform: str,
        reference_images: List[str] = None,
        style_hint: Optional[str] = None,
        num_candidates: int = 1,
        db=None,
        image_provider_id: Optional[str] = None,
        image_model: Optional[str] = None,
    ) -> Dict:
        from bebcare.providers.registry import resolve_image_provider

        use_scene_reference = product_info.get("use_scene_reference", False)

        selected_dimensions = None
        image_prompt = None
        positive_prompt = None
        meta_prompt = None

        # 仅在查维度/拼提示词时占用连接，不跨 DeepSeek / 出图 API
        session, own = self._db_session(db)
        try:
            if use_scene_reference:
                scene_prompt_result = await asyncio.to_thread(
                    prompt_engine.build_scene_reference_prompt,
                    product_info,
                    platform,
                    style_hint,
                    session,
                )
                positive_prompt = scene_prompt_result["prompt"]
                image_prompt = positive_prompt
                selected_dimensions = scene_prompt_result.get("dimensions")
            else:
                image_prompt_result = await asyncio.to_thread(
                    prompt_engine.build_image_prompt,
                    product_info,
                    platform,
                    style_hint,
                    session,
                )
                meta_prompt = image_prompt_result["prompt"]
                selected_dimensions = image_prompt_result.get("dimensions", None)
        finally:
            if own:
                session.close()

        if not use_scene_reference:
            positive_prompt = await self._call_deepseek_async(
                meta_prompt, self.image_prompt_system_prompt, 1024
            )
            image_prompt = positive_prompt

        negative_prompt = prompt_engine.build_negative_prompt()

        provider_id = image_provider_id or product_info.get("image_provider_id")
        model_id = image_model or product_info.get("image_model")
        session, own = self._db_session(db)
        try:
            provider, resolved_model = resolve_image_provider(session, provider_id, model_id)
        finally:
            if own:
                session.close()

        async def make_image_request():
            return await asyncio.to_thread(
                lambda: provider.generate(
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    reference_images=reference_images if reference_images else None,
                    size="2048x2048",
                    model=resolved_model,
                )
            )

        try:
            image_urls = await self._retry_request_async(
                make_image_request, max_retries=3, initial_delay=5.0
            )
        except Exception as e:
            raise Exception(f"Image generation failed after retries: {e}") from e

        if not image_urls:
            raise Exception("No images generated")

        product_id = product_info.get("product_id", "gen")
        cdn_urls = []
        cdn_upload_failed = False
        logger.info(
            "[CDN] persist batch start product_id=%s count=%s",
            product_id,
            len(image_urls),
        )
        for i, url in enumerate(image_urls):
            file_name = f"{product_id}_{int(time.time())}_{i}.jpg"
            try:
                cdn_urls.append(
                    await asyncio.to_thread(persist_image_url_to_cdn, url, file_name)
                )
            except Exception as e:
                cdn_upload_failed = True
                logger.exception(
                    "[CDN] persist batch item failed product_id=%s index=%s "
                    "file_name=%s err=%s; falling back to temporary URL",
                    product_id,
                    i,
                    file_name,
                    e,
                )
                cdn_urls.append(url)

        result = {
            "image_urls": cdn_urls,
            "dimensions": selected_dimensions,
            "image_prompt": image_prompt,
        }
        if cdn_upload_failed:
            logger.error(
                "[CDN] persist batch finished with failures product_id=%s "
                "ok=%s failed=%s",
                product_id,
                sum(1 for u in cdn_urls if "cdn.jsdelivr.net" in str(u)),
                sum(1 for u in cdn_urls if "cdn.jsdelivr.net" not in str(u)),
            )
            result["warning"] = (
                "上传 GitHub CDN 失败，已使用临时图片链接展示；请尽快发布（链接可能过期）"
            )
        else:
            logger.info(
                "[CDN] persist batch ok product_id=%s count=%s",
                product_id,
                len(cdn_urls),
            )
        return result

    def generate_image(
        self,
        product_info: Dict,
        platform: str,
        reference_images: List[str] = None,
        style_hint: Optional[str] = None,
        num_candidates: int = 1,
        db=None,
        image_provider_id: Optional[str] = None,
        image_model: Optional[str] = None,
    ) -> Dict:
        return _run_sync(
            self.generate_image_async(
                product_info,
                platform,
                reference_images,
                style_hint,
                num_candidates,
                db,
                image_provider_id,
                image_model,
            )
        )


content_generator = ContentGenerator()
