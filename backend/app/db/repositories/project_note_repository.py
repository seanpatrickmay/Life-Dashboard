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

  async def get_for_user(self, *, user_id: int, note_id: int) -> ProjectNote | None:
    stmt = select(ProjectNote).where(
      ProjectNote.user_id == user_id,
      ProjectNote.id == note_id,
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def create_one(
    self,
    *,
    user_id: int,
    project_id: int,
    title: str,
    body_markdown: str = "",
    tags: list[str] | None = None,
    pinned: bool = False,
  ) -> ProjectNote:
    note = ProjectNote(
      user_id=user_id,
      project_id=project_id,
      title=title.strip(),
      body_markdown=body_markdown or "",
      tags=_sanitize_tags(tags),
      pinned=bool(pinned),
    )
    self.session.add(note)
    await self.session.flush()
    return note


def _sanitize_tags(tags: list[str] | None) -> list[str]:
  if not tags:
    return []
  cleaned: list[str] = []
  for tag in tags:
    text = tag.strip()
    if not text:
      continue
    if text not in cleaned:
      cleaned.append(text[:64])
  return cleaned
