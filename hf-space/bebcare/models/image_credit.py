from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from bebcare.database import Base
import uuid
from datetime import datetime


class ImageCreditGrant(Base):
    __tablename__ = "image_credit_grants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(32), nullable=False)  # signup_trial | admin_grant | stripe | wechat
    quantity = Column(Integer, nullable=False)
    remaining = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="active")  # active|exhausted|revoked|expired
    note = Column(Text, nullable=True)
    external_ref = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImageCreditReservation(Base):
    __tablename__ = "image_credit_reservations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generate_task_id = Column(
        String(36),
        ForeignKey("generate_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    grant_id = Column(
        String(36),
        ForeignKey("image_credit_grants.id"),
        nullable=False,
    )
    amount = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="reserved")  # reserved|confirmed|refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
