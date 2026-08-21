from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from bebcare.database import Base
import uuid
from datetime import datetime


class StripeCheckoutSession(Base):
    __tablename__ = "stripe_checkout_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_session_id = Column(String(255), nullable=True, unique=True)
    price_id = Column(String(255), nullable=False)
    credits = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending|paid|expired
    grant_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
