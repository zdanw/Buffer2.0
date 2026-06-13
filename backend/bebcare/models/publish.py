from sqlalchemy import Column, String, Text, DateTime, JSON
from bebcare.database import Base
import uuid
from datetime import datetime

class PublishRecord(Base):
    __tablename__ = "publish_records"
    
    publish_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36))
    product_id = Column(String(36))
    platform = Column(String(50))
    content = Column(JSON)
    status = Column(String(50), default="pending")
    buffer_id = Column(String(255))
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
