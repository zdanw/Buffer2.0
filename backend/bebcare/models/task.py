from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, Integer, ForeignKey
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime

class ScheduledTask(OwnedMixin, Base):
    __tablename__ = "scheduled_tasks"
    
    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    cron = Column(String(100), nullable=False)
    mode = Column(String(20), default="auto")
    target_categories = Column(JSON)
    target_products = Column(JSON)
    platforms = Column(JSON)
    reference_image_count = Column(Integer, default=2)
    run_count_per_execution = Column(Integer, default=1)
    generate_image_count = Column(Integer, default=1)
    generate_copy_count = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    use_scene_reference = Column(Boolean, default=False)
    use_vision_image_prompt = Column(Boolean, default=False)
    image_provider_id = Column(String(36), nullable=True)
    image_model = Column(String(255), nullable=True)
    image_size = Column(String(32), nullable=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskExecution(OwnedMixin, Base):
    __tablename__ = "task_executions"
    
    execution_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scheduled_tasks.task_id", ondelete="CASCADE"))
    product_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False)
    error_message = Column(Text)
    generated_images = Column(JSON)
    published_platforms = Column(JSON)
    copywriting = Column(Text)
    dimensions = Column(JSON)
    image_prompt = Column(Text)
    reference_product_images = Column(JSON)
    reference_scene_images = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ManualTaskDraft(OwnedMixin, Base):
    __tablename__ = "manual_task_drafts"
    
    draft_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scheduled_tasks.task_id", ondelete="CASCADE"))
    product_id = Column(String(36))
    images = Column(JSON)
    copywritings = Column(JSON)
    dimensions = Column(JSON)
    image_prompts = Column(JSON)
    reference_product_images = Column(JSON)
    reference_scene_images = Column(JSON)
    status = Column(String(20), default="pending")
    selected_image = Column(Text)
    selected_copy = Column(Text)
    published_platforms = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
