"""Integration tests for DynamoKVStore against real LocalStack.

Proves:
- set / get round-trip returns the correct value
- get() on a missing key returns None
- incr() returns 1 on first call and 2 on the second call
- set() with a TTL writes an expires_at attribute in the future
- The atomic ConditionExpression path (TOCTOU guard on fresh window) does not
  error against real DynamoDB / LocalStack

LocalStack must be running (make local-up).  Tests are skipped automatically
when LocalStack is unreachable (see conftest.py).
"""
from __future__ import annotations

import time

import pytest

TABLE = "integ-test-kv-store"


@pytest.fixture(scope="module")
def ddb_table(ls_dynamodb):
    """Create (and clean up) a DynamoDB table for this module's tests."""
    table = ls_dynamodb.create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()

    # Enable TTL on the expires_at attribute
    ls_dynamodb.meta.client.update_time_to_live(
        TableName=TABLE,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )

    yield table

    # Best-effort cleanup
    try:
        table.delete()
    except Exception:
        pass


@pytest.fixture()
def store(ddb_table):
    """Construct DynamoKVStore pointing at the LocalStack table.

    We pass the table object directly via the ``client`` parameter to avoid
    constructing a second boto3 resource — this exercises the same code path
    as production (the table object's methods are identical).
    """
    from app.kv.kv_store import DynamoKVStore

    return DynamoKVStore(TABLE, client=ddb_table)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_get_roundtrip(store):
    """Value stored via set() is returned unchanged by get()."""
    await store.set("integ:key:rtrip", "hello-dynamo")
    result = await store.get("integ:key:rtrip")
    assert result == "hello-dynamo"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_missing_returns_none(store):
    """get() on a non-existent key returns None."""
    result = await store.get("integ:key:does-not-exist-xyz")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_overwrites_value(store):
    """A second set() on the same key overwrites the first value."""
    await store.set("integ:key:overwrite", "first")
    await store.set("integ:key:overwrite", "second")
    assert await store.get("integ:key:overwrite") == "second"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incr_first_call_returns_one(store):
    """First incr() on a fresh key returns 1."""
    result = await store.incr("integ:counter:fresh", ttl_seconds=300)
    assert result == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incr_second_call_returns_two(store):
    """Second incr() within the same window returns 2."""
    key = "integ:counter:two"
    r1 = await store.incr(key, ttl_seconds=300)
    r2 = await store.incr(key, ttl_seconds=300)
    assert r1 == 1
    assert r2 == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incr_condition_expression_path(store):
    """The ConditionExpression guard on the fresh-window put_item does not error.

    This exercises the most important DynamoDB-specific code path: the atomic
    put_item with ``attribute_not_exists(pk)`` that closes the TOCTOU race.
    On moto this always succeeds; on LocalStack (and real DynamoDB) the
    condition evaluation must also succeed.
    """
    key = "integ:counter:ce-path"
    # First incr: hits the ConditionExpression path (fresh window)
    r1 = await store.incr(key, ttl_seconds=300)
    # Second incr: hits the update_item ADD path (active window)
    r2 = await store.incr(key, ttl_seconds=300)
    # Third incr: still active window
    r3 = await store.incr(key, ttl_seconds=300)
    assert r1 == 1
    assert r2 == 2
    assert r3 == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_with_ttl_writes_expires_at_in_future(store, ddb_table):
    """set() with ttl_seconds writes an expires_at epoch integer in the future.

    We do NOT wait for native TTL deletion (that's eventually consistent and can
    lag hours).  We just confirm the attribute is present and correct.
    """
    key = "integ:key:ttl-attr"
    before = int(time.time())
    await store.set(key, "temp-value", ttl_seconds=3600)

    # Read the raw item from DynamoDB to inspect the expires_at attribute
    resp = ddb_table.get_item(Key={"pk": key})
    item = resp.get("Item")
    assert item is not None, "Item should exist immediately after set()"
    assert "expires_at" in item, "expires_at attribute must be written when ttl_seconds is given"

    expires_at = int(item["expires_at"])
    assert expires_at > before, "expires_at must be in the future"
    # Sanity: should be approximately now + 3600 (allow 60 s of slack)
    assert expires_at <= before + 3600 + 60


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_without_ttl_does_not_write_expires_at(store, ddb_table):
    """set() without ttl_seconds must NOT write an expires_at attribute."""
    key = "integ:key:no-ttl"
    await store.set(key, "persistent")

    resp = ddb_table.get_item(Key={"pk": key})
    item = resp.get("Item")
    assert item is not None
    assert "expires_at" not in item
