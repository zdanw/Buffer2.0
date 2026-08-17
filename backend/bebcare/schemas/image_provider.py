from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime


ProviderType = Literal["openai_compatible", "doubao_ark", "aliyun_maas"]


class ManualModelEntry(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


def _normalize_manual_models(value: Optional[List[Any]]) -> List[ManualModelEntry]:
    if not value:
        return []
    seen = set()
    out: List[ManualModelEntry] = []
    for item in value:
        if isinstance(item, ManualModelEntry):
            mid = item.id.strip()
            desc = (item.description or "").strip() or None
        elif isinstance(item, dict):
            mid = str(item.get("id") or item.get("model") or "").strip()
            desc = str(item.get("description") or item.get("desc") or "").strip() or None
        else:
            mid = str(item or "").strip()
            desc = None
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(ManualModelEntry(id=mid, description=desc))
    return out


class ImageProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: ProviderType
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str = Field(min_length=1)
    supports_list_models: bool = True
    default_model: Optional[str] = None
    manual_models: List[ManualModelEntry] = []
    extra_headers: Optional[Dict[str, Any]] = None
    extra_params: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_default: bool = False

    @field_validator("manual_models", mode="before")
    @classmethod
    def validate_manual_models(cls, v):
        return _normalize_manual_models(v)


class ImageProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider_type: Optional[ProviderType] = None
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=512)
    api_key: Optional[str] = None  # omit or empty = keep existing
    supports_list_models: Optional[bool] = None
    default_model: Optional[str] = None
    manual_models: Optional[List[ManualModelEntry]] = None
    extra_headers: Optional[Dict[str, Any]] = None
    extra_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

    @field_validator("manual_models", mode="before")
    @classmethod
    def validate_manual_models(cls, v):
        if v is None:
            return None
        return _normalize_manual_models(v)


class ImageProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    api_key_masked: str
    supports_list_models: bool
    default_model: Optional[str] = None
    manual_models: List[ManualModelEntry] = []
    extra_headers: Optional[Dict[str, Any]] = None
    extra_params: Optional[Dict[str, Any]] = None
    is_active: bool
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImageModelInfo(BaseModel):
    id: str
    description: Optional[str] = None
    owned_by: Optional[str] = None
    source: Optional[str] = None  # manual | remote


class ImageModelsResponse(BaseModel):
    models: List[ImageModelInfo] = []
    message: Optional[str] = None
    allow_manual_input: bool = True


class ImageProviderTestResponse(BaseModel):
    ok: bool
    message: str


class ImageSizeOption(BaseModel):
    aspect: str
    size: str
    width: int
    height: int
    label: str


class ImageSizeCapabilitiesResponse(BaseModel):
    supported_sizes: List[ImageSizeOption] = []
    default_size: str = "2048x2048"
    provider_type: Optional[str] = None
    allow_custom: bool = True
