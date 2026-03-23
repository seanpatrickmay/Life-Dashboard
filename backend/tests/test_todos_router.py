from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.auth import get_current_user
from app.db.models.todo import TodoItem
from app.db.session import get_session
from app.routers import todos as todos_router


class FakeSession:
    def __init__(self) -> None:
        self.flush_calls = 0
        self.commit_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeTodoRepository:
    todo: TodoItem | None = None
    delete_calls: list[tuple[int, int]] = []

    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session

    async def get_for_user(self, user_id: int, todo_id: int) -> TodoItem | None:
        todo = self.todo
        if todo is None or todo.id != todo_id or todo.user_id != user_id:
            return None
        return todo

    async def delete_for_user(self, user_id: int, todo_id: int) -> None:
        self.delete_calls.append((user_id, todo_id))
        todo = await self.get_for_user(user_id, todo_id)
        if todo is not None:
            self.todo = None


class FakeProjectRepository:
    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session

    async def get_for_user(self, user_id: int, project_id: int):  # noqa: ANN001
        return SimpleNamespace(id=project_id, user_id=user_id)


class FakeSuggestionRepository:
    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session

    async def delete_for_todo(self, user_id: int, todo_id: int) -> None:  # noqa: ARG002
        return None


class FakeCalendarLinkService:
    unlink_calls: list[tuple[int, bool]] = []
    upsert_calls: list[tuple[int, str | None]] = []

    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session

    async def unlink_todo(self, todo: TodoItem, *, delete_event: bool) -> None:
        self.unlink_calls.append((todo.id, delete_event))

    async def upsert_event_for_todo(self, todo: TodoItem, *, time_zone: str | None) -> None:
        self.upsert_calls.append((todo.id, time_zone))


def build_client(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(todos_router.router, prefix="/api")

    async def override_get_session():
        yield session

    async def override_get_current_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


@pytest.fixture(autouse=True)
def patch_router_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(todos_router, "TodoRepository", FakeTodoRepository)
    monkeypatch.setattr(todos_router, "ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr(todos_router, "TodoProjectSuggestionRepository", FakeSuggestionRepository)
    monkeypatch.setattr(todos_router, "TodoCalendarLinkService", FakeCalendarLinkService)
    monkeypatch.setattr(
        todos_router.AsyncAIService,
        "get_cached_accomplishment",
        staticmethod(lambda text: f"Completed {text}"),
    )
    monkeypatch.setattr(
        todos_router.AsyncAIService,
        "schedule_accomplishment_generation",
        staticmethod(lambda todo_id, user_id, text: None),
    )
    FakeCalendarLinkService.unlink_calls.clear()
    FakeCalendarLinkService.upsert_calls.clear()
    FakeTodoRepository.delete_calls.clear()


def test_update_todo_accepts_historical_completion_timestamp() -> None:
    session = FakeSession()
    client = build_client(session)
    now = datetime(2026, 3, 11, 0, 45, tzinfo=timezone.utc)
    todo = TodoItem(
        id=7,
        user_id=1,
        project_id=2,
        text="Replay-created todo",
        completed=False,
    )
    todo.deadline_is_date_only = False
    todo.created_at = now
    todo.updated_at = now
    FakeTodoRepository.todo = todo

    response = client.patch(
        "/api/todos/7",
        json={
            "completed": True,
            "completed_at_utc": "2025-12-12T15:30:00Z",
            "time_zone": "America/New_York",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    assert body["completed_at_utc"] == "2025-12-12T15:30:00Z"
    assert todo.completed is True
    assert todo.completed_at_utc == datetime(2025, 12, 12, 15, 30, tzinfo=timezone.utc)
    assert todo.completed_time_zone == "America/New_York"
    assert todo.completed_local_date == date(2025, 12, 12)
    assert todo.accomplishment_text == "Completed Replay-created todo"
    assert FakeCalendarLinkService.unlink_calls == [(7, True)]


def test_update_todo_can_rewrite_timestamp_for_already_completed_todo() -> None:
    session = FakeSession()
    client = build_client(session)
    now = datetime(2026, 3, 11, 0, 45, tzinfo=timezone.utc)
    todo = TodoItem(
        id=8,
        user_id=1,
        project_id=2,
        text="Already complete",
        completed=True,
    )
    todo.deadline_is_date_only = False
    todo.created_at = now
    todo.updated_at = now
    todo.completed_at_utc = datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc)
    todo.completed_time_zone = "UTC"
    todo.completed_local_date = date(2026, 1, 1)
    FakeTodoRepository.todo = todo

    response = client.patch(
        "/api/todos/8",
        json={
            "completed_at_utc": "2025-12-10T04:15:00Z",
            "time_zone": "America/New_York",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completed_at_utc"] == "2025-12-10T04:15:00Z"
    assert todo.completed is True
    assert todo.completed_at_utc == datetime(2025, 12, 10, 4, 15, tzinfo=timezone.utc)
    assert todo.completed_time_zone == "America/New_York"
    assert todo.completed_local_date == date(2025, 12, 9)
    assert FakeCalendarLinkService.unlink_calls == [(8, True)]


def test_delete_todo_uses_repository_cleanup_before_commit() -> None:
    session = FakeSession()
    client = build_client(session)
    now = datetime(2026, 3, 11, 0, 45, tzinfo=timezone.utc)
    todo = TodoItem(
        id=96,
        user_id=1,
        project_id=2,
        text="Replay-created todo",
        completed=False,
    )
    todo.deadline_is_date_only = False
    todo.created_at = now
    todo.updated_at = now
    FakeTodoRepository.todo = todo

    response = client.delete("/api/todos/96")

    assert response.status_code == 204
    assert FakeCalendarLinkService.unlink_calls == [(96, True)]
    assert FakeTodoRepository.delete_calls == [(1, 96)]
    assert session.commit_calls == 1
