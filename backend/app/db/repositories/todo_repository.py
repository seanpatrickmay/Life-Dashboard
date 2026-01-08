"""Todo item persistence helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.todo import TodoItem


class TodoRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_for_user(self, user_id: int) -> list[TodoItem]:
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
      .where(TodoItem.user_id == user_id)
      .order_by(
        TodoItem.completed.asc(),
        overdue_bucket.asc(),
        TodoItem.deadline_utc.asc().nullslast(),
        TodoItem.created_at.asc(),
      )
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def create_many(
    self,
    user_id: int,
    items: Iterable[tuple[str, datetime | None]],
  ) -> list[TodoItem]:
    """Create multiple todo items."""
    created: list[TodoItem] = []
    for text, deadline in items:
      todo = TodoItem(user_id=user_id, text=text.strip(), deadline_utc=_to_utc(deadline))
      self.session.add(todo)
      created.append(todo)
    return created

  async def create_one(self, user_id: int, text: str, deadline: datetime | None) -> TodoItem:
    todo = TodoItem(user_id=user_id, text=text.strip(), deadline_utc=_to_utc(deadline))
    self.session.add(todo)
    return todo

  async def get_for_user(self, user_id: int, todo_id: int) -> TodoItem | None:
    stmt = select(TodoItem).where(TodoItem.user_id == user_id, TodoItem.id == todo_id)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def delete_for_user(self, user_id: int, todo_id: int) -> None:
    todo = await self.get_for_user(user_id, todo_id)
    if todo is not None:
      await self.session.delete(todo)


def _to_utc(value: datetime | None) -> datetime | None:
  if value is None:
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=timezone.utc)
  return value.astimezone(timezone.utc)

