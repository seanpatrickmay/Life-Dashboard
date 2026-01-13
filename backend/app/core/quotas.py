"""Quota enforcement helpers."""
from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import ChatUsage, User, UserRole
from app.db.session import get_session
from app.utils.timezone import eastern_midnight, eastern_now, eastern_today

CHAT_DAILY_LIMIT = 3


async def enforce_chat_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    if user.role == UserRole.ADMIN:
        return user

    today = eastern_today()
    stmt = select(ChatUsage).where(ChatUsage.user_id == user.id, ChatUsage.usage_date == today)
    result = await session.execute(stmt)
    usage = result.scalar_one_or_none()
    if usage and usage.count >= CHAT_DAILY_LIMIT:
        reset_at = eastern_midnight(today + timedelta(days=1))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Daily chat limit reached.",
                "limit": CHAT_DAILY_LIMIT,
                "remaining": 0,
                "reset_at": reset_at.isoformat(),
            },
        )

    now = eastern_now()
    if usage:
        usage.count += 1
        usage.last_request_at = now
    else:
        usage = ChatUsage(
            user_id=user.id,
            usage_date=today,
            count=1,
            last_request_at=now,
        )
        session.add(usage)
    await session.commit()
    return user
