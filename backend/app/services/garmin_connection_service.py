"""Manage per-user Garmin credential storage and client creation."""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.garmin_client import GarminClient
from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.entities import GarminConnection
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
        client = GarminClient(
            tokens_dir=token_store_path,
            email=garmin_email,
            password=garmin_password,
        )
        client.authenticate()
        encrypted_password = encrypt_secret(garmin_password)
        now = eastern_now()

        existing = await self.get_connection(user_id)
        if existing:
            existing.garmin_email = garmin_email
            existing.encrypted_password = encrypted_password
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
                token_store_path=str(token_store_path),
                connected_at=now,
                last_sync_at=now,
                requires_reauth=False,
            )
            self.session.add(connection)
        await self.session.commit()
        return connection

    async def get_client(self, user_id: int) -> GarminClient:
        connection = await self.get_connection(user_id)
        if not connection:
            raise RuntimeError("Garmin connection not found.")
        password = decrypt_secret(connection.encrypted_password)
        return GarminClient(
            tokens_dir=Path(connection.token_store_path),
            email=connection.garmin_email,
            password=password,
        )

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
