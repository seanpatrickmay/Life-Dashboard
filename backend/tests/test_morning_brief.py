"""Tests for the POST /api/morning/brief endpoint."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.db.session import get_session


# ---------------------------------------------------------------------------
# Helpers / shared doubles
# ---------------------------------------------------------------------------

FAKE_PARAGRAPH = "With 7.2h of solid sleep your body is primed for the deep work block at 9 AM — lean into 'Why Attention Is the New Currency': it maps directly to what you're protecting this morning. What would make today count?"


def _build_client(generate_text_return: str = FAKE_PARAGRAPH, raise_exc: Exception | None = None) -> TestClient:
    """Build a TestClient with auth and DB overridden, LLM patched."""
    from app.routers import morning_brief as morning_brief_router

    app = FastAPI()
    app.include_router(morning_brief_router.router, prefix="/api")

    async def override_get_session():
        yield SimpleNamespace()

    async def override_get_current_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    if raise_exc is not None:
        mock_result = AsyncMock(side_effect=raise_exc)
    else:
        mock_result = AsyncMock(
            return_value=SimpleNamespace(text=generate_text_return, total_tokens=80)
        )

    with patch.object(morning_brief_router, "OpenAIResponsesClient") as MockClient:
        instance = MockClient.return_value
        instance.generate_text = mock_result
        client = TestClient(app, raise_server_exceptions=False)
        # Store the mock so tests can inspect prompt calls
        client._mock_llm_instance = instance  # type: ignore[attr-defined]
        return client


# ---------------------------------------------------------------------------
# Shared full-signal payload
# ---------------------------------------------------------------------------

FULL_PAYLOAD = {
    "readiness": {
        "score": 74,
        "label": "Balanced",
        "sleep_hours": 7.2,
        "hrv_ms": 58.0,
        "narrative": "HRV is trending up this week.",
    },
    "events": [
        {"summary": "Deep work block", "start_time": "2026-06-07T09:00:00-04:00"},
        {"summary": "Team Standup", "start_time": "2026-06-07T11:00:00-04:00"},
    ],
    "overdue_tasks": ["Draft quarterly update", "Review PR #42"],
    "reads": [
        {"title": "Why Attention Is the New Currency", "annotation": "Relevant to your focus patterns."},
        {"title": "The Compounding Effect of Sleep Debt", "annotation": None},
    ],
}


# ---------------------------------------------------------------------------
# Test: full signals → 200 + paragraph
# ---------------------------------------------------------------------------

class TestMorningBriefFullSignals:
    def test_returns_200_with_paragraph(self) -> None:
        from app.routers import morning_brief as router_mod

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_instance = AsyncMock()
        mock_instance.generate_text = AsyncMock(
            return_value=SimpleNamespace(text=FAKE_PARAGRAPH, total_tokens=80)
        )

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/morning/brief", json=FULL_PAYLOAD)

        assert response.status_code == 200
        body = response.json()
        assert "paragraph" in body
        assert FAKE_PARAGRAPH in body["paragraph"]

    def test_prompt_includes_readiness_signal(self) -> None:
        from app.routers import morning_brief as router_mod

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        captured_prompt: list[str] = []

        async def capture_generate_text(prompt: str, **kwargs):  # noqa: ANN002
            captured_prompt.append(prompt)
            return SimpleNamespace(text=FAKE_PARAGRAPH, total_tokens=80)

        mock_instance = AsyncMock()
        mock_instance.generate_text = capture_generate_text

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            client.post("/api/morning/brief", json=FULL_PAYLOAD)

        assert len(captured_prompt) == 1
        prompt = captured_prompt[0]
        # Readiness signals are in prompt
        assert "74" in prompt or "Balanced" in prompt or "7.2" in prompt
        # Events in prompt
        assert "Deep work" in prompt or "Standup" in prompt
        # Tasks in prompt
        assert "Draft quarterly" in prompt or "overdue" in prompt.lower()
        # Reads in prompt
        assert "Attention" in prompt or "Currency" in prompt
        # Synthesis instruction present
        assert "synth" in prompt.lower() or "connect" in prompt.lower() or "tie" in prompt.lower() or "weav" in prompt.lower()
        # Reflection close instruction present
        assert "What would make today count" in prompt

    def test_prompt_instructs_synthesis_and_reflection_close(self) -> None:
        from app.routers import morning_brief as router_mod
        from app.prompts.llm_prompts import MORNING_BRIEF_PROMPT

        # The template must mention synthesis and the reflection close
        assert "What would make today count" in MORNING_BRIEF_PROMPT
        # Must instruct tying domains together
        synthesis_keywords = ["synth", "connect", "tie", "weav", "cross-domain", "together"]
        assert any(kw in MORNING_BRIEF_PROMPT.lower() for kw in synthesis_keywords)


# ---------------------------------------------------------------------------
# Test: partial signals (no events) → still 200
# ---------------------------------------------------------------------------

class TestMorningBriefPartialSignals:
    def test_no_events_still_returns_200(self) -> None:
        from app.routers import morning_brief as router_mod

        payload = {
            "readiness": {"score": 60, "label": "Moderate", "sleep_hours": 6.0, "hrv_ms": None, "narrative": None},
            "events": [],
            "overdue_tasks": [],
            "reads": [],
        }

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_instance = AsyncMock()
        mock_instance.generate_text = AsyncMock(
            return_value=SimpleNamespace(text="A light morning to build on. What would make today count?", total_tokens=30)
        )

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/morning/brief", json=payload)

        assert response.status_code == 200
        assert "paragraph" in response.json()

    def test_null_readiness_still_returns_200(self) -> None:
        from app.routers import morning_brief as router_mod

        payload = {
            "readiness": None,
            "events": [{"summary": "Team Standup", "start_time": None}],
            "overdue_tasks": ["Finish report"],
            "reads": [{"title": "Flow States", "annotation": "A deep dive."}],
        }

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_instance = AsyncMock()
        mock_instance.generate_text = AsyncMock(
            return_value=SimpleNamespace(text="Team Standup is up first. What would make today count?", total_tokens=25)
        )

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/morning/brief", json=payload)

        assert response.status_code == 200
        assert "paragraph" in response.json()


# ---------------------------------------------------------------------------
# Test: LLM failure → clean 502 error (not 500-crash), frontend can fall back
# ---------------------------------------------------------------------------

class TestMorningBriefLLMFailure:
    def test_llm_exception_returns_502_not_500(self) -> None:
        from app.routers import morning_brief as router_mod

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_instance = AsyncMock()
        mock_instance.generate_text = AsyncMock(side_effect=RuntimeError("OpenAI connection failed"))

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/morning/brief", json=FULL_PAYLOAD)

        assert response.status_code == 502
        body = response.json()
        assert "detail" in body

    def test_empty_llm_response_returns_502(self) -> None:
        from app.routers import morning_brief as router_mod

        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        async def override_get_current_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_instance = AsyncMock()
        mock_instance.generate_text = AsyncMock(
            return_value=SimpleNamespace(text="", total_tokens=0)
        )

        with patch.object(router_mod, "OpenAIResponsesClient", return_value=mock_instance):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/morning/brief", json=FULL_PAYLOAD)

        assert response.status_code == 502


# ---------------------------------------------------------------------------
# Test: auth required — unauthenticated request returns 401/403
# ---------------------------------------------------------------------------

class TestMorningBriefAuth:
    def test_unauthenticated_request_rejected(self) -> None:
        from app.routers import morning_brief as router_mod

        # Build a plain app with NO auth override — the real dependency will fire
        app = FastAPI()
        app.include_router(router_mod.router, prefix="/api")

        async def override_get_session():
            yield SimpleNamespace()

        app.dependency_overrides[get_session] = override_get_session
        # Intentionally do NOT override get_current_user

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/morning/brief", json=FULL_PAYLOAD)

        assert response.status_code in {401, 403}
