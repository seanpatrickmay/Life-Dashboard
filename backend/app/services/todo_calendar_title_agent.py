"""Generate concise calendar titles for todo-linked events."""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from google.genai.types import GenerateContentConfig

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
    from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
    HttpOptions = None  # type: ignore[assignment]
from loguru import logger

from app.clients.genai_client import build_genai_client
from app.core.config import settings
from app.prompts import TODO_CALENDAR_TITLE_PROMPT


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
        http_options = HttpOptions(api_version="v1") if HttpOptions else None
        self.client = build_genai_client(http_options=http_options)
        self.model_name = settings.vertex_model_name or "gemini-2.5-flash"

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
            response = await self._call_model(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[todos] calendar title fallback: {}", exc)
            return _fallback_title(normalized, self.max_length, self.max_details_length)
        payload = self._safe_parse_json(response)
        if payload:
            title = _sanitize_title(str(payload.get("title") or ""), self.max_length)
            details = _sanitize_details(
                str(payload.get("details") or ""),
                self.max_details_length,
                title,
            )
            if title:
                return TodoCalendarTitleResult(title, details)

        return _fallback_title(normalized, self.max_length, self.max_details_length)

    async def _call_model(self, prompt: str) -> str:
        def _invoke() -> str:
            config = GenerateContentConfig(temperature=0.2)
            logger.debug("[todos] calendar title model chars=%s", len(prompt))
            result = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return result.text or ""

        return await asyncio.to_thread(_invoke)

    def _safe_parse_json(self, text: str) -> dict[str, Any] | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None


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
