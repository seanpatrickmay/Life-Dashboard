from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.session import get_session
from app.schemas.garmin import (
    GarminConnectRequest,
    GarminConnectResponse,
    GarminStatusResponse,
)
from app.services.garmin_connection_service import GarminConnectionService
from app.utils.timezone import eastern_now

router = APIRouter(prefix="/garmin", tags=["garmin"])


@router.get("/status", response_model=GarminStatusResponse)
async def garmin_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GarminStatusResponse:
    service = GarminConnectionService(session)
    connection = await service.get_connection(current_user.id)
    if not connection:
        return GarminStatusResponse(
            connected=False,
            garmin_email=None,
            connected_at=None,
            last_sync_at=None,
            requires_reauth=False,
        )
    return GarminStatusResponse(
        connected=True,
        garmin_email=connection.garmin_email,
        connected_at=connection.connected_at,
        last_sync_at=connection.last_sync_at,
        requires_reauth=connection.requires_reauth,
    )


@router.post("/connect", response_model=GarminConnectResponse)
async def connect_garmin(
    payload: GarminConnectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GarminConnectResponse:
    service = GarminConnectionService(session)
    try:
        connection = await service.connect(
            user_id=current_user.id,
            garmin_email=str(payload.garmin_email),
            garmin_password=payload.garmin_password,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to authenticate with Garmin.",
        ) from exc
    return GarminConnectResponse(
        connected=True,
        garmin_email=connection.garmin_email,
        connected_at=connection.connected_at,
        requires_reauth=connection.requires_reauth,
    )


@router.post("/reauth", response_model=GarminStatusResponse)
async def reauth_garmin(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GarminStatusResponse:
    service = GarminConnectionService(session)
    connection = await service.get_connection(current_user.id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Garmin not connected.")
    try:
        client = await service.get_client(current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stored Garmin credentials could not be decrypted.",
        ) from exc
    try:
        client.authenticate()
    except Exception as exc:  # noqa: BLE001
        await service.mark_reauth_required(current_user.id, True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin re-authentication failed.",
        ) from exc
    connection.last_sync_at = eastern_now()
    connection.requires_reauth = False
    await session.commit()
    return GarminStatusResponse(
        connected=True,
        garmin_email=connection.garmin_email,
        connected_at=connection.connected_at,
        last_sync_at=connection.last_sync_at,
        requires_reauth=connection.requires_reauth,
    )
