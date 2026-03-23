"""Suggestion service for mapping todos into projects."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.todo import TodoItem
from app.db.repositories.project_repository import (
  INBOX_PROJECT_NAME,
  ProjectRepository,
  TodoProjectSuggestionRepository,
)
from app.prompts import TODO_PROJECT_MAPPING_PROMPT
from app.schemas.llm_outputs import ProjectAssignmentOutput


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
    try:
      self.client = OpenAIResponsesClient()
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
      result = await self.client.generate_json(
        prompt,
        response_model=ProjectAssignmentOutput,
        temperature=0.2,
      )
      parsed: list[ProjectAssignment] = []
      for item in result.data.assignments:
        todo_id = item.todo_id
        project_name = item.project_name.strip()
        confidence_raw = item.confidence
        reason = (item.reason or "").strip() or None
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
      logger.error("[llm-fallback] todo_project_suggestion_service._suggest_with_llm failed: {}", exc)
      return []

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
