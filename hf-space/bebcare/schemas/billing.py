from typing import List

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
