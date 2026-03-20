"""Shared OpenAI Responses API client."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from loguru import logger
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, APIStatusError
from pydantic import BaseModel

from app.core.config import settings


StructuredT = TypeVar("StructuredT", bound=BaseModel)

_REQUEST_TIMEOUT = 120.0  # seconds
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 2.0  # seconds, doubles each attempt


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient errors worth retrying."""
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    return False


def build_openai_client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=_REQUEST_TIMEOUT)


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
        kwargs = self._base_request_kwargs(
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        response = await self._call_with_retry(self.client.responses.create, **kwargs)
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
        response = await self._call_with_retry(
            self.client.responses.parse,
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

    @staticmethod
    async def _call_with_retry(fn, **kwargs) -> Any:
        """Call an OpenAI API function with retry on transient errors."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                result = await fn(**kwargs)
                elapsed = time.monotonic() - t0
                logger.debug("[openai] call succeeded in {:.1f}s (attempt {})", elapsed, attempt + 1)
                return result
            except Exception as exc:
                elapsed = time.monotonic() - t0
                last_exc = exc
                if not _is_retryable(exc) or attempt >= _MAX_RETRIES:
                    logger.warning(
                        "[openai] call failed in {:.1f}s (attempt {}/{}, non-retryable={}): {}",
                        elapsed, attempt + 1, _MAX_RETRIES + 1, not _is_retryable(exc), exc,
                    )
                    raise
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.info(
                    "[openai] retryable error in {:.1f}s (attempt {}/{}), retrying in {:.0f}s: {}",
                    elapsed, attempt + 1, _MAX_RETRIES + 1, delay, exc,
                )
                await asyncio.sleep(delay)
        raise last_exc  # unreachable but satisfies type checker


def _total_tokens(response: Any) -> int | None:
    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", None)
    return int(total_tokens) if isinstance(total_tokens, int) else None
