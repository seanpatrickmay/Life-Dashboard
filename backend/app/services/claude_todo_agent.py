"""Claude-style todo agent backed by Google GenAI + Vertex AI."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dateutil import parser as date_parser
from google import genai
from google.genai.types import GenerateContentConfig

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
  from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
  HttpOptions = None  # type: ignore[assignment]
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.repositories.todo_repository import TodoRepository
from app.prompts import CLAUDE_TODO_EXTRACTION_PROMPT
from app.utils.timezone import eastern_now, ensure_eastern


@dataclass
class ClaudeTodoResult:
  """Structured result from the Claude todo agent."""

  session_id: str
  reply: str
  items: list[Any]
  raw_payload: dict[str, Any] | None = None


class ClaudeTodoAgent:
  """Todo mentor that uses Gemini via Vertex AI for parsing + normalization."""

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.repo = TodoRepository(session)
    http_options = HttpOptions(api_version="v1") if HttpOptions else None
    client_kwargs = {"http_options": http_options} if http_options else {}
    self.client = genai.Client(**client_kwargs)
    self.model_name = settings.vertex_model_name or "gemini-2.5-flash"

  async def respond(
    self, user_id: int, message: str, request_id: str | None = None
  ) -> ClaudeTodoResult:
    request_id = request_id or str(uuid4())
    logger.info("[claude-todo] respond start id={} user={} text={}", request_id, user_id, message)

    parsed = await self._extract_todos(message)
    logger.info("[claude-todo] parsed payload={}", parsed)

    items = parsed.get("items") or []
    if not isinstance(items, list) or not items:
      logger.info("[claude-todo] no todos detected for request id={}", request_id)
      return ClaudeTodoResult(
        session_id=request_id,
        reply="I didn't find a clear task to track yet. Try something like ‘Pay rent by Friday 5pm’ or ‘Do the laundry’.",
        items=[],
        raw_payload=parsed if isinstance(parsed, dict) else None,
      )

    todo_specs: list[tuple[str, datetime | None]] = []
    for item in items:
      text = (item.get("text") or "").strip() if isinstance(item, dict) else ""
      if not text:
        continue
      raw_deadline = item.get("deadline_utc") if isinstance(item, dict) else None
      deadline = self._parse_deadline(raw_deadline)
      todo_specs.append((text, deadline))

    if not todo_specs:
      logger.info("[claude-todo] parsed items but none usable for request id={}", request_id)
      return ClaudeTodoResult(
        session_id=request_id,
        reply="I couldn't turn that into any concrete to-dos yet. Try phrasing one task per sentence.",
        items=[],
        raw_payload=parsed if isinstance(parsed, dict) else None,
      )

    created = await self.repo.create_many(user_id=user_id, items=todo_specs)
    await self.session.flush()
    await self.session.commit()

    reply = parsed.get("summary") if isinstance(parsed, dict) else None
    if not reply:
      reply = self._build_summary(created)

    logger.info("[claude-todo] respond complete id={} created={}", request_id, len(created))
    return ClaudeTodoResult(
      session_id=request_id,
      reply=reply,
      items=created,
      raw_payload=parsed if isinstance(parsed, dict) else None,
    )

  async def _extract_todos(self, user_text: str) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    now_eastern = eastern_now()
    prompt = CLAUDE_TODO_EXTRACTION_PROMPT.format(
      user_text=user_text,
      today_utc=now_utc.date().isoformat(),
      now_utc_iso=now_utc.isoformat(),
      today_eastern=now_eastern.date().isoformat(),
      now_eastern_iso=now_eastern.isoformat(),
    )
    response = await self._call_model(prompt)
    data = self._extract_json(response)
    if isinstance(data, dict):
      return data
    return {"items": [], "summary": None}

  async def _call_model(self, prompt: str) -> str:
    def _invoke() -> str:
      config = GenerateContentConfig()
      logger.info("[claude-todo] model call start")
      result = self.client.models.generate_content(
        model=self.model_name,
        contents=prompt,
        config=config,
      )
      text = result.text or ""
      logger.info("[claude-todo] model call complete chars={}", len(text))
      return text

    return await asyncio.to_thread(_invoke)

  def _extract_json(self, text: str) -> dict[str, Any] | None:
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

  def _parse_deadline(self, raw: Any) -> datetime | None:
    if not raw:
      return None
    if isinstance(raw, (int, float)):
      return None
    if isinstance(raw, datetime):
      return raw
    if not isinstance(raw, str):
      return None
    try:
      dt = date_parser.isoparse(raw)
      # Treat naive timestamps as US Eastern local time, then convert to UTC.
      if dt.tzinfo is None:
        dt = ensure_eastern(dt)
      return dt.astimezone(timezone.utc)
    except Exception:  # pragma: no cover - defensive parsing
      logger.warning("[claude-todo] failed to parse deadline '{}'", raw)
      return None

  def _build_summary(self, items: list[Any]) -> str:
    if not items:
      return "No to-dos were created."
    parts: list[str] = []
    for todo in items:
      label = getattr(todo, "text", "")
      deadline = getattr(todo, "deadline_utc", None)
      if deadline is None:
        parts.append(f"“{label}” (no deadline)")
      else:
        parts.append(f"“{label}” (due {deadline.isoformat()})")
    return "Added to your lily pad list: " + ", ".join(parts)
