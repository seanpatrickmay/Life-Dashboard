"""Generate concise calendar titles for todo-linked events."""
from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient
from app.prompts import TODO_CALENDAR_TITLE_PROMPT
from app.schemas.llm_outputs import TodoCalendarTitleOutput


DEFAULT_MAX_TITLE_LENGTH = 50
DEFAULT_MAX_DETAILS_LENGTH = 160
PREFIX_PATTERN = re.compile(r"^(todo|task)[:\-]\s*", re.IGNORECASE)
BULLET_PATTERN = re.compile(r"^[•\-\*]\s*")


@dataclass
class TodoCalendarTitleResult:
    title: str
    details: str | None = None


class TodoCalendarTitleAgent:
    """Create succinct calendar event titles from todo text."""

    def __init__(
        self,
        max_length: int = DEFAULT_MAX_TITLE_LENGTH,
        max_details_length: int = DEFAULT_MAX_DETAILS_LENGTH,
    ) -> None:
        """Initialize the title generator.

        Args:
            max_length: Maximum allowed title length before shortening.
            max_details_length: Maximum allowed details length for descriptions.
        """
        self.max_length = max_length
        self.max_details_length = max_details_length
        self.client = OpenAIResponsesClient()

    def normalize_text(self, text: str) -> str:
        """Normalize todo text for comparisons and hashing."""
        return _normalize_title(text)

    async def build_title(self, text: str, *, allow_llm: bool = True) -> TodoCalendarTitleResult:
        """Generate a calendar-friendly title from raw todo text."""
        normalized = _normalize_title(text)
        if not normalized:
            return TodoCalendarTitleResult("Todo")
        if len(normalized) <= self.max_length:
            return TodoCalendarTitleResult(normalized)
        if not allow_llm:
            return _fallback_title(normalized, self.max_length, self.max_details_length)

        prompt = TODO_CALENDAR_TITLE_PROMPT.format(
            todo_text=normalized,
            max_length=self.max_length,
            max_details=self.max_details_length,
        )
        try:
            result = await self.client.generate_json(
                prompt,
                response_model=TodoCalendarTitleOutput,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[llm-fallback] todo_calendar_title_agent.build_title failed: {}", exc)
            return _fallback_title(normalized, self.max_length, self.max_details_length)
        title = _sanitize_title(result.data.title, self.max_length)
        details = _sanitize_details(
            result.data.details or "",
            self.max_details_length,
            title,
        )
        if title:
            return TodoCalendarTitleResult(title, details)

        return _fallback_title(normalized, self.max_length, self.max_details_length)


def _normalize_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    cleaned = BULLET_PATTERN.sub("", cleaned)
    cleaned = PREFIX_PATTERN.sub("", cleaned)
    return cleaned


def _sanitize_title(value: str, max_length: int) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    cleaned = cleaned.replace("...", "").replace("\u2026", "")
    cleaned = cleaned.rstrip(" ,.;:!-")
    if not cleaned:
        return ""
    if len(cleaned) <= max_length:
        return cleaned
    return _shorten_text(cleaned, max_length)


def _sanitize_details(value: str, max_length: int, title: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value.strip())
    cleaned = cleaned.replace("...", "").replace("\u2026", "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if title and cleaned.lower() == title.lower():
        return None
    if len(cleaned) > max_length:
        cleaned = _shorten_text(cleaned, max_length)
    return cleaned or None


def _shorten_text(text: str, max_length: int) -> str:
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    candidate = text[: max_length + 1]
    cutoff = candidate.rfind(" ")
    if cutoff < max(6, max_length // 2):
        cutoff = max_length
    trimmed = text[:cutoff].rstrip(" ,.;:!-")
    return trimmed[:max_length]


def _fallback_title(
    normalized: str,
    max_length: int,
    max_details_length: int,
) -> TodoCalendarTitleResult:
    title = _shorten_text(normalized, max_length)
    if not title:
        return TodoCalendarTitleResult("Todo")
    details = normalized if normalized.lower() != title.lower() else None
    if details and len(details) > max_details_length:
        details = _shorten_text(details, max_details_length)
    return TodoCalendarTitleResult(title, details)
