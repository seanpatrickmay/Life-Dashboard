"""Project note persistence helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_note import ProjectNote


class ProjectNoteRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_for_project(
    self,
    *,
    user_id: int,
    project_id: int,
    include_archived: bool = False,
  ) -> list[ProjectNote]:
    stmt = select(ProjectNote).where(
      ProjectNote.user_id == user_id,
      ProjectNote.project_id == project_id,
    )
    if not include_archived:
      stmt = stmt.where(ProjectNote.archived.is_(False))
    stmt = stmt.order_by(ProjectNote.pinned.desc(), ProjectNote.updated_at.desc())
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

