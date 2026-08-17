from pydantic import BaseModel, Field
from typing import Optional, Dict

class GenerateRequest(BaseModel):
    product_id: str
    platform: str = Field(description="目标平台")
    reference_count: int = 2
    style_hint: Optional[str] = None
    use_scene_reference: bool = False
    use_vision_image_prompt: bool = False
    image_provider_id: Optional[str] = None
    image_model: Optional[str] = None
    image_size: Optional[str] = None

class GenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"

class DimensionInfo(BaseModel):
    scene: str
    viewpoint: str
    composition: str
    style: str
    quality: str
    details: str
    lighting: str

class GenerateResult(BaseModel):
    text: Optional[str] = None
    image: Optional[str] = None
    dimensions: Optional[DimensionInfo] = None
    image_prompt: Optional[str] = None
    reference_product_images: Optional[list] = None
    reference_scene_images: Optional[list] = None
    warning: Optional[str] = None