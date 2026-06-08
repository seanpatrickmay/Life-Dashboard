"""Tests for KVStore: MemoryKVStore, DynamoKVStore (construction only), and factory.

All async tests use @pytest.mark.asyncio.  Clock injection via monkeypatching
``app.kv.kv_store._now`` makes TTL and window-expiry tests fully deterministic.
"""
from __future__ import annotations

import pytest
import app.kv.kv_store as kv_module
from app.kv.kv_store import MemoryKVStore, get_kv_store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_store() -> MemoryKVStore:
    """Return a fresh MemoryKVStore per test (avoids singleton leakage)."""
    return MemoryKVStore()


# ---------------------------------------------------------------------------
# Basic set / get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_get_roundtrip():
    store = make_store()
    await store.set("k", "hello")
    assert await store.get("k") == "hello"


@pytest.mark.asyncio
async def test_get_missing_returns_none():
    store = make_store()
    assert await store.get("does_not_exist") is None


@pytest.mark.asyncio
async def test_set_overwrites_value():
    store = make_store()
    await store.set("k", "first")
    await store.set("k", "second")
    assert await store.get("k") == "second"


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ttl_not_expired_returns_value(monkeypatch):
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.set("k", "val", ttl_seconds=300)

    # Move time forward but stay within window
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 299)
    assert await store.get("k") == "val"


@pytest.mark.asyncio
async def test_ttl_expired_returns_none(monkeypatch):
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.set("k", "val", ttl_seconds=300)

    # Advance past expiry (expires_at = fake_time + 300; now >= expires_at → expired)
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 300)
    assert await store.get("k") is None


@pytest.mark.asyncio
async def test_ttl_exactly_at_expiry_returns_none(monkeypatch):
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.set("k", "val", ttl_seconds=300)

    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 300)
    assert await store.get("k") is None


@pytest.mark.asyncio
async def test_no_ttl_never_expires(monkeypatch):
    """A key set without ttl_seconds should survive large time jumps."""
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.set("k", "forever")

    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 99_999_999)
    assert await store.get("k") == "forever"


# ---------------------------------------------------------------------------
# incr — basic counting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incr_first_call_returns_one():
    store = make_store()
    assert await store.incr("counter", ttl_seconds=60) == 1


@pytest.mark.asyncio
async def test_incr_second_call_returns_two():
    store = make_store()
    await store.incr("counter", ttl_seconds=60)
    assert await store.incr("counter", ttl_seconds=60) == 2


@pytest.mark.asyncio
async def test_incr_multiple_increments():
    store = make_store()
    for expected in range(1, 6):
        assert await store.incr("c", ttl_seconds=60) == expected


# ---------------------------------------------------------------------------
# incr — fixed window semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incr_window_reset_after_expiry(monkeypatch):
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.incr("ip:1.2.3.4", ttl_seconds=60)
    await store.incr("ip:1.2.3.4", ttl_seconds=60)

    # Advance past the window
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 60)
    result = await store.incr("ip:1.2.3.4", ttl_seconds=60)
    assert result == 1, "Window should have reset to 1 after expiry"


@pytest.mark.asyncio
async def test_incr_fixed_window_preserves_expiry(monkeypatch):
    """Incrementing within an active window must NOT extend the expires_at."""
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    # Start window: expires_at = fake_time + 60
    await store.incr("k", ttl_seconds=60)

    # 30 s later, increment again — window should still expire at fake_time + 60
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 30)
    await store.incr("k", ttl_seconds=60)

    # At fake_time + 61 the window should be expired
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 61)
    assert await store.get("k") is None


@pytest.mark.asyncio
async def test_incr_counts_accumulate_within_window(monkeypatch):
    """Multiple increments spread across a window all count."""
    fake_time = 1_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = make_store()
    await store.incr("k", ttl_seconds=120)

    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 50)
    await store.incr("k", ttl_seconds=120)

    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 100)
    count = await store.incr("k", ttl_seconds=120)
    assert count == 3

    # Original window still expires at fake_time + 120
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 120)
    assert await store.get("k") is None


# ---------------------------------------------------------------------------
# Factory: default → MemoryKVStore
# ---------------------------------------------------------------------------


def test_factory_default_returns_memory(monkeypatch):
    monkeypatch.setenv("LD_KV_STORE", "memory")
    store = get_kv_store()
    assert isinstance(store, MemoryKVStore)


def test_factory_singleton_same_instance(monkeypatch):
    """Two calls to get_kv_store() in memory mode must return the SAME object."""
    monkeypatch.setenv("LD_KV_STORE", "memory")
    a = get_kv_store()
    b = get_kv_store()
    assert a is b


# ---------------------------------------------------------------------------
# Factory: DynamoDB backend (offline construction)
# ---------------------------------------------------------------------------


def test_factory_dynamodb_when_selected(monkeypatch):
    """Setting LD_KV_STORE=dynamodb should produce a DynamoKVStore.

    boto3.resource is imported lazily inside DynamoKVStore.__init__; constructing
    the object does NOT require a live AWS connection or real credentials, so this
    test is safe to run offline.

    Note: pydantic-settings v2 reads the field-name-uppercased env var
    (DYNAMODB_KV_TABLE), not the deprecated Field(env=...) kwarg.
    """
    from app.kv.kv_store import DynamoKVStore

    monkeypatch.setenv("LD_KV_STORE", "dynamodb")
    monkeypatch.setenv("DYNAMODB_KV_TABLE", "test-table")

    store = get_kv_store()
    assert isinstance(store, DynamoKVStore)


def test_factory_dynamodb_uses_table_name(monkeypatch):
    """DynamoKVStore exposes the table name used to construct it.

    The correct env var is LD_DDB_KV_TABLE (mapped via validation_alias).
    The old Field(env='LD_DDB_KV_TABLE') kwarg was silently ignored by
    pydantic-settings v2 — that bug has been fixed.
    """
    from app.kv.kv_store import DynamoKVStore

    monkeypatch.setenv("LD_KV_STORE", "dynamodb")
    monkeypatch.setenv("LD_DDB_KV_TABLE", "my-kv-table")

    store = get_kv_store()
    assert isinstance(store, DynamoKVStore)
    assert store.table_name == "my-kv-table"


def test_factory_dynamodb_singleton_same_instance(monkeypatch):
    """Two calls to get_kv_store() in dynamodb mode must return the SAME object."""
    from app.kv.kv_store import DynamoKVStore

    monkeypatch.setenv("LD_KV_STORE", "dynamodb")
    monkeypatch.setenv("LD_DDB_KV_TABLE", "singleton-table")

    a = get_kv_store()
    b = get_kv_store()
    assert a is b
    assert isinstance(a, DynamoKVStore)
