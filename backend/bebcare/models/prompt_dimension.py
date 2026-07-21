from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from bebcare.database import Base
import uuid
from datetime import datetime


class DimensionType(str, Enum):
    SCENES = "scenes"
    VIEWPOINTS = "viewpoints"
    COMPOSITIONS = "compositions"
    STYLES = "styles"
    QUALITY = "quality"
    DETAILS = "details"
    LIGHTING = "lighting"

    @property
    def display_name(self):
        names = {
            "scenes": "场景",
            "viewpoints": "视角",
            "compositions": "构图",
            "styles": "风格",
            "quality": "画质",
            "details": "细节",
            "lighting": "光线"
        }
        return names[self.value]


class PromptDimension(Base):
    __tablename__ = "prompt_dimensions"

    dimension_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_type = Column(String(100), nullable=False, index=True)
    dimension_type = Column(String(50), nullable=False, index=True)
    item_id = Column(String(100), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    time = Column(String(50))
    lighting = Column(JSON)
    # False = 禁用，生成/兼容选取时不会使用
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    compatibilities = relationship(
        "PromptDimensionCompatibility",
        back_populates="dimension",
        cascade="all, delete-orphan"
    )


class PromptDimensionCompatibility(Base):
    __tablename__ = "prompt_dimension_compatibilities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dimension_id = Column(String(36), ForeignKey("prompt_dimensions.dimension_id", ondelete="CASCADE"))
    source_dimension_type = Column(String(50), nullable=False)
    target_dimension_type = Column(String(50), nullable=False)
    target_item_id = Column(String(100), nullable=False)
    relation_type = Column(String(20), nullable=False, default="compatible")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dimension = relationship("PromptDimension", back_populates="compatibilities")


class ProductDimension(Base):
    __tablename__ = "product_dimensions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.product_id", ondelete="CASCADE"))
    dimension_id = Column(String(36), ForeignKey("prompt_dimensions.dimension_id", ondelete="SET NULL"))
    dimension_type = Column(String(50), nullable=False)
    item_id = Column(String(100))
    name = Column(String(500))
    time = Column(String(50))
    lighting = Column(JSON)
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)