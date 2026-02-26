from __future__ import annotations

import os
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://life_dashboard:life_dashboard@localhost:5432/life_dashboard"
)
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "x" * 32)
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_CLIENT_ID_LOCAL", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET_LOCAL", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI_LOCAL", "http://localhost:8000/api/auth/google/callback")

from app.db.models.todo import TodoItem
from app.services.todo_project_suggestion_service import INBOX_PROJECT_NAME, TodoProjectSuggestionService


def _build_todo(todo_id: int, text: str) -> TodoItem:
    return TodoItem(id=todo_id, user_id=1, project_id=1, text=text, completed=False)


def test_heuristic_uses_existing_project_name_overlap() -> None:
    service = TodoProjectSuggestionService.__new__(TodoProjectSuggestionService)
    todo = _build_todo(101, "Finish onboarding checklist for capital one")

    assignment = service._heuristic_assignment(todo, ["Capital One Onboarding", "School Work"])

    assert assignment.project_name == "Capital One Onboarding"
    assert assignment.confidence >= 0.8


def test_heuristic_keyword_fallback() -> None:
    service = TodoProjectSuggestionService.__new__(TodoProjectSuggestionService)
    todo = _build_todo(102, "Submit reimbursement form and receipts")

    assignment = service._heuristic_assignment(todo, [])

    assert assignment.project_name == "Finance"
    assert assignment.confidence >= 0.75


def test_heuristic_defaults_to_inbox_when_uncertain() -> None:
    service = TodoProjectSuggestionService.__new__(TodoProjectSuggestionService)
    todo = _build_todo(103, "Buy birthday gift")

    assignment = service._heuristic_assignment(todo, [])

    assert assignment.project_name == INBOX_PROJECT_NAME
    assert assignment.confidence < 0.75
