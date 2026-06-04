"""Tests for lazy, env-profiled DB engine (Task 2.1).

Test coverage:
1. _engine_kwargs — local profile yields 5/5 pool; aws profile yields 2/2 + recycle=300.
2. get_engine() memoization — same object on repeated calls; new object after init_engine().
3. Backward compat — `from app.db.session import engine, AsyncSessionLocal` both resolve.
4. get_session() — yields a working AsyncSession (trivial SELECT 1 against SQLite).

Engine-leak strategy:
- All tests that build an extra engine call `await engine.dispose()` after use.
- An autouse fixture resets the module-level _engine/_sessionmaker before and after
  each test so the memoized state from one test never pollutes another.
- The conftest DATABASE_URL is sqlite+aiosqlite, so no Postgres connection is needed.
"""
from __future__ import annotations


import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession



# ---------------------------------------------------------------------------
# Autouse fixture — reset module singletons around every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_session_module():
    """Reset the lazy engine/sessionmaker globals before and after each test.

    This prevents memoized state from one test leaking into the next and
    ensures each test starts with a clean slate without touching conftest.
    """
    import app.db.session as session_mod
    # Reset before
    session_mod._engine = None
    session_mod._sessionmaker = None
    yield
    # Reset after (dispose any engine that was created during the test)
    if session_mod._engine is not None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an async test — schedule disposal as a fire-and-forget
                loop.create_task(session_mod._engine.dispose())
            else:
                loop.run_until_complete(session_mod._engine.dispose())
        except RuntimeError:
            pass
    session_mod._engine = None
    session_mod._sessionmaker = None


# ---------------------------------------------------------------------------
# 1. _engine_kwargs profile tests
# ---------------------------------------------------------------------------

class _StubSettings:
    """Minimal Settings-like stub for testing _engine_kwargs without env setup."""

    def __init__(self, ld_runtime: str, database_url: str = "sqlite+aiosqlite:///test.db",
                 database_pool_pre_ping: bool = True,
                 database_pool_recycle_seconds: int = 1800,
                 database_pool_use_lifo: bool = True) -> None:
        self.ld_runtime = ld_runtime
        self.database_url = database_url
        self.database_pool_pre_ping = database_pool_pre_ping
        self.database_pool_recycle_seconds = database_pool_recycle_seconds
        self.database_pool_use_lifo = database_pool_use_lifo


def test_engine_kwargs_local_profile():
    """Local profile (ld_runtime='local') produces the current EC2/test 5/5 pool."""
    from app.db.session import _engine_kwargs

    stub = _StubSettings(ld_runtime="local")
    kwargs = _engine_kwargs(stub)  # type: ignore[arg-type]

    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 5
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_use_lifo"] is True
    assert kwargs["connect_args"] == {}  # SQLite stub — no postgres


def test_engine_kwargs_aws_profile():
    """AWS profile (ld_runtime='aws') produces lean 2/2 pool with recycle=300."""
    from app.db.session import _engine_kwargs

    stub = _StubSettings(ld_runtime="aws")
    kwargs = _engine_kwargs(stub)  # type: ignore[arg-type]

    assert kwargs["pool_size"] == 2
    assert kwargs["max_overflow"] == 2
    assert kwargs["pool_recycle"] == 300


def test_engine_kwargs_aws_profile_with_postgres_connect_args():
    """AWS profile with a postgres URL includes the expected connect_args."""
    from app.db.session import _engine_kwargs

    stub = _StubSettings(
        ld_runtime="aws",
        database_url="postgresql+asyncpg://user:pass@host/db",
    )
    kwargs = _engine_kwargs(stub)  # type: ignore[arg-type]

    assert kwargs["connect_args"] == {"server_settings": {"jit": "off"}, "command_timeout": 60}


def test_engine_kwargs_local_profile_with_postgres_connect_args():
    """Local profile with a postgres URL also includes connect_args (unchanged behavior)."""
    from app.db.session import _engine_kwargs

    stub = _StubSettings(
        ld_runtime="local",
        database_url="postgresql+asyncpg://user:pass@host/db",
    )
    kwargs = _engine_kwargs(stub)  # type: ignore[arg-type]

    assert kwargs["connect_args"] == {"server_settings": {"jit": "off"}, "command_timeout": 60}
    assert kwargs["pool_size"] == 5


# ---------------------------------------------------------------------------
# 2. Memoization — get_engine() / get_sessionmaker() / init_engine()
# ---------------------------------------------------------------------------

def test_get_engine_returns_same_object():
    """get_engine() is memoized — repeated calls return the identical object."""
    from app.db.session import get_engine

    e1 = get_engine()
    e2 = get_engine()
    assert e1 is e2


def test_get_sessionmaker_returns_same_object():
    """get_sessionmaker() is memoized — repeated calls return the identical object."""
    from app.db.session import get_sessionmaker

    sm1 = get_sessionmaker()
    sm2 = get_sessionmaker()
    assert sm1 is sm2


@pytest.mark.asyncio
async def test_init_engine_returns_new_object():
    """init_engine() resets singletons so the next get_engine() returns a new object."""
    from app.db.session import get_engine, init_engine

    e1 = get_engine()
    new_engine = init_engine()  # resets and rebuilds
    assert new_engine is not e1

    # Verify the singleton was replaced
    e2 = get_engine()
    assert e2 is new_engine

    # Clean up both engines
    await e1.dispose()
    await new_engine.dispose()


# ---------------------------------------------------------------------------
# 3. Backward compat — module __getattr__
# ---------------------------------------------------------------------------

def test_backward_compat_engine_import():
    """from app.db.session import engine must resolve to an AsyncEngine."""
    from app.db.session import engine  # type: ignore[attr-defined]

    assert isinstance(engine, AsyncEngine)


def test_backward_compat_async_session_local_import():
    """from app.db.session import AsyncSessionLocal must be callable."""
    from app.db.session import AsyncSessionLocal  # type: ignore[attr-defined]

    assert callable(AsyncSessionLocal)


def test_backward_compat_engine_module_attr():
    """session_mod.engine attribute access (used by monkeypatch) also works."""
    import app.db.session as session_mod

    engine = session_mod.engine  # triggers __getattr__
    assert isinstance(engine, AsyncEngine)


def test_unknown_attr_raises_attribute_error():
    """Accessing a non-existent attribute raises AttributeError (not infinite loop)."""
    import app.db.session as session_mod

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = session_mod.nonexistent_name_xyz  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 4. get_session() — functional test against SQLite
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_yields_async_session(monkeypatch):
    """get_session() yields a working AsyncSession; SELECT 1 succeeds.

    Uses monkeypatch to pin DATABASE_URL to SQLite so this test is not
    affected by other test modules that set os.environ["DATABASE_URL"] to
    a Postgres URL at module level (e.g. test_garmin_crypto.py).
    """
    from sqlalchemy import text

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test_session.db")

    from app.db.session import get_session, init_engine

    # Rebuild the engine with the patched DATABASE_URL
    init_engine()

    # get_session is an async generator — drive it manually
    gen = get_session()
    session: AsyncSession = await gen.__anext__()
    try:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        # Close the generator (triggers context manager __aexit__)
        try:
            await gen.aclose()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_session_can_be_used_as_dependency(monkeypatch):
    """get_session() can be iterated with async for (FastAPI dependency pattern)."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test_session.db")

    from app.db.session import get_session, init_engine

    init_engine()

    sessions_yielded: list[AsyncSession] = []
    async for session in get_session():
        sessions_yielded.append(session)

    assert len(sessions_yielded) == 1
    assert isinstance(sessions_yielded[0], AsyncSession)


# ---------------------------------------------------------------------------
# 5. Monkeypatching compat — setattr on the module still works
#    (critical for test_jobs_handlers.py which does
#     monkeypatch.setattr(session_mod, "AsyncSessionLocal", FakeSessionCtx))
# ---------------------------------------------------------------------------

def test_monkeypatch_setattr_overrides_getattr():
    """Setting AsyncSessionLocal directly on the module hides __getattr__."""
    import app.db.session as session_mod

    class FakeSM:
        pass

    original = getattr(session_mod, "__dict__", {}).get("AsyncSessionLocal")
    try:
        session_mod.AsyncSessionLocal = FakeSM  # type: ignore[attr-defined]
        # After setattr, __dict__ has the key so __getattr__ is NOT called
        assert session_mod.AsyncSessionLocal is FakeSM
    finally:
        # Clean up — remove the patched attr so __getattr__ takes over again
        if original is None:
            try:
                delattr(session_mod, "AsyncSessionLocal")
            except AttributeError:
                pass
        else:
            session_mod.AsyncSessionLocal = original  # type: ignore[attr-defined]
