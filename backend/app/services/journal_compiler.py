"""Compile journal entries and completed todos into grouped day summaries."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from typing import Any

from google.genai.types import GenerateContentConfig

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
  from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
  HttpOptions = None  # type: ignore[assignment]
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.genai_client import build_genai_client
from app.core.config import settings
from app.prompts import (
  JOURNAL_DEDUP_PROMPT,
  JOURNAL_ENTRY_EXTRACTION_PROMPT,
  JOURNAL_GROUPING_PROMPT,
)


class JournalCompiler:
  """Runs LLM extraction, deduplication, and grouping for journal summaries."""

  VERSION = "v1"

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    http_options = HttpOptions(api_version="v1") if HttpOptions else None
    self.client = build_genai_client(http_options=http_options)
    self.model_name = settings.vertex_model_name or "gemini-2.5-flash"

  async def compile_day(
    self,
    *,
    local_date: date,
    time_zone: str,
    entries: list[str],
    todo_items: list[str],
  ) -> dict[str, Any]:
    if not entries and not todo_items:
      return {"groups": []}

    journal_items = await self._extract_entries(local_date, time_zone, entries)
    merged_items = await self._dedupe_items(todo_items, journal_items)
    grouped = await self._group_items(merged_items)
    return grouped

  async def _extract_entries(
    self, local_date: date, time_zone: str, entries: list[str]
  ) -> list[str]:
    if not entries:
      return []
    prompt = JOURNAL_ENTRY_EXTRACTION_PROMPT.format(
      local_date=local_date.isoformat(),
      time_zone=time_zone,
      entries_json=json.dumps(entries, ensure_ascii=False),
    )
    response = await self._call_model(prompt)
    payload = self._safe_parse_json(response)
    return self._parse_text_items(payload)

  async def _dedupe_items(self, todo_items: list[str], journal_items: list[str]) -> list[str]:
    if not todo_items and not journal_items:
      return []
    prompt = JOURNAL_DEDUP_PROMPT.format(
      todo_items_json=json.dumps(todo_items, ensure_ascii=False),
      journal_items_json=json.dumps(journal_items, ensure_ascii=False),
    )
    response = await self._call_model(prompt)
    payload = self._safe_parse_json(response)
    return self._parse_text_items(payload)

  async def _group_items(self, items: list[str]) -> dict[str, Any]:
    if not items:
      return {"groups": []}
    prompt = JOURNAL_GROUPING_PROMPT.format(items_json=json.dumps(items, ensure_ascii=False))
    response = await self._call_model(prompt)
    payload = self._safe_parse_json(response)
    groups = self._parse_groups(payload)
    return {"groups": groups}

  async def _call_model(self, prompt: str) -> str:
    def _invoke() -> str:
      config = GenerateContentConfig(temperature=0.2)
      logger.debug("[journal] model invocation payload chars=%s", len(prompt))
      result = self.client.models.generate_content(
        model=self.model_name,
        contents=prompt,
        config=config,
      )
      return result.text or ""

    return await asyncio.to_thread(_invoke)

  def _safe_parse_json(self, text: str) -> dict[str, Any] | None:
    try:
      return json.loads(text)
    except json.JSONDecodeError:
      match = re.search(r"\{.*\}", text, re.DOTALL)
      if match:
        try:
          return json.loads(match.group(0))
        except json.JSONDecodeError:
          return None
    return None

  def _parse_text_items(self, payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
      return []
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
      return []
    items: list[str] = []
    for item in raw_items:
      if isinstance(item, dict):
        text = str(item.get("text") or "").strip()
      else:
        text = str(item).strip()
      if text:
        items.append(text)
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
      items = group.get("items")
      if not isinstance(items, list):
        items = []
      cleaned_items = [str(item).strip() for item in items if str(item).strip()]
      if not title or not cleaned_items:
        continue
      groups.append({"title": title, "items": cleaned_items})
    return groups[:4]
