"""Manage Google Calendar OAuth connections and token refresh."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_calendar_token, encrypt_calendar_token
from app.db.models.calendar import GoogleCalendarConnection


GOOGLE_CALENDAR_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]


class GoogleCalendarConnectionService:
    """Persist and refresh per-user Google Calendar OAuth credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_connection(self, user_id: int) -> GoogleCalendarConnection | None:
        """Return the stored Google Calendar connection for a user, if any."""
        stmt = select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def store_tokens(
        self, *, user_id: int, tokens: dict[str, Any]
    ) -> GoogleCalendarConnection:
        """Persist OAuth tokens for a user and refresh cached account metadata."""
        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("Access token missing from Google response.")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")
        scope = tokens.get("scope")
        expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            if expires_in
            else None
        )

        existing = await self.get_connection(user_id)
        encrypted_access = encrypt_calendar_token(access_token)
        encrypted_refresh = encrypt_calendar_token(refresh_token) if refresh_token else None
        if existing:
            existing.encrypted_access_token = encrypted_access
            if encrypted_refresh:
                existing.encrypted_refresh_token = encrypted_refresh
            existing.token_expiry = expiry
            existing.scopes = scope
            existing.requires_reauth = False
            connection = existing
        else:
            connection = GoogleCalendarConnection(
                user_id=user_id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expiry=expiry,
                scopes=scope,
                requires_reauth=False,
            )
            self.session.add(connection)

        account_email = await self._fetch_account_email(access_token)
        if account_email:
            connection.account_email = account_email

        await self.session.commit()
        return connection

    async def get_access_token(self, user_id: int) -> str | None:
        """Return a valid access token, refreshing when nearing expiry."""
        connection = await self.get_connection(user_id)
        if not connection:
            return None
        if connection.requires_reauth:
            return None
        if connection.token_expiry and connection.token_expiry <= datetime.now(timezone.utc) + timedelta(
            minutes=1
        ):
            return await self.refresh_access_token(connection)
        try:
            return decrypt_calendar_token(connection.encrypted_access_token)
        except ValueError:
            await self.mark_reauth_required(user_id)
            return None

    async def refresh_access_token(self, connection: GoogleCalendarConnection) -> str | None:
        """Refresh the access token using the stored refresh token."""
        refresh_token = connection.encrypted_refresh_token
        if not refresh_token:
            await self.mark_reauth_required(connection.user_id)
            return None
        try:
            decrypted_refresh = decrypt_calendar_token(refresh_token)
        except ValueError:
            await self.mark_reauth_required(connection.user_id)
            return None
        payload = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": decrypted_refresh,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post("https://oauth2.googleapis.com/token", data=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Failed to refresh Google Calendar token for user {}: {}", connection.user_id, exc)
            await self.mark_reauth_required(connection.user_id)
            return None

        access_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not access_token:
            await self.mark_reauth_required(connection.user_id)
            return None
        connection.encrypted_access_token = encrypt_calendar_token(access_token)
        connection.token_expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            if expires_in
            else None
        )
        connection.requires_reauth = False
        await self.session.commit()
        return access_token

    async def mark_reauth_required(self, user_id: int, required: bool = True) -> None:
        """Flag the connection as requiring re-authentication."""
        connection = await self.get_connection(user_id)
        if not connection:
            return
        connection.requires_reauth = required
        await self.session.commit()

    async def _fetch_account_email(self, access_token: str) -> str | None:
        """Return the email associated with the provided access token, if available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("email")
        except Exception as exc:
            logger.warning("Unable to fetch Google Calendar account email: {}", exc)
            return None
