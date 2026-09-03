import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from bebcare.config.settings import settings
from bebcare.generator.content_generator import (
    ContentGenerator,
    agnes_images_generations_url,
    deepseek_chat_completions_url,
)
from bebcare.schemas.dev_vision_chat import (
    VisionChatConfigResponse,
    VisionChatRequest,
    VisionChatResponse,
    VisionImageRequest,
    VisionImageResponse,
)
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.utils.user_errors import user_safe_detail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev/vision-chat", tags=["dev-vision-chat"])

_generator = ContentGenerator()


def _require_dev_playground() -> None:
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Vision chat playground is only available in development")


@router.get("/config", response_model=VisionChatConfigResponse)
async def get_vision_chat_config(
    _user=Depends(get_current_active_user),
):
    _require_dev_playground()
    chat_api_url = deepseek_chat_completions_url(settings.vision_api_url or settings.deepseek_api_url)
    image_api_url = agnes_images_generations_url(
        settings.vision_image_api_url or settings.vision_api_url or settings.deepseek_api_url
    )
    return VisionChatConfigResponse(
        enabled=True,
        chat_model=_generator.vision_model,
        chat_api_url=chat_api_url,
        image_model=_generator.vision_image_model,
        image_api_url=image_api_url,
    )


@router.post("", response_model=VisionChatResponse)
async def vision_chat(
    body: VisionChatRequest,
    _user=Depends(get_current_active_user),
):
    _require_dev_playground()

    if not _generator.vision_api_key:
        raise HTTPException(
            status_code=503,
            detail="VISION_API_KEY / DEEPSEEK_API_KEY is not configured",
        )

    messages: list[dict] = []
    if body.system_prompt and body.system_prompt.strip():
        messages.append({"role": "system", "content": body.system_prompt.strip()})

    for idx, msg in enumerate(body.messages):
        is_last_user = msg.role == "user" and idx == len(body.messages) - 1
        if is_last_user and body.image_urls:
            user_content: list | str = []
            for url in body.image_urls[:3]:
                url = (url or "").strip()
                if not url:
                    continue
                user_content.append({"type": "image_url", "image_url": {"url": url}})
            user_content.append({"type": "text", "text": msg.content})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": msg.role, "content": msg.content})

    try:
        content, finish_reason = await _generator.call_vision_chat_async(
            messages,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except httpx.HTTPStatusError as exc:
        detail = (exc.response.text or "")[:2000]
        logger.error("Vision chat API %s: %s", exc.response.status_code, detail)
        raise HTTPException(status_code=502, detail=detail or "Vision model request failed") from exc
    except Exception as exc:
        logger.exception("Vision chat failed")
        raise HTTPException(
            status_code=502,
            detail=user_safe_detail(exc, fallback="Vision chat request failed"),
        ) from exc

    return VisionChatResponse(
        content=content,
        model=_generator.vision_model,
        finish_reason=finish_reason,
    )


@router.post("/image", response_model=VisionImageResponse)
async def vision_image(
    body: VisionImageRequest,
    _user=Depends(get_current_active_user),
):
    _require_dev_playground()

    if not _generator.vision_api_key:
        raise HTTPException(
            status_code=503,
            detail="VISION_API_KEY / DEEPSEEK_API_KEY is not configured",
        )

    try:
        image_urls = await _generator.call_agnes_image_async(
            body.prompt,
            size=body.size,
            image_urls=body.image_urls,
        )
    except httpx.HTTPStatusError as exc:
        detail = (exc.response.text or "")[:2000]
        logger.error("Agnes image API %s: %s", exc.response.status_code, detail)
        raise HTTPException(status_code=502, detail=detail or "Image generation failed") from exc
    except Exception as exc:
        logger.exception("Agnes image generation failed")
        raise HTTPException(
            status_code=502,
            detail=user_safe_detail(exc, fallback="Vision chat request failed"),
        ) from exc

    return VisionImageResponse(
        model=_generator.vision_image_model,
        image_urls=image_urls,
    )
