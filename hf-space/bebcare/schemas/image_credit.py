from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreditGrantCreate(BaseModel):
    quantity: int = Field(..., ge=1)
    note: Optional[str] = None


class CreditGrantResponse(BaseModel):
    id: str
    user_id: str
    source: str
    quantity: int
    remaining: int
    status: str
    note: Optional[str] = None
    external_ref: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreditGrantListResponse(BaseModel):
    remaining_total: int
    grants: List[CreditGrantResponse]
