from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class JournalEntryCreateRequest(BaseModel):
  text: str = Field(min_length=1, max_length=4000)
  time_zone: str = Field(min_length=1, max_length=64)


class JournalEntryResponse(BaseModel):
  id: int
  text: str
  created_at: datetime

  class Config:
    from_attributes = True


class JournalCompletedItem(BaseModel):
  id: int
  text: str
  completed_at_utc: datetime | None = None


class JournalDaySummaryGroup(BaseModel):
  title: str
  items: list[str]


class JournalDaySummaryResponse(BaseModel):
  groups: list[JournalDaySummaryGroup]


class JournalDayResponse(BaseModel):
  local_date: date
  time_zone: str
  status: str
  entries: list[JournalEntryResponse]
  completed_items: list[JournalCompletedItem]
  summary: JournalDaySummaryResponse | None = None


class JournalWeekDayStatus(BaseModel):
  local_date: date
  has_entries: bool
  has_summary: bool
  completed_count: int


class JournalWeekResponse(BaseModel):
  week_start: date
  week_end: date
  days: list[JournalWeekDayStatus]
