"""Tests for the news title shortening endpoint."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.auth import get_current_user
from app.routers import news


# ── Fixtures ──


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(news.router, prefix="/api")

    async def override_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


# ── Unit Tests (mocked LLM) ──


class TestShortenTitlesMocked:
    """Tests with a mocked OpenAI client."""

    def test_empty_titles_returns_empty(self):
        client = _make_client()
        resp = client.post("/api/news/shorten-titles", json={"titles": []})
        assert resp.status_code == 200
        assert resp.json() == {"short_titles": []}

    @patch("app.routers.news.OpenAIResponsesClient")
    def test_returns_shortened_titles(self, MockClient):
        mock_llm = AsyncMock()
        mock_llm.generate_text.return_value = AsyncMock(
            text="AI Reshapes Healthcare\nBitcoin Hits Record High"
        )
        MockClient.return_value = mock_llm

        client = _make_client()
        resp = client.post("/api/news/shorten-titles", json={
            "titles": [
                "How Artificial Intelligence Is Reshaping the Future of Healthcare Delivery",
                "Bitcoin Surges Past $100,000, Hitting All-Time Record High Amid Market Rally",
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["short_titles"]) == 2
        assert data["short_titles"][0] == "AI Reshapes Healthcare"
        assert data["short_titles"][1] == "Bitcoin Hits Record High"

    @patch("app.routers.news.OpenAIResponsesClient")
    def test_pads_missing_responses_with_originals(self, MockClient):
        """If LLM returns fewer lines than titles, fall back to originals."""
        mock_llm = AsyncMock()
        mock_llm.generate_text.return_value = AsyncMock(text="Short Title One")
        MockClient.return_value = mock_llm

        client = _make_client()
        resp = client.post("/api/news/shorten-titles", json={
            "titles": ["Original Title One", "Original Title Two"]
        })
        data = resp.json()
        assert data["short_titles"][0] == "Short Title One"
        assert data["short_titles"][1] == "Original Title Two"  # fallback


# ── Live LLM Tests ──


def _require_live_llm() -> None:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM tests.")


class TestShortenTitlesLive:
    """Tests that make real calls to gpt-4o-mini."""

    @pytest.mark.live_llm
    def test_live_shortens_real_titles(self):
        """Send real article titles to gpt-4o-mini and verify shortened output."""
        _require_live_llm()

        client = _make_client()
        titles = [
            "The United States and China Reach a Tentative Agreement on Trade Tariffs After Months of Negotiations",
            "Scientists Discover New Species of Deep-Sea Fish in the Mariana Trench During Research Expedition",
            "Apple Announces Next-Generation M5 Chip with Unprecedented Performance Gains for MacBook Pro",
        ]
        resp = client.post("/api/news/shorten-titles", json={"titles": titles})
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["short_titles"]) == 3
        for i, short in enumerate(data["short_titles"]):
            assert len(short) > 0, f"Title {i} is empty"
            assert len(short) <= 60, f"Title {i} too long ({len(short)} chars): {short}"
            assert short != titles[i], f"Title {i} was not shortened"

    @pytest.mark.live_llm
    def test_live_preserves_meaning(self):
        """Shortened titles should still contain key subject matter."""
        _require_live_llm()

        client = _make_client()
        resp = client.post("/api/news/shorten-titles", json={
            "titles": [
                "NASA's Perseverance Rover Finds Compelling Evidence of Ancient Microbial Life on Mars",
            ]
        })
        assert resp.status_code == 200
        short = resp.json()["short_titles"][0].lower()
        # Should mention Mars or Perseverance or life — at least one key concept
        assert any(kw in short for kw in ["mars", "perseverance", "life", "rover", "nasa", "microbial"]), \
            f"Short title lost meaning: {short}"
