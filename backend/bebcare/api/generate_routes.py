from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import uuid4
from bebcare.database import get_db
from bebcare.models import Product
from bebcare.schemas.generate import GenerateRequest, GenerateResponse
from bebcare.generator.content_generator import ContentGenerator
from bebcare.utils.reference_selector import select_reference_images
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])

generate_tasks = {}


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

    return {
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
        "image_provider_id": request.image_provider_id,
        "image_model": request.image_model,
    }


@router.post("/", response_model=GenerateResponse)
def generate_content(request: GenerateRequest, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    product = db.query(Product).filter(Product.product_id == request.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_info = _build_product_info(product, request, db)

    task_id = str(uuid4())
    generate_tasks[task_id] = {
        "status": "PENDING",
        "result": None,
        "product_info": product_info,
    }

    def run_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting generation task", task_id)
            generate_tasks[task_id]["status"] = "PROGRESS"

            platform = product_info.get("platform", "instagram")
            reference_images = product_info.get("reference_images", [])

            generator = ContentGenerator()
            style_hint = product_info.get("style_hint", None)

            # 不传入请求级 Session；生成器内部短生命周期占用连接
            copywriting_text = generator.generate_copywriting(product_info, platform)
            generate_tasks[task_id]["copywriting"] = copywriting_text

            image_result = generator.generate_image(
                product_info,
                platform,
                reference_images,
                style_hint,
                1,
                image_provider_id=product_info.get("image_provider_id"),
                image_model=product_info.get("image_model"),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            generate_tasks[task_id]["image"] = image_urls
            generate_tasks[task_id]["status"] = "SUCCESS"
            generate_tasks[task_id]["result"] = {
                "text": copywriting_text,
                "image": image_urls[0],
                "dimensions": image_result.get("dimensions", None),
                "image_prompt": image_result.get("image_prompt", None),
                "reference_product_images": product_info.get("reference_product_images", []),
                "reference_scene_images": product_info.get("reference_scene_images", []),
                "warning": image_result.get("warning"),
            }
            logger.info("[%s] Generation completed: %s images", task_id, len(image_urls))
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            generate_tasks[task_id]["status"] = "FAILURE"
            generate_tasks[task_id]["result"] = {"error": str(e)}

    if background_tasks:
        background_tasks.add_task(run_generation, task_id, product_info)
    else:
        run_generation(task_id, product_info)

    return {"task_id": task_id, "status": "queued"}


@router.post("/copywriting/", response_model=GenerateResponse)
def generate_copywriting_only(request: GenerateRequest, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    product = db.query(Product).filter(Product.product_id == request.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_info = {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points,
        "brand_voice": product.brand_voice,
        "platform": request.platform,
        "style_hint": request.style_hint,
    }

    task_id = str(uuid4())
    generate_tasks[task_id] = {
        "status": "PENDING",
        "result": None,
        "product_info": product_info,
    }

    def run_copywriting_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting copywriting generation", task_id)
            generate_tasks[task_id]["status"] = "PROGRESS"

            generator = ContentGenerator()
            copywriting_text = generator.generate_copywriting(
                product_info, product_info.get("platform", "instagram")
            )

            generate_tasks[task_id]["status"] = "SUCCESS"
            generate_tasks[task_id]["result"] = {
                "text": copywriting_text,
                "image": None,
            }
            logger.info("[%s] Copywriting completed", task_id)
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            generate_tasks[task_id]["status"] = "FAILURE"
            generate_tasks[task_id]["result"] = {"error": str(e)}

    if background_tasks:
        background_tasks.add_task(run_copywriting_generation, task_id, product_info)
    else:
        run_copywriting_generation(task_id, product_info)

    return {"task_id": task_id, "status": "queued"}


@router.post("/image/", response_model=GenerateResponse)
def generate_image_only(request: GenerateRequest, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    product = db.query(Product).filter(Product.product_id == request.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_info = _build_product_info(product, request, db)

    task_id = str(uuid4())
    generate_tasks[task_id] = {
        "status": "PENDING",
        "result": None,
        "product_info": product_info,
    }

    def run_image_generation(task_id: str, product_info: dict):
        try:
            logger.info("[%s] Starting image generation", task_id)
            generate_tasks[task_id]["status"] = "PROGRESS"

            platform = product_info.get("platform", "instagram")
            reference_images = product_info.get("reference_images", [])

            generator = ContentGenerator()
            style_hint = product_info.get("style_hint", None)

            image_result = generator.generate_image(
                product_info,
                platform,
                reference_images,
                style_hint,
                1,
                image_provider_id=product_info.get("image_provider_id"),
                image_model=product_info.get("image_model"),
            )
            image_urls = image_result.get("image_urls", [])
            if not image_urls:
                raise Exception("Image generation returned no URLs")

            generate_tasks[task_id]["status"] = "SUCCESS"
            generate_tasks[task_id]["result"] = {
                "text": None,
                "image": image_urls[0],
                "dimensions": image_result.get("dimensions", None),
                "image_prompt": image_result.get("image_prompt", None),
                "reference_product_images": product_info.get("reference_product_images", []),
                "reference_scene_images": product_info.get("reference_scene_images", []),
                "warning": image_result.get("warning"),
            }
            logger.info("[%s] Image generation completed: %s images", task_id, len(image_urls))
        except Exception as e:
            logger.exception("[%s] Task failed: %s", task_id, e)
            generate_tasks[task_id]["status"] = "FAILURE"
            generate_tasks[task_id]["result"] = {"error": str(e)}

    if background_tasks:
        background_tasks.add_task(run_image_generation, task_id, product_info)
    else:
        run_image_generation(task_id, product_info)

    return {"task_id": task_id, "status": "queued"}


@router.get("/status/{task_id}")
def get_generate_status(task_id: str):
    task = generate_tasks.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task.get("result"),
    }
