from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from bebcare.database import get_db
from bebcare.models.prompt_dimension import (
    PromptDimension,
    PromptDimensionCompatibility,
    PromptDimensionCompatPolicy,
    ProductDimension,
    DimensionType,
    CompatMode,
)
from bebcare.schemas.prompt_dimension import (
    DimensionTypeResponse,
    DimensionCompatEntry,
    DimensionCompatibilities,
    COMPAT_TARGET_TYPES,
    PromptDimensionCreate,
    PromptDimensionUpdate,
    PromptDimensionResponse,
    ProductDimensionCreate,
    ProductDimensionResponse,
)
from bebcare.services.dimension_service import dimension_service
from bebcare.models import Product

router = APIRouter(prefix="/prompt-dimensions", tags=["prompt-dimensions"])


def _empty_compat_dict() -> dict:
    return {
        t: DimensionCompatEntry(mode="unrestricted", items=[])
        for t in COMPAT_TARGET_TYPES
    }


def _compat_dict_from_dim(dim: PromptDimension) -> dict:
    """策略表为准；无策略行 = unrestricted（忽略可能残留的反向边）。"""
    result = _empty_compat_dict()
    policy_by_type = {
        p.target_dimension_type: p.mode
        for p in (dim.compat_policies or [])
    }
    allow_items: dict[str, list[str]] = {t: [] for t in COMPAT_TARGET_TYPES}
    block_items: dict[str, list[str]] = {t: [] for t in COMPAT_TARGET_TYPES}

    for comp in dim.compatibilities or []:
        t = comp.target_dimension_type
        if t not in allow_items:
            continue
        rel = (comp.relation_type or "compatible")
        if rel == "blocked":
            block_items[t].append(comp.target_item_id)
        else:
            allow_items[t].append(comp.target_item_id)

    for t in COMPAT_TARGET_TYPES:
        mode = policy_by_type.get(t)
        if mode == CompatMode.ALLOWLIST.value:
            # 空 items 仍为 allowlist = 都不兼容
            result[t] = DimensionCompatEntry(mode="allowlist", items=list(allow_items[t]))
        elif mode == CompatMode.BLOCKLIST.value:
            items = list(block_items[t])
            if items:
                result[t] = DimensionCompatEntry(mode="blocklist", items=items)
            else:
                result[t] = DimensionCompatEntry(mode="unrestricted", items=[])
        else:
            result[t] = DimensionCompatEntry(mode="unrestricted", items=[])

    return result


def _to_dimension_response(dim: PromptDimension, compatibilities=None) -> PromptDimensionResponse:
    if compatibilities is None:
        compatibilities = DimensionCompatibilities(**_compat_dict_from_dim(dim))
    elif isinstance(compatibilities, dict):
        compatibilities = DimensionCompatibilities(**compatibilities)
    return PromptDimensionResponse(
        dimension_id=dim.dimension_id,
        product_type=dim.product_type,
        dimension_type=dim.dimension_type,
        item_id=dim.item_id,
        name=dim.name,
        enabled=bool(dim.enabled) if dim.enabled is not None else True,
        created_at=dim.created_at,
        updated_at=dim.updated_at,
        compatibilities=compatibilities,
    )


def _iter_compat_entries(compat: DimensionCompatibilities):
    data = compat.model_dump()
    for target_dim_type, entry in data.items():
        if entry is None:
            continue
        yield target_dim_type, DimensionCompatEntry(**entry)


def _save_compatibilities(
    db: Session,
    dim: PromptDimension,
    compat: DimensionCompatibilities,
):
    """写入本维度的策略 + 正向边（mode 单向，不改写对端策略）。"""
    db.query(PromptDimensionCompatibility).filter(
        PromptDimensionCompatibility.dimension_id == dim.dimension_id
    ).delete()
    db.query(PromptDimensionCompatPolicy).filter(
        PromptDimensionCompatPolicy.dimension_id == dim.dimension_id
    ).delete()

    for target_dim_type, entry in _iter_compat_entries(compat):
        if target_dim_type == dim.dimension_type:
            continue

        if entry.mode == "unrestricted":
            continue

        db.add(
            PromptDimensionCompatPolicy(
                dimension_id=dim.dimension_id,
                target_dimension_type=target_dim_type,
                mode=entry.mode,
            )
        )

        relation = "blocked" if entry.mode == "blocklist" else "compatible"
        for target_item_id in entry.items:
            db.add(
                PromptDimensionCompatibility(
                    dimension_id=dim.dimension_id,
                    source_dimension_type=dim.dimension_type,
                    target_dimension_type=target_dim_type,
                    target_item_id=target_item_id,
                    relation_type=relation,
                    is_active=True,
                )
            )


@router.get("/dimension-types", response_model=List[DimensionTypeResponse])
def get_dimension_types():
    return [
        {"name": dim_type.value, "display_name": dim_type.display_name}
        for dim_type in DimensionType
    ]


@router.get("/product-types")
def get_product_types(db: Session = Depends(get_db)):
    """产品类型列表：直接使用素材 category 与已有维度 product_type 的并集。"""
    prompt_types = db.query(PromptDimension.product_type).distinct().all()
    prompt_type_list = [pt[0] for pt in prompt_types if pt[0]]

    product_categories = db.query(Product.category).distinct().all()
    category_list = [cat[0] for cat in product_categories if cat[0]]

    all_types = set(prompt_type_list + category_list)

    result = []
    for pt in sorted(all_types):
        result.append({
            "value": pt,
            "label": pt
        })

    return {"product_types": result}


@router.get("/")
def list_prompt_dimensions(
    product_type: Optional[str] = None,
    dimension_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(PromptDimension)

    if product_type:
        query = query.filter(PromptDimension.product_type == product_type)
    if dimension_type:
        query = query.filter(PromptDimension.dimension_type == dimension_type)

    total = query.count()
    offset = (page - 1) * page_size
    dimensions = query.order_by(PromptDimension.product_type, PromptDimension.dimension_type, PromptDimension.item_id).offset(offset).limit(page_size).all()

    results = []
    for dim in dimensions:
        results.append(_to_dimension_response(dim))

    return {
        "data": results,
        "pagination": {
            "current": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }


@router.post("/", response_model=PromptDimensionResponse, status_code=201)
def create_prompt_dimension(
    dimension: PromptDimensionCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(PromptDimension).filter(
        PromptDimension.product_type == dimension.product_type,
        PromptDimension.dimension_type == dimension.dimension_type,
        PromptDimension.item_id == dimension.item_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="维度项已存在")

    new_dim = PromptDimension(
        product_type=dimension.product_type,
        dimension_type=dimension.dimension_type,
        item_id=dimension.item_id,
        name=dimension.name
    )
    db.add(new_dim)
    db.flush()

    if dimension.compatibilities:
        try:
            _save_compatibilities(db, new_dim, dimension.compatibilities)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(new_dim)

    dimension_service.clear_cache()

    return _to_dimension_response(new_dim)


@router.get("/{dimension_id}", response_model=PromptDimensionResponse)
def get_prompt_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dimension = db.query(PromptDimension).filter(
        PromptDimension.dimension_id == dimension_id
    ).first()

    if not dimension:
        raise HTTPException(status_code=404, detail="维度项不存在")

    return _to_dimension_response(dimension)


@router.put("/{dimension_id}", response_model=PromptDimensionResponse)
def update_prompt_dimension(
    dimension_id: str,
    update_data: PromptDimensionUpdate,
    db: Session = Depends(get_db)
):
    dimension = db.query(PromptDimension).filter(
        PromptDimension.dimension_id == dimension_id
    ).first()

    if not dimension:
        raise HTTPException(status_code=404, detail="维度项不存在")

    if update_data.name is not None:
        dimension.name = update_data.name

    if update_data.enabled is not None:
        dimension.enabled = update_data.enabled

    if update_data.compatibilities is not None:
        try:
            _save_compatibilities(
                db, dimension, update_data.compatibilities
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(dimension)

    dimension_service.clear_cache()

    return _to_dimension_response(dimension)


@router.delete("/{dimension_id}", status_code=204)
def delete_prompt_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dimension = db.query(PromptDimension).filter(
        PromptDimension.dimension_id == dimension_id
    ).first()

    if not dimension:
        raise HTTPException(status_code=404, detail="维度项不存在")

    db.query(PromptDimensionCompatibility).filter(
        PromptDimensionCompatibility.target_dimension_type == dimension.dimension_type,
        PromptDimensionCompatibility.target_item_id == dimension.item_id
    ).delete()

    db.delete(dimension)
    db.commit()

    dimension_service.clear_cache()


@router.post("/initialize/")
def initialize_dimensions(db: Session = Depends(get_db)):
    return dimension_service.initialize_default_dimensions(db)


@router.get("/{product_type}/by-type/{dimension_type}")
def get_dimensions_by_type(
    product_type: str,
    dimension_type: str,
    db: Session = Depends(get_db)
):
    return dimension_service.get_dimensions_by_type(db, product_type, dimension_type)


@router.get("/{product_type}/compatible")
def get_compatible_dimensions(
    product_type: str,
    source_dim_type: str,
    source_item_id: str,
    target_dim_type: str,
    db: Session = Depends(get_db)
):
    return dimension_service.get_compatible_dimensions(
        db, product_type, source_dim_type, source_item_id, target_dim_type
    )


@router.get("/products/{product_id}/dimensions", response_model=List[ProductDimensionResponse])
def get_product_dimensions(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    dimensions = db.query(ProductDimension).filter(
        ProductDimension.product_id == product_id
    ).order_by(ProductDimension.dimension_type).all()

    return [ProductDimensionResponse.from_orm(dim) for dim in dimensions]


@router.post("/products/{product_id}/dimensions/", response_model=ProductDimensionResponse, status_code=201)
def create_product_dimension(
    product_id: str,
    dimension: ProductDimensionCreate,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    if dimension.dimension_id:
        template_dim = db.query(PromptDimension).filter(
            PromptDimension.dimension_id == dimension.dimension_id
        ).first()
        if not template_dim:
            raise HTTPException(status_code=400, detail="模板维度不存在")

        new_dim = ProductDimension(
            product_id=product_id,
            dimension_id=dimension.dimension_id,
            dimension_type=template_dim.dimension_type,
            item_id=template_dim.item_id,
            name=template_dim.name,
            time=template_dim.time,
            lighting=template_dim.lighting,
            is_custom=False
        )
    else:
        if not dimension.item_id or not dimension.name:
            raise HTTPException(status_code=400, detail="自定义维度需要提供item_id和name")

        new_dim = ProductDimension(
            product_id=product_id,
            dimension_type=dimension.dimension_type,
            item_id=dimension.item_id,
            name=dimension.name,
            time=dimension.time,
            lighting=dimension.lighting,
            is_custom=True
        )

    db.add(new_dim)
    db.commit()
    db.refresh(new_dim)

    dimension_service.clear_cache()

    return ProductDimensionResponse.from_orm(new_dim)


@router.put("/products/{product_id}/dimensions/{id}", response_model=ProductDimensionResponse)
def update_product_dimension(
    product_id: str,
    id: str,
    update_data: ProductDimensionCreate,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    dimension = db.query(ProductDimension).filter(
        ProductDimension.id == id,
        ProductDimension.product_id == product_id
    ).first()

    if not dimension:
        raise HTTPException(status_code=404, detail="产品维度不存在")

    if update_data.dimension_id:
        template_dim = db.query(PromptDimension).filter(
            PromptDimension.dimension_id == update_data.dimension_id
        ).first()
        if not template_dim:
            raise HTTPException(status_code=400, detail="模板维度不存在")

        dimension.dimension_id = update_data.dimension_id
        dimension.dimension_type = template_dim.dimension_type
        dimension.item_id = template_dim.item_id
        dimension.name = template_dim.name
        dimension.time = template_dim.time
        dimension.lighting = template_dim.lighting
        dimension.is_custom = False
    else:
        if update_data.item_id:
            dimension.item_id = update_data.item_id
        if update_data.name:
            dimension.name = update_data.name
        if update_data.time is not None:
            dimension.time = update_data.time
        if update_data.lighting is not None:
            dimension.lighting = update_data.lighting
        dimension.is_custom = True

    db.commit()
    db.refresh(dimension)

    dimension_service.clear_cache()

    return ProductDimensionResponse.from_orm(dimension)


@router.delete("/products/{product_id}/dimensions/{id}", status_code=204)
def delete_product_dimension(product_id: str, id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    dimension = db.query(ProductDimension).filter(
        ProductDimension.id == id,
        ProductDimension.product_id == product_id
    ).first()

    if not dimension:
        raise HTTPException(status_code=404, detail="产品维度不存在")

    db.delete(dimension)
    db.commit()

    dimension_service.clear_cache()
