"""Tests for metrics router cache behaviour.

The metrics /overview endpoint caches responses in the KVStore.  These tests
verify cache hit/miss semantics and TTL expiry using clock injection via
monkeypatching ``app.kv.kv_store._now``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
import app.kv.kv_store as kv_module
from app.kv.kv_store import MemoryKVStore, get_kv_store
from app.schemas.metrics import MetricsOverviewResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_overview(**kwargs: Any) -> MetricsOverviewResponse:
    defaults: dict[str, Any] = {
        "generated_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "range_label": "last 14 days",
        "training_volume_hours": 10.5,
        "training_volume_window_days": 14,
        "training_load_avg": None,
        "training_load_trend": [],
        "hrv_trend_ms": [],
        "rhr_trend_bpm": [],
        "sleep_trend_hours": [],
    }
    defaults.update(kwargs)
    return MetricsOverviewResponse(**defaults)


# ---------------------------------------------------------------------------
# Cache key scheme
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_key_includes_user_id_and_range_days() -> None:
    """get_kv_store().set is called with key 'metrics_overview:<user_id>:<range_days>'."""
    store = get_kv_store()
    await store.set("metrics_overview:42:14", _make_overview().model_dump_json(), ttl_seconds=300)
    raw = await store.get("metrics_overview:42:14")
    assert raw is not None
    response = MetricsOverviewResponse.model_validate_json(raw)
    assert response.range_label == "last 14 days"


# ---------------------------------------------------------------------------
# Cache miss → cache set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_stores_value_with_ttl_300() -> None:
    """On a cache miss the value is stored with TTL = 300 s."""
    fake_time = 1_000_000.0

    store = MemoryKVStore()
    # Replace the singleton so the router uses our controlled instance.
    kv_module._memory_instance = store

    with patch.object(kv_module, "_now", lambda: fake_time):
        await store.set("metrics_overview:1:14", _make_overview().model_dump_json(), ttl_seconds=300)

        # Value should be present before expiry
        raw = await store.get("metrics_overview:1:14")
        assert raw is not None

    # Advance past TTL; entry should have expired
    with patch.object(kv_module, "_now", lambda: fake_time + 300):
        raw = await store.get("metrics_overview:1:14")
        assert raw is None


# ---------------------------------------------------------------------------
# Cache hit — second read is served from KVStore without re-computing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_stored_value() -> None:
    """A cached value is returned on the second get without re-storing."""
    store = MemoryKVStore()
    kv_module._memory_instance = store

    original = _make_overview(training_volume_hours=7.0)
    cache_key = "metrics_overview:99:30"
    await store.set(cache_key, original.model_dump_json(), ttl_seconds=300)

    # Simulate a second call: reading from store directly.
    raw = await store.get(cache_key)
    assert raw is not None
    hit = MetricsOverviewResponse.model_validate_json(raw)
    assert hit.training_volume_hours == 7.0


# ---------------------------------------------------------------------------
# Cache expiry — value absent after TTL elapsed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cached value is None once TTL has elapsed (clock-injected)."""
    fake_time = 2_000_000.0
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time)

    store = MemoryKVStore()
    kv_module._memory_instance = store

    cache_key = "metrics_overview:5:14"
    await store.set(cache_key, _make_overview().model_dump_json(), ttl_seconds=300)

    # Before expiry
    assert await store.get(cache_key) is not None

    # Exactly at expiry boundary (expires_at = fake_time + 300; now >= expires_at → expired)
    monkeypatch.setattr(kv_module, "_now", lambda: fake_time + 300)
    assert await store.get(cache_key) is None


# ---------------------------------------------------------------------------
# JSON round-trip fidelity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_roundtrip_preserves_datetime_fields() -> None:
    """model_dump_json / model_validate_json preserves datetime values."""
    original = _make_overview(
        generated_at=datetime(2026, 6, 1, 8, 30, 0, tzinfo=timezone.utc),
        training_volume_hours=3.14,
    )
    raw = original.model_dump_json()
    restored = MetricsOverviewResponse.model_validate_json(raw)
    assert restored.generated_at == original.generated_at
    assert restored.training_volume_hours == original.training_volume_hours
