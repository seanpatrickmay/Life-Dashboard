"""Todo item persistence helpers."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import and_, case, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.imessage import IMessageActionAudit
from app.db.models.project import TodoProjectSuggestion
from app.db.models.project_note import project_note_todo_ref
from app.db.models.todo import TodoItem
from app.db.models.workspace import WorkspacePage


class TodoRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_for_user(
    self,
    user_id: int,
    local_date: date | None = None,
    *,
    limit: int | None = None,
    offset: int | None = None,
  ) -> list[TodoItem]:
    """Return todos ordered with uncompleted + overdue items first."""
    now_utc = datetime.now(timezone.utc)
    overdue_bucket = case(
      (
        and_(
          TodoItem.deadline_utc.is_not(None),
          TodoItem.deadline_utc < now_utc,
        ),
        0,
      ),
      (TodoItem.deadline_utc.is_(None), 2),
      else_=1,
    )
    stmt = (
      select(TodoItem)
      .options(
        selectinload(TodoItem.project),  # Eager load project
        selectinload(TodoItem.calendar_link),  # Eager load calendar link
        selectinload(TodoItem.project_suggestion),  # Eager load suggestions
      )
      .where(TodoItem.user_id == user_id)
    )
    if local_date is not None:
      stmt = stmt.where(
        or_(TodoItem.completed.is_(False), TodoItem.completed_local_date == local_date)
      )
    stmt = stmt.order_by(
      TodoItem.completed.asc(),
      overdue_bucket.asc(),
      TodoItem.deadline_utc.asc().nullslast(),
      TodoItem.created_at.asc(),
    )
    if offset is not None:
      stmt = stmt.offset(offset)
    if limit is not None:
      stmt = stmt.limit(limit)
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def create_many(
    self,
    user_id: int,
    project_id: int,
    items: Iterable[tuple[str, datetime | None] | tuple[str, datetime | None, bool] | tuple[str, datetime | None, bool, str]],
    *,
    created_at: datetime | None = None,
  ) -> list[TodoItem]:
    """Create multiple todo items."""
    created: list[TodoItem] = []
    for item in items:
      if len(item) == 4:
        text, deadline, date_only, horizon = item
      elif len(item) == 3:
        text, deadline, date_only = item
        horizon = "this_week"
      else:
        text, deadline = item
        date_only = False
        horizon = "this_week"
      todo = TodoItem(
        user_id=user_id,
        project_id=project_id,
        text=text.strip(),
        deadline_utc=_to_utc(deadline),
        deadline_is_date_only=bool(date_only),
        time_horizon=horizon,
      )
      if created_at is not None:
        todo.created_at = _to_utc(created_at) or todo.created_at
        todo.updated_at = todo.created_at
      self.session.add(todo)
      created.append(todo)
    return created

  async def create_one(
    self,
    user_id: int,
    project_id: int,
    text: str,
    deadline: datetime | None,
    deadline_is_date_only: bool = False,
    *,
    created_at: datetime | None = None,
    time_horizon: str = "this_week",
  ) -> TodoItem:
    todo = TodoItem(
      user_id=user_id,
      project_id=project_id,
      text=text.strip(),
      deadline_utc=_to_utc(deadline),
      deadline_is_date_only=deadline_is_date_only,
      time_horizon=time_horizon,
    )
    if created_at is not None:
      todo.created_at = _to_utc(created_at) or todo.created_at
      todo.updated_at = todo.created_at
    self.session.add(todo)
    return todo

  async def get_for_user(self, user_id: int, todo_id: int) -> TodoItem | None:
    stmt = select(TodoItem).where(TodoItem.user_id == user_id, TodoItem.id == todo_id)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def delete_for_user(self, user_id: int, todo_id: int) -> None:
    todo = await self.get_for_user(user_id, todo_id)
    if todo is not None:
      await self.session.execute(
        update(IMessageActionAudit)
        .where(
          IMessageActionAudit.target_todo_id == todo.id,
        )
        .values(target_todo_id=None)
      )
      await self.session.execute(
        delete(TodoProjectSuggestion).where(
          TodoProjectSuggestion.user_id == user_id,
          TodoProjectSuggestion.todo_id == todo.id,
        )
      )
      await self.session.execute(
        delete(project_note_todo_ref).where(
          project_note_todo_ref.c.user_id == user_id,
          project_note_todo_ref.c.todo_id == todo.id,
        )
      )
      await self.session.execute(
        update(WorkspacePage)
        .where(
          WorkspacePage.user_id == user_id,
          WorkspacePage.legacy_todo_id == todo.id,
        )
        .values(legacy_todo_id=None)
      )
      await self.session.execute(
        delete(TodoItem).where(
          TodoItem.user_id == user_id,
          TodoItem.id == todo.id,
        )
      )

  async def list_completed_for_day(self, user_id: int, local_date: date) -> list[TodoItem]:
    """Return completed todos for a specific local date."""
    stmt = (
      select(TodoItem)
      .where(
        TodoItem.user_id == user_id,
        TodoItem.completed.is_(True),
        TodoItem.completed_local_date == local_date,
      )
      .order_by(TodoItem.completed_at_utc.asc().nullslast())
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())


def _to_utc(value: datetime | None) -> datetime | None:
  if value is None:
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=timezone.utc)
  return value.astimezone(timezone.utc)
