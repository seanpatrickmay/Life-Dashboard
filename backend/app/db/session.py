"""Database session and engine management."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,  # Turn off SQL logging for speed
    future=True,
    pool_size=5,  # Optimized for single user (was 20)
    max_overflow=5,  # Less overflow needed (was 30)
    pool_pre_ping=settings.database_pool_pre_ping,
    pool_recycle=settings.database_pool_recycle_seconds,
    pool_use_lifo=settings.database_pool_use_lifo,
    connect_args={
        "server_settings": {
            "jit": "off",  # Disable JIT for faster short queries
        },
        "command_timeout": 60,
    } if "postgresql" in settings.database_url else {}
)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
