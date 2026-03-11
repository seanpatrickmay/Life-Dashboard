from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import MethodType

from dotenv import load_dotenv

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
load_dotenv(backend_root.parent / ".env")

from app.db.models.todo import TodoItem
from app.db.repositories.todo_repository import TodoRepository


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[object] = []

    async def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)
        return None


def test_delete_for_user_nulls_imessage_audit_refs_before_delete() -> None:
    session = FakeSession()
    repo = TodoRepository(session)
    todo = TodoItem(
        id=83,
        user_id=1,
        project_id=2,
        text="Send $18.01",
        completed=False,
    )
    todo.created_at = datetime(2025, 12, 11, 18, 2, 38, tzinfo=timezone.utc)
    todo.updated_at = todo.created_at

    async def fake_get_for_user(self, user_id: int, todo_id: int) -> TodoItem | None:
        if user_id == 1 and todo_id == 83:
            return todo
        return None

    repo.get_for_user = MethodType(fake_get_for_user, repo)

    run(repo.delete_for_user(1, 83))

    statements = [str(stmt) for stmt in session.executed]
    audit_update_index = next(
        i
        for i, stmt in enumerate(statements)
        if "UPDATE imessage_action_audit SET target_todo_id" in stmt and "user_id" not in stmt
    )
    todo_delete_index = next(i for i, stmt in enumerate(statements) if "DELETE FROM todo_item" in stmt)
    assert audit_update_index < todo_delete_index
