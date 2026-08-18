"""Auth related schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, max_length=200)


class UserResponse(BaseModel):
    id: int
    public_id: str
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    role: str
    provider: str

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
