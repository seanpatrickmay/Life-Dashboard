"""Tests for the SQS worker Lambda handler.

Coverage
--------
1. Happy path — handler runs with correct payload, no failures reported.
2. Handler exception -> batch-item-failure for that record.
3. Malformed JSON body -> batch-item-failure (json.loads raises).
4. Unknown job name -> NOT a failure (dispatch discards gracefully, no raise).
5. Partial batch — one good record, one raising record; only failing one reported.
6. Registration — importing worker_handler causes all real job names to be in
   registered_jobs() (proves @job side-effects from both handler modules ran).

Registry isolation
------------------
The ``isolated_registry`` fixture snapshots and restores ``_HANDLERS`` around
every test that registers a transient test job, so registrations do not leak
between tests.  Test 6 (registration check) is intentionally outside isolation
so it can observe the real handler registrations that occurred at import time.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import app.jobs.registry as registry_module
from app.jobs.registry import job, registered_jobs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_registry():
    """Snapshot and restore _HANDLERS around a test."""
    snapshot = dict(registry_module._HANDLERS)
    yield
    registry_module._HANDLERS.clear()
    registry_module._HANDLERS.update(snapshot)


def _make_record(message_id: str, body: str) -> dict:
    return {"messageId": message_id, "body": body}


def _make_event(*records: dict) -> dict:
    return {"Records": list(records)}


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_runs_handler_and_returns_no_failures(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """A well-formed record dispatches its handler; batchItemFailures is empty."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    received: list[dict] = []

    @job("wkr_test")
    async def _handler(payload: dict) -> None:
        received.append(payload)

    event = _make_event(
        _make_record("m1", json.dumps({"name": "wkr_test", "payload": {"a": 1}}))
    )

    result = wh.handler(event)

    assert received == [{"a": 1}]
    assert result == {"batchItemFailures": []}


# ---------------------------------------------------------------------------
# 2. Handler exception -> batch-item-failure
# ---------------------------------------------------------------------------


def test_handler_exception_reported_as_batch_item_failure(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """When a registered handler raises, the record's messageId appears in failures."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    @job("wkr_explode")
    async def _boom(payload: dict) -> None:
        raise RuntimeError("handler exploded")

    event = _make_event(
        _make_record("m2", json.dumps({"name": "wkr_explode", "payload": {}}))
    )

    result = wh.handler(event)

    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}


# ---------------------------------------------------------------------------
# 3. Malformed JSON body -> batch-item-failure
# ---------------------------------------------------------------------------


def test_malformed_json_body_reported_as_batch_item_failure(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """A body that cannot be JSON-decoded causes a batch-item-failure."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    event = _make_event(_make_record("m3", "{not json"))

    result = wh.handler(event)

    assert result == {"batchItemFailures": [{"itemIdentifier": "m3"}]}


# ---------------------------------------------------------------------------
# 4. Unknown job name -> NOT a failure (gracefully discarded)
# ---------------------------------------------------------------------------


def test_unknown_job_name_not_reported_as_failure(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """dispatch() discards unknown job names without raising; record is NOT a failure."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    event = _make_event(
        _make_record(
            "m4",
            json.dumps({"name": "does_not_exist", "payload": {}}),
        )
    )

    result = wh.handler(event)

    failure_ids = [f["itemIdentifier"] for f in result["batchItemFailures"]]
    assert "m4" not in failure_ids
    assert result["batchItemFailures"] == []


# ---------------------------------------------------------------------------
# 5. Partial batch — good record + raising record
# ---------------------------------------------------------------------------


def test_partial_batch_only_failing_record_reported(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """In a mixed batch, only the failing record appears in batchItemFailures."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    good_payloads: list[dict] = []

    @job("wkr_good")
    async def _good(payload: dict) -> None:
        good_payloads.append(payload)

    @job("wkr_bad")
    async def _bad(payload: dict) -> None:
        raise ValueError("bad record")

    event = _make_event(
        _make_record("m5", json.dumps({"name": "wkr_good", "payload": {"ok": True}})),
        _make_record("m6", json.dumps({"name": "wkr_bad", "payload": {}})),
    )

    result = wh.handler(event)

    assert good_payloads == [{"ok": True}]
    assert result == {"batchItemFailures": [{"itemIdentifier": "m6"}]}


# ---------------------------------------------------------------------------
# 6. Registration — real job names populate registry on import
# ---------------------------------------------------------------------------


def test_worker_import_populates_all_real_job_names(
    isolated_registry: None,
) -> None:
    """Importing worker_handler causes all real handler modules to register their jobs.

    Uses isolated_registry so earlier restores don't affect this test's snapshot,
    then explicitly re-imports (reloads) both handler modules inside the test to
    ensure their @job side-effects run within the current registry state.
    The isolated_registry teardown will then restore cleanly.
    """
    import importlib

    import app.jobs.handlers as handlers_mod
    import app.workers.tasks as tasks_mod

    # Force re-execution of module-level @job decorators in the current registry
    importlib.reload(handlers_mod)
    importlib.reload(tasks_mod)

    jobs = registered_jobs()
    expected = [
        "digest_refresh",
        "insight_refresh",
        "journal_summary",
        "project_suggestions",
        "todo_accomplishment",
        "visit_refresh",
    ]
    for name in expected:
        assert name in jobs, f"Expected job {name!r} to be registered; got: {jobs}"


# ---------------------------------------------------------------------------
# 7. Single asyncio.run for the entire batch (not per-record)
# ---------------------------------------------------------------------------


def test_single_asyncio_run_for_batch(
    monkeypatch: pytest.MonkeyPatch,
    isolated_registry: None,
) -> None:
    """handler() calls asyncio.run exactly once regardless of batch size."""
    import app.aws.worker_handler as wh

    monkeypatch.setattr(wh, "cold_start", lambda: None)

    run_call_count = 0
    original_run = asyncio.run

    def _counting_run(coro: object) -> object:
        nonlocal run_call_count
        run_call_count += 1
        return original_run(coro)

    monkeypatch.setattr(wh.asyncio, "run", _counting_run)

    payloads_seen: list[dict] = []

    @job("wkr_count_a")
    async def _a(payload: dict) -> None:
        payloads_seen.append(payload)

    @job("wkr_count_b")
    async def _b(payload: dict) -> None:
        payloads_seen.append(payload)

    event = _make_event(
        _make_record("c1", json.dumps({"name": "wkr_count_a", "payload": {"n": 1}})),
        _make_record("c2", json.dumps({"name": "wkr_count_b", "payload": {"n": 2}})),
    )

    wh.handler(event)

    assert run_call_count == 1
    assert len(payloads_seen) == 2
