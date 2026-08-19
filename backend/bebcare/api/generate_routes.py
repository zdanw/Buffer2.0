from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import uuid4
from bebcare.database import get_db
from bebcare.models import Product
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.models.user import User
from bebcare.schemas.generate import GenerateRequest, GenerateResponse
from bebcare.generator.content_generator import ContentGenerator
from bebcare.utils.reference_selector import select_reference_images
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.brand_context import enrich_product_info
from bebcare.services.generate_task_store import (
    create_generate_task,
    get_generate_task,
    update_generate_task,
)
from bebcare.services.ownership import assert_owned_ref, get_owned_or_404
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])


def _build_product_info(product, request: GenerateRequest, db: Session) -> dict:
    selected = select_reference_images(
        db,
        request.product_id,
        request.reference_count,
        request.use_scene_reference,
    )
    if request.use_scene_reference and not selected["use_scene_reference"]:
        logger.warning(
            "No scene images for product %s, falling back to regular mode",
            request.product_id,
        )
    if request.use_scene_reference and not selected["reference_product_images"]:
        logger.warning("No product images for product %s", request.product_id)
    if (
        not request.use_scene_reference
        and len(selected["reference_images"]) < request.reference_count
    ):
        logger.warning(
            "Only %s images for product %s, requested %s",
            len(selected["reference_images"]),
            request.product_id,
            request.reference_count,
        )

    base = {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points,
        "brand_voice": product.brand_voice,
        "reference_images": selected["reference_images"],
        "reference_product_images": selected["reference_product_images"],
        "reference_scene_images": selected["reference_scene_images"],
        "platform": request.platform,
        "style_hint": request.style_hint,
        "use_scene_reference": selected["use_scene_reference"],
        "use_vision_image_prompt": bool(request.use_vision_image_prompt),
        "image_provider_id": request.image_provider_id,
        "image_model": request.image_model,
        "image_size": request.image_size,
    }
    return enrich_product_info(db, product, base)


def _owned_generate_product(
    db: Session, request: GenerateRequest, current_user: User
) -> Product:
    product = get_owned_or_404(
        db, Product, request.product_id, current_user, id_attr="product_id"
    )
    assert_owned_ref(
        db, ImageProviderConfig, request.image_provider_id, current_user, id_attr="id"
    )
    return product


@router.post("/", response_model=GenerateResponse)
def generate_content(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = _owned_generate_product(db, request, current_user)

    product_info = _build_product_info(product, request, db)

    task_id = str(uuid4())
    create_generate_task(
        task_id, status="PENDING", owner_user_id=current_user.user_id
    )

    async def run_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting generation task", task_id)
            await asyncio.to_thread(update_generate_task, task_id, status="PROGRESS")

            platform = product_info.get("platform", "instagram")
            reference_images = product_info.get("reference_images", [])

            generator = ContentGenerator()
            style_hint = product_info.get("style_hint", None)

            copywriting_text = await generator.generate_copywriting_async(
                product_info, platform
            )

            image_result = await generator.generate_image_async(
                product_info,
                platform,
                reference_images,
                style_hint,
                1,
                image_provider_id=product_info.get("image_provider_id"),
                image_model=product_info.get("image_model"),
                image_size=product_info.get("image_size"),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                set_result=True,
                result={
                    "text": copywriting_text,
                    "image": image_urls[0],
                    "dimensions": image_result.get("dimensions", None),
                    "image_prompt": image_result.get("image_prompt", None),
                    "reference_product_images": product_info.get(
                        "reference_product_images", []
                    ),
                    "reference_scene_images": product_info.get(
                        "reference_scene_images", []
                    ),
                    "warning": image_result.get("warning"),
                },
            )
            warning = image_result.get("warning")
            if warning:
                logger.error(
                    "[%s] [CDN] Generation completed with CDN warning: %s "
                    "(images=%s first_url=%s)",
                    task_id,
                    warning,
                    len(image_urls),
                    (image_urls[0][:160] if image_urls else None),
                )
            else:
                logger.info(
                    "[%s] Generation completed: %s images", task_id, len(image_urls)
                )
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="FAILURE",
                set_result=True,
                result={"error": str(e)},
            )

    background_tasks.add_task(run_generation, task_id, product_info)
    return {"task_id": task_id, "status": "queued"}


@router.post("/copywriting/", response_model=GenerateResponse)
def generate_copywriting_only(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = _owned_generate_product(db, request, current_user)

    base = {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points,
        "brand_voice": product.brand_voice,
        "platform": request.platform,
        "style_hint": request.style_hint,
    }
    product_info = enrich_product_info(db, product, base)

    task_id = str(uuid4())
    create_generate_task(
        task_id, status="PENDING", owner_user_id=current_user.user_id
    )

    async def run_copywriting_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting copywriting generation", task_id)
            await asyncio.to_thread(update_generate_task, task_id, status="PROGRESS")

            generator = ContentGenerator()
            copywriting_text = await generator.generate_copywriting_async(
                product_info, product_info.get("platform", "instagram")
            )

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                set_result=True,
                result={
                    "text": copywriting_text,
                    "image": None,
                },
            )
            logger.info("[%s] Copywriting completed", task_id)
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="FAILURE",
                set_result=True,
                result={"error": str(e)},
            )

    background_tasks.add_task(run_copywriting_generation, task_id, product_info)
    return {"task_id": task_id, "status": "queued"}


@router.post("/image/", response_model=GenerateResponse)
def generate_image_only(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = _owned_generate_product(db, request, current_user)

    product_info = _build_product_info(product, request, db)

    task_id = str(uuid4())
    create_generate_task(
        task_id, status="PENDING", owner_user_id=current_user.user_id
    )

    async def run_image_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting image generation", task_id)
            await asyncio.to_thread(update_generate_task, task_id, status="PROGRESS")

            platform = product_info.get("platform", "instagram")
            reference_images = product_info.get("reference_images", [])

            generator = ContentGenerator()
            style_hint = product_info.get("style_hint", None)

            image_result = await generator.generate_image_async(
                product_info,
                platform,
                reference_images,
                style_hint,
                1,
                image_provider_id=product_info.get("image_provider_id"),
                image_model=product_info.get("image_model"),
                image_size=product_info.get("image_size"),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                set_result=True,
                result={
                    "text": None,
                    "image": image_urls[0],
                    "dimensions": image_result.get("dimensions", None),
                    "image_prompt": image_result.get("image_prompt", None),
                    "reference_product_images": product_info.get(
                        "reference_product_images", []
                    ),
                    "reference_scene_images": product_info.get(
                        "reference_scene_images", []
                    ),
                    "warning": image_result.get("warning"),
                },
            )
            warning = image_result.get("warning")
            if warning:
                logger.error(
                    "[%s] [CDN] Image generation completed with CDN warning: %s "
                    "(images=%s first_url=%s)",
                    task_id,
                    warning,
                    len(image_urls),
                    (image_urls[0][:160] if image_urls else None),
                )
            else:
                logger.info(
                    "[%s] Image generation completed: %s images",
                    task_id,
                    len(image_urls),
                )
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="FAILURE",
                set_result=True,
                result={"error": str(e)},
            )

    background_tasks.add_task(run_image_generation, task_id, product_info)
    return {"task_id": task_id, "status": "queued"}


@router.get("/status/{task_id}")
def get_generate_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    task = get_generate_task(task_id, owner_user_id=current_user.user_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task.get("result"),
    }
