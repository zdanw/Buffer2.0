from sqlalchemy import Column, String, Text, DateTime, JSON
from bebcare.database import Base
import uuid
from datetime import datetime

class OperationLog(Base):
    __tablename__ = "operation_logs"
    
    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    level = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    context = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
