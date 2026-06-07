"""Manage per-user Garmin credential storage and client creation."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.garmin_client import GarminClient
from app.core.config import settings
from app.core.crypto import (
    current_garmin_encryption_key_id,
    decrypt_secret_with_context,
    encrypt_secret,
)
from app.db.models.entities import GarminConnection
from app.services.garmin_token_store import garmin_token_dir
from app.utils.timezone import eastern_now


class GarminConnectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_connection(self, user_id: int) -> GarminConnection | None:
        stmt = select(GarminConnection).where(GarminConnection.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def connect(
        self, *, user_id: int, garmin_email: str, garmin_password: str
    ) -> GarminConnection:
        token_store_path = self._token_store_path(user_id)
        # Request-scoped sessions may already have an open read transaction from auth.
        await self.session.rollback()
        async with garmin_token_dir(self.session, user_id) as tok_dir:
            client = GarminClient(
                tokens_dir=tok_dir if tok_dir is not None else token_store_path,
                email=garmin_email,
                password=garmin_password,
            )
            await asyncio.to_thread(client.authenticate)
        encrypted_password = encrypt_secret(garmin_password)
        now = eastern_now()

        existing = await self.get_connection(user_id)
        if existing:
            existing.garmin_email = garmin_email
            existing.encrypted_password = encrypted_password
            existing.encryption_key_id = current_garmin_encryption_key_id()
            existing.token_store_path = str(token_store_path)
            existing.connected_at = now
            existing.last_sync_at = now
            existing.requires_reauth = False
            connection = existing
        else:
            connection = GarminConnection(
                user_id=user_id,
                garmin_email=garmin_email,
                encrypted_password=encrypted_password,
                encryption_key_id=current_garmin_encryption_key_id(),
                token_store_path=str(token_store_path),
                connected_at=now,
                last_sync_at=now,
                requires_reauth=False,
            )
            self.session.add(connection)
        await self.session.commit()
        return connection

    async def get_client(self, user_id: int) -> GarminClient:
        """Return a GarminClient for legacy callers (dir mode only).

        In db mode prefer ``get_client_ctx`` so token persist/cleanup is automatic.
        This method remains for backward compat: in db mode it still hydrates a temp
        dir but cleanup + persist are the caller's responsibility.
        """
        connection = await self.get_connection(user_id)
        if not connection:
            raise RuntimeError("Garmin connection not found.")
        try:
            password, used_fallback_key = decrypt_secret_with_context(connection.encrypted_password)
        except ValueError:
            connection.requires_reauth = True
            connection.last_sync_at = eastern_now()
            await self.session.commit()
            raise
        current_key_id = current_garmin_encryption_key_id()
        if used_fallback_key or connection.encryption_key_id != current_key_id:
            connection.encrypted_password = encrypt_secret(password)
            connection.encryption_key_id = current_key_id
            connection.requires_reauth = False
            await self.session.commit()
        return GarminClient(
            tokens_dir=Path(connection.token_store_path),
            email=connection.garmin_email,
            password=password,
        )

    @asynccontextmanager
    async def get_client_ctx(self, user_id: int) -> AsyncIterator[GarminClient]:
        """Async context manager yielding a GarminClient with automatic token persist/cleanup.

        db mode: hydrates tokens from DB → yields client → persists refreshed tokens → cleans up.
        dir mode: yields a client using the filesystem token_store_path (legacy; no DB interaction).

        Usage::

            async with service.get_client_ctx(user_id) as client:
                await asyncio.to_thread(client.authenticate)
                ...
        """
        connection = await self.get_connection(user_id)
        if not connection:
            raise RuntimeError("Garmin connection not found.")
        try:
            password, used_fallback_key = decrypt_secret_with_context(
                connection.encrypted_password
            )
        except ValueError:
            connection.requires_reauth = True
            connection.last_sync_at = eastern_now()
            await self.session.commit()
            raise
        current_key_id = current_garmin_encryption_key_id()
        if used_fallback_key or connection.encryption_key_id != current_key_id:
            connection.encrypted_password = encrypt_secret(password)
            connection.encryption_key_id = current_key_id
            connection.requires_reauth = False
            await self.session.commit()

        async with garmin_token_dir(self.session, user_id) as tok_dir:
            client = GarminClient(
                tokens_dir=tok_dir if tok_dir is not None else Path(connection.token_store_path),
                email=connection.garmin_email,
                password=password,
            )
            yield client

    async def mark_reauth_required(self, user_id: int, required: bool = True) -> None:
        connection = await self.get_connection(user_id)
        if not connection:
            return
        connection.requires_reauth = required
        connection.last_sync_at = eastern_now()
        await self.session.commit()
        logger.info("Updated Garmin reauth status for user {} -> {}", user_id, required)

    @staticmethod
    def _token_store_path(user_id: int) -> Path:
        root = Path(settings.garmin_tokens_dir).expanduser()
        return root / str(user_id)
