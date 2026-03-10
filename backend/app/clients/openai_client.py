"""Shared OpenAI Responses API client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings


StructuredT = TypeVar("StructuredT", bound=BaseModel)


def build_openai_client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    return AsyncOpenAI(api_key=settings.openai_api_key)


@dataclass(slots=True)
class TextGenerationResult:
    text: str
    total_tokens: int | None


@dataclass(slots=True)
class StructuredGenerationResult(Generic[StructuredT]):
    data: StructuredT
    text: str
    total_tokens: int | None


class OpenAIResponsesClient:
    """Thin wrapper around the OpenAI Responses API."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model_name: str | None = None,
    ) -> None:
        self.client = client or build_openai_client()
        self.model_name = model_name or settings.openai_model_name

    def _supports_temperature(self) -> bool:
        # GPT-5 models reject temperature in the Responses API.
        return not self.model_name.lower().startswith("gpt-5")

    def _base_request_kwargs(
        self,
        *,
        prompt: str,
        temperature: float | None,
        max_output_tokens: int | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "input": prompt,
        }
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if temperature is not None and self._supports_temperature():
            kwargs["temperature"] = temperature
        return kwargs

    async def generate_text(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> TextGenerationResult:
        logger.debug("[openai] text response request model={} chars={}", self.model_name, len(prompt))
        response = await self.client.responses.create(
            **self._base_request_kwargs(
                prompt=prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
        return TextGenerationResult(
            text=(response.output_text or "").strip(),
            total_tokens=_total_tokens(response),
        )

    async def generate_json(
        self,
        prompt: str,
        *,
        response_model: type[StructuredT],
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> StructuredGenerationResult[StructuredT]:
        return await self._generate_structured(
            prompt,
            response_model=response_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=None,
        )

    async def generate_json_with_web_search(
        self,
        prompt: str,
        *,
        response_model: type[StructuredT],
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> StructuredGenerationResult[StructuredT]:
        return await self._generate_structured(
            prompt,
            response_model=response_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=[{"type": "web_search"}],
        )

    async def _generate_structured(
        self,
        prompt: str,
        *,
        response_model: type[StructuredT],
        temperature: float,
        max_output_tokens: int | None,
        tools: list[dict[str, Any]] | None,
    ) -> StructuredGenerationResult[StructuredT]:
        logger.debug(
            "[openai] structured response request model={} schema={} chars={} tools={}",
            self.model_name,
            response_model.__name__,
            len(prompt),
            [tool.get("type") for tool in tools or []],
        )
        request_kwargs = self._base_request_kwargs(
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        response = await self.client.responses.parse(
            **request_kwargs,
            text_format=response_model,
            tools=tools or [],
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError(f"OpenAI returned no structured output for {response_model.__name__}.")
        return StructuredGenerationResult(
            data=parsed,
            text=(response.output_text or "").strip(),
            total_tokens=_total_tokens(response),
        )


def _total_tokens(response: Any) -> int | None:
    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", None)
    return int(total_tokens) if isinstance(total_tokens, int) else None
