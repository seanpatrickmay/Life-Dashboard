"""LLM helper to rewrite completed to-dos into accomplishments."""
from __future__ import annotations

from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient
from app.prompts import TODO_ACCOMPLISHMENT_PROMPT
from app.schemas.llm_outputs import TodoAccomplishmentOutput


class TodoAccomplishmentAgent:
  """Rewrite a completed todo into a neutral past-tense accomplishment."""

  def __init__(self) -> None:
    self.client = OpenAIResponsesClient()

  async def rewrite(self, todo_text: str) -> str:
    prompt = TODO_ACCOMPLISHMENT_PROMPT.format(todo_text=todo_text)
    try:
      result = await self.client.generate_json(
        prompt,
        response_model=TodoAccomplishmentOutput,
        temperature=0.2,
      )
    except Exception as exc:  # noqa: BLE001
      logger.error("[llm-fallback] todo_accomplishment_agent.rewrite failed: {}", exc)
      return self._fallback(todo_text)
    text = result.data.text.strip()
    return text or self._fallback(todo_text)

  def _fallback(self, todo_text: str) -> str:
    cleaned = " ".join(todo_text.split())
    if not cleaned:
      return "Completed a task."
    return f"Completed {cleaned}".strip()
