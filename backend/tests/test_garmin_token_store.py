"""Tests for garmin_token_store service.

Uses an in-memory SQLite database via aiosqlite.  The Fernet key is
generated fresh per test so that encrypt_secret / decrypt_secret are
exercised against a real valid key (the conftest default "test-key" is
intentionally NOT a valid Fernet key, so tests that call real Fernet must
supply their own key before importing crypto-using modules).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---- set a valid Fernet key BEFORE any app imports touch crypto ----
_VALID_KEY = Fernet.generate_key().decode("utf-8")
os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = _VALID_KEY

from app.db.models.base import Base  # noqa: E402  (after env set)
from app.db.models import garmin_token as _garmin_token_module  # noqa: E402 (registers model)
from app.services.garmin_token_store import hydrate_dir, save_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------

def run(coro):  # noqa: ANN001, ANN201
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# In-memory SQLite session fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    """Yields a real async SQLAlchemy session backed by in-memory SQLite."""

    async def _make():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            # Create only the garmin_token table (no FKs needed in isolation).
            await conn.run_sync(Base.metadata.create_all, tables=[_garmin_token_module.GarminToken.__table__])
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
    """Create a temp dir containing the given {filename: content} mapping."""
    d = tempfile.mkdtemp(prefix="garmin_src_")
    for name, content in files.items():
        (Path(d) / name).write_bytes(content)
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_round_trip_identical_bytes(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """save_dir then hydrate_dir returns files with identical bytes."""
    monkeypatch.setattr(
        "app.core.crypto.settings",
        type("S", (), {
            "garmin_password_encryption_key": _VALID_KEY,
            "garmin_password_encryption_key_fallbacks": "",
            "garmin_password_encryption_key_id": None,
        })(),
    )

    token_files = {
        "oauth1_token.json": b'{"oauth_token":"tok1","oauth_token_secret":"sec1"}',
        "oauth2_token.json": b'{"access_token":"at","refresh_token":"rt","expires_at":9999}',
    }
    src_dir = _make_token_dir(token_files)

    run(save_dir(session, user_id=1, token_dir=src_dir))

    out_dir = run(hydrate_dir(session, user_id=1))
    assert out_dir is not None

    for name, expected in token_files.items():
        restored = (Path(out_dir) / name).read_bytes()
        assert restored == expected, f"Mismatch for {name}"


def test_missing_user_returns_none(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """hydrate_dir for an unknown user_id returns None."""
    monkeypatch.setattr(
        "app.core.crypto.settings",
        type("S", (), {
            "garmin_password_encryption_key": _VALID_KEY,
            "garmin_password_encryption_key_fallbacks": "",
            "garmin_password_encryption_key_id": None,
        })(),
    )

    result = run(hydrate_dir(session, user_id=999))
    assert result is None


def test_encryption_at_rest(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stored encrypted_blob is not equal to the plaintext base64 and does not
    contain the raw token bytes."""
    import base64

    from app.db.models.garmin_token import GarminToken

    monkeypatch.setattr(
        "app.core.crypto.settings",
        type("S", (), {
            "garmin_password_encryption_key": _VALID_KEY,
            "garmin_password_encryption_key_fallbacks": "",
            "garmin_password_encryption_key_id": None,
        })(),
    )

    secret_bytes = b"SUPER_SECRET_TOKEN_BYTES_1234567890"
    src_dir = _make_token_dir({"token.bin": secret_bytes})

    run(save_dir(session, user_id=2, token_dir=src_dir))

    row = run(session.get(GarminToken, 2))
    assert row is not None

    blob = row.encrypted_blob
    # Must not contain the raw secret
    assert secret_bytes not in blob.encode("utf-8")
    # blob should NOT be valid base64 that decodes to the tarball directly
    # (i.e., it is actually encrypted, not just base64-encoded)
    try:
        decoded = base64.b64decode(blob)
        # If it decoded to something, it must NOT start with the tar magic
        # (Fernet ciphertext starts with 'gAAAAA' in base64 form)
        assert not decoded.startswith(b"\x1f\x8b"), "blob appears to be raw gzip, not encrypted"
    except Exception:
        pass  # decode failure is also fine (means it's encrypted)

    # The blob must begin with Fernet's base64-url token prefix
    assert blob.startswith("gAAAAA"), f"Expected Fernet ciphertext, got: {blob[:20]!r}"


def test_overwrite_upsert(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling save_dir twice for the same user_id results in exactly one row
    and the second write's contents are returned by hydrate_dir."""
    from sqlalchemy import func, select

    from app.db.models.garmin_token import GarminToken

    monkeypatch.setattr(
        "app.core.crypto.settings",
        type("S", (), {
            "garmin_password_encryption_key": _VALID_KEY,
            "garmin_password_encryption_key_fallbacks": "",
            "garmin_password_encryption_key_id": None,
        })(),
    )

    first_dir = _make_token_dir({"token.json": b"first-token"})
    second_dir = _make_token_dir({"token.json": b"second-token"})

    run(save_dir(session, user_id=3, token_dir=first_dir))
    run(save_dir(session, user_id=3, token_dir=second_dir))

    # Exactly one row in the table for user 3
    async def _count() -> int:
        result = await session.execute(
            select(func.count()).select_from(GarminToken).where(GarminToken.id == 3)
        )
        return result.scalar_one()

    count = run(_count())
    assert count == 1, f"Expected 1 row, found {count}"

    # Latest content is returned
    out_dir = run(hydrate_dir(session, user_id=3))
    assert out_dir is not None
    assert (Path(out_dir) / "token.json").read_bytes() == b"second-token"
