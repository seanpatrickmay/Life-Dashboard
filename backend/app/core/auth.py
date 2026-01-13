"""Authentication helpers for session-based login."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.entities import User, UserRole, UserSession
from app.db.session import get_session
from app.utils.timezone import eastern_now


SESSION_COOKIE = settings.session_cookie_name


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_ttl(remember_me: bool) -> timedelta:
    if remember_me:
        return timedelta(days=settings.session_ttl_days)
    return timedelta(hours=settings.session_ttl_hours)


async def create_user_session(
    session: AsyncSession, *, user: User, remember_me: bool
) -> str:
    token = secrets.token_urlsafe(48)
    now = eastern_now()
    expires_at = now + _session_ttl(remember_me)
    session_obj = UserSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
        last_seen_at=now,
        remember_me=remember_me,
    )
    session.add(session_obj)
    await session.commit()
    return token


def set_session_cookie(response: Response, token: str, *, remember_me: bool) -> None:
    max_age = int(_session_ttl(remember_me).total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        domain=settings.session_cookie_domain,
    )


async def get_current_session(
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(None, alias=SESSION_COOKIE),
) -> UserSession:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_hash = _hash_token(token)
    stmt = (
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.token_hash == token_hash)
    )
    result = await session.execute(stmt)
    session_obj = result.scalar_one_or_none()
    now = eastern_now()
    if not session_obj or session_obj.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if session_obj.expires_at <= now:
        session_obj.revoked_at = now
        await session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session_obj


async def get_current_user(
    session_obj: UserSession = Depends(get_current_session),
) -> User:
    return session_obj.user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
