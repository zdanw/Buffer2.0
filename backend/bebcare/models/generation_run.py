from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class GenerationRun(OwnedMixin, Base):
    """One requested image-generation workflow (durable provenance)."""

    __tablename__ = "generation_runs"
    __table_args__ = (
        Index("ix_generation_runs_owner_created", "owner_user_id", "created_at"),
        Index("ix_generation_runs_product_created", "product_id", "created_at"),
        Index("ix_generation_runs_compare_group", "compare_group_id"),
        Index("ix_generation_runs_experiment", "experiment_variant"),
        Index("ix_generation_runs_generate_task", "generate_task_id"),
    )

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(32), nullable=False)
    product_id = Column(
        String(36),
        ForeignKey("products.product_id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_task_id = Column(
        String(36),
        ForeignKey("scheduled_tasks.task_id", ondelete="SET NULL"),
        nullable=True,
    )
    generate_task_id = Column(
        String(36),
        ForeignKey("generate_tasks.task_id", ondelete="SET NULL"),
        nullable=True,
    )
    rollout_mode_at_start = Column(String(32), nullable=False)
    experiment_variant = Column(String(64), nullable=True)
    requested_pipeline_version = Column(String(64), nullable=False)
    executed_pipeline_version = Column(String(64), nullable=False)
    fallback_reason = Column(Text, nullable=True)
    fallback_path = Column(String(64), nullable=True)
    image_prompt_pipeline = Column(String(32), nullable=True)
    compare_group_id = Column(String(36), nullable=True)
    reference_manifest = Column(JSON, nullable=True)
    provider_type = Column(String(32), nullable=True)
    provider_id = Column(String(36), nullable=True)
    model = Column(String(128), nullable=True)
    image_size = Column(String(32), nullable=True)
    image_provider_mode = Column(String(16), nullable=True)
    status = Column(String(24), nullable=False, default="pending")
    error_category = Column(String(64), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=True)
    credits_charged = Column(Integer, nullable=False, default=0)
    provider_usage = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    artifacts = relationship(
        "GenerationArtifact",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    product = relationship("Product")


class GenerationArtifact(OwnedMixin, Base):
    """One candidate image returned for a generation run."""

    __tablename__ = "generation_artifacts"
    __table_args__ = (Index("ix_generation_artifacts_run", "run_id"),)

    artifact_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(
        String(36),
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_index = Column(Integer, nullable=False, default=0)
    cdn_url = Column(String(500), nullable=False)
    selected = Column(Boolean, nullable=False, default=False)
    persistence_warning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("GenerationRun", back_populates="artifacts")
