from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from bebcare.database import Base
import uuid
from datetime import datetime

# Stable IDs for system brands (seed + migrations)
GENERIC_BRAND_ID = "00000000-0000-0000-0000-000000000001"
BEBCARE_BRAND_ID = "00000000-0000-0000-0000-000000000002"


class Brand(Base):
    """Reusable brand kit: voice, prompt skills, and vertical defaults."""

    __tablename__ = "brands"

    brand_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    is_generic = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)

    voice = Column(Text)
    audience = Column(Text)
    tone_keywords = Column(String(500))
    default_selling_points = Column(JSON)  # list[str]
    default_hashtags = Column(JSON)  # list[str]
    emoji_style = Column(String(32), default="moderate")
    words_to_avoid = Column(Text)
    logo_url = Column(String(500))
    logo_font_rule = Column(Text)
    vertical_pack = Column(String(64), default="general")
    default_product_type = Column(String(100))

    # Prompt skills (preserved from legacy hard-coded engine)
    copy_system_prompt = Column(Text)
    image_system_prompt = Column(Text)
    vision_image_system_prompt = Column(Text)
    vision_scene_system_prompt = Column(Text)
    narrative_perspectives = Column(JSON)  # list[{id,name,description}]
    writing_styles = Column(JSON)  # list[{id,name,description}]
    copy_emoji_hints = Column(String(200))
    copy_example = Column(Text)
    image_fallback_selling_points = Column(String(500))
    copy_fallback_selling_points = Column(JSON)  # list[str]

    extra = Column(JSON)  # product types, notes, export metadata

    buffer_account_id = Column(
        String(36),
        ForeignKey("buffer_accounts.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="brand")
    buffer_account = relationship("BufferAccount", back_populates="brands")
