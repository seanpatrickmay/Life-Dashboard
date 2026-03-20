"""Lightweight news utilities — title shortening via LLM."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.entities import User

router = APIRouter(prefix="/news", tags=["news"])


class ShortenRequest(BaseModel):
    titles: list[str]


class ShortenResponse(BaseModel):
    short_titles: list[str]


SHORTEN_PROMPT = """\
You are a headline editor. For each title below, produce a punchy short version
(max 50 characters) that preserves the core meaning. Return one short title per
line, in the same order. No numbering, no quotes — just the shortened title.

Titles:
{titles}"""


@router.post("/shorten-titles", response_model=ShortenResponse)
async def shorten_titles(
    payload: ShortenRequest,
    _current_user: User = Depends(get_current_user),
) -> ShortenResponse:
    if not payload.titles:
        return ShortenResponse(short_titles=[])

    numbered = "\n".join(f"- {t}" for t in payload.titles)
    prompt = SHORTEN_PROMPT.format(titles=numbered)

    llm = OpenAIResponsesClient(model_name="gpt-4o-mini")
    result = await llm.generate_text(prompt, temperature=0.3, max_output_tokens=1024)

    lines = [line.strip() for line in result.text.strip().splitlines() if line.strip()]

    # Pad or trim to match input length
    short_titles = []
    for i, original in enumerate(payload.titles):
        short_titles.append(lines[i] if i < len(lines) else original)

    return ShortenResponse(short_titles=short_titles)
