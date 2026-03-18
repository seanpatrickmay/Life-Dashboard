"""Todo assistant backed by the OpenAI Responses API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dateutil import parser as date_parser
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.todo_repository import TodoRepository
from app.prompts import TODO_EXTRACTION_PROMPT
from app.schemas.llm_outputs import TodoExtractionOutput
from app.services.todo_calendar_link_service import TodoCalendarLinkService
from app.utils.timezone import eastern_now, ensure_eastern


@dataclass
class TodoAssistantResult:
  """Structured result from the todo assistant."""

  session_id: str
  reply: str
  items: list[Any]
  raw_payload: dict[str, Any] | None = None


class TodoAssistantAgent:
  """Todo mentor that uses OpenAI for parsing and normalization."""

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.repo = TodoRepository(session)
    self.client = OpenAIResponsesClient()

  async def respond(
    self, user_id: int, message: str, request_id: str | None = None
  ) -> TodoAssistantResult:
    request_id = request_id or str(uuid4())
    logger.info("[todo-assistant] respond start id={} user={} text={}", request_id, user_id, message)

    parsed = await self._extract_todos(message)
    logger.info("[todo-assistant] parsed payload={}", parsed)

    items = parsed.get("items") or []
    if not isinstance(items, list) or not items:
      logger.info("[todo-assistant] no todos detected for request id={}", request_id)
      return TodoAssistantResult(
        session_id=request_id,
        reply="I didn't find a clear task to track yet. Try something like ‘Pay rent by Friday 5pm’ or ‘Do the laundry’.",
        items=[],
        raw_payload=parsed,
      )

    todo_specs: list[tuple[str, datetime | None, bool, str]] = []
    for item in items:
      text = (item.get("text") or "").strip() if isinstance(item, dict) else ""
      if not text:
        continue
      raw_deadline = item.get("deadline_utc") if isinstance(item, dict) else None
      deadline = self._parse_deadline(raw_deadline)
      horizon = item.get("time_horizon", "this_week") if isinstance(item, dict) else "this_week"
      if horizon not in ("this_week", "this_month", "this_year"):
        horizon = "this_week"
      todo_specs.append((text, deadline, False, horizon))

    if not todo_specs:
      logger.info("[todo-assistant] parsed items but none usable for request id={}", request_id)
      return TodoAssistantResult(
        session_id=request_id,
        reply="I couldn't turn that into any concrete to-dos yet. Try phrasing one task per sentence.",
        items=[],
        raw_payload=parsed,
      )

    project_repo = ProjectRepository(self.session)
    inbox = await project_repo.ensure_inbox_project(user_id)
    created = await self.repo.create_many(user_id=user_id, project_id=inbox.id, items=todo_specs)
    await self.session.flush()
    await self.session.commit()
    link_service = TodoCalendarLinkService(self.session)
    for todo in created:
      if todo.deadline_utc is not None and not todo.completed:
        await link_service.upsert_event_for_todo(todo)

    reply = parsed.get("summary") if isinstance(parsed, dict) else None
    if not reply:
      reply = self._build_summary(created)

    logger.info("[todo-assistant] respond complete id={} created={}", request_id, len(created))
    return TodoAssistantResult(
      session_id=request_id,
      reply=reply,
      items=created,
      raw_payload=parsed,
    )

  async def _extract_todos(self, user_text: str) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    now_eastern = eastern_now()
    prompt = TODO_EXTRACTION_PROMPT.format(
      user_text=user_text,
      today_utc=now_utc.date().isoformat(),
      now_utc_iso=now_utc.isoformat(),
      today_eastern=now_eastern.date().isoformat(),
      now_eastern_iso=now_eastern.isoformat(),
    )
    try:
      result = await self.client.generate_json(
        prompt,
        response_model=TodoExtractionOutput,
      )
    except Exception as exc:  # noqa: BLE001
      logger.warning("[todo-assistant] extraction failed: {}", exc)
      return {"items": [], "summary": None}
    return result.data.model_dump()

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
      logger.warning("[todo-assistant] failed to parse deadline '{}'", raw)
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
