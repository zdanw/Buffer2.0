from pydantic import BaseModel, Field
from typing import Optional

class GenerateRequest(BaseModel):
    product_id: str
    platform: str = Field(description="目标平台")
    reference_count: int = 2
    style_hint: Optional[str] = None
    use_scene_reference: bool = False

class GenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"