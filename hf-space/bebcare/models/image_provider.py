from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class ImageProviderConfig(OwnedMixin, Base):
    __tablename__ = "image_provider_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
