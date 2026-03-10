from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import os
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace

import pytest

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
  sys.path.insert(0, str(backend_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("ADMIN_EMAIL", "test@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")

from app.services.journal_compiler import JournalCompiler, JournalGroupedItem, JournalSourceItem
from app.services.journal_service import JournalService
from app.utils.timezone import resolve_time_zone


def run(coro):
  return asyncio.run(coro)


def make_service() -> JournalService:
  service = object.__new__(JournalService)
  service.session = None
  service.journal_repo = SimpleNamespace()
  service.todo_repo = SimpleNamespace()
  service.compiler = SimpleNamespace(VERSION="v3", model_name="test-model")
  return service


def test_ensure_summary_reuses_final_summary_when_source_hash_matches() -> None:
  service = make_service()
  zone = resolve_time_zone("America/New_York")
  completed = [
    SimpleNamespace(
      id=41,
      text="Drafted the permit packet",
      accomplishment_text=None,
      completed_at_utc=datetime(2026, 3, 10, 18, 15, tzinfo=timezone.utc),
    )
  ]
  compiler_todos = service._serialize_completed_for_compile(completed, zone)
  source_hash = service._build_source_hash(
    local_date=date(2026, 3, 10),
    time_zone="America/New_York",
    entries=[],
    completed=compiler_todos,
    calendar_events=[],
  )
  summary = SimpleNamespace(
    status="final",
    version="v3",
    source_hash=source_hash,
    time_zone="America/New_York",
    summary_json={"groups": []},
  )

  async def get_summary_for_day(self, user_id, local_date):
    return summary

  async def list_entries_for_day(self, user_id, local_date):
    return []

  async def list_completed_for_day(self, user_id, local_date):
    return completed

  async def compile_day(**kwargs):
    raise AssertionError("compile_day should not be called when the source hash is unchanged")

  async def list_calendar_events_for_day(self, *, user_id, local_date, time_zone):
    return []

  service.journal_repo.get_summary_for_day = MethodType(get_summary_for_day, service.journal_repo)
  service.journal_repo.list_entries_for_day = MethodType(list_entries_for_day, service.journal_repo)
  service.todo_repo.list_completed_for_day = MethodType(list_completed_for_day, service.todo_repo)
  service.compiler.compile_day = compile_day
  service._list_calendar_events_for_day = MethodType(list_calendar_events_for_day, service)

  result = run(
    service._ensure_summary(
      user_id=1,
      local_date=date(2026, 3, 10),
      time_zone="America/New_York",
    )
  )

  assert result is summary


def test_ensure_summary_rebuilds_final_summary_when_late_entry_changes_hash() -> None:
  service = make_service()
  updated: dict[str, object] = {}
  deleted: dict[str, object] = {}
  entry = SimpleNamespace(
    id=88,
    text="Signed the permit packet",
    created_at=datetime(2026, 3, 10, 19, 5, tzinfo=timezone.utc),
    time_zone="America/New_York",
  )
  summary = SimpleNamespace(
    status="final",
    version="v3",
    source_hash="stale-hash",
    time_zone="America/New_York",
    summary_json={"groups": []},
  )

  async def get_summary_for_day(self, user_id, local_date):
    return summary

  async def list_entries_for_day(self, user_id, local_date):
    return [entry]

  async def list_completed_for_day(self, user_id, local_date):
    return []

  async def update_summary(self, summary_obj, **kwargs):
    updated.update(kwargs)
    summary_obj.status = kwargs["status"]
    summary_obj.summary_json = kwargs["summary_json"]
    summary_obj.source_hash = kwargs["source_hash"]
    summary_obj.version = kwargs["version"]
    return summary_obj

  async def delete_entries_for_day(self, user_id, local_date):
    deleted["user_id"] = user_id
    deleted["local_date"] = local_date

  async def compile_day(**kwargs):
    updated["compile_kwargs"] = kwargs
    return {
      "groups": [
        {
          "title": "Highlights",
          "items": [
            {
              "text": "Signed the permit packet",
              "time_label": "3:05 PM",
              "occurred_at_local": "2026-03-10T15:05:00-04:00",
              "time_precision": "exact",
            }
          ],
        }
      ]
    }

  async def list_calendar_events_for_day(self, *, user_id, local_date, time_zone):
    return []

  service.journal_repo.get_summary_for_day = MethodType(get_summary_for_day, service.journal_repo)
  service.journal_repo.list_entries_for_day = MethodType(list_entries_for_day, service.journal_repo)
  service.todo_repo.list_completed_for_day = MethodType(list_completed_for_day, service.todo_repo)
  service.journal_repo.update_summary = MethodType(update_summary, service.journal_repo)
  service.journal_repo.delete_entries_for_day = MethodType(delete_entries_for_day, service.journal_repo)
  service.compiler.compile_day = compile_day
  service._list_calendar_events_for_day = MethodType(list_calendar_events_for_day, service)

  result = run(
    service._ensure_summary(
      user_id=7,
      local_date=date(2026, 3, 10),
      time_zone="America/New_York",
    )
  )

  assert result is summary
  assert updated["status"] == "final"
  assert updated["version"] == "v3"
  assert updated["source_hash"] != "stale-hash"
  compile_kwargs = updated["compile_kwargs"]
  assert compile_kwargs["entries"][0]["source_id"] == "entry:88"
  assert compile_kwargs["entries"][0]["time_label"] == "3:05 PM"
  assert deleted == {"user_id": 7, "local_date": date(2026, 3, 10)}


@pytest.mark.parametrize(
  ("completed_items", "calendar_events"),
  [
    (
      [
        SimpleNamespace(
          id=11,
          text="Uploaded the reimbursement PDF",
          accomplishment_text=None,
          completed_at_utc=datetime(2026, 3, 10, 17, 45, tzinfo=timezone.utc),
        )
      ],
      [],
    ),
    (
      [],
      [
        {
          "source_id": "calendar:22",
          "event_id": 22,
          "google_event_id": "evt_22",
          "summary": "Permit review",
          "location": "Town hall",
          "calendar": {"summary": "Primary", "primary": True, "is_life_dashboard": False},
          "occurred_at_local": "2026-03-10T14:00:00-04:00",
          "start_time_local": "2026-03-10T14:00:00-04:00",
          "end_time_local": "2026-03-10T15:00:00-04:00",
          "time_label": "2:00 PM - 3:00 PM",
          "time_precision": "range",
          "is_all_day": False,
        }
      ],
    ),
  ],
)
def test_ensure_summary_rebuilds_when_completed_or_calendar_inputs_change(
  completed_items: list[object],
  calendar_events: list[dict[str, object]],
) -> None:
  service = make_service()
  updated: dict[str, object] = {}
  summary = SimpleNamespace(
    status="final",
    version="v3",
    source_hash="stale-hash",
    time_zone="America/New_York",
    summary_json={"groups": []},
  )

  async def get_summary_for_day(self, user_id, local_date):
    return summary

  async def list_entries_for_day(self, user_id, local_date):
    return []

  async def list_completed_for_day(self, user_id, local_date):
    return completed_items

  async def update_summary(self, summary_obj, **kwargs):
    updated.update(kwargs)
    return summary_obj

  async def delete_entries_for_day(self, user_id, local_date):
    return None

  async def compile_day(**kwargs):
    updated["compile_kwargs"] = kwargs
    return {"groups": []}

  async def list_calendar_events_for_day(self, *, user_id, local_date, time_zone):
    return calendar_events

  service.journal_repo.get_summary_for_day = MethodType(get_summary_for_day, service.journal_repo)
  service.journal_repo.list_entries_for_day = MethodType(list_entries_for_day, service.journal_repo)
  service.todo_repo.list_completed_for_day = MethodType(list_completed_for_day, service.todo_repo)
  service.journal_repo.update_summary = MethodType(update_summary, service.journal_repo)
  service.journal_repo.delete_entries_for_day = MethodType(delete_entries_for_day, service.journal_repo)
  service.compiler.compile_day = compile_day
  service._list_calendar_events_for_day = MethodType(list_calendar_events_for_day, service)

  run(
    service._ensure_summary(
      user_id=5,
      local_date=date(2026, 3, 10),
      time_zone="America/New_York",
    )
  )

  assert updated["status"] == "final"
  assert updated["source_hash"] != "stale-hash"
  assert "compile_kwargs" in updated


def test_pick_best_metadata_prefers_calendar_then_todo_then_entry_and_known_time() -> None:
  compiler = object.__new__(JournalCompiler)
  entry_time = datetime(2026, 3, 10, 19, 0, tzinfo=timezone.utc)
  todo_time = datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc)
  calendar_time = datetime(2026, 3, 10, 17, 0, tzinfo=timezone.utc)

  entry_item = JournalSourceItem(
    source_id="entry:1::1",
    text="Sent the permit packet",
    occurred_at_local=entry_time,
    time_label="3:00 PM",
    time_precision="exact",
    source_rank=3,
  )
  todo_item = JournalSourceItem(
    source_id="todo:1",
    text="Sent the permit packet",
    occurred_at_local=todo_time,
    time_label="2:00 PM",
    time_precision="exact",
    source_rank=2,
  )
  calendar_item = JournalSourceItem(
    source_id="calendar:1::1",
    text="Permit review",
    occurred_at_local=calendar_time,
    time_label="1:00 PM - 2:00 PM",
    time_precision="range",
    source_rank=1,
  )
  unknown_todo = JournalSourceItem(
    source_id="todo:2",
    text="Uploaded the receipts",
    occurred_at_local=None,
    time_label="Time unknown",
    time_precision="unknown",
    source_rank=2,
  )

  best = compiler._pick_best_metadata([entry_item, todo_item, calendar_item])
  known_over_unknown = compiler._pick_best_metadata([unknown_todo, entry_item])

  assert best is calendar_item
  assert known_over_unknown is entry_item


def test_serialize_group_item_preserves_all_day_and_unknown_labels() -> None:
  compiler = object.__new__(JournalCompiler)
  all_day = JournalGroupedItem(
    item_id="item:1",
    text="Filing deadline",
    occurred_at_local=datetime(2026, 3, 10, 0, 0, tzinfo=timezone.utc),
    time_label="All day",
    time_precision="all_day",
  )
  unknown = JournalGroupedItem(
    item_id="item:2",
    text="Uploaded reimbursement paperwork",
    occurred_at_local=None,
    time_label="Time unknown",
    time_precision="unknown",
  )

  serialized_all_day = compiler._serialize_group_item(all_day)
  serialized_unknown = compiler._serialize_group_item(unknown)

  assert serialized_all_day["time_label"] == "All day"
  assert serialized_all_day["time_precision"] == "all_day"
  assert serialized_unknown["time_label"] == "Time unknown"
  assert serialized_unknown["time_precision"] == "unknown"
