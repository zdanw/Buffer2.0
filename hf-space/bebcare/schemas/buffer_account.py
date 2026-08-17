from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class BufferBrandSummary(BaseModel):
    brand_id: str
    name: str
    slug: str
    is_generic: bool = False
    is_system: bool = False


class BufferAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    api_token: str = Field(min_length=1)
    brand_ids: List[str] = []
    is_active: bool = True
    is_default: bool = False


class BufferAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    api_token: Optional[str] = None  # omit or empty = keep existing
    brand_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class BufferAccountResponse(BaseModel):
    id: str
    name: str
    api_token_masked: str
    buffer_email: Optional[str] = None
    buffer_remote_id: Optional[str] = None
    brand_ids: List[str] = []
    brands: List[BufferBrandSummary] = []
    is_active: bool
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BufferAccountTestResponse(BaseModel):
    ok: bool
    message: str
    email: Optional[str] = None
    remote_id: Optional[str] = None
