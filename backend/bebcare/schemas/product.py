from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Literal

OFFERING_TYPES = (
    "physical_product",
    "software",
    "saas",
    "service",
    "digital_product",
    "event_or_experience",
    "mixed",
    "unknown",
)
OfferingType = Literal[
    "physical_product",
    "software",
    "saas",
    "service",
    "digital_product",
    "event_or_experience",
    "mixed",
    "unknown",
]

class BrandNested(BaseModel):
    brand_id: str
    name: str
    slug: str
    is_generic: bool = False

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    product_name: str
    category: str
    description: Optional[str] = None
    selling_points: Optional[List[str]] = None
    brand_id: Optional[str] = None
    brand_voice: Optional[str] = None
    use_brand_voice: bool = True
    has_on_body_branding: bool = True
    offering_type: OfferingType = "unknown"

    @field_validator("offering_type", mode="before")
    @classmethod
    def normalize_offering_type(cls, value):
        if value is None or value == "":
            return "unknown"
        text = str(value).strip().lower()
        if text not in OFFERING_TYPES:
            raise ValueError("invalid offering_type")
        return text

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    selling_points: Optional[List[str]] = None
    brand_id: Optional[str] = None
    brand_voice: Optional[str] = None
    use_brand_voice: Optional[bool] = None
    has_on_body_branding: Optional[bool] = None
    offering_type: Optional[OfferingType] = None

    @field_validator("offering_type", mode="before")
    @classmethod
    def normalize_offering_type(cls, value):
        if value is None or value == "":
            return value
        text = str(value).strip().lower()
        if text not in OFFERING_TYPES:
            raise ValueError("invalid offering_type")
        return text

class ProductImageSchema(BaseModel):
    image_id: UUID
    cdn_url: str
    phash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    uploaded_at: datetime
    image_type: Optional[str] = None
    sort_index: Optional[int] = None
    is_preferred: bool = False
    analysis_status: Optional[str] = None

class ProductResponse(ProductBase):
    product_id: UUID
    created_at: datetime
    updated_at: datetime
    images: List[ProductImageSchema] = []
    brand: Optional[BrandNested] = None
    
    model_config = {"from_attributes": True}
    
    @classmethod
    def from_orm(cls, obj):
        result = super().from_orm(obj)
        if result.selling_points and isinstance(result.selling_points, str):
            result.selling_points = result.selling_points.split(",") if result.selling_points else []
        return result

class ImageUploadResponse(BaseModel):
    product_id: str
    uploaded: List[dict]
    failed: Optional[List[str]] = None
    message: Optional[str] = None
