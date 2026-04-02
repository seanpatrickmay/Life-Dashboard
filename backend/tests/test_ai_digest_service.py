"""Tests for the AI Digest service."""
from __future__ import annotations

import pytest


def test_normalize_url_strips_tracking_params():
    from app.services.ai_digest_service import normalize_url
    raw = "https://example.com/article?utm_source=rss&utm_medium=feed&ref=newsletter"
    result = normalize_url(raw)
    assert result == "https://example.com/article"


def test_normalize_url_lowercases_and_strips_trailing_slash():
    from app.services.ai_digest_service import normalize_url
    raw = "HTTPS://Example.COM/Article/"
    result = normalize_url(raw)
    assert result == "https://example.com/article"


def test_normalize_url_removes_www():
    from app.services.ai_digest_service import normalize_url
    raw = "https://www.example.com/article"
    result = normalize_url(raw)
    assert result == "https://example.com/article"


def test_normalize_url_preserves_path_params():
    from app.services.ai_digest_service import normalize_url
    raw = "https://github.com/anthropics/claude-code/releases/tag/v2.1.0"
    result = normalize_url(raw)
    assert result == "https://github.com/anthropics/claude-code/releases/tag/v2.1.0"


def test_content_hash_is_deterministic():
    from app.services.ai_digest_service import _content_hash
    h1 = _content_hash("Claude Code v2.1", "https://github.com/anthropics/claude-code/releases/tag/v2.1")
    h2 = _content_hash("Claude Code v2.1", "https://github.com/anthropics/claude-code/releases/tag/v2.1")
    assert h1 == h2
    assert len(h1) == 16


def test_content_hash_differs_for_different_input():
    from app.services.ai_digest_service import _content_hash
    h1 = _content_hash("Title A", "https://a.com")
    h2 = _content_hash("Title B", "https://b.com")
    assert h1 != h2
