from sqlalchemy import Column, String, DateTime, JSON
from bebcare.database import Base
from datetime import datetime


class GenerateTask(Base):
    """Async content-generation job status (survives process restart)."""

    __tablename__ = "generate_tasks"

    task_id = Column(String(36), primary_key=True)
    status = Column(String(20), nullable=False, default="PENDING")
    result = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
