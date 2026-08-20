from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, ForeignKey
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class ImageProviderConfig(OwnedMixin, Base):
    __tablename__ = "image_provider_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # System (platform) rows may have owner_user_id NULL; BYOK rows must set it.
    owner_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False)  # openai_compatible | doubao_ark | aliyun_maas | google_gemini
    base_url = Column(String(512), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    supports_list_models = Column(Boolean, default=True)
    default_model = Column(String(255))
    manual_models = Column(JSON)  # [{"id": "qwen-image-2.0", "description": "..."}, ...]
    extra_headers = Column(JSON)
    extra_params = Column(JSON)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
