from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreditPackOut(BaseModel):
    price_id: str
    credits: int
    label: str
    price_display: str | None = None


class CreditPacksResponse(BaseModel):
    enabled: bool
    packs: List[CreditPackOut]


class CheckoutSessionCreate(BaseModel):
    price_id: str = Field(..., min_length=1)


class CheckoutSessionResponse(BaseModel):
    url: str
    session_id: str


class SubscriptionItemOut(BaseModel):
    stripe_subscription_id: str
    price_id: Optional[str] = None
    label: Optional[str] = None
    status: Optional[str] = None
    cancel_at_period_end: bool = False
    current_period_end: Optional[datetime] = None


class SubscriptionActionRequest(BaseModel):
    stripe_subscription_id: str = Field(..., min_length=1)


class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    status: Optional[str] = None
    cancel_at_period_end: bool = False
    current_period_end: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    price_id: Optional[str] = None
    label: Optional[str] = None
    subscriptions: List[SubscriptionItemOut] = Field(default_factory=list)


class InvoiceOut(BaseModel):
    invoice_id: str
    status: Optional[str] = None
    amount_paid: int = 0
    amount_refunded: int = 0
    currency: Optional[str] = None
    created: Optional[datetime] = None
    hosted_invoice_url: Optional[str] = None
    grant_id: Optional[str] = None
    grant_remaining: int = 0
    refundable: bool = False


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceOut]


class RefundCreate(BaseModel):
    invoice_id: str = Field(..., min_length=1)
    revoke_credits: bool = False


class RefundResponse(BaseModel):
    refund_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    invoice_id: str
    revoked_grant_id: Optional[str] = None
