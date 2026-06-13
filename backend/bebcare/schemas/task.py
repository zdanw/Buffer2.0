from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class TaskBase(BaseModel):
    name: str
    cron: str = Field(description="CRON表达式")
    target_categories: List[str] = []
    target_products: List[str] = []
    platforms: List[str] = Field(description="支持的平台: instagram, tiktok, facebook")
    reference_image_count: int = 3
    run_count_per_execution: int = 1
    enabled: bool = True

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    target_categories: Optional[List[str]] = None
    target_products: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    reference_image_count: Optional[int] = None
    run_count_per_execution: Optional[int] = None
    enabled: Optional[bool] = None

class TaskResponse(TaskBase):
    task_id: UUID
    created_at: datetime
    updated_at: datetime