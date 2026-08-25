from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import List, Optional, Literal


CompatMode = Literal["unrestricted", "allowlist", "blocklist"]

COMPAT_TARGET_TYPES = (
    "scenes",
    "lighting",
    "styles",
    "compositions",
    "details",
    "quality",
    "viewpoints",
)


class DimensionCompatEntry(BaseModel):
    mode: CompatMode = Field("unrestricted", description="unrestricted | allowlist | blocklist")
    items: List[str] = Field(default_factory=list, description="白名单或黑名单 item_id")

    @model_validator(mode="after")
    def normalize_by_mode(self):
        if self.mode == "unrestricted":
            self.items = []
        elif self.mode == "blocklist" and not self.items:
            # 空排除 ≡ 不限制
            self.mode = "unrestricted"
            self.items = []
        # allowlist + 空 items = 都不兼容（显式保留）
        return self


class DimensionCompatibilities(BaseModel):
    scenes: Optional[DimensionCompatEntry] = None
    lighting: Optional[DimensionCompatEntry] = None
    styles: Optional[DimensionCompatEntry] = None
    compositions: Optional[DimensionCompatEntry] = None
    details: Optional[DimensionCompatEntry] = None
    quality: Optional[DimensionCompatEntry] = None
    viewpoints: Optional[DimensionCompatEntry] = None


class DimensionTypeResponse(BaseModel):
    name: str
    display_name: str


class PromptDimensionBase(BaseModel):
    product_type: str = Field(..., description="产品类型，与素材 category 一致，如 Night Lights, Audio Monitor")
    dimension_type: str = Field(..., description="维度类型，如 scenes, viewpoints")
    name: str = Field(..., description="维度项名称（中文或主语言）")
    name_en: Optional[str] = Field(None, description="英文展示名称（可选）")


class PromptDimensionCreate(PromptDimensionBase):
    item_id: Optional[str] = Field(None, description="维度项ID（创建时忽略，由服务端随机生成）")
    compatibilities: Optional[DimensionCompatibilities] = Field(None, description="兼容性配置")


class PromptDimensionUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    enabled: Optional[bool] = None
    compatibilities: Optional[DimensionCompatibilities] = None


class PromptDimensionResponse(PromptDimensionBase):
    dimension_id: str
    item_id: str
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
