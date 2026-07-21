from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class ProductBase(BaseModel):
    product_name: str
    category: str
    description: Optional[str] = None
    selling_points: Optional[List[str]] = None
    brand_voice: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class ProductImageSchema(BaseModel):
    image_id: UUID
    cdn_url: str
    phash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    uploaded_at: datetime

class ProductResponse(ProductBase):
    product_id: UUID
    created_at: datetime
    updated_at: datetime
    images: List[ProductImageSchema] = []
    
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