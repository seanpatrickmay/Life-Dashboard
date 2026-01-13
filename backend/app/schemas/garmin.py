"""Garmin connection schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class GarminConnectRequest(BaseModel):
    garmin_email: EmailStr
    garmin_password: str = Field(min_length=6)


class GarminStatusResponse(BaseModel):
    connected: bool
    garmin_email: EmailStr | None
    connected_at: datetime | None
    last_sync_at: datetime | None
    requires_reauth: bool


class GarminConnectResponse(BaseModel):
    connected: bool
    garmin_email: EmailStr
    connected_at: datetime
    requires_reauth: bool
