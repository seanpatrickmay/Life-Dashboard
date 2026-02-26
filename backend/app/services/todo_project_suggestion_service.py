"""Suggestion service for mapping todos into projects."""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from google.genai.types import GenerateContentConfig
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.genai_client import build_genai_client
from app.core.config import settings
from app.db.models.todo import TodoItem
from app.db.repositories.project_repository import (
  INBOX_PROJECT_NAME,
  ProjectRepository,
  TodoProjectSuggestionRepository,
)
from app.prompts import TODO_PROJECT_MAPPING_PROMPT

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
  from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
  HttpOptions = None  # type: ignore[assignment]


AUTO_APPLY_CONFIDENCE = 0.75


@dataclass
class ProjectAssignment:
  todo_id: int
  project_name: str
  confidence: float
  reason: str | None = None


class TodoProjectSuggestionService:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.project_repo = ProjectRepository(session)
    self.suggestion_repo = TodoProjectSuggestionRepository(session)
    self.model_name = settings.vertex_model_name or "gemini-2.5-flash"
    http_options = HttpOptions(api_version="v1") if HttpOptions else None
    try:
      self.client = build_genai_client(http_options=http_options)
    except Exception as exc:  # noqa: BLE001
      logger.warning("[todo-project] failed to init genai client: {}", exc)
      self.client = None

  async def process_todo_ids(self, user_id: int, todo_ids: list[int]) -> None:
    if not todo_ids:
      return
    todos = await self._load_todos(user_id, todo_ids)
    if not todos:
      return
    inbox = await self.project_repo.ensure_inbox_project(user_id)
    assignments = await self._suggest_assignments(user_id, todos)
    assignment_by_todo = {assignment.todo_id: assignment for assignment in assignments}

    for todo in todos:
      assignment = assignment_by_todo.get(todo.id)
      if assignment is None:
        if todo.project_id == inbox.id:
          await self.suggestion_repo.delete_for_todo(user_id, todo.id)
        continue
      target_name = assignment.project_name.strip()
      if not target_name:
        continue
      if assignment.confidence >= AUTO_APPLY_CONFIDENCE:
        project = await self.project_repo.get_or_create_by_name(user_id, target_name)
        todo.project_id = project.id
        await self.suggestion_repo.delete_for_todo(user_id, todo.id)
      else:
        if todo.project_id != inbox.id:
          todo.project_id = inbox.id
        await self.suggestion_repo.upsert(
          user_id=user_id,
          todo_id=todo.id,
          suggested_project_name=target_name,
          confidence=assignment.confidence,
          reason=assignment.reason,
        )
    await self.session.flush()
    await self.session.commit()

  async def process_todo_id(self, user_id: int, todo_id: int) -> None:
    await self.process_todo_ids(user_id, [todo_id])

  async def _load_todos(self, user_id: int, todo_ids: list[int]) -> list[TodoItem]:
    stmt = (
      select(TodoItem)
      .where(TodoItem.user_id == user_id, TodoItem.id.in_(todo_ids))
      .order_by(TodoItem.created_at.asc())
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def _suggest_assignments(
    self,
    user_id: int,
    todos: list[TodoItem],
  ) -> list[ProjectAssignment]:
    projects = await self.project_repo.list_for_user(user_id, include_archived=False)
    project_names = [project.name for project in projects]
    llm_assignments = await self._suggest_with_llm(project_names, todos)
    if llm_assignments:
      return llm_assignments
    return [self._heuristic_assignment(todo, project_names) for todo in todos]

  async def _suggest_with_llm(
    self,
    project_names: list[str],
    todos: list[TodoItem],
  ) -> list[ProjectAssignment]:
    if self.client is None:
      return []
    prompt = TODO_PROJECT_MAPPING_PROMPT.format(
      project_names_json=json.dumps(project_names),
      todos_json=json.dumps([{"todo_id": todo.id, "text": todo.text} for todo in todos]),
    )
    try:
      payload_text = await self._call_model(prompt)
      payload = self._safe_parse_json(payload_text)
      if not isinstance(payload, dict):
        return []
      assignments_raw = payload.get("assignments")
      if not isinstance(assignments_raw, list):
        return []
      parsed: list[ProjectAssignment] = []
      for item in assignments_raw:
        if not isinstance(item, dict):
          continue
        todo_id = item.get("todo_id")
        project_name = str(item.get("project_name") or "").strip()
        confidence_raw = item.get("confidence", 0)
        reason = str(item.get("reason") or "").strip() or None
        try:
          confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (TypeError, ValueError):
          confidence = 0.0
        if not isinstance(todo_id, int) or not project_name:
          continue
        parsed.append(
          ProjectAssignment(
            todo_id=todo_id,
            project_name=project_name,
            confidence=confidence,
            reason=reason,
          )
        )
      return parsed
    except Exception as exc:  # noqa: BLE001
      logger.warning("[todo-project] model suggestion failed: {}", exc)
      return []

  async def _call_model(self, prompt: str) -> str:
    def _invoke() -> str:
      config = GenerateContentConfig(temperature=0.2)
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
      if not match:
        return None
      try:
        return json.loads(match.group(0))
      except json.JSONDecodeError:
        return None

  def _heuristic_assignment(self, todo: TodoItem, project_names: list[str]) -> ProjectAssignment:
    text = todo.text.lower()
    existing = self._find_existing_match(project_names, text)
    if existing:
      return ProjectAssignment(todo_id=todo.id, project_name=existing, confidence=0.88)

    mapping = [
      ("onboarding", "Onboarding"),
      ("capital one", "Capital One Onboarding"),
      ("school", "School Work"),
      ("class", "School Work"),
      ("assignment", "School Work"),
      ("exam", "School Work"),
      ("reimburse", "Finance"),
      ("expense", "Finance"),
      ("budget", "Finance"),
      ("insurance", "Health Admin"),
      ("physical", "Health"),
      ("doctor", "Health"),
      ("workout", "Health"),
      ("run ", "Health"),
      ("meeting", "Work"),
      ("loom", "Work"),
      ("demo", "Work"),
    ]
    for needle, project_name in mapping:
      if needle in text:
        confidence = 0.81 if project_name != INBOX_PROJECT_NAME else 0.4
        return ProjectAssignment(
          todo_id=todo.id,
          project_name=project_name,
          confidence=confidence,
          reason=f"Matched keyword '{needle.strip()}'",
        )
    return ProjectAssignment(
      todo_id=todo.id,
      project_name=INBOX_PROJECT_NAME,
      confidence=0.4,
      reason="No strong category signal detected",
    )

  def _find_existing_match(self, project_names: list[str], text: str) -> str | None:
    normalized_words = set(re.findall(r"[a-z0-9]+", text))
    best_name: str | None = None
    best_score = 0
    for name in project_names:
      candidate_words = set(re.findall(r"[a-z0-9]+", name.lower()))
      if not candidate_words:
        continue
      overlap = len(candidate_words.intersection(normalized_words))
      if overlap > best_score:
        best_score = overlap
        best_name = name
    return best_name if best_score > 0 else None
