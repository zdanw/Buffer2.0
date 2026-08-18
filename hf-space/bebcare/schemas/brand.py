from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


class BrandSummary(BaseModel):
    brand_id: str
    slug: str
    name: str
    is_generic: bool = False
    is_system: bool = False
    voice: Optional[str] = None
    logo_url: Optional[str] = None
    vertical_pack: Optional[str] = None
    product_count: int = 0
    buffer_account_id: Optional[str] = None

    model_config = {"from_attributes": True}


class BrandBase(BaseModel):
    name: str = Field(..., max_length=255)
    voice: Optional[str] = None
    audience: Optional[str] = None
    tone_keywords: Optional[str] = Field(None, max_length=500)
    default_selling_points: Optional[List[str]] = None
    default_hashtags: Optional[List[str]] = None
    emoji_style: Optional[str] = Field("moderate", max_length=32)
    words_to_avoid: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    logo_font_rule: Optional[str] = None
    vertical_pack: Optional[str] = Field("general", max_length=64)
    default_product_type: Optional[str] = Field(None, max_length=100)


class BrandCreate(BrandBase):
    slug: Optional[str] = Field(None, max_length=64)
    buffer_account_id: Optional[str] = Field(None, max_length=36)


class BrandUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    voice: Optional[str] = None
    audience: Optional[str] = None
    tone_keywords: Optional[str] = Field(None, max_length=500)
    default_selling_points: Optional[List[str]] = None
    default_hashtags: Optional[List[str]] = None
    emoji_style: Optional[str] = Field(None, max_length=32)
    words_to_avoid: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    logo_font_rule: Optional[str] = None
    vertical_pack: Optional[str] = Field(None, max_length=64)
    default_product_type: Optional[str] = Field(None, max_length=100)
    copy_system_prompt: Optional[str] = None
    image_system_prompt: Optional[str] = None
    vision_image_system_prompt: Optional[str] = None
    vision_scene_system_prompt: Optional[str] = None
    narrative_perspectives: Optional[List[Dict[str, Any]]] = None
    writing_styles: Optional[List[Dict[str, Any]]] = None
    copy_emoji_hints: Optional[str] = Field(None, max_length=200)
    copy_example: Optional[str] = None
    image_fallback_selling_points: Optional[str] = Field(None, max_length=500)
    copy_fallback_selling_points: Optional[List[str]] = None
    buffer_account_id: Optional[str] = Field(None, max_length=36)


class BrandResponse(BrandBase):
    brand_id: str
    slug: str
    is_generic: bool = False
    is_system: bool = False
    copy_system_prompt: Optional[str] = None
    image_system_prompt: Optional[str] = None
    vision_image_system_prompt: Optional[str] = None
    vision_scene_system_prompt: Optional[str] = None
    narrative_perspectives: Optional[List[Dict[str, Any]]] = None
    writing_styles: Optional[List[Dict[str, Any]]] = None
    copy_emoji_hints: Optional[str] = None
    copy_example: Optional[str] = None
    image_fallback_selling_points: Optional[str] = None
    copy_fallback_selling_points: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None
    buffer_account_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
