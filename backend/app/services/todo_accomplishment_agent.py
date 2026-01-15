"""LLM helper to rewrite completed to-dos into accomplishments."""
from __future__ import annotations

import asyncio
import json
import re
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
from app.prompts import TODO_ACCOMPLISHMENT_PROMPT


class TodoAccomplishmentAgent:
  """Rewrite a completed todo into a neutral past-tense accomplishment."""

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    http_options = HttpOptions(api_version="v1") if HttpOptions else None
    self.client = build_genai_client(http_options=http_options)
    self.model_name = settings.vertex_model_name or "gemini-2.5-flash"

  async def rewrite(self, todo_text: str) -> str:
    prompt = TODO_ACCOMPLISHMENT_PROMPT.format(todo_text=todo_text)
    response = await self._call_model(prompt)
    payload = self._safe_parse_json(response)
    text = ""
    if isinstance(payload, dict):
      text = str(payload.get("text") or "").strip()
    if text:
      return text
    logger.warning("[journal] fallback accomplishment text for todo")
    return self._fallback(todo_text)

  async def _call_model(self, prompt: str) -> str:
    def _invoke() -> str:
      config = GenerateContentConfig(temperature=0.2)
      logger.debug("[journal] todo accomplishment model chars=%s", len(prompt))
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

  def _fallback(self, todo_text: str) -> str:
    cleaned = " ".join(todo_text.split())
    if not cleaned:
      return "Completed a task."
    return f"Completed {cleaned}".strip()
