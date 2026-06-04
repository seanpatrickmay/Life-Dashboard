"""Database session and engine management — lazy, env-profiled for Lambda cold-start."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def _engine_kwargs(s: Settings) -> dict:
    """Return SQLAlchemy engine kwargs tuned for the active runtime profile.

    AWS/Lambda profile uses NullPool — no connections are cached across
    invocations.  Each Lambda invocation creates a fresh event loop via
    asyncio.run(), and asyncpg connections are bound to the loop that
    created them; reusing a pooled connection on the next warm invocation
    points at a closed loop ("Event loop is closed" / "attached to a
    different loop").  NullPool avoids this entirely; Neon's PgBouncer
    makes per-invocation connection setup cheap.
    """
    connect_args = (
        {"server_settings": {"jit": "off"}, "command_timeout": 60}
        if "postgresql" in s.database_url
        else {}
    )
    if s.ld_runtime == "aws":
        return dict(
            echo=False,
            future=True,
            poolclass=NullPool,
            connect_args=connect_args,
        )
    return dict(
        echo=False,
        future=True,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=s.database_pool_pre_ping,
        pool_recycle=s.database_pool_recycle_seconds,
        pool_use_lifo=s.database_pool_use_lifo,
        connect_args=connect_args,
    )


# Module-level singletons — None until first access (lazy).
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the shared engine, building it on the first call."""
    global _engine
    if _engine is None:
        s = Settings()
        _engine = create_async_engine(s.database_url, **_engine_kwargs(s))
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the shared sessionmaker, building it on the first call."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


def init_engine() -> AsyncEngine:
    """Reset and rebuild the engine and sessionmaker (call after env/secrets are loaded).

    Intended for Lambda cold-start handlers that set env vars or inject secrets
    before the first DB connection is opened.
    """
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None
    return get_engine()


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields an AsyncSession."""
    async with get_sessionmaker()() as session:
        yield session


# ---------------------------------------------------------------------------
# PEP 562 — lazy module attribute access for backward compatibility.
#
# Many modules do:
#   from app.db.session import engine
#   from app.db.session import AsyncSessionLocal
#
# `from x import name` resolves via __getattr__ when the name is absent from
# the module's __dict__, so removing the eager globals and routing through
# __getattr__ preserves the public API without eagerly building the engine at
# import time.
# ---------------------------------------------------------------------------

def __getattr__(name: str) -> object:
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
