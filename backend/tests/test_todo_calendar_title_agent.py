from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.llm_outputs import TodoCalendarTitleOutput
from app.services.todo_calendar_title_agent import TodoCalendarTitleAgent


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
