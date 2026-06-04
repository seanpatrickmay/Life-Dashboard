"""Tests for the garmin_token_dir async context manager.

Exercises the three scenarios:
  - db mode, existing row: hydrate → yield → modify → persist round-trip
  - db mode, no row: fresh empty dir → write token → persist first-time
  - dir mode (LD_GARMIN_TOKENS != "db"): yields None, no DB interaction
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Set a valid Fernet key BEFORE any app imports touch crypto.
# Must come before any app import that pulls in app.core.crypto.
# ---------------------------------------------------------------------------
_VALID_KEY = Fernet.generate_key().decode("utf-8")
os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = _VALID_KEY

from app.db.models.base import Base  # noqa: E402
from app.db.models import garmin_token as _garmin_token_module  # noqa: E402
from app.services.garmin_token_store import (  # noqa: E402
    garmin_token_dir,
    hydrate_dir,
    save_dir,
)


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------

def run(coro):  # noqa: ANN001, ANN201
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# In-memory SQLite session fixture (mirrors test_garmin_token_store.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    """Yields a real async SQLAlchemy session backed by in-memory SQLite."""

    async def _make():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[_garmin_token_module.GarminToken.__table__],
            )
        maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        return maker, engine

    maker, engine = run(_make())

    async def _session_ctx():
        async with maker() as s:
            yield s

    gen = _session_ctx()
    sess = run(gen.__anext__())
    yield sess
    try:
        run(gen.aclose())
    except StopAsyncIteration:
        pass
    run(engine.dispose())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token_dir(files: dict[str, bytes]) -> str:
    """Create a temp dir with the given {filename: bytes} contents."""
    d = tempfile.mkdtemp(prefix="garmin_src_")
    for name, content in files.items():
        (Path(d) / name).write_bytes(content)
    return d


def _patch_settings_crypto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch crypto settings to use the valid test Fernet key."""
    monkeypatch.setattr(
        "app.core.crypto.settings",
        type("S", (), {
            "garmin_password_encryption_key": _VALID_KEY,
            "garmin_password_encryption_key_fallbacks": "",
            "garmin_password_encryption_key_id": None,
        })(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_db_mode_round_trip(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """db mode: seeded tokens are hydrated, modifications persist after context exit.

    Steps:
      1. Seed a DB row via save_dir.
      2. Enter garmin_token_dir — assert the seeded file bytes are present.
      3. Modify a file (simulate token refresh) inside the context.
      4. After exit, hydrate again and assert the modification is stored.
      5. Assert the temp dir was cleaned up.
    """
    _patch_settings_crypto(monkeypatch)
    # garmin_token_store now calls Settings() at call time; patch the class
    # so that Settings() returns a fake with ld_garmin_tokens="db".
    import app.services.garmin_token_store as _gts
    monkeypatch.setattr(
        _gts,
        "Settings",
        lambda: type("S", (), {"ld_garmin_tokens": "db"})(),
    )

    original_token = b'{"access_token":"original","refresh_token":"orig_rt"}'
    src_dir = _make_token_dir({"oauth2_token.json": original_token})
    run(save_dir(session, user_id=10, token_dir=src_dir))

    captured_dir: str | None = None

    async def _use_ctx() -> None:
        nonlocal captured_dir
        async with garmin_token_dir(session, 10) as tok_dir:
            assert tok_dir is not None, "Expected a temp dir in db mode"
            assert Path(tok_dir).is_dir(), "Yielded dir must exist during context"

            # Verify seeded bytes are present
            token_bytes = (Path(tok_dir) / "oauth2_token.json").read_bytes()
            assert token_bytes == original_token, "Hydrated bytes must match seeded bytes"

            # Simulate token refresh
            refreshed_token = b'{"access_token":"refreshed","refresh_token":"new_rt"}'
            (Path(tok_dir) / "oauth2_token.json").write_bytes(refreshed_token)

            captured_dir = tok_dir  # capture path so we can check cleanup after exit

    run(_use_ctx())

    # Temp dir must be cleaned up after context exit
    assert captured_dir is not None
    assert not Path(captured_dir).exists(), "Temp dir must be deleted after context exit"

    # Verify the modification was persisted to DB
    async def _verify() -> bytes:
        new_dir = await hydrate_dir(session, 10)
        assert new_dir is not None
        return (Path(new_dir) / "oauth2_token.json").read_bytes()

    persisted = run(_verify())
    assert persisted == b'{"access_token":"refreshed","refresh_token":"new_rt"}'


def test_db_mode_no_existing_row(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """db mode, no prior row: yields a fresh empty dir; first write is persisted.

    Steps:
      1. Use user_id=20 (no row in DB).
      2. Enter garmin_token_dir — assert a fresh, empty dir is yielded.
      3. Write a token file inside the context.
      4. After exit, hydrate and assert the file was stored.
    """
    _patch_settings_crypto(monkeypatch)
    import app.services.garmin_token_store as _gts
    monkeypatch.setattr(
        _gts,
        "Settings",
        lambda: type("S", (), {"ld_garmin_tokens": "db"})(),
    )

    initial_token = b'{"access_token":"brand_new","refresh_token":"new_rt"}'
    captured_dir: str | None = None

    async def _use_ctx() -> None:
        nonlocal captured_dir
        async with garmin_token_dir(session, 20) as tok_dir:
            assert tok_dir is not None, "Expected a fresh temp dir for unknown user"
            assert Path(tok_dir).is_dir(), "Yielded dir must exist"
            # No pre-existing files
            existing = list(Path(tok_dir).iterdir())
            assert existing == [], f"Expected empty dir, got: {existing}"
            # Write a token (simulating first login)
            (Path(tok_dir) / "oauth1_token.json").write_bytes(initial_token)
            captured_dir = tok_dir

    run(_use_ctx())

    assert captured_dir is not None
    assert not Path(captured_dir).exists(), "Temp dir must be cleaned up after exit"

    async def _verify() -> bytes:
        new_dir = await hydrate_dir(session, 20)
        assert new_dir is not None, "Token should have been persisted after context exit"
        return (Path(new_dir) / "oauth1_token.json").read_bytes()

    persisted = run(_verify())
    assert persisted == initial_token


def test_dir_mode_yields_none_no_db_interaction(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dir mode: garmin_token_dir yields None and does NOT touch the DB.

    With LD_GARMIN_TOKENS != "db" the context manager should be a no-op
    from the DB perspective: it yields None and leaves the garmin_token table
    completely untouched.
    """
    _patch_settings_crypto(monkeypatch)
    import app.services.garmin_token_store as _gts
    monkeypatch.setattr(
        _gts,
        "Settings",
        lambda: type("S", (), {"ld_garmin_tokens": "dir"})(),
    )

    # Pre-seed a row for user 30 so we can confirm it is NOT modified.
    seed_dir = _make_token_dir({"token.json": b"original_dir_mode_token"})
    run(save_dir(session, user_id=30, token_dir=seed_dir))

    yielded_value: list = []

    async def _use_ctx() -> None:
        async with garmin_token_dir(session, 30) as tok_dir:
            yielded_value.append(tok_dir)
            # Confirm no temp dir was created
            assert tok_dir is None, "dir mode must yield None"

    run(_use_ctx())

    assert yielded_value == [None]

    # The DB row must be unchanged — hydrate should still return the original seeded bytes.
    async def _verify() -> bytes | None:
        restored = await hydrate_dir(session, 30)
        if restored is None:
            return None
        return (Path(restored) / "token.json").read_bytes()

    still_there = run(_verify())
    assert still_there == b"original_dir_mode_token", (
        "dir mode must not modify the DB row"
    )


def test_exception_inside_context_propagates_and_does_not_persist(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exception raised inside garmin_token_dir: propagates, no persist, temp dir cleaned up.

    This documents the contract: if the caller raises inside the context block,
      (a) the exception propagates out of the context manager,
      (b) the temp directory is cleaned up (finally: shutil.rmtree),
      (c) save_dir is NOT called (the exception bypassed the save step),
      (d) the DB row is UNCHANGED — partial/failed token state is never persisted.
    """
    _patch_settings_crypto(monkeypatch)
    import app.services.garmin_token_store as _gts
    monkeypatch.setattr(
        _gts,
        "Settings",
        lambda: type("S", (), {"ld_garmin_tokens": "db"})(),
    )

    # Seed an existing token row for user 40
    original_token = b'{"access_token":"original_40"}'
    src_dir = _make_token_dir({"oauth2_token.json": original_token})
    run(save_dir(session, user_id=40, token_dir=src_dir))

    captured_dir: list[str] = []

    async def _raise_inside() -> None:
        async with garmin_token_dir(session, 40) as tok_dir:
            assert tok_dir is not None
            captured_dir.append(tok_dir)
            # Modify the file (but this should NOT be persisted because we raise)
            (Path(tok_dir) / "oauth2_token.json").write_bytes(b"partial-modified")
            raise RuntimeError("deliberate test error")

    # (a) exception propagates
    with pytest.raises(RuntimeError, match="deliberate test error"):
        run(_raise_inside())

    # (b) temp dir is cleaned up
    assert len(captured_dir) == 1
    assert not Path(captured_dir[0]).exists(), "Temp dir must be deleted even when an exception occurred"

    # (c)+(d) DB row is UNCHANGED — the original token is still there
    async def _verify_unchanged() -> bytes | None:
        restored = await hydrate_dir(session, 40)
        if restored is None:
            return None
        return (Path(restored) / "oauth2_token.json").read_bytes()

    persisted = run(_verify_unchanged())
    assert persisted == original_token, (
        "DB row must not be updated when an exception is raised inside garmin_token_dir"
    )
