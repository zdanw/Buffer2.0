from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, List

class GenerateRequest(BaseModel):
    product_id: str
    platform: str = Field(description="目标平台")
    reference_count: int = 2
    style_hint: Optional[str] = None
    use_scene_reference: bool = False
    use_vision_image_prompt: bool = False
    realistic_placement: bool = True
    image_provider_id: Optional[str] = None
    image_model: Optional[str] = None
    image_size: Optional[str] = None
    image_provider_mode: Optional[Literal["platform", "byok"]] = None
    locale: Optional[Literal["en", "zh"]] = None
    # Studio compare: force scene-fusion pipeline (legacy=text template, vision=multimodal)
    image_prompt_pipeline: Optional[Literal["legacy_scene", "vision_scene"]] = None
    # Pin the same reference URLs across parallel generations (Studio compare)
    reference_product_images: Optional[List[str]] = None
    reference_scene_images: Optional[List[str]] = None
    reference_product_image_ids: Optional[List[str]] = None
    reference_scene_image_ids: Optional[List[str]] = None
    compare_group_id: Optional[str] = None
    experiment_variant: Optional[str] = None


class ReferenceSelectionRequest(BaseModel):
    product_id: str
    reference_count: int = 2
    use_scene_reference: bool = False
    image_size: Optional[str] = None
    reference_product_image_ids: Optional[List[str]] = None
    reference_scene_image_ids: Optional[List[str]] = None


class ReferenceSelectionResponse(BaseModel):
    reference_images: List[str]
    reference_product_images: List[str]
    reference_scene_images: List[str]
    use_scene_reference: bool
    reference_product_image_ids: List[str] = []
    reference_scene_image_ids: List[str] = []
    reference_manifest: Optional[Dict] = None

class CompareSelectionRequest(BaseModel):
    compare_group_id: str
    image_prompt_pipeline: Literal["legacy_scene", "vision_scene"]


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
    logo_mode: Optional[str] = None