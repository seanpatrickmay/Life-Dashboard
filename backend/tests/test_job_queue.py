"""Tests for JobQueue: registry, InlineJobQueue, SqsJobQueue (moto), dispatch, factory.

Registry isolation
------------------
Each test that registers a handler uses a unique name scoped to that test
(prefixed with a function-unique string) so that the global ``_HANDLERS`` dict
does not leak state between tests.  The ``isolated_registry`` fixture additionally
snapshots and restores the full dict around every test that uses it, providing a
belt-and-suspenders guarantee for the registry tests.

Inline determinism
------------------
InlineJobQueue uses ``asyncio.create_task`` which schedules work on the running
loop but does not await it inline.  Tests drive the task to completion by
awaiting ``asyncio.sleep(0)`` twice — one yield to let ``create_task`` queue the
coroutine, a second to let the event loop run it to completion.

Moto SQS
---------
``@mock_aws`` intercepts all real boto3 SQS calls.  AWS credentials are set to
dummy values and ``AWS_ENDPOINT_URL`` is cleared so moto intercepts correctly.
"""
from __future__ import annotations

import asyncio
import json

import boto3
import pytest

import app.jobs.registry as registry_module
from app.jobs.queue import InlineJobQueue, SqsJobQueue, dispatch, get_job_queue
from app.jobs.registry import get_handler, job, registered_jobs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_registry():
    """Snapshot and restore _HANDLERS around a test to prevent leakage."""
    snapshot = dict(registry_module._HANDLERS)
    yield
    registry_module._HANDLERS.clear()
    registry_module._HANDLERS.update(snapshot)


# ---------------------------------------------------------------------------
# 1. Registry
# ---------------------------------------------------------------------------


def test_registry_register_and_get(isolated_registry):
    @job("reg_test_t")
    async def _handler(payload: dict) -> None:
        pass

    assert get_handler("reg_test_t") is _handler


def test_registry_unknown_raises_key_error(isolated_registry):
    with pytest.raises(KeyError):
        get_handler("reg_test_nope_xyz")


def test_registry_registered_jobs_includes_name(isolated_registry):
    @job("reg_test_listed")
    async def _handler(payload: dict) -> None:
        pass

    assert "reg_test_listed" in registered_jobs()


def test_registry_registered_jobs_sorted(isolated_registry):
    @job("reg_test_z")
    async def _z(payload: dict) -> None:
        pass

    @job("reg_test_a")
    async def _a(payload: dict) -> None:
        pass

    jobs = registered_jobs()
    assert jobs == sorted(jobs)


# ---------------------------------------------------------------------------
# 2. InlineJobQueue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inline_runs_handler(isolated_registry):
    results: list[dict] = []
    event = asyncio.Event()

    @job("inline_test_run")
    async def _handler(payload: dict) -> None:
        results.append(payload)
        event.set()

    queue = InlineJobQueue()
    await queue.enqueue("inline_test_run", {"x": 1})

    # Yield twice: first to schedule the task, second to run it to completion.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert event.is_set()
    assert results == [{"x": 1}]


@pytest.mark.asyncio
async def test_inline_unknown_job_raises_eagerly(isolated_registry):
    queue = InlineJobQueue()
    with pytest.raises(KeyError):
        await queue.enqueue("inline_test_does_not_exist_xyz", {})


# ---------------------------------------------------------------------------
# 3. SqsJobQueue — moto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sqs_publishes_message(monkeypatch, isolated_registry):
    from moto import mock_aws

    # Provide dummy credentials so moto does not complain about missing creds.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # Clear endpoint override so moto intercepts (not a real localstack endpoint).
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

    @job("sqs_test_publish")
    async def _handler(payload: dict) -> None:
        pass

    with mock_aws():
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="test-queue")
        queue_url = resp["QueueUrl"]

        q = SqsJobQueue(queue_url, client=sqs)
        await q.enqueue("sqs_test_publish", {"a": 2})

        messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
        assert "Messages" in messages
        body = json.loads(messages["Messages"][0]["Body"])
        assert body == {"name": "sqs_test_publish", "payload": {"a": 2}}


# ---------------------------------------------------------------------------
# 4. dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_runs_handler(isolated_registry):
    received: list[dict] = []

    @job("dispatch_test_run")
    async def _handler(payload: dict) -> None:
        received.append(payload)

    await dispatch({"name": "dispatch_test_run", "payload": {"k": 9}})
    assert received == [{"k": 9}]


@pytest.mark.asyncio
async def test_dispatch_missing_payload_defaults_to_empty(isolated_registry):
    received: list[dict] = []

    @job("dispatch_test_no_payload")
    async def _handler(payload: dict) -> None:
        received.append(payload)

    await dispatch({"name": "dispatch_test_no_payload"})
    assert received == [{}]


@pytest.mark.asyncio
async def test_dispatch_unknown_name_no_ops(isolated_registry):
    """dispatch() with an unknown job name discards the message (no exception).

    Poison-message handling: unknown job names must not cause infinite SQS retry
    loops.  The error is logged but the call returns normally.
    """
    # Must NOT raise — the message is discarded (logged) so SQS won't retry forever
    result = await dispatch({"name": "dispatch_test_unknown_xyz", "payload": {}})
    assert result is None


@pytest.mark.asyncio
async def test_dispatch_missing_name_no_ops(isolated_registry):
    """dispatch() with no 'name' key discards the message (no exception)."""
    result = await dispatch({"payload": {"k": 1}})
    assert result is None

    result2 = await dispatch({})
    assert result2 is None


@pytest.mark.asyncio
async def test_dispatch_handler_exception_propagates(isolated_registry):
    """dispatch() must re-raise exceptions from the handler itself.

    Handler errors should propagate so SQS can retry / route to DLQ.
    """

    @job("dispatch_test_raises")
    async def _explode(payload: dict) -> None:
        raise ValueError("handler exploded")

    with pytest.raises(ValueError, match="handler exploded"):
        await dispatch({"name": "dispatch_test_raises", "payload": {}})


# ---------------------------------------------------------------------------
# 5. Factory
# ---------------------------------------------------------------------------


def test_factory_default_returns_inline(monkeypatch):
    monkeypatch.setenv("LD_JOB_QUEUE", "inline")
    assert isinstance(get_job_queue(), InlineJobQueue)


def test_factory_sqs_returns_sqs(monkeypatch):
    monkeypatch.setenv("LD_JOB_QUEUE", "sqs")
    monkeypatch.setenv("LD_SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    # Provide dummy creds so boto3 client construction does not fail.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    store = get_job_queue()
    assert isinstance(store, SqsJobQueue)
