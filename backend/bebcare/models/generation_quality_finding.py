from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    Index,
)
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class GenerationArtifactQualityFinding(OwnedMixin, Base):
    """Durable deterministic QA finding. Never stores secrets or image bytes."""

    __tablename__ = "generation_artifact_quality_findings"
    __table_args__ = (
        Index("ix_qa_findings_run", "generation_run_id"),
        Index("ix_qa_findings_artifact", "artifact_id"),
        Index("ix_qa_findings_severity", "severity"),
        Index("ix_qa_findings_stage", "stage"),
        Index("ix_qa_findings_hard", "passed", "severity"),
        Index("ix_qa_findings_owner", "owner_user_id"),
    )

    finding_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id = Column(
        String(36),
        ForeignKey("generation_artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    generation_run_id = Column(
        String(36),
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    stage = Column(String(24), nullable=False)
    check_code = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)
    passed = Column(Boolean, nullable=False, default=True)
    details = Column(JSON, nullable=True)
    policy_version = Column(String(32), nullable=False)
    qa_kind = Column(String(32), nullable=False, default="deterministic")
    confidence = Column(String(16), nullable=True)
    visual_model_version = Column(String(64), nullable=True)
    cache_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
