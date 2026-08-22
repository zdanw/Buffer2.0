from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from bebcare.database import Base
import uuid
from datetime import datetime


class StripeSubscription(Base):
    __tablename__ = "stripe_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), nullable=False, unique=True)
    price_id = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
