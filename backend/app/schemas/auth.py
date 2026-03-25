"""Auth-related request/response schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr


class AuthUserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str | None
    role: Literal["admin", "user"]
    email_verified: bool


class AuthMeResponse(BaseModel):
    user: AuthUserResponse | None
