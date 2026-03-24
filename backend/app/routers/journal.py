from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.session import AsyncSessionLocal, get_session
from app.schemas.journal import (
  JournalDayResponse,
  JournalDaySummaryResponse,
  JournalEntryCreateRequest,
  JournalEntryResponse,
  JournalWeekResponse,
)
from app.services.journal_service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


async def _background_ensure_summary(user_id: int, local_date: date, time_zone: str) -> None:
  """Compile a day summary in the background so the request is not blocked."""
  try:
    async with AsyncSessionLocal() as session:
      service = JournalService(session)
      await service._ensure_summary(user_id=user_id, local_date=local_date, time_zone=time_zone)
      await session.commit()
  except Exception as exc:  # noqa: BLE001
    logger.warning("Background journal summary compilation failed for date={}: {}", local_date, exc)


@router.post("/entries", response_model=JournalEntryResponse)
async def create_entry(
  payload: JournalEntryCreateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> JournalEntryResponse:
  service = JournalService(session)
  result = await service.add_entry(
    user_id=current_user.id,
    text=payload.text,
    time_zone=payload.time_zone,
  )
  await session.flush()
  await session.commit()
  return JournalEntryResponse.model_validate(result["entry"])


@router.get("/day/{local_date}", response_model=JournalDayResponse)
async def get_day(
  local_date: date,
  background_tasks: BackgroundTasks,
  time_zone: str = Query("UTC"),
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> JournalDayResponse:
  service = JournalService(session)
  data = await service.fetch_day(
    user_id=current_user.id,
    local_date=local_date,
    time_zone=time_zone,
  )
  await session.commit()

  if data["status"] == "open":
    from app.utils.timezone import local_today
    yesterday = local_today(time_zone) - timedelta(days=1)
    background_tasks.add_task(_background_ensure_summary, current_user.id, yesterday, time_zone)

  completed_items = [
    {
      "id": item.id,
      "text": item.accomplishment_text or item.text,
      "completed_at_utc": item.completed_at_utc,
    }
    for item in data["completed_items"]
  ]
  summary_payload = data.get("summary")
  summary = None
  if isinstance(summary_payload, dict):
    summary = JournalDaySummaryResponse.model_validate(summary_payload)

  return JournalDayResponse(
    local_date=local_date,
    time_zone=time_zone,
    status=data["status"],
    entries=[JournalEntryResponse.model_validate(entry) for entry in data["entries"]],
    completed_items=completed_items,
    summary=summary,
  )


@router.get("/week", response_model=JournalWeekResponse)
async def get_week(
  week_start: date,
  time_zone: str = Query("UTC"),
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> JournalWeekResponse:
  week_end = week_start + timedelta(days=6)
  service = JournalService(session)
  days = await service.fetch_week(
    user_id=current_user.id,
    week_start=week_start,
    week_end=week_end,
  )
  return JournalWeekResponse(week_start=week_start, week_end=week_end, days=days)
