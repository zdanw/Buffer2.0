from sqlalchemy import Column, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class BufferAccount(OwnedMixin, Base):
    """Buffer API account: encrypted token + brand bindings."""

    __tablename__ = "buffer_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    api_token_encrypted = Column(Text, nullable=False)
    buffer_email = Column(String(255), nullable=True)
    buffer_remote_id = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    brands = relationship("Brand", back_populates="buffer_account")
