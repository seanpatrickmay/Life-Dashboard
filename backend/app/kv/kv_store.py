"""Runtime-agnostic key-value store adapter.

Backends
--------
MemoryKVStore  – default; an in-process dict with TTL.  Returned as a
                 process-wide singleton by ``get_kv_store()`` so that the
                 metrics cache and rate-limiter share state across requests
                 within a single process (mirroring the existing in-proc
                 OrderedDict / dict behaviour).

DynamoKVStore  – selected via ``LD_KV_STORE=dynamodb``.  boto3 is imported
                 lazily to avoid import-time side-effects.  All blocking
                 boto3 calls are offloaded to a thread-executor, consistent
                 with ``blob_store.py``.

Clock injection
---------------
The module-level ``_now()`` function is used for all expiry comparisons.
Tests may monkeypatch ``app.kv.kv_store._now`` to control time deterministically
without real sleeps.

TTL semantics
-------------
Both backends use a FIXED window for ``incr``: once a counter window opens,
``expires_at`` is set exactly once (when the prior entry was missing or
expired).  Subsequent increments within the window do NOT extend ``expires_at``.

DynamoDB TTL caveat
-------------------
DynamoDB's native TTL deletion is eventually consistent and can lag hours.
``get()`` and ``incr()`` therefore perform an explicit ``expires_at`` check on
every read, treating items whose ``expires_at <= int(_now())`` as absent.
Native TTL is present on items only for eventual storage cleanup — never for
correctness.

Race note (DynamoDB incr)
--------------------------
``DynamoKVStore.incr`` uses a read-then-write pattern: read to decide if the
window expired, then either ``put_item`` (fresh window) or ``update_item ADD``
(existing window).  A small TOCTOU race exists for concurrent callers; this is
acceptable for a single-user application.
"""
from __future__ import annotations

import abc
import asyncio
import functools
import time
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Injectable clock — monkeypatch this in tests for deterministic TTL behaviour
# ---------------------------------------------------------------------------


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class KVStore(abc.ABC):
    @abc.abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abc.abstractmethod
    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None: ...

    @abc.abstractmethod
    async def incr(self, key: str, *, ttl_seconds: int) -> int:
        """Atomically increment an integer counter at ``key``.

        On the first increment within a window (or after the previous window
        expired) the counter resets to 1 and a new TTL window begins.  Within
        an active window the counter increases and the window expiry is NOT
        extended (fixed window).

        Returns the new count.
        """


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------


class MemoryKVStore(KVStore):
    """In-process KV store backed by a plain dict.

    Item shape: ``{key: (value: str, expires_at: float | None)}``
    """

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    def _is_expired(self, key: str) -> bool:
        """Return True if ``key`` exists and its TTL has elapsed."""
        entry = self._data.get(key)
        if entry is None:
            return False
        _, expires_at = entry
        return expires_at is not None and _now() >= expires_at

    async def get(self, key: str) -> str | None:
        if key not in self._data:
            return None
        if self._is_expired(key):
            del self._data[key]
            return None
        return self._data[key][0]

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        expires_at = _now() + ttl_seconds if ttl_seconds is not None else None
        self._data[key] = (value, expires_at)

    async def incr(self, key: str, *, ttl_seconds: int) -> int:
        """Increment with fixed-window semantics.

        If the key is missing or expired, start a fresh window at count 1.
        Otherwise add 1 to the existing count while preserving the original
        ``expires_at`` (fixed window — not sliding).
        """
        existing = self._data.get(key)

        if existing is None or self._is_expired(key):
            # Fresh window
            if existing is not None:
                # Lazy-delete the stale entry
                del self._data[key]
            new_count = 1
            expires_at = _now() + ttl_seconds
            self._data[key] = (str(new_count), expires_at)
        else:
            # Existing active window — preserve expires_at
            value_str, expires_at = existing
            new_count = int(value_str) + 1
            self._data[key] = (str(new_count), expires_at)

        return new_count


# ---------------------------------------------------------------------------
# DynamoDB backend
# ---------------------------------------------------------------------------


class DynamoKVStore(KVStore):
    """DynamoDB-backed KV store.

    Item schema: ``{"pk": <str>, "value": <str>, "expires_at": <int>}``

    ``table_name`` is exposed as a public attribute so the factory test can
    verify the correct table was passed.

    The ``client`` parameter is provided for dependency-injection in tests
    (e.g., a moto-patched resource).  When ``None``, a real ``boto3.resource``
    is constructed using ``Settings().aws_endpoint_url``.

    boto3 is imported *lazily* inside ``__init__`` so that importing this
    module without boto3 installed raises only when a DynamoKVStore is
    instantiated — not at import time.
    """

    def __init__(self, table_name: str, *, client: object | None = None) -> None:
        import boto3  # lazy import

        self.table_name = table_name

        if client is not None:
            self._table = client
        else:
            endpoint_url = Settings().aws_endpoint_url
            dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            self._table = dynamodb.Table(table_name)

    # ------------------------------------------------------------------
    # Internal helper: run blocking boto3 in a thread executor
    # ------------------------------------------------------------------

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        response = await self._run(
            self._table.get_item,
            Key={"pk": key},
        )
        item = response.get("Item")
        if item is None:
            return None

        expires_at = item.get("expires_at")
        if expires_at is not None and int(_now()) >= int(expires_at):
            # DynamoDB TTL is eventual; enforce expiry explicitly
            return None

        return item.get("value")

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        item: dict = {"pk": key, "value": value}
        if ttl_seconds is not None:
            item["expires_at"] = int(_now()) + ttl_seconds
        await self._run(self._table.put_item, Item=item)

    async def incr(self, key: str, *, ttl_seconds: int) -> int:
        """Fixed-window increment for DynamoDB.

        Strategy:
        1. Read the current item.
        2. If missing or expired → put_item with count=1 and a fresh expires_at.
        3. If active → update_item with ADD to increment atomically.

        A small TOCTOU race exists between the read and write (step 2→3).
        Acceptable for a single-user application.
        """
        response = await self._run(
            self._table.get_item,
            Key={"pk": key},
        )
        item = response.get("Item")
        now_int = int(_now())

        if item is None or (
            item.get("expires_at") is not None and now_int >= int(item["expires_at"])
        ):
            # Fresh window
            new_expires_at = now_int + ttl_seconds
            await self._run(
                self._table.put_item,
                Item={"pk": key, "value": "1", "expires_at": new_expires_at},
            )
            return 1

        # Active window — increment atomically, preserving expires_at
        result = await self._run(
            self._table.update_item,
            Key={"pk": key},
            UpdateExpression="ADD #c :one",
            ExpressionAttributeNames={"#c": "value"},
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        # DynamoDB returns a Decimal; convert to int
        return int(result["Attributes"]["value"])


# ---------------------------------------------------------------------------
# Singleton for MemoryKVStore (process-wide in-proc cache/rate-limiter state)
# ---------------------------------------------------------------------------

_memory_instance: MemoryKVStore | None = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_kv_store() -> KVStore:
    """Return the configured KV backend.

    Reads a fresh ``Settings()`` at call time so that ``monkeypatch.setenv``
    in tests is honoured (the module-level ``settings`` singleton is
    ``lru_cache``'d and would not see env changes applied after import).

    In ``memory`` mode (the default) the same ``MemoryKVStore`` instance is
    returned on every call within a process so that the metrics cache and
    rate-limiter accumulate state correctly across requests.
    """
    global _memory_instance

    s = Settings()
    if s.ld_kv_store == "dynamodb":
        return DynamoKVStore(s.dynamodb_kv_table or "")

    # Memory mode — return (or create) the process-wide singleton
    if _memory_instance is None:
        _memory_instance = MemoryKVStore()
    return _memory_instance
