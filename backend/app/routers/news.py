"""News utilities — title shortening, article scoring, and annotations via LLM."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.entities import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


# ── Title Shortening ─────────────────────────────────────────────────────

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

    short_titles = []
    for i, original in enumerate(payload.titles):
        short_titles.append(lines[i] if i < len(lines) else original)

    return ShortenResponse(short_titles=short_titles)


# ── Profile Summarization ────────────────────────────────────────────────

class ProfileSummarizeRequest(BaseModel):
    projects: list[str]
    todos: list[str]
    calendar_events: list[str]
    reading_categories: dict[str, int]


class ProfileSummarizeResponse(BaseModel):
    narrative: str
    topics: list[str]


PROFILE_PROMPT = """\
You are a personal interest analyst. Based on the user data below, write a concise
~200-word narrative summary of who this person is and what they care about. Also
extract a flat list of 10-20 specific topic keywords that reflect their interests.

Active projects: {projects}
Current todos: {todos}
Upcoming calendar: {calendar}
Reading history (category: article count): {reading}

Respond with JSON:
{{"narrative": "...", "topics": ["topic1", "topic2", ...]}}"""


@router.post("/summarize-profile", response_model=ProfileSummarizeResponse)
async def summarize_profile(
    payload: ProfileSummarizeRequest,
    _current_user: User = Depends(get_current_user),
) -> ProfileSummarizeResponse:
    prompt = PROFILE_PROMPT.format(
        projects=", ".join(payload.projects) or "none",
        todos=", ".join(payload.todos[:20]) or "none",
        calendar=", ".join(payload.calendar_events[:10]) or "none",
        reading=json.dumps(payload.reading_categories),
    )

    llm = OpenAIResponsesClient(model_name="gpt-4o-mini")
    result = await llm.generate_text(prompt, temperature=0.3, max_output_tokens=1024)

    try:
        data = json.loads(result.text.strip())
        return ProfileSummarizeResponse(
            narrative=data.get("narrative", ""),
            topics=data.get("topics", []),
        )
    except (json.JSONDecodeError, KeyError):
        logger.warning("Failed to parse profile summary LLM response")
        return ProfileSummarizeResponse(narrative="", topics=[])


# ── Batch Article Scoring ────────────────────────────────────────────────

class ArticleForScoring(BaseModel):
    id: str
    title: str
    summary: str | None = None
    category: str


class ScoreRequest(BaseModel):
    articles: list[ArticleForScoring]
    profile_narrative: str


class ArticleScore(BaseModel):
    id: str
    score: float


class ScoreResponse(BaseModel):
    scores: list[ArticleScore]


SCORE_PROMPT = """\
You are a news relevance scorer for a personal dashboard. Given the user profile
and a list of articles, rate each article's relevance to this specific user on a
scale of 1-10 (1=irrelevant, 10=perfectly matched to their interests).

User profile:
{profile}

Articles (respond with a JSON array of {{"id": "...", "score": N}} for each):
{articles}

Respond ONLY with the JSON array, no other text."""


@router.post("/score", response_model=ScoreResponse)
async def score_articles(
    payload: ScoreRequest,
    _current_user: User = Depends(get_current_user),
) -> ScoreResponse:
    if not payload.articles:
        return ScoreResponse(scores=[])

    articles_text = "\n".join(
        f'- id: {a.id} | title: "{a.title}" | category: {a.category} | summary: "{a.summary or ""}"'
        for a in payload.articles
    )
    prompt = SCORE_PROMPT.format(
        profile=payload.profile_narrative,
        articles=articles_text,
    )

    llm = OpenAIResponsesClient(model_name="gpt-4o-mini")
    result = await llm.generate_text(prompt, temperature=0.2, max_output_tokens=4096)

    try:
        raw = result.text.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        scores = [
            ArticleScore(id=item["id"], score=max(1, min(10, float(item["score"]))))
            for item in data
            if "id" in item and "score" in item
        ]
        return ScoreResponse(scores=scores)
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Failed to parse article scoring LLM response")
        return ScoreResponse(scores=[])


# ── Personalized Annotations ─────────────────────────────────────────────

class ArticleForAnnotation(BaseModel):
    id: str
    title: str
    summary: str | None = None
    category: str


class AnnotateRequest(BaseModel):
    articles: list[ArticleForAnnotation]
    profile_narrative: str


class ArticleAnnotation(BaseModel):
    id: str
    annotation: str


class AnnotateResponse(BaseModel):
    annotations: list[ArticleAnnotation]


ANNOTATE_PROMPT = """\
You are a personal news curator. For each article below, write a SHORT (max 15 words)
annotation explaining why this specific user would care about it, based on their profile.

User profile:
{profile}

Articles:
{articles}

Respond with a JSON array of {{"id": "...", "annotation": "..."}}.
Keep annotations personal and specific — reference the user's projects, interests, or role.
Examples: "Directly relevant to your wildfire prediction work" or "New tool for your ML pipeline"
Respond ONLY with the JSON array."""


@router.post("/annotate", response_model=AnnotateResponse)
async def annotate_articles(
    payload: AnnotateRequest,
    _current_user: User = Depends(get_current_user),
) -> AnnotateResponse:
    if not payload.articles:
        return AnnotateResponse(annotations=[])

    articles_text = "\n".join(
        f'- id: {a.id} | title: "{a.title}" | category: {a.category} | summary: "{a.summary or ""}"'
        for a in payload.articles
    )
    prompt = ANNOTATE_PROMPT.format(
        profile=payload.profile_narrative,
        articles=articles_text,
    )

    llm = OpenAIResponsesClient(model_name="gpt-4o-mini")
    result = await llm.generate_text(prompt, temperature=0.4, max_output_tokens=2048)

    try:
        raw = result.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        annotations = [
            ArticleAnnotation(id=item["id"], annotation=item["annotation"])
            for item in data
            if "id" in item and "annotation" in item
        ]
        return AnnotateResponse(annotations=annotations)
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Failed to parse annotation LLM response")
        return AnnotateResponse(annotations=[])
