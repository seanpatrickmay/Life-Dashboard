"""LLM-powered summarization for the AI Digest."""
from __future__ import annotations

import re

from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient, get_shared_openai_client
from app.db.models.ai_digest import DigestItem

_SUMMARIZE_MODEL = "gpt-4o-mini"

_SUMMARIZE_INSTRUCTIONS = (
    "You are a concise technical news summarizer. For each item, write a 1-2 sentence "
    "summary that captures the key takeaway for a software developer. Be specific about "
    "what changed or what was announced. No hype, no filler."
)

_NARRATIVE_INSTRUCTIONS = (
    "You are a concise AI industry analyst writing a daily briefing for a software "
    "developer who uses Claude Code daily. Given today's AI news items, write a 2-3 "
    "paragraph overview that:\n"
    "1. Opens with the single most important development of the day\n"
    "2. Groups related items into coherent themes\n"
    "3. Explains why each theme matters for a developer using AI tools\n"
    "4. Closes with one actionable takeaway or thing to watch\n"
    "Write in a direct, analytical tone. No hype. No filler."
)


class AIDigestLLMService:

    def __init__(self) -> None:
        self._client = OpenAIResponsesClient(
            client=get_shared_openai_client(),
            model_name=_SUMMARIZE_MODEL,
        )

    async def summarize_items(self, items: list[DigestItem]) -> dict[int, str]:
        needs_summary = [item for item in items if not item.llm_summary and item.title]
        if not needs_summary:
            return {}

        lines = []
        for i, item in enumerate(needs_summary):
            snippet = item.summary[:200] if item.summary else ""
            lines.append(f"[{i+1}] {item.title}")
            if snippet:
                lines.append(f"    {snippet}")

        prompt = (
            "Summarize each numbered news item in 1-2 sentences. "
            "Return ONLY numbered summaries matching the input numbers.\n\n"
            + "\n".join(lines)
        )

        try:
            result = await self._client.generate_text(
                prompt,
                temperature=0.2,
                max_output_tokens=2000,
                instructions=_SUMMARIZE_INSTRUCTIONS,
            )
            return self._parse_numbered_summaries(result.text, needs_summary)
        except Exception as exc:
            logger.warning("LLM summarization failed, using RSS summaries: {}", exc)
            return {}

    def _parse_numbered_summaries(self, text: str, items: list[DigestItem]) -> dict[int, str]:
        summaries: dict[int, str] = {}
        pattern = re.compile(r"^\s*\[?(\d+)\]?[.):]?\s*(.+)", re.MULTILINE)
        for match in pattern.finditer(text):
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(items):
                summary = match.group(2).strip()
                if summary:
                    summaries[items[idx].id] = summary
        return summaries

    async def generate_narrative(self, items: list[DigestItem]) -> str | None:
        if not items:
            return None

        lines = []
        for item in items[:30]:
            category = item.category or "general"
            summary = item.llm_summary or item.summary or ""
            lines.append(f"- [{category}] {item.title}: {summary[:150]}")

        prompt = "Today's AI news items:\n\n" + "\n".join(lines)

        try:
            result = await self._client.generate_text(
                prompt,
                temperature=0.3,
                max_output_tokens=500,
                instructions=_NARRATIVE_INSTRUCTIONS,
            )
            return result.text if result.text else None
        except Exception as exc:
            logger.warning("Daily narrative generation failed: {}", exc)
            return None
