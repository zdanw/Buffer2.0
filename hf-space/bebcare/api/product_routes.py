import logging

logger = logging.getLogger(__name__)

from collections import defaultdict

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from bebcare.database import get_db
from bebcare.models import Product, ProductImage, Brand
from bebcare.models.prompt_dimension import ProductDimension
from bebcare.models.user import User
from bebcare.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ImageUploadResponse
from bebcare.knowledge_base.chroma_client import chroma_client
from bebcare.utils.image_utils import calculate_phash, get_image_dimensions
from bebcare.utils.github_uploader import github_uploader
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.ownership import (
    assert_owned_ref,
    get_owned_or_404,
    owned_query,
    stamp_owner,
)
from PIL import Image
import uuid
import io

router = APIRouter(prefix="/products", tags=["products"])


def _brand_nested(product: Product) -> dict | None:
    if not product.brand:
        return None
    return {
        "brand_id": product.brand.brand_id,
        "name": product.brand.name,
        "slug": product.brand.slug,
        "is_generic": bool(product.brand.is_generic),
    }


def _product_to_dict(product: Product, product_dimensions: list | None = None) -> dict:
    product_images = []
    scene_images = []
    for img in product.images:
        img_dict = {
            "image_id": img.image_id,
            "cdn_url": img.cdn_url,
            "phash": img.phash,
            "width": img.width,
            "height": img.height,
            "image_type": img.image_type,
            "uploaded_at": img.uploaded_at,
        }
        if img.image_type == "product":
            product_images.append(img_dict)
        else:
            scene_images.append(img_dict)

    result = {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "brand_id": product.brand_id,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points.split(",") if product.selling_points else [],
        "brand_voice": product.brand_voice,
        "use_brand_voice": bool(getattr(product, "use_brand_voice", True)),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "product_images": product_images,
        "scene_images": scene_images,
        "brand": _brand_nested(product),
    }
    if product_dimensions is not None:
        result["dimensions"] = product_dimensions
    return result


def _resolve_brand_id(db: Session, brand_id: str | None, current_user: User) -> str | None:
    if not brand_id:
        return None
    assert_owned_ref(db, Brand, brand_id, current_user, id_attr="brand_id")
    return brand_id

@router.get("/categories")
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取所有产品分类列表"""
    categories = (
        owned_query(db, Product, current_user)
        .with_entities(Product.category)
        .distinct()
        .all()
    )
    category_list = [cat[0] for cat in categories if cat[0]]
    return {"categories": category_list}

@router.get("/")
def list_products(
    page: int = 1,
    page_size: int = 10,
    brand_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = owned_query(db, Product, current_user).options(
        joinedload(Product.images),
        joinedload(Product.brand),
    )
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    total = query.count()
    
    offset = (page - 1) * page_size
    products = query.order_by(Product.created_at.desc()).offset(offset).limit(page_size).all()

    dims_by_product: dict[str, list] = defaultdict(list)
    if products:
        product_ids = [p.product_id for p in products]
        all_dims = (
            db.query(ProductDimension)
            .filter(ProductDimension.product_id.in_(product_ids))
            .order_by(ProductDimension.dimension_type)
            .all()
        )
        for dim in all_dims:
            dims_by_product[dim.product_id].append(dim)

    result = []
    for product in products:
        product_dimensions = [
            {
                "id": dim.id,
                "dimension_id": dim.dimension_id,
                "dimension_type": dim.dimension_type,
                "item_id": dim.item_id,
                "name": dim.name,
                "time": dim.time,
                "lighting": dim.lighting,
                "is_custom": dim.is_custom,
                "created_at": dim.created_at,
            }
            for dim in dims_by_product.get(product.product_id, [])
        ]
        result.append(_product_to_dict(product, product_dimensions))
    
    return {
        "data": result,
        "pagination": {
            "current": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }

@router.post("/", status_code=201)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_brand_id = _resolve_brand_id(db, product.brand_id, current_user)
    new_product = Product(
        product_name=product.product_name,
        brand_id=resolved_brand_id,
        category=product.category,
        description=product.description,
        selling_points=",".join(product.selling_points) if product.selling_points else None,
        brand_voice=product.brand_voice,
        use_brand_voice=product.use_brand_voice,
    )
    stamp_owner(new_product, current_user)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    product = (
        db.query(Product)
        .options(joinedload(Product.images), joinedload(Product.brand))
        .filter(Product.product_id == new_product.product_id)
        .first()
    )
    return _product_to_dict(product, [])

@router.get("/{product_id}")
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    product = (
        db.query(Product)
        .options(joinedload(Product.images), joinedload(Product.brand))
        .filter(Product.product_id == product_id)
        .first()
    )

    dimensions = db.query(ProductDimension).filter(
        ProductDimension.product_id == product_id
    ).order_by(ProductDimension.dimension_type).all()

    product_dimensions = [
        {
            "id": dim.id,
            "dimension_id": dim.dimension_id,
            "dimension_type": dim.dimension_type,
            "item_id": dim.item_id,
            "name": dim.name,
            "time": dim.time,
            "lighting": dim.lighting,
            "is_custom": dim.is_custom,
            "created_at": dim.created_at,
        }
        for dim in dimensions
    ]
    return _product_to_dict(product, product_dimensions)
@router.put("/{product_id}")
def update_product(
    product_id: str,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    product = (
        db.query(Product)
        .options(joinedload(Product.images), joinedload(Product.brand))
        .filter(Product.product_id == product_id)
        .first()
    )

    if product_update.product_name is not None:
        product.product_name = product_update.product_name
    if product_update.brand_id is not None:
        product.brand_id = _resolve_brand_id(db, product_update.brand_id, current_user)
    if product_update.category is not None:
        product.category = product_update.category
    if product_update.description is not None:
        product.description = product_update.description
    if product_update.selling_points is not None:
        product.selling_points = ",".join(product_update.selling_points) if product_update.selling_points else None
    if product_update.brand_voice is not None:
        product.brand_voice = product_update.brand_voice
    if product_update.use_brand_voice is not None:
        product.use_brand_voice = product_update.use_brand_voice

    db.commit()
    db.refresh(product)
    return _product_to_dict(product)
@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    
    db.delete(product)
    db.commit()

@router.post("/{product_id}/images", response_model=ImageUploadResponse)
async def upload_product_images(
    product_id: str,
    request: Request,
    image_urls: Optional[str] = None,
    image_type: str = "product",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if image_type not in ["product", "scene"]:
        raise HTTPException(status_code=400, detail="Invalid image_type. Must be 'product' or 'scene'")
    
    product = get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    
    uploaded = []
    failed = []
    
    all_files = []
    form_data = await request.form()
    
    files_field = form_data.getlist("files")
    if files_field:
        all_files = files_field
    
    if not all_files and not image_urls:
        raise HTTPException(status_code=400, detail="No files or URLs provided")
    
    for file in all_files:
        try:
            file_content = file.file.read()
            logger.info(
                "[CDN] product upload start product_id=%s filename=%s bytes=%s",
                product_id,
                file.filename,
                len(file_content),
            )

            # Process locally — jsDelivr often 404s for seconds/minutes after GitHub write
            image = Image.open(io.BytesIO(file_content))
            image.load()
            phash = calculate_phash(image)
            width, height = get_image_dimensions(image)

            cdn_url = github_uploader.upload_file(file_content, file.filename)
            logger.info(
                "[CDN] product upload ok product_id=%s filename=%s cdn_url=%s",
                product_id,
                file.filename,
                cdn_url,
            )
            logger.debug('Image dimensions: %sx%s, phash: %s', width, height, phash)
            
            embedding = chroma_client.get_image_embedding(image)
            if chroma_client.embeddings_enabled:
                logger.debug('Generated embedding with %s dimensions', len(embedding))
            else:
                logger.info('CLIP disabled; storing placeholder embedding for metadata only')
            
            new_image = ProductImage(
                product_id=product_id,
                cdn_url=cdn_url,
                phash=phash,
                width=width,
                height=height,
                image_type=image_type
            )
            db.add(new_image)
            db.flush()
            
            chroma_client.add_image(
                str(new_image.image_id),
                embedding,
                {
                    "product_id": str(product_id),
                    "image_id": str(new_image.image_id),
                    "product_name": product.product_name,
                    "category": product.category,
                    "description": product.description,
                    "cdn_url": cdn_url,
                    "phash": phash,
                    "selling_points": product.selling_points,
                    "brand_id": product.brand_id,
                    "image_type": image_type,
                    "created_at": str(new_image.uploaded_at)
                }
            )
            
            uploaded.append({
                "image_id": str(new_image.image_id),
                "cdn_url": cdn_url,
                "phash": phash,
                "width": width,
                "height": height,
                "image_type": image_type
            })
            logger.info('Image %s processed successfully', file.filename)
            
            db.commit()
            
        except Exception as e:
            logger.exception(
                "[CDN] product upload failed product_id=%s filename=%s err=%s",
                product_id,
                file.filename,
                e,
            )
            db.rollback()
            failed.append(file.filename)
    
    if failed:
        return {"product_id": product_id, "uploaded": uploaded, "failed": failed, "message": f"部分图片上传失败: {', '.join(failed)}"}
    
    return {"product_id": product_id, "uploaded": uploaded}

@router.get("/{product_id}/images")
def get_product_images(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    return {"product_id": product_id, "images": images}

@router.delete("/{product_id}/images/{image_id}", status_code=204)
def delete_product_image(
    product_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_owned_or_404(db, Product, product_id, current_user, id_attr="product_id")
    image = db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.image_id == image_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    chroma_client.delete_image(image_id)
    db.delete(image)
    db.commit()