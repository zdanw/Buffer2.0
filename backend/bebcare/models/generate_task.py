from sqlalchemy import Column, String, DateTime, Integer, JSON
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
from datetime import datetime


class GenerateTask(OwnedMixin, Base):
    """Async content-generation job status (survives process restart)."""

    __tablename__ = "generate_tasks"

    task_id = Column(String(36), primary_key=True)
    status = Column(String(20), nullable=False, default="PENDING")
    progress = Column(Integer, nullable=False, default=0)
    stage = Column(String(50), nullable=True)
    result = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
