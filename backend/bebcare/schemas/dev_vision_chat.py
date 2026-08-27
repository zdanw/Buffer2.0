from typing import Literal, Optional

from pydantic import BaseModel, Field


class VisionChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class VisionChatRequest(BaseModel):
    messages: list[VisionChatMessage] = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=8192)


class VisionChatResponse(BaseModel):
    content: str
    model: str
    finish_reason: Optional[str] = None


class VisionImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    size: str = Field(default="1024x1024")
    image_urls: list[str] = Field(default_factory=list)


class VisionImageResponse(BaseModel):
    model: str
    image_urls: list[str]


class VisionChatConfigResponse(BaseModel):
    enabled: bool
    chat_model: str
    chat_api_url: str
    image_model: str
    image_api_url: str
