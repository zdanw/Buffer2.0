from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

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

class UserLogin(BaseModel):
    username: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    onboarding_completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True