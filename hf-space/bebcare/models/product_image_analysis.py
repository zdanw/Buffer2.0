from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Index,
    UniqueConstraint,
)
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime


class ProductImageAnalysis(OwnedMixin, Base):
    __tablename__ = "product_image_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "content_hash",
            "schema_version",
            "model_version",
            "offering_context_version",
            name="uq_product_image_analyses_cache_key",
        ),
        Index("ix_product_image_analyses_image", "product_image_id"),
        Index("ix_product_image_analyses_owner", "owner_user_id"),
        Index("ix_product_image_analyses_status", "status"),
        Index(
            "ix_product_image_analyses_cache_identity",
            "content_hash",
            "schema_version",
            "model_version",
            "offering_context_version",
        ),
        Index("ix_product_image_analyses_next_retry_at", "next_retry_at"),
    )

    analysis_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_image_id = Column(
        String(36),
        ForeignKey("product_images.image_id", ondelete="SET NULL"),
        nullable=True,
    )
    content_hash = Column(String(64), nullable=False)
    schema_version = Column(String(32), nullable=False)
    model_version = Column(String(128), nullable=False)
    offering_context_version = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="pending")
    normalized_result = Column(JSON, nullable=True)
    raw_response = Column(Text, nullable=True)
    usage = Column(JSON, nullable=True)
    error_category = Column(String(64), nullable=True)
    failure_type = Column(String(16), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    analyzed_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
