from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/life_dashboard_test")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")

from app.schemas.llm_outputs import TodoCalendarTitleOutput  # noqa: E402
from app.services.todo_calendar_title_agent import TodoCalendarTitleAgent  # noqa: E402


def test_build_title_formats_prompt_without_key_error(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    class FakeClient:
        async def generate_json(self, prompt: str, *, response_model, temperature: float):
            prompts.append(prompt)
            return SimpleNamespace(
                data=TodoCalendarTitleOutput(
                    title="Send permit packet",
                    details="to Sam tonight",
                )
            )

    monkeypatch.setattr(
        "app.services.todo_calendar_title_agent.OpenAIResponsesClient",
        lambda: FakeClient(),
    )

    agent = TodoCalendarTitleAgent(max_length=12, max_details_length=40)
    result = asyncio.run(
        agent.build_title(
            "Please send the signed permit packet to Sam tonight after dinner.",
            allow_llm=True,
        )
    )

    assert result.title == "Send permit"
    assert result.details == "to Sam tonight"
    assert prompts
    assert '{"title": "string", "details": "string"}' in prompts[0]
