"""Generate concise calendar titles for todo-linked events."""
from __future__ import annotations

import re


DEFAULT_MAX_TITLE_LENGTH = 48
ELLIPSIS = "…"
PREFIX_PATTERN = re.compile(r"^(todo|task)[:\-]\s*", re.IGNORECASE)
BULLET_PATTERN = re.compile(r"^[•\-\*]\s*")


class TodoCalendarTitleAgent:
    """Create succinct calendar event titles from todo text."""

    def __init__(self, max_length: int = DEFAULT_MAX_TITLE_LENGTH) -> None:
        """Initialize the title generator.

        Args:
            max_length: Maximum allowed title length before truncation.
        """
        self.max_length = max_length

    def build_title(self, text: str) -> str:
        """Generate a calendar-friendly title from raw todo text.

        Args:
            text: Raw todo string.

        Returns:
            Cleaned and truncated title string.
        """
        normalized = _normalize_title(text)
        if not normalized:
            return "Todo"
        if len(normalized) <= self.max_length:
            return normalized
        return _truncate_title(normalized, self.max_length)


def _normalize_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    cleaned = BULLET_PATTERN.sub("", cleaned)
    cleaned = PREFIX_PATTERN.sub("", cleaned)
    return cleaned


def _truncate_title(text: str, max_length: int) -> str:
    if max_length <= 0:
        return ""
    if max_length <= len(ELLIPSIS):
        return text[:max_length]
    candidate = text[: max_length + 1]
    cutoff = candidate.rfind(" ")
    if cutoff < max(6, max_length // 2):
        cutoff = max_length
    trimmed = text[:cutoff].rstrip(" ,.;:!-")
    return f"{trimmed}{ELLIPSIS}"
