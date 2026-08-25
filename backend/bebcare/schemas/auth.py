from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=6)
    is_admin: bool = False


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class MeUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    current_password: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OnboardingRewardResponse(BaseModel):
    granted: int
    already_claimed: bool
    image_credits_remaining: int


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    onboarding_completed_at: Optional[datetime] = None
    has_generated_content: bool = False
    onboarding_reward_claimed: bool = False
    image_credits_remaining: int = 0
    has_system_image_provider: bool = False
    billing_contact: Optional[str] = None
    billing_enabled: bool = False

    class Config:
        from_attributes = True
