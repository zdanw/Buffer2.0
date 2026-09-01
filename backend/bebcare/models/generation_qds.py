from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Index, UniqueConstraint
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class GenerationReferenceSelection(OwnedMixin, Base):
    """One QDS (or grounded) reference selection for a generation run."""

    __tablename__ = "generation_reference_selections"
    __table_args__ = (
        UniqueConstraint("generation_run_id", name="uq_qds_selection_run"),
        Index("ix_qds_selection_owner_created", "owner_user_id", "created_at"),
        Index("ix_qds_selection_run", "generation_run_id"),
    )

    selection_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generation_run_id = Column(
        String(36),
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    selector_version = Column(String(64), nullable=False)
    seed = Column(String(64), nullable=True)
    strategy = Column(String(64), nullable=False)
    requested_strategy = Column(String(64), nullable=True)
    executed_strategy = Column(String(64), nullable=False)
    risk_profile = Column(String(24), nullable=True)
    coverage_class = Column(String(24), nullable=True)
    selected_primary_image_id = Column(String(36), nullable=True)
    selected_scene_image_id = Column(String(36), nullable=True)
    candidate_summary = Column(JSON, nullable=True)
    selected_manifest = Column(JSON, nullable=True)
    fingerprint = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GenerationDecisionEvent(OwnedMixin, Base):
    """Material generation-decision event. No secrets, bytes, or raw provider payloads."""

    __tablename__ = "generation_decision_events"
    __table_args__ = (
        UniqueConstraint(
            "generation_run_id",
            "sequence_number",
            name="uq_decision_event_run_seq",
        ),
        Index("ix_decision_event_run", "generation_run_id"),
        Index("ix_decision_event_owner", "owner_user_id"),
        Index("ix_decision_event_type", "event_type"),
        Index("ix_decision_event_created", "created_at"),
    )

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generation_run_id = Column(
        String(36),
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    generation_artifact_id = Column(
        String(36),
        ForeignKey("generation_artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    sequence_number = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False)
    stage = Column(String(24), nullable=False, default="select")
    outcome = Column(String(24), nullable=True)
    severity = Column(String(16), nullable=False, default="info")
    policy_name = Column(String(64), nullable=True)
    policy_version = Column(String(32), nullable=True)
    summary = Column(String(500), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
