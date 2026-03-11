"""Compile journal entries and completed todos into grouped day summaries."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.prompts import (
  JOURNAL_CALENDAR_EVENT_EXTRACTION_PROMPT,
  JOURNAL_DEDUP_PROMPT,
  JOURNAL_ENTRY_EXTRACTION_PROMPT,
  JOURNAL_GROUPING_PROMPT,
)
from app.schemas.llm_outputs import (
  JournalDedupedItemsOutput,
  JournalGroupingOutput,
  JournalSourceTextItemsOutput,
)


TimePrecision = str


@dataclass(frozen=True)
class JournalSourceItem:
  source_id: str
  text: str
  occurred_at_local: datetime | None
  time_label: str | None
  time_precision: TimePrecision
  source_rank: int


@dataclass(frozen=True)
class JournalGroupedItem:
  item_id: str
  text: str
  occurred_at_local: datetime | None
  time_label: str | None
  time_precision: TimePrecision


class JournalCompiler:
  """Runs LLM extraction, deduplication, and grouping for journal summaries."""

  VERSION = "v3"

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.client = OpenAIResponsesClient()

  @property
  def model_name(self) -> str:
    return self.client.model_name

  async def compile_day(
    self,
    *,
    local_date: date,
    time_zone: str,
    entries: list[dict[str, Any]],
    todo_items: list[dict[str, Any]],
    calendar_events: list[dict[str, Any]] | None = None,
  ) -> dict[str, Any]:
    calendar_events = calendar_events or []
    if not entries and not todo_items and not calendar_events:
      return {"groups": []}

    todo_candidates = self._build_todo_items(todo_items)
    journal_items = await self._extract_entries(local_date, time_zone, entries)
    calendar_items = await self._extract_calendar_events(local_date, time_zone, calendar_events)
    merged_items = await self._dedupe_items(todo_candidates, [*journal_items, *calendar_items])
    grouped = await self._group_items(merged_items)
    return grouped

  def _build_todo_items(self, todo_items: list[dict[str, Any]]) -> list[JournalSourceItem]:
    items: list[JournalSourceItem] = []
    for todo in todo_items:
      source_id = str(todo.get("source_id") or "").strip()
      text = str(todo.get("text") or "").strip()
      if not source_id or not text:
        continue
      items.append(
        JournalSourceItem(
          source_id=source_id,
          text=text,
          occurred_at_local=_parse_datetime(todo.get("occurred_at_local")),
          time_label=_clean_label(todo.get("time_label")),
          time_precision=_coerce_time_precision(todo.get("time_precision")),
          source_rank=2,
        )
      )
    return items

  async def _extract_entries(
    self, local_date: date, time_zone: str, entries: list[dict[str, Any]]
  ) -> list[JournalSourceItem]:
    if not entries:
      return []
    prompt_entries = [
      {"source_id": item["source_id"], "text": item["text"]}
      for item in entries
      if item.get("source_id") and item.get("text")
    ]
    if not prompt_entries:
      return []
    prompt = JOURNAL_ENTRY_EXTRACTION_PROMPT.format(
      local_date=local_date.isoformat(),
      time_zone=time_zone,
      entries_json=json.dumps(prompt_entries, ensure_ascii=False),
    )
    result = await self.client.generate_json(
      prompt,
      response_model=JournalSourceTextItemsOutput,
      temperature=0.2,
    )
    extracted = [
      {"source_id": item.source_id, "text": item.text}
      for item in result.data.items
    ]
    return self._bind_extracted_items(entries, extracted, source_rank=3)

  async def _extract_calendar_events(
    self, local_date: date, time_zone: str, events: list[dict[str, Any]]
  ) -> list[JournalSourceItem]:
    if not events:
      return []
    prompt_events = [
      {
        "source_id": item["source_id"],
        "summary": item.get("summary"),
        "location": item.get("location"),
        "calendar": item.get("calendar"),
        "start_time_local": item.get("start_time_local"),
        "end_time_local": item.get("end_time_local"),
        "is_all_day": item.get("is_all_day"),
      }
      for item in events
      if item.get("source_id")
    ]
    if not prompt_events:
      return []
    prompt = JOURNAL_CALENDAR_EVENT_EXTRACTION_PROMPT.format(
      local_date=local_date.isoformat(),
      time_zone=time_zone,
      events_json=json.dumps(prompt_events, ensure_ascii=False),
    )
    try:
      result = await self.client.generate_json(
        prompt,
        response_model=JournalSourceTextItemsOutput,
        temperature=0.2,
      )
      extracted = [
        {"source_id": item.source_id, "text": item.text}
        for item in result.data.items
      ]
      bound = self._bind_extracted_items(events, extracted, source_rank=1)
      if bound:
        return bound
    except Exception as exc:  # noqa: BLE001
      logger.warning("[journal] calendar event extraction failed: {}", exc)

    fallback: list[JournalSourceItem] = []
    for event in events:
      source_id = str(event.get("source_id") or "").strip()
      summary = str(event.get("summary") or "").strip()
      if not source_id or not summary:
        continue
      fallback.append(
        JournalSourceItem(
          source_id=f"{source_id}::1",
          text=summary,
          occurred_at_local=_parse_datetime(event.get("occurred_at_local")),
          time_label=_clean_label(event.get("time_label")),
          time_precision=_coerce_time_precision(event.get("time_precision")),
          source_rank=1,
        )
      )
    return fallback

  def _bind_extracted_items(
    self,
    sources: list[dict[str, Any]],
    extracted: list[dict[str, str]],
    *,
    source_rank: int,
  ) -> list[JournalSourceItem]:
    source_map = {
      str(source.get("source_id") or "").strip(): source
      for source in sources
      if source.get("source_id")
    }
    counts: dict[str, int] = {}
    items: list[JournalSourceItem] = []
    for item in extracted:
      parent_id = item["source_id"]
      source = source_map.get(parent_id)
      text = item["text"]
      if source is None or not text:
        continue
      counts[parent_id] = counts.get(parent_id, 0) + 1
      items.append(
        JournalSourceItem(
          source_id=f"{parent_id}::{counts[parent_id]}",
          text=text,
          occurred_at_local=_parse_datetime(source.get("occurred_at_local")),
          time_label=_clean_label(source.get("time_label")),
          time_precision=_coerce_time_precision(source.get("time_precision")),
          source_rank=source_rank,
        )
      )
    return items

  async def _dedupe_items(
    self, todo_items: list[JournalSourceItem], journal_items: list[JournalSourceItem]
  ) -> list[JournalGroupedItem]:
    if not todo_items and not journal_items:
      return []
    all_items = [*todo_items, *journal_items]
    item_map = {item.source_id: item for item in all_items}
    prompt = JOURNAL_DEDUP_PROMPT.format(
      todo_items_json=json.dumps(self._serialize_sources(todo_items), ensure_ascii=False),
      journal_items_json=json.dumps(self._serialize_sources(journal_items), ensure_ascii=False),
    )
    result = await self.client.generate_json(
      prompt,
      response_model=JournalDedupedItemsOutput,
      temperature=0.2,
    )
    deduped = [
      {"source_ids": item.source_ids, "text": item.text}
      for item in result.data.items
    ]
    bound = self._bind_deduped_items(deduped, item_map)
    if bound:
      return bound
    return self._fallback_group_items(all_items)

  async def _group_items(self, items: list[JournalGroupedItem]) -> dict[str, Any]:
    if not items:
      return {"groups": []}
    prompt = JOURNAL_GROUPING_PROMPT.format(
      items_json=json.dumps(
        [{"item_id": item.item_id, "text": item.text} for item in items],
        ensure_ascii=False,
      )
    )
    result = await self.client.generate_json(
      prompt,
      response_model=JournalGroupingOutput,
      temperature=0.2,
    )
    groups = [
      {"title": group.title, "item_ids": group.item_ids}
      for group in result.data.groups
    ]
    built = self._bind_groups(groups, items)
    if built:
      return {"groups": built}
    return {
      "groups": [
        {
          "title": "Highlights",
          "items": [self._serialize_group_item(item) for item in self._sort_group_items(items)],
        }
      ]
    }

  def _bind_deduped_items(
    self,
    deduped: list[dict[str, Any]],
    item_map: dict[str, JournalSourceItem],
  ) -> list[JournalGroupedItem]:
    items: list[JournalGroupedItem] = []
    for index, item in enumerate(deduped, start=1):
      source_ids = [
        source_id for source_id in item["source_ids"]
        if source_id in item_map
      ]
      if not source_ids or not item["text"]:
        continue
      metadata = self._pick_best_metadata([item_map[source_id] for source_id in source_ids])
      items.append(
        JournalGroupedItem(
          item_id=f"item:{index}",
          text=item["text"],
          occurred_at_local=metadata.occurred_at_local,
          time_label=metadata.time_label,
          time_precision=metadata.time_precision,
        )
      )
    return items

  def _bind_groups(
    self,
    groups: list[dict[str, Any]],
    items: list[JournalGroupedItem],
  ) -> list[dict[str, Any]]:
    item_map = {item.item_id: item for item in items}
    assigned: set[str] = set()
    built: list[dict[str, Any]] = []
    for group in groups:
      resolved_items = [
        item_map[item_id]
        for item_id in group["item_ids"]
        if item_id in item_map and item_id not in assigned
      ]
      if not resolved_items:
        continue
      assigned.update(item.item_id for item in resolved_items)
      built.append(
        {
          "title": group["title"],
          "items": [
            self._serialize_group_item(item)
            for item in self._sort_group_items(resolved_items)
          ],
        }
      )

    leftovers = [item for item in items if item.item_id not in assigned]
    if leftovers:
      serialized_leftovers = [
        self._serialize_group_item(item)
        for item in self._sort_group_items(leftovers)
      ]
      if built:
        built[0]["items"].extend(serialized_leftovers)
      else:
        built.append({"title": "Highlights", "items": serialized_leftovers})
    return built[:4]

  def _fallback_group_items(self, items: list[JournalSourceItem]) -> list[JournalGroupedItem]:
    return [
      JournalGroupedItem(
        item_id=f"item:{index}",
        text=item.text,
        occurred_at_local=item.occurred_at_local,
        time_label=item.time_label,
        time_precision=item.time_precision,
      )
      for index, item in enumerate(items, start=1)
    ]

  def _sort_group_items(self, items: list[JournalGroupedItem]) -> list[JournalGroupedItem]:
    unknown_sort = datetime.max.replace(tzinfo=timezone.utc)
    return sorted(
      items,
      key=lambda item: (
        item.occurred_at_local is None,
        item.occurred_at_local or unknown_sort,
        item.text.lower(),
      ),
    )

  def _pick_best_metadata(self, items: list[JournalSourceItem]) -> JournalSourceItem:
    unknown_sort = datetime.max.replace(tzinfo=timezone.utc)
    return min(
      items,
      key=lambda item: (
        item.occurred_at_local is None,
        item.source_rank,
        item.occurred_at_local or unknown_sort,
        item.text.lower(),
      ),
    )

  def _serialize_group_item(self, item: JournalGroupedItem) -> dict[str, Any]:
    return {
      "text": item.text,
      "time_label": item.time_label,
      "occurred_at_local": item.occurred_at_local.isoformat() if item.occurred_at_local else None,
      "time_precision": item.time_precision,
    }

  def _serialize_sources(self, items: list[JournalSourceItem]) -> list[dict[str, str]]:
    return [{"source_id": item.source_id, "text": item.text} for item in items]

  def _parse_source_text_items(self, payload: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
      return []
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
      return []
    items: list[dict[str, str]] = []
    for item in raw_items:
      if not isinstance(item, dict):
        continue
      source_id = str(item.get("source_id") or "").strip()
      text = str(item.get("text") or "").strip()
      if source_id and text:
        items.append({"source_id": source_id, "text": text})
    return items

  def _parse_deduped_items(self, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
      return []
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
      return []
    items: list[dict[str, Any]] = []
    for item in raw_items:
      if not isinstance(item, dict):
        continue
      source_ids = item.get("source_ids")
      text = str(item.get("text") or "").strip()
      if not isinstance(source_ids, list) or not text:
        continue
      cleaned_source_ids = [str(source_id).strip() for source_id in source_ids if str(source_id).strip()]
      if cleaned_source_ids:
        items.append({"source_ids": cleaned_source_ids, "text": text})
    return items

  def _parse_groups(self, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
      return []
    raw_groups = payload.get("groups")
    if not isinstance(raw_groups, list):
      return []
    groups: list[dict[str, Any]] = []
    for group in raw_groups:
      if not isinstance(group, dict):
        continue
      title = str(group.get("title") or "").strip()
      item_ids = group.get("item_ids")
      if not isinstance(item_ids, list) or not title:
        continue
      cleaned_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
      if cleaned_ids:
        groups.append({"title": title, "item_ids": cleaned_ids})
    return groups[:4]


def _clean_label(value: Any) -> str | None:
  text = str(value or "").strip()
  return text or None


def _coerce_time_precision(value: Any) -> TimePrecision:
  text = str(value or "").strip()
  if text in {"exact", "range", "all_day", "unknown"}:
    return text
  return "unknown"


def _parse_datetime(value: Any) -> datetime | None:
  if isinstance(value, datetime):
    return value
  if not value:
    return None
  try:
    return datetime.fromisoformat(str(value))
  except ValueError:
    return None
