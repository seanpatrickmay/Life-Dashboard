"""Tests for auth rate-limiting backed by KVStore.

The auth endpoints use ``_check_rate_limit`` (now async) to enforce a fixed-window
counter: max 10 attempts per 60-second window per client IP.

The 11th request in the same window raises HTTP 429.  After the window expires
the counter resets and the client can make requests again.

Clock injection is via ``app.kv.kv_store._now`` monkeypatching.
"""
from __future__ import annotations

import pytest
import app.kv.kv_store as kv_module
from app.kv.kv_store import MemoryKVStore

# Import the router module via importlib (same pattern as test_auth_router.py)
import importlib.util
from pathlib import Path
from fastapi import HTTPException

auth_module_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
spec = importlib.util.spec_from_file_location("auth_router_rl", auth_module_path)
assert spec and spec.loader
auth_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth_router)

_AUTH_RATE_LIMIT = auth_router._AUTH_RATE_LIMIT  # 10
_AUTH_RATE_WINDOW = auth_router._AUTH_RATE_WINDOW  # 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_store() -> MemoryKVStore:
    store = MemoryKVStore()
    kv_module._memory_instance = store
    return store


# ---------------------------------------------------------------------------
# Basic counting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_request_does_not_raise() -> None:
    _fresh_store()
    # Should not raise
    await auth_router._check_rate_limit("1.2.3.4")


@pytest.mark.asyncio
async def test_requests_within_limit_do_not_raise() -> None:
    _fresh_store()
    for _ in range(_AUTH_RATE_LIMIT):
        await auth_router._check_rate_limit("1.2.3.4")


@pytest.mark.asyncio
async def test_exceeding_limit_raises_429() -> None:
    """The 11th request in the same window should raise HTTP 429."""
    _fresh_store()
    for _ in range(_AUTH_RATE_LIMIT):
        await auth_router._check_rate_limit("10.0.0.1")

    with pytest.raises(HTTPException) as exc_info:
        await auth_router._check_rate_limit("10.0.0.1")

    assert exc_info.value.status_code == 429
    assert "Too many authentication attempts" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 429 response detail matches expected message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_detail_message() -> None:
    _fresh_store()
    for _ in range(_AUTH_RATE_LIMIT):
        await auth_router._check_rate_limit("5.5.5.5")

    with pytest.raises(HTTPException) as exc_info:
        await auth_router._check_rate_limit("5.5.5.5")

    assert exc_info.value.detail == "Too many authentication attempts. Please try again later."


# ---------------------------------------------------------------------------
# Per-IP isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_ips_are_independent() -> None:
    """Requests from different IPs do not share rate-limit counters."""
    _fresh_store()

    for _ in range(_AUTH_RATE_LIMIT):
        await auth_router._check_rate_limit("192.168.1.1")

    # A different IP should still be allowed
    await auth_router._check_rate_limit("192.168.1.2")


# ---------------------------------------------------------------------------
# Window reset after expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counter_resets_after_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """After the rate-limit window expires the counter resets to 0."""
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    _fresh_store()

    # Fill up the limit
    for _ in range(_AUTH_RATE_LIMIT):
        await auth_router._check_rate_limit("7.7.7.7")

    # Verify we're at the limit
    with pytest.raises(HTTPException):
        await auth_router._check_rate_limit("7.7.7.7")

    # Advance time past the window
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + _AUTH_RATE_WINDOW)

    # Counter should have reset — requests should succeed again
    await auth_router._check_rate_limit("7.7.7.7")


# ---------------------------------------------------------------------------
# KVStore key scheme
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_key_scheme() -> None:
    """Rate-limit counter is stored under 'ratelimit:auth:<ip>'."""
    store = _fresh_store()
    await auth_router._check_rate_limit("9.9.9.9")
    raw = await store.get("ratelimit:auth:9.9.9.9")
    assert raw == "1"
