import logging
import re
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from bebcare.database import get_db
from bebcare.models import Brand, Product, GENERIC_BRAND_ID, BEBCARE_BRAND_ID
from bebcare.schemas.brand import BrandCreate, BrandResponse, BrandSummary, BrandUpdate
from bebcare.services.auth_dependency import get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brands", tags=["brands"])

_GENERIC_LOCKED_FIELDS = frozenset(
    {
        "name",
        "voice",
        "vertical_pack",
        "copy_system_prompt",
        "image_system_prompt",
        "vision_image_system_prompt",
        "vision_scene_system_prompt",
    }
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"brand-{uuid.uuid4().hex[:8]}"


def _brand_summary(brand: Brand, product_count: int = 0) -> dict:
    return {
        "brand_id": brand.brand_id,
        "slug": brand.slug,
        "name": brand.name,
        "is_generic": bool(brand.is_generic),
        "is_system": bool(brand.is_system),
        "voice": brand.voice,
        "logo_url": brand.logo_url,
        "vertical_pack": brand.vertical_pack,
        "product_count": product_count,
    }


def _brand_response(brand: Brand) -> dict:
    data = BrandResponse.model_validate(brand).model_dump()
    return data


@router.get("/")
def list_brands(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import func

    brands = db.query(Brand).order_by(Brand.is_generic.desc(), Brand.name).all()
    count_rows = (
        db.query(Product.brand_id, func.count(Product.product_id))
        .group_by(Product.brand_id)
        .all()
    )
    counts = {bid: cnt for bid, cnt in count_rows}
    return {
        "data": [_brand_summary(b, counts.get(b.brand_id, 0)) for b in brands],
    }


@router.post("/", status_code=201, response_model=BrandResponse)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    slug = (payload.slug or _slugify(payload.name)).strip().lower()
    if db.query(Brand).filter(Brand.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"Brand slug '{slug}' already exists")

    brand = Brand(
        brand_id=str(uuid.uuid4()),
        slug=slug,
        name=payload.name,
        is_generic=False,
        is_system=False,
        voice=payload.voice,
        audience=payload.audience,
        tone_keywords=payload.tone_keywords,
        default_selling_points=payload.default_selling_points or [],
        default_hashtags=payload.default_hashtags or [],
        emoji_style=payload.emoji_style or "moderate",
        words_to_avoid=payload.words_to_avoid,
        logo_font_rule=payload.logo_font_rule,
        logo_url=payload.logo_url,
        vertical_pack=payload.vertical_pack or "general",
        default_product_type=payload.default_product_type or "General",
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return _brand_response(brand)


@router.get("/{brand_id}", response_model=BrandResponse)
def get_brand(brand_id: str, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return _brand_response(brand)


@router.put("/{brand_id}", response_model=BrandResponse)
def update_brand(brand_id: str, payload: BrandUpdate, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    updates = payload.model_dump(exclude_unset=True)
    if brand.is_generic:
        blocked = [k for k in updates if k in _GENERIC_LOCKED_FIELDS]
        if blocked:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot modify locked fields on Generic brand: {', '.join(blocked)}",
            )

    for key, value in updates.items():
        setattr(brand, key, value)

    db.commit()
    db.refresh(brand)
    return _brand_response(brand)


@router.delete("/{brand_id}", status_code=204)
def delete_brand(brand_id: str, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if brand.is_generic or brand.brand_id in (GENERIC_BRAND_ID, BEBCARE_BRAND_ID):
        raise HTTPException(status_code=400, detail="Built-in brands cannot be deleted")

    db.query(Product).filter(Product.brand_id == brand_id).update(
        {Product.brand_id: GENERIC_BRAND_ID}
    )
    db.delete(brand)
    db.commit()


@router.post("/{brand_id}/initialize-pack")
def initialize_brand_pack(
    brand_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin_user),
):
    from bebcare.services.vertical_pack_service import initialize_pack

    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    pack_id = brand.vertical_pack or "general"
    try:
        return initialize_pack(pack_id, db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{brand_id}/logo")
async def upload_brand_logo(brand_id: str, request: Request, db: Session = Depends(get_db)):
    from bebcare.utils.github_uploader import github_uploader

    brand = db.query(Brand).filter(Brand.brand_id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    form_data = await request.form()
    file = form_data.get("file")
    if not file or not getattr(file, "filename", None):
        raise HTTPException(status_code=400, detail="No file provided")

    file_content = file.file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Empty file")

    cdn_url = github_uploader.upload_file(file_content, file.filename)
    brand.logo_url = cdn_url
    db.commit()
    db.refresh(brand)
    return {"logo_url": cdn_url}
