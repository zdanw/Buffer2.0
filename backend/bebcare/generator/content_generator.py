import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from bebcare.config.settings import settings
from bebcare.prompt_builder.prompt_engine import prompt_engine
from bebcare.utils.image_utils import persist_image_url_to_cdn
from bebcare.services.logo_policy import (
    resolve_effective_logo_mode,
    should_composite_logo,
    build_vision_logo_instruction,
)

logger = logging.getLogger(__name__)

_MAX_VISION_REF_IMAGES = 3
_RECENT_IMAGE_PROMPT_LIMIT = 3


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
        self.deepseek_model = settings.deepseek_model
        self.doubao_api_key = settings.doubao_api_key
        self.doubao_api_url = settings.doubao_api_url
        self.doubao_model_id = settings.doubao_model_id

        self.vision_api_key = (settings.vision_api_key or settings.deepseek_api_key or "").strip()
        self.vision_api_url = deepseek_chat_completions_url(
            settings.vision_api_url or settings.deepseek_api_url
        )
        self.vision_model = (settings.vision_model or "qwen-vl-max").strip()

        self.image_prompt_system_prompt = """
你是一位专业的AI图像提示词工程师。
你的任务是将产品信息和维度选项转换为详细、生动、富有感染力的中文图像描述，让AI图像生成器能够完美理解并生成高质量图片。

遵循以下指南：
1. 仅输出图像提示词，不要额外文本或解释
2. 使用丰富细腻的描述性语言，包含大量感官细节和具体形容词
3. 将场景、光线、构图、风格、画质、细节道具等元素自然融合，形成连贯的叙事
4. 注重光影层次：描述光线的方向、质感、色温，以及光影如何塑造产品形态和氛围
5. 强调材质表现：描述产品的材质质感，以及材质之间的对比
6. 营造符合产品定位的情感氛围
7. 采用生活方式叙事：描述产品在真实生活场景中的使用状态
8. 确保适合商业产品摄影，同时具备艺术感染力
9. 描述要有层次感：从前景到背景，从主体到细节，逐步展开
10. 使用精确的色彩描述，避免笼统的颜色词
"""

        self.vision_image_prompt_system_prompt = """
你是一位专业的AI图像提示词工程师，专注于商业产品摄影。
你将仅根据用户提供的参考图，自主撰写一段最终中文图像提示词，供下游图像生成模型使用。

遵循以下指南：
1. 仅输出一段最终中文图像提示词，不要额外说明、标题或列表前缀
2. 先仔细观察参考图中的产品外形、颜色、材质、比例、部件与印刷标识
3. 产品外观必须以参考图为准，禁止改色、变形、缺失或编造参考图中不存在的部件
4. 可自主设计合理的场景、光线、构图与生活方式氛围，但不得覆盖产品保真要求
5. 使用丰富细腻的描述性语言，包含光影、材质与情感氛围
6. 画面中禁止生成文字、水印、二维码、网址、字幕或额外品牌名（产品自带印刷除外）
7. 适合高端商业产品摄影，画面干净、有代入感
"""

        self.vision_scene_image_prompt_system_prompt = """
你是一位专业的AI图像提示词工程师，专注于商业产品「场景融合」摄影。
用户会分别提供场景参考图与产品参考图。你仅根据这些图片，自主撰写一段最终中文图像提示词，供下游图生图模型把产品融入场景。

遵循以下指南：
1. 仅输出一段最终中文图像提示词，不要额外说明、标题或列表前缀
2. 产品外形、颜色、材质、比例、角度与印刷标识必须以产品参考图为准，禁止改色、变形或编造部件
3. 场景构图、空间布局、整体色调与光线方向应尽量沿用场景参考图，可做轻度氛围优化
4. 明确描述：将产品自然放入场景中的位置关系、尺度与融合方式；若场景中有其他产品，用本次产品替换
5. 道具不得遮挡或改变产品主体；禁止文字、水印、二维码、网址或额外品牌名
6. 适合商业生活方式摄影，画面干净、有代入感
"""

    def _copy_system_prompt(self, product_info: Dict) -> str:
        return (product_info.get("copy_system_prompt") or "").strip() or prompt_engine.system_prompt

    def _image_system_prompt(self, product_info: Dict) -> str:
        return (product_info.get("image_system_prompt") or "").strip() or self.image_prompt_system_prompt

    def _vision_image_system_prompt(self, product_info: Dict) -> str:
        return (
            (product_info.get("vision_image_system_prompt") or "").strip()
            or self.vision_image_prompt_system_prompt
        )

    def _vision_scene_system_prompt(self, product_info: Dict) -> str:
        return (
            (product_info.get("vision_scene_system_prompt") or "").strip()
            or self.vision_scene_image_prompt_system_prompt
        )

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
                "model": self.deepseek_model,
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

    @staticmethod
    def _ref_urls_to_data_urls(
        reference_images: List[str], max_images: int = _MAX_VISION_REF_IMAGES
    ) -> List[str]:
        from bebcare.providers.aliyun_maas import _image_url_to_data_url

        out = []
        for url in reference_images:
            if not url:
                continue
            out.append(_image_url_to_data_url(url))
            if len(out) >= max_images:
                break
        return out

    @staticmethod
    def _format_recent_prompt_avoidance(recent_prompts: List[str]) -> str:
        lines = [p.strip() for p in (recent_prompts or []) if p and str(p).strip()]
        if not lines:
            return ""
        numbered = "\n".join(f"{i}. {p}" for i, p in enumerate(lines, 1))
        return (
            "\n\n以下是该产品最近已使用的图像提示词。本次必须在场景空间、光线方向/色温、"
            "构图景别、主要道具上明显不同；禁止复用相同空间或光影套路。"
            "产品外观仍以参考图为准，禁止改色、变形。\n"
            f"{numbered}"
        )

    def _fetch_recent_image_prompts(
        self,
        product_id: str,
        db=None,
        limit: int = _RECENT_IMAGE_PROMPT_LIMIT,
        extra_prompts: Optional[List[str]] = None,
    ) -> List[str]:
        """Newest-first recent image prompts for a product (in-batch + DB)."""
        product_id = (product_id or "").strip()
        out: List[str] = []
        seen = set()

        def _add(text: str) -> bool:
            text = (text or "").strip()
            if not text or text in seen:
                return False
            seen.add(text)
            out.append(text)
            return len(out) >= limit

        for p in reversed(list(extra_prompts or [])):
            if _add(p):
                return out

        if not product_id:
            return out

        from bebcare.models.task import ManualTaskDraft, TaskExecution

        session, own = self._db_session(db)
        try:
            rows = []
            drafts = (
                session.query(ManualTaskDraft)
                .filter(
                    ManualTaskDraft.product_id == product_id,
                    ManualTaskDraft.image_prompts.isnot(None),
                )
                .order_by(ManualTaskDraft.created_at.desc())
                .limit(20)
                .all()
            )
            for draft in drafts:
                for idx, prompt in enumerate(draft.image_prompts or []):
                    if prompt and str(prompt).strip():
                        rows.append((draft.created_at, idx, str(prompt).strip()))

            executions = (
                session.query(TaskExecution)
                .filter(
                    TaskExecution.product_id == product_id,
                    TaskExecution.status == "SUCCESS",
                    TaskExecution.image_prompt.isnot(None),
                )
                .order_by(TaskExecution.created_at.desc())
                .limit(limit * 3)
                .all()
            )
            for ex in executions:
                if ex.image_prompt and str(ex.image_prompt).strip():
                    rows.append((ex.created_at, 0, str(ex.image_prompt).strip()))

            rows.sort(
                key=lambda r: (r[0] or datetime.min, r[1]),
                reverse=True,
            )
            for _, _, prompt in rows:
                if _add(prompt):
                    break
        except Exception:
            logger.exception(
                "Failed to fetch recent image prompts for product_id=%s", product_id
            )
        finally:
            if own:
                session.close()

        return out

    def _build_vision_user_content(
        self,
        product_info: Dict,
        reference_images: List[str],
        recent_prompts: Optional[List[str]] = None,
    ) -> tuple[List[dict], str]:
        """Build multimodal user content. Scene mode labels scene vs product images."""
        product_name = (product_info.get("product_name") or "产品").strip()
        use_scene = bool(product_info.get("use_scene_reference", False))
        scene_urls = [u for u in (product_info.get("reference_scene_images") or []) if u]
        product_urls = [u for u in (product_info.get("reference_product_images") or []) if u]
        avoid_text = self._format_recent_prompt_avoidance(recent_prompts or [])
        logo_instruction = build_vision_logo_instruction(product_info)
        logo_suffix = f" {logo_instruction}" if logo_instruction else ""

        # 调度等路径可能未拆分；回退到扁平参考图列表
        if use_scene and not scene_urls and reference_images:
            scene_urls = [reference_images[0]]
            product_urls = product_urls or [u for u in reference_images[1:] if u]
        if not product_urls and reference_images:
            product_urls = [u for u in reference_images if u]

        user_content: List[dict] = []
        system_prompt = self._vision_image_system_prompt(product_info)

        if use_scene and scene_urls and product_urls:
            system_prompt = self._vision_scene_system_prompt(product_info)
            # 1 张场景 + 最多 2 张产品，总计不超过上限
            scene_data = self._ref_urls_to_data_urls(scene_urls, 1)
            remain = max(1, _MAX_VISION_REF_IMAGES - len(scene_data))
            product_data = self._ref_urls_to_data_urls(product_urls, remain)
            user_content.append({"type": "text", "text": "【场景参考图】"})
            for u in scene_data:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
            user_content.append({"type": "text", "text": "【产品参考图】"})
            for u in product_data:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        f"请仅根据以上场景参考图与产品参考图，为「{product_name}」自主生成一段"
                        "最终中文图像提示词：把产品自然融入场景，产品外观以产品图为准，"
                        "场景结构与光线尽量沿用场景图。不要使用任何外部维度或模板文案。"
                        f"{avoid_text}{logo_suffix}"
                    ),
                }
            )
        else:
            data_urls = self._ref_urls_to_data_urls(
                product_urls or reference_images or [], _MAX_VISION_REF_IMAGES
            )
            for u in data_urls:
                user_content.append({"type": "image_url", "image_url": {"url": u}})
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        f"请仅根据以上参考图，为「{product_name}」自主生成一段最终中文图像提示词。"
                        "外观以参考图为准；场景与光线由你自主决定。"
                        f"{avoid_text}{logo_suffix}"
                    ),
                }
            )

        return user_content, system_prompt

    async def _call_vision_image_prompt_async(
        self,
        product_info: Dict,
        reference_images: List[str],
        max_tokens: int = 1024,
        recent_prompts: Optional[List[str]] = None,
    ) -> str:
        """Multimodal: read reference images only → autonomously write final Chinese image prompt.

        Scene mode: scene + product images labeled separately (still no meta-prompt).
        """
        if not self.vision_api_key:
            raise ValueError("VISION_API_KEY / DEEPSEEK_API_KEY is required for vision image prompt")

        user_content, system_prompt = await asyncio.to_thread(
            self._build_vision_user_content,
            product_info,
            reference_images or [],
            recent_prompts or [],
        )
        has_image = any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in user_content
        )
        if not has_image:
            raise ValueError("vision image prompt requires at least one readable reference image")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.vision_api_key}",
        }

        async def request_once(token_limit: int):
            data = {
                "model": self.vision_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.7,
                "max_tokens": token_limit,
            }
            # DeepSeek V4 only; Qwen-VL 等视觉模型不传 thinking
            if "deepseek" in (self.vision_model or "").lower():
                data["thinking"] = {"type": "disabled"}
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.vision_api_url, headers=headers, json=data)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.error(
                    "Vision API %s: %s",
                    response.status_code,
                    (response.text or "")[:2000],
                )
                raise
            choice = response.json()["choices"][0]
            content = (choice["message"].get("content") or "").strip()
            return content, choice.get("finish_reason")

        async def make_request():
            content, finish_reason = await request_once(max_tokens)
            retry_limit = max_tokens
            if finish_reason == "length":
                retry_limit = min(max(max_tokens * 2, 1024), 4096)
                if retry_limit > max_tokens:
                    content, finish_reason = await request_once(retry_limit)
            if finish_reason == "length":
                raise Exception(f"Vision output truncated after max_tokens={retry_limit}")
            if not content:
                raise Exception("Vision model returned empty image prompt")
            return content

        return await self._retry_request_async(make_request, max_retries=3, initial_delay=2.0)

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
        return await self._call_deepseek_async(
            prompt, self._copy_system_prompt(product_info), 500
        )

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
        image_size: Optional[str] = None,
    ) -> Dict:
        from bebcare.providers.registry import (
            resolve_image_provider,
            resolve_system_image_provider,
        )
        from bebcare.providers.size_catalog import resolve_size

        use_scene_reference = product_info.get("use_scene_reference", False)
        use_vision = bool(product_info.get("use_vision_image_prompt", False))
        refs = [u for u in (reference_images or []) if u]

        selected_dimensions = None
        image_prompt = None
        positive_prompt = None
        meta_prompt = None

        if use_vision and refs:
            try:
                recent_prompts = await asyncio.to_thread(
                    self._fetch_recent_image_prompts,
                    str(product_info.get("product_id") or ""),
                    db,
                    _RECENT_IMAGE_PROMPT_LIMIT,
                    product_info.get("avoid_image_prompts") or [],
                )
                positive_prompt = await self._call_vision_image_prompt_async(
                    product_info, refs, 1024, recent_prompts
                )
                image_prompt = positive_prompt
                dim_label = (
                    "视觉模型自主(场景融合)"
                    if use_scene_reference
                    else "视觉模型自主"
                )
                selected_dimensions = {
                    "scene": "参考场景图+视觉模型" if use_scene_reference else dim_label,
                    "viewpoint": dim_label,
                    "composition": dim_label,
                    "style": dim_label,
                    "quality": dim_label,
                    "details": dim_label,
                    "lighting": dim_label,
                }
                logger.info(
                    "Image prompt built via vision model=%s refs=%s scene=%s "
                    "recent_avoid=%s (no meta-prompt)",
                    self.vision_model,
                    min(len(refs), _MAX_VISION_REF_IMAGES),
                    bool(use_scene_reference),
                    len(recent_prompts),
                )
            except Exception as e:
                logger.exception(
                    "Vision image prompt failed, falling back to text path: %s", e
                )
                use_vision = False
        elif use_vision and not refs:
            logger.warning(
                "use_vision_image_prompt=True but no reference images; falling back to text path"
            )
            use_vision = False

        if not use_vision:
            # 旧方案：PromptEngine meta-prompt → DeepSeek / 场景模板
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
                    meta_prompt = scene_prompt_result["prompt"]
                    positive_prompt = meta_prompt
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
                    positive_prompt = await self._call_deepseek_async(
                        meta_prompt, self._image_system_prompt(product_info), 1024
                    )
                    image_prompt = positive_prompt
            finally:
                if own:
                    session.close()

        negative_prompt = prompt_engine.build_negative_prompt()

        provider_id = image_provider_id or product_info.get("image_provider_id")
        model_id = image_model or product_info.get("image_model")
        size = resolve_size(image_size or product_info.get("image_size"))
        session, own = self._db_session(db)
        try:
            owner_user_id = product_info.get("owner_user_id")
            if not owner_user_id:
                from bebcare.models import Product

                product_row = (
                    session.query(Product)
                    .filter(Product.product_id == str(product_info.get("product_id") or ""))
                    .first()
                )
                owner_user_id = product_row.owner_user_id if product_row else None
            mode = product_info.get("image_provider_mode") or "byok"
            if mode == "platform":
                provider, resolved_model = resolve_system_image_provider(
                    session, model_id
                )
            else:
                provider, resolved_model = resolve_image_provider(
                    session, provider_id, model_id, owner_user_id=owner_user_id
                )
        finally:
            if own:
                session.close()

        async def make_image_request():
            return await asyncio.to_thread(
                lambda: provider.generate(
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    reference_images=reference_images if reference_images else None,
                    size=size,
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
        effective_logo_mode = resolve_effective_logo_mode(product_info)
        composite_logo_url = (
            (product_info.get("logo_url") or "").strip()
            if should_composite_logo(product_info)
            else None
        )
        if (
            effective_logo_mode == "composite"
            and not composite_logo_url
        ):
            logger.warning(
                "logo_in_images=composite but brand has no logo_url; skipping overlay"
            )
        logger.info(
            "[CDN] persist batch start product_id=%s count=%s logo_mode=%s composite=%s",
            product_id,
            len(image_urls),
            effective_logo_mode,
            bool(composite_logo_url),
        )
        for i, url in enumerate(image_urls):
            file_name = f"{product_id}_{int(time.time())}_{i}.jpg"
            try:
                cdn_urls.append(
                    await asyncio.to_thread(
                        persist_image_url_to_cdn,
                        url,
                        file_name,
                        composite_logo_url,
                    )
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
            "logo_mode": effective_logo_mode,
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
        image_size: Optional[str] = None,
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
                image_size,
            )
        )


content_generator = ContentGenerator()
