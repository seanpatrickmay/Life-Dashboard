"""Auth-related request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class AuthUserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str | None
    role: str
    email_verified: bool


class AuthMeResponse(BaseModel):
    user: AuthUserResponse
