"""Tests for the AI Digest LLM service."""
from __future__ import annotations


def test_parse_numbered_summaries():
    from app.services.ai_digest_llm_service import AIDigestLLMService

    class FakeItem:
        def __init__(self, id: int):
            self.id = id

    service = AIDigestLLMService.__new__(AIDigestLLMService)
    items = [FakeItem(100), FakeItem(200), FakeItem(300)]
    text = (
        "[1] Claude Code now supports terminal integration.\n"
        "[2] OpenAI released GPT-5 turbo with improved reasoning.\n"
        "[3] Google DeepMind's Gemini 2.5 achieves new coding benchmarks."
    )
    result = service._parse_numbered_summaries(text, items)
    assert result[100] == "Claude Code now supports terminal integration."
    assert result[200] == "OpenAI released GPT-5 turbo with improved reasoning."
    assert result[300] == "Google DeepMind's Gemini 2.5 achieves new coding benchmarks."


def test_parse_numbered_summaries_alternate_format():
    from app.services.ai_digest_llm_service import AIDigestLLMService

    class FakeItem:
        def __init__(self, id: int):
            self.id = id

    service = AIDigestLLMService.__new__(AIDigestLLMService)
    items = [FakeItem(10), FakeItem(20)]
    text = "1. First summary here.\n2. Second summary here."
    result = service._parse_numbered_summaries(text, items)
    assert result[10] == "First summary here."
    assert result[20] == "Second summary here."


def test_parse_numbered_summaries_out_of_range():
    from app.services.ai_digest_llm_service import AIDigestLLMService

    class FakeItem:
        def __init__(self, id: int):
            self.id = id

    service = AIDigestLLMService.__new__(AIDigestLLMService)
    items = [FakeItem(1)]
    text = "[1] Valid.\n[99] Out of range."
    result = service._parse_numbered_summaries(text, items)
    assert 1 in result
    assert len(result) == 1
