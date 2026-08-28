from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import uuid4
from bebcare.database import get_db
from bebcare.models import Product
from bebcare.models.image_provider import ImageProviderConfig
from bebcare.models.user import User
from bebcare.schemas.generate import (
    GenerateRequest,
    GenerateResponse,
    ReferenceSelectionRequest,
    ReferenceSelectionResponse,
)
from bebcare.generator.content_generator import ContentGenerator
from bebcare.utils.reference_selector import resolve_reference_images, select_reference_images
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


def _report_progress(task_id: str, progress: int, stage: str, *, status: str | None = None) -> None:
    kwargs: dict = {"progress": progress, "stage": stage}
    if status is not None:
        kwargs["status"] = status
    update_generate_task(task_id, **kwargs)


def _image_progress_callback(task_id: str, start: int, end: int):
    span = max(end - start, 1)

    def callback(stage: str, fraction: float) -> None:
        clamped = max(0.0, min(1.0, fraction))
        progress = start + int(span * clamped)
        update_generate_task(task_id, progress=progress, stage=stage)

    return callback


def _build_product_info(product, request: GenerateRequest, db: Session) -> dict:
    try:
        selected = resolve_reference_images(
            db,
            request.product_id,
            request.reference_count,
            request.use_scene_reference,
            pinned_product_images=request.reference_product_images,
            pinned_scene_images=request.reference_scene_images,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        "realistic_placement": bool(request.realistic_placement),
        "image_provider_id": request.image_provider_id,
        "image_model": request.image_model,
        "image_size": request.image_size,
        "image_provider_mode": request.image_provider_mode,
        "owner_user_id": product.owner_user_id,
        "locale": request.locale or "en",
        "image_prompt_pipeline": request.image_prompt_pipeline,
    }
    return enrich_product_info(db, product, base)


@router.post("/reference-selection/", response_model=ReferenceSelectionResponse)
def resolve_reference_selection(
    request: ReferenceSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_owned_or_404(
        db, Product, request.product_id, current_user, id_attr="product_id"
    )
    selected = select_reference_images(
        db,
        request.product_id,
        request.reference_count,
        request.use_scene_reference,
    )
    return ReferenceSelectionResponse(**selected)


def _owned_generate_product(
    db: Session, request: GenerateRequest, current_user: User, *, mode: str | None = None
) -> Product:
    product = get_owned_or_404(
        db, Product, request.product_id, current_user, id_attr="product_id"
    )
    if mode != "platform":
        assert_owned_ref(
            db, ImageProviderConfig, request.image_provider_id, current_user, id_attr="id"
        )
    return product


def _resolve_provider_mode(
    db: Session, request: GenerateRequest, current_user: User
) -> str:
    if request.image_provider_mode in ("platform", "byok"):
        return request.image_provider_mode

    from bebcare.services.ownership import owned_query
    from bebcare.services.credit_grant_service import remaining_credits

    has_byok = (
        owned_query(db, ImageProviderConfig, current_user)
        .filter(ImageProviderConfig.is_active == True)  # noqa: E712
        .filter(ImageProviderConfig.is_system == False)  # noqa: E712
        .first()
        is not None
    )
    if has_byok:
        return "byok"
    if remaining_credits(db, current_user.user_id) > 0:
        return "platform"
    raise HTTPException(
        status_code=400,
        detail="未配置图像供应商，且平台出图额度已用尽。请添加自己的 API Key 或联系管理员发放次数。",
    )


def _require_image_provider(
    db: Session, request: GenerateRequest, current_user: User, mode: str
) -> None:
    from bebcare.providers.registry import (
        resolve_image_provider,
        resolve_system_image_provider,
        SYSTEM_PROVIDER_UNAVAILABLE_MSG,
    )
    from bebcare.services.credit_grant_service import remaining_credits

    try:
        if mode == "platform":
            if remaining_credits(db, current_user.user_id) < 1:
                raise HTTPException(
                    status_code=402,
                    detail="平台出图额度不足。请联系管理员发放次数，或配置自己的图像供应商。",
                )
            resolve_system_image_provider(db, request.image_model)
        else:
            resolve_image_provider(
                db,
                request.image_provider_id,
                request.image_model,
                owner_user_id=current_user.user_id,
            )
    except HTTPException:
        raise
    except ValueError as exc:
        msg = str(exc)
        if msg == SYSTEM_PROVIDER_UNAVAILABLE_MSG or "平台图像供应商" in msg:
            raise HTTPException(status_code=503, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc


def _create_task_and_maybe_reserve(
    db: Session, *, task_id: str, user_id: str, mode: str
) -> None:
    from bebcare.services.credit_grant_service import CreditError, reserve_one

    create_generate_task(task_id, status="PENDING", owner_user_id=user_id)
    if mode != "platform":
        return
    try:
        reserve_one(db, user_id=user_id, generate_task_id=task_id)
        db.commit()
    except CreditError as exc:
        update_generate_task(
            task_id,
            status="FAILURE",
            set_result=True,
            result={"error": str(exc)},
        )
        raise HTTPException(
            status_code=402,
            detail="平台出图额度不足。请联系管理员发放次数，或配置自己的图像供应商。",
        ) from exc


@router.post("/", response_model=GenerateResponse)
def generate_content(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    mode = _resolve_provider_mode(db, request, current_user)
    product = _owned_generate_product(db, request, current_user, mode=mode)
    _require_image_provider(db, request, current_user, mode)

    product_info = _build_product_info(product, request, db)
    product_info["image_provider_mode"] = mode

    task_id = str(uuid4())
    _create_task_and_maybe_reserve(
        db, task_id=task_id, user_id=current_user.user_id, mode=mode
    )

    async def run_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting generation task", task_id)
            await asyncio.to_thread(
                _report_progress, task_id, 5, "queued", status="PROGRESS"
            )

            platform = product_info.get("platform", "instagram")
            reference_images = product_info.get("reference_images", [])

            generator = ContentGenerator()
            style_hint = product_info.get("style_hint", None)

            copywriting_text = await generator.generate_copywriting_async(
                product_info,
                platform,
                progress_callback=_image_progress_callback(task_id, 15, 45),
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
                progress_callback=_image_progress_callback(task_id, 45, 95),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                progress=100,
                stage="done",
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
                    "logo_mode": image_result.get("logo_mode"),
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
    product = _owned_generate_product(db, request, current_user, mode="byok")

    base = {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points,
        "brand_voice": product.brand_voice,
        "platform": request.platform,
        "style_hint": request.style_hint,
        "locale": request.locale or "en",
    }
    product_info = enrich_product_info(db, product, base)

    task_id = str(uuid4())
    create_generate_task(
        task_id, status="PENDING", owner_user_id=current_user.user_id
    )

    async def run_copywriting_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting copywriting generation", task_id)
            await asyncio.to_thread(
                _report_progress, task_id, 5, "queued", status="PROGRESS"
            )

            generator = ContentGenerator()
            copywriting_text = await generator.generate_copywriting_async(
                product_info,
                product_info.get("platform", "instagram"),
                progress_callback=_image_progress_callback(task_id, 20, 90),
            )

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                progress=100,
                stage="done",
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
    mode = _resolve_provider_mode(db, request, current_user)
    product = _owned_generate_product(db, request, current_user, mode=mode)
    _require_image_provider(db, request, current_user, mode)

    product_info = _build_product_info(product, request, db)
    product_info["image_provider_mode"] = mode

    task_id = str(uuid4())
    _create_task_and_maybe_reserve(
        db, task_id=task_id, user_id=current_user.user_id, mode=mode
    )

    async def run_image_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting image generation", task_id)
            await asyncio.to_thread(
                _report_progress, task_id, 5, "queued", status="PROGRESS"
            )

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
                progress_callback=_image_progress_callback(task_id, 10, 95),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            await asyncio.to_thread(
                update_generate_task,
                task_id,
                status="SUCCESS",
                progress=100,
                stage="done",
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
                    "logo_mode": image_result.get("logo_mode"),
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
        "progress": task.get("progress", 0),
        "stage": task.get("stage"),
        "result": task.get("result"),
    }
