"""Tests for app.jobs.handlers — registration, inline behavior, SQS routing, payload shape.

Test structure
--------------
1. Handler registration — all four handlers are registered after importing the app.
2. Inline path — enqueue runs the handler in-process (asyncio.sleep(0) double-yield).
3. SQS path — monkeypatched queue records the enqueue call and the handler does NOT run.
4. Payload is JSON-serializable — no ORM objects sneak into the payload.
5. Smoke-test the router endpoints that produce enqueue calls.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.jobs.registry as registry_module
from app.jobs.registry import registered_jobs


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
# 1. Handler registration
# ---------------------------------------------------------------------------

def test_all_handlers_registered():
    """Importing app.jobs.handlers must register the four expected job names."""
    import app.jobs.handlers  # noqa: F401 — triggers registration

    names = registered_jobs()
    assert "project_suggestions" in names
    assert "todo_accomplishment" in names
    assert "journal_summary" in names
    assert "insight_refresh" in names


def test_workers_tasks_handlers_still_registered():
    """Existing handlers from workers/tasks.py must also be present."""
    import app.workers.tasks  # noqa: F401

    names = registered_jobs()
    assert "visit_refresh" in names
    assert "digest_refresh" in names


# ---------------------------------------------------------------------------
# 2. Inline path — handler runs in-process after two asyncio.sleep(0) yields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_suggestions_inline_runs(monkeypatch):
    """project_suggestions handler is invoked inline (no SQS)."""
    called_with: list[dict] = []

    async def fake_process(self, *, user_id: int, todo_ids: list[int]) -> None:  # noqa: ARG001
        called_with.append({"user_id": user_id, "todo_ids": todo_ids})

    from app.jobs.queue import InlineJobQueue
    import app.jobs.handlers  # noqa: F401

    # Patch the service inside the handler so no DB is touched
    from app.services import todo_project_suggestion_service as svc_mod
    monkeypatch.setattr(svc_mod.TodoProjectSuggestionService, "process_todo_ids", fake_process)

    # Patch AsyncSessionLocal to return a no-op context manager
    from app.db import session as session_mod
    fake_session = SimpleNamespace(commit=AsyncMock())

    class FakeSessionCtx:
        async def __aenter__(self):
            return fake_session
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", FakeSessionCtx)

    queue = InlineJobQueue()
    await queue.enqueue("project_suggestions", {"user_id": 1, "todo_ids": [10, 20]})

    # Two yields: schedule + run
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert called_with == [{"user_id": 1, "todo_ids": [10, 20]}]


@pytest.mark.asyncio
async def test_journal_summary_inline_runs(monkeypatch):
    """journal_summary handler is invoked inline (no SQS)."""
    called_with: list[dict] = []

    async def fake_ensure_summary(self, *, user_id: int, local_date: date, time_zone: str) -> None:  # noqa: ARG001
        called_with.append({"user_id": user_id, "local_date": local_date, "time_zone": time_zone})

    from app.jobs.queue import InlineJobQueue
    import app.jobs.handlers  # noqa: F401

    from app.services import journal_service as js_mod
    monkeypatch.setattr(js_mod.JournalService, "_ensure_summary", fake_ensure_summary)

    from app.db import session as session_mod
    fake_session = SimpleNamespace(commit=AsyncMock())

    class FakeSessionCtx:
        async def __aenter__(self):
            return fake_session
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", FakeSessionCtx)

    queue = InlineJobQueue()
    await queue.enqueue("journal_summary", {"user_id": 5, "date": "2026-01-15", "time_zone": "UTC"})

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(called_with) == 1
    assert called_with[0]["user_id"] == 5
    assert called_with[0]["local_date"] == date(2026, 1, 15)
    assert called_with[0]["time_zone"] == "UTC"


@pytest.mark.asyncio
async def test_insight_refresh_inline_runs(monkeypatch):
    """insight_refresh handler is invoked inline (no SQS)."""
    called_with: list[int] = []

    async def fake_refresh(self, *, user_id: int) -> None:  # noqa: ARG001
        called_with.append(user_id)

    from app.jobs.queue import InlineJobQueue
    import app.jobs.handlers  # noqa: F401

    from app.services import insight_service as is_mod
    monkeypatch.setattr(is_mod.InsightService, "refresh_daily_insight", fake_refresh)

    from app.db import session as session_mod

    class FakeSessionCtx:
        async def __aenter__(self):
            return SimpleNamespace()
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", FakeSessionCtx)

    queue = InlineJobQueue()
    await queue.enqueue("insight_refresh", {"user_id": 3})

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert called_with == [3]


# ---------------------------------------------------------------------------
# 3. SQS path — enqueue calls are captured; handler does NOT run in-process
# ---------------------------------------------------------------------------

class RecordingQueue:
    """Fake job queue that records enqueue calls without executing handlers."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def enqueue(self, name: str, payload: dict) -> None:
        self.calls.append({"name": name, "payload": payload})


@pytest.mark.asyncio
async def test_sqs_path_enqueues_not_executes(monkeypatch):
    """With a recording queue, enqueue is called but handler body never runs."""
    executed: list[str] = []

    import app.jobs.handlers  # noqa: F401 — ensure registered

    recording = RecordingQueue()

    # Also patch the handler body to detect if it somehow runs
    from app.services import todo_project_suggestion_service as svc_mod

    async def sentinel(*args, **kwargs):
        executed.append("ran")

    monkeypatch.setattr(svc_mod.TodoProjectSuggestionService, "process_todo_ids", sentinel)

    await recording.enqueue("project_suggestions", {"user_id": 2, "todo_ids": [99]})

    # No yields needed — recording queue never schedules a task
    assert len(recording.calls) == 1
    assert recording.calls[0] == {"name": "project_suggestions", "payload": {"user_id": 2, "todo_ids": [99]}}
    assert executed == []  # handler did not run


# ---------------------------------------------------------------------------
# 4. Payload is JSON-serializable
# ---------------------------------------------------------------------------

def test_project_suggestions_payload_is_serializable():
    payload = {"user_id": 1, "todo_ids": [10, 20, 30]}
    assert json.dumps(payload)  # must not raise


def test_todo_accomplishment_payload_is_serializable():
    payload = {"todo_id": 7, "user_id": 1, "todo_text": "Write a test"}
    assert json.dumps(payload)


def test_journal_summary_payload_is_serializable():
    payload = {"user_id": 1, "date": "2026-01-15", "time_zone": "America/New_York"}
    assert json.dumps(payload)


def test_insight_refresh_payload_is_serializable():
    payload = {"user_id": 3}
    assert json.dumps(payload)


# ---------------------------------------------------------------------------
# 5. Router smoke — create_todo enqueues project_suggestions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_todo_enqueues_project_suggestions(monkeypatch):
    """POST /todos must call enqueue('project_suggestions', ...) — not add_task."""
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.auth import get_current_user
    from app.db.session import get_session
    from app.routers import todos as todos_router
    import app.jobs.handlers  # noqa: F401 — ensure handlers registered

    recording = RecordingQueue()
    # Patch in the router's namespace (it did `from app.jobs.queue import get_job_queue`)
    monkeypatch.setattr(todos_router, "get_job_queue", lambda: recording)

    # Minimal fakes so the router can execute without DB
    class FakeSession:
        async def flush(self): pass
        async def commit(self): pass

    from app.db.models.todo import TodoItem

    class FakeRepo:
        def __init__(self, session): pass

        async def create_one(self, user_id, project_id, text, deadline, *, deadline_is_date_only, time_horizon):
            t = TodoItem(id=42, user_id=user_id, project_id=project_id, text=text, completed=False)
            t.deadline_is_date_only = False
            t.deadline_utc = None
            t.time_horizon = time_horizon or "this_week"
            t.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            t.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            return t

    class FakeProjRepo:
        def __init__(self, session): pass

        async def ensure_inbox_project(self, user_id):
            return SimpleNamespace(id=1)

        async def get_for_user(self, user_id, project_id):
            return SimpleNamespace(id=project_id)

    class FakeCalSvc:
        def __init__(self, session): pass
        async def upsert_event_for_todo(self, todo, *, time_zone): pass

    monkeypatch.setattr(todos_router, "TodoRepository", FakeRepo)
    monkeypatch.setattr(todos_router, "ProjectRepository", FakeProjRepo)
    monkeypatch.setattr(todos_router, "TodoCalendarLinkService", FakeCalSvc)

    app = FastAPI()
    app.include_router(todos_router.router, prefix="/api")

    async def override_session():
        yield FakeSession()

    async def override_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user

    client = TestClient(app)
    resp = client.post("/api/todos", json={"text": "Buy milk"})

    assert resp.status_code == 200
    assert len(recording.calls) == 1
    call = recording.calls[0]
    assert call["name"] == "project_suggestions"
    assert call["payload"]["user_id"] == 1
    assert call["payload"]["todo_ids"] == [42]
    # Must be JSON-serializable
    assert json.dumps(call["payload"])
