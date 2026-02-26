"""Project and suggestion persistence helpers."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project, TodoProjectSuggestion


INBOX_PROJECT_NAME = "Inbox"


class ProjectRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_for_user(self, user_id: int, include_archived: bool = True) -> list[Project]:
    stmt = select(Project).where(Project.user_id == user_id)
    if not include_archived:
      stmt = stmt.where(Project.archived.is_(False))
    stmt = stmt.order_by(Project.sort_order.asc(), Project.created_at.asc())
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def get_for_user(self, user_id: int, project_id: int) -> Project | None:
    stmt = select(Project).where(Project.user_id == user_id, Project.id == project_id)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def get_by_name_for_user(self, user_id: int, name: str) -> Project | None:
    normalized = name.strip().lower()
    stmt = select(Project).where(
      Project.user_id == user_id,
      func.lower(Project.name) == normalized,
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def create_one(
    self,
    user_id: int,
    name: str,
    notes: str | None = None,
    sort_order: int = 0,
    archived: bool = False,
  ) -> Project:
    project = Project(
      user_id=user_id,
      name=name.strip(),
      notes=notes.strip() if notes else None,
      sort_order=sort_order,
      archived=archived,
    )
    self.session.add(project)
    await self.session.flush()
    return project

  async def ensure_inbox_project(self, user_id: int) -> Project:
    inbox = await self.get_by_name_for_user(user_id, INBOX_PROJECT_NAME)
    if inbox is not None:
      return inbox
    return await self.create_one(user_id=user_id, name=INBOX_PROJECT_NAME, sort_order=-100)

  async def get_or_create_by_name(self, user_id: int, name: str) -> Project:
    existing = await self.get_by_name_for_user(user_id, name)
    if existing is not None:
      return existing
    return await self.create_one(user_id=user_id, name=name)


class TodoProjectSuggestionRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_for_user(self, user_id: int) -> list[TodoProjectSuggestion]:
    stmt = (
      select(TodoProjectSuggestion)
      .where(TodoProjectSuggestion.user_id == user_id)
      .order_by(TodoProjectSuggestion.updated_at.desc())
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def get_for_todo(self, user_id: int, todo_id: int) -> TodoProjectSuggestion | None:
    stmt = select(TodoProjectSuggestion).where(
      TodoProjectSuggestion.user_id == user_id, TodoProjectSuggestion.todo_id == todo_id
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def upsert(
    self,
    user_id: int,
    todo_id: int,
    suggested_project_name: str,
    confidence: float,
    reason: str | None,
  ) -> TodoProjectSuggestion:
    existing = await self.get_for_todo(user_id, todo_id)
    if existing is not None:
      existing.suggested_project_name = suggested_project_name.strip()
      existing.confidence = confidence
      existing.reason = reason
      await self.session.flush()
      return existing
    suggestion = TodoProjectSuggestion(
      user_id=user_id,
      todo_id=todo_id,
      suggested_project_name=suggested_project_name.strip(),
      confidence=confidence,
      reason=reason,
    )
    self.session.add(suggestion)
    await self.session.flush()
    return suggestion

  async def delete_for_todo(self, user_id: int, todo_id: int) -> None:
    existing = await self.get_for_todo(user_id, todo_id)
    if existing is not None:
      await self.session.delete(existing)
