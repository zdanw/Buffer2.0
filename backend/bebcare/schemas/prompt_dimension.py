from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict
from bebcare.models.prompt_dimension import DimensionType


class DimensionTypeResponse(BaseModel):
    name: str
    display_name: str


class DimensionCompatibilities(BaseModel):
    scenes: Optional[List[str]] = Field(None, description="兼容的场景item_id列表")
    lighting: Optional[List[str]] = Field(None, description="兼容的光线item_id列表")
    styles: Optional[List[str]] = Field(None, description="兼容的风格item_id列表")
    compositions: Optional[List[str]] = Field(None, description="兼容的构图item_id列表")
    details: Optional[List[str]] = Field(None, description="兼容的细节item_id列表")
    quality: Optional[List[str]] = Field(None, description="兼容的画质item_id列表")
    viewpoints: Optional[List[str]] = Field(None, description="兼容的视角item_id列表")


class PromptDimensionBase(BaseModel):
    product_type: str = Field(..., description="产品类型，与素材 category 一致，如 Night Lights, Audio Monitor")
    dimension_type: str = Field(..., description="维度类型，如 scenes, viewpoints")
    item_id: str = Field(..., description="维度项ID")
    name: str = Field(..., description="维度项名称")


class PromptDimensionCreate(PromptDimensionBase):
    compatibilities: Optional[DimensionCompatibilities] = Field(None, description="兼容性配置")


class PromptDimensionUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    compatibilities: Optional[DimensionCompatibilities] = None


class PromptDimensionResponse(PromptDimensionBase):
    dimension_id: str
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    compatibilities: Optional[DimensionCompatibilities] = None

    model_config = {"from_attributes": True}


class ProductDimensionBase(BaseModel):
    dimension_type: str = Field(..., description="维度类型")
    dimension_id: Optional[str] = Field(None, description="关联的模板维度ID")
    item_id: Optional[str] = Field(None, description="维度项ID")
    name: Optional[str] = Field(None, description="维度项名称")
    time: Optional[str] = Field(None, description="时间属性")
    lighting: Optional[List[str]] = Field(None, description="光线属性列表")
    is_custom: Optional[bool] = Field(False, description="是否自定义")


class ProductDimensionCreate(ProductDimensionBase):
    pass


class ProductDimensionResponse(ProductDimensionBase):
    id: str
    product_id: str
    created_at: datetime

    model_config = {"from_attributes": True}