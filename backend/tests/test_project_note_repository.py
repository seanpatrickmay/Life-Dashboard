from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
  sys.path.insert(0, str(backend_root))

os.environ["APP_ENV"] = "local"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://life_dashboard:life_dashboard@localhost:5432/life_dashboard"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = "x" * 32
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["READINESS_ADMIN_TOKEN"] = "test-token"
os.environ["GOOGLE_CLIENT_ID_LOCAL"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET_LOCAL"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI_LOCAL"] = "http://localhost:8000/api/auth/google/callback"

from app.db.repositories.project_note_repository import ProjectNoteRepository


class _FakeScalarResult:
  def all(self) -> list[object]:
    return []


class _FakeResult:
  def scalars(self) -> _FakeScalarResult:
    return _FakeScalarResult()


class _CapturingSession:
  def __init__(self) -> None:
    self.statement = None

  async def execute(self, statement):  # noqa: ANN001
    self.statement = statement
    return _FakeResult()


def test_list_for_project_filters_archived_and_orders() -> None:
  session = _CapturingSession()
  repo = ProjectNoteRepository(session)  # type: ignore[arg-type]

  asyncio.run(repo.list_for_project(user_id=11, project_id=22))
  sql = str(session.statement)

  assert "project_note.user_id = :user_id_1" in sql
  assert "project_note.project_id = :project_id_1" in sql
  assert "project_note.archived IS false" in sql
  assert "ORDER BY project_note.pinned DESC, project_note.updated_at DESC" in sql


def test_list_for_project_can_include_archived() -> None:
  session = _CapturingSession()
  repo = ProjectNoteRepository(session)  # type: ignore[arg-type]

  asyncio.run(repo.list_for_project(user_id=11, project_id=22, include_archived=True))
  sql = str(session.statement)

  assert "project_note.user_id = :user_id_1" in sql
  assert "project_note.project_id = :project_id_1" in sql
  assert "project_note.archived IS false" not in sql
  assert "ORDER BY project_note.pinned DESC, project_note.updated_at DESC" in sql
