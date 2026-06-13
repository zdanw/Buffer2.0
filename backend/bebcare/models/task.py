from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, Integer
from bebcare.database import Base
import uuid
from datetime import datetime

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    
    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    cron = Column(String(100), nullable=False)
    target_categories = Column(JSON)
    target_products = Column(JSON)
    platforms = Column(JSON)
    reference_image_count = Column(Integer, default=3)
    run_count_per_execution = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
