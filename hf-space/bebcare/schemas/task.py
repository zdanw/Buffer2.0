from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class TaskBase(BaseModel):
    name: str
    cron: str = Field(description="CRON表达式")
    mode: str = Field(default="auto", description="任务模式: auto | manual")
    target_categories: List[str] = []
    target_products: List[str] = []
    platforms: List[str] = Field(default=["instagram"], description="支持的平台: instagram, tiktok, facebook")
    reference_image_count: int = 3
    run_count_per_execution: int = 1
    generate_image_count: int = 1
    generate_copy_count: int = 1
    enabled: bool = True
    use_scene_reference: bool = False

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    mode: Optional[str] = None
    target_categories: Optional[List[str]] = None
    target_products: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    reference_image_count: Optional[int] = None
    run_count_per_execution: Optional[int] = None
    generate_image_count: Optional[int] = None
    generate_copy_count: Optional[int] = None
    enabled: Optional[bool] = None
    use_scene_reference: Optional[bool] = None

class TaskResponse(TaskBase):
    task_id: UUID
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

class ManualTaskDraftResponse(BaseModel):
    draft_id: UUID
    task_id: UUID
    product_id: Optional[str] = None
    images: List[str] = []
    copywritings: List[str] = []
    status: str = "pending"
    selected_image: Optional[str] = None
    selected_copy: Optional[str] = None
    published_platforms: List[str] = []
    created_at: datetime

class DraftPublishRequest(BaseModel):
    selected_image_index: int
    selected_copy_index: int
    platforms: List[str]


class DraftCreateRequest(BaseModel):
    product_id: Optional[str] = None
    images: List[str] = []
    copywritings: List[str] = []
    dimensions: Optional[List] = None
    image_prompts: Optional[List] = None
    reference_product_images: Optional[List[str]] = None
    reference_scene_images: Optional[List[str]] = None
