"""Morning Brief API — POST /api/morning/brief."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient, get_shared_openai_client
from app.core.auth import get_current_user
from app.db.models.entities import User
from app.prompts.llm_prompts import MORNING_BRIEF_PROMPT, MORNING_BRIEF_SYSTEM_INSTRUCTIONS
from app.schemas.morning_brief import MorningBriefRequest, MorningBriefResponse

router = APIRouter(prefix="/morning", tags=["morning-brief"])

# Temperature kept low for consistent, professional prose
_BRIEF_TEMPERATURE = 0.4
# Max tokens — one paragraph of 3–4 sentences fits comfortably in 200
_BRIEF_MAX_TOKENS = 220


def _build_prompt(req: MorningBriefRequest) -> str:
    """Render the morning brief prompt template from the request signals."""

    # ── Readiness section ─────────────────────────────────────────────────
    if req.readiness is not None:
        r = req.readiness
        parts: list[str] = []
        if r.score is not None:
            parts.append(f"Readiness score: {r.score:.0f}/100")
        if r.label:
            parts.append(f"label: {r.label}")
        if r.sleep_hours is not None:
            parts.append(f"sleep last night: {r.sleep_hours:.1f}h")
        if r.hrv_ms is not None:
            parts.append(f"HRV: {r.hrv_ms:.0f} ms")
        if r.narrative:
            parts.append(f"context: {r.narrative}")
        readiness_section = "BODY / READINESS:\n" + ", ".join(parts) if parts else ""
    else:
        readiness_section = ""

    # ── Events section ────────────────────────────────────────────────────
    named_events = [e for e in req.events if e.summary]
    if named_events:
        event_lines = []
        for e in named_events[:4]:
            time_str = f" at {e.start_time}" if e.start_time else ""
            event_lines.append(f"  - {e.summary}{time_str}")
        events_section = "TODAY'S SCHEDULE:\n" + "\n".join(event_lines)
    else:
        events_section = ""

    # ── Tasks section ─────────────────────────────────────────────────────
    if req.overdue_tasks:
        task_lines = [f"  - {t}" for t in req.overdue_tasks[:4]]
        tasks_section = "OVERDUE TASKS:\n" + "\n".join(task_lines)
    else:
        tasks_section = ""

    # ── Reads section ─────────────────────────────────────────────────────
    if req.reads:
        read_lines = []
        for read in req.reads[:2]:
            annotation_str = f" — {read.annotation}" if read.annotation else ""
            read_lines.append(f"  - \"{read.title}\"{annotation_str}")
        reads_section = "TOP READS:\n" + "\n".join(read_lines)
    else:
        reads_section = ""

    return MORNING_BRIEF_PROMPT.format(
        readiness_section=readiness_section,
        events_section=events_section,
        tasks_section=tasks_section,
        reads_section=reads_section,
    ).strip()


@router.post("/brief", response_model=MorningBriefResponse)
async def generate_morning_brief(
    req: MorningBriefRequest,
    current_user: User = Depends(get_current_user),
) -> MorningBriefResponse:
    """Generate a synthesized morning brief paragraph via LLM.

    Stateless — no DB reads or writes. The frontend session-locks the result
    once per morning and falls back to composeBrief() on error/timeout.
    """
    prompt = _build_prompt(req)

    llm = OpenAIResponsesClient(client=get_shared_openai_client())
    logger.info("[morning-brief] generating brief for user_id={}", current_user.id)

    try:
        result = await llm.generate_text(
            prompt,
            temperature=_BRIEF_TEMPERATURE,
            max_output_tokens=_BRIEF_MAX_TOKENS,
            instructions=MORNING_BRIEF_SYSTEM_INSTRUCTIONS,
        )
    except Exception as exc:
        logger.warning("[morning-brief] LLM call failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Morning brief generation unavailable — please use the local fallback.",
        ) from exc

    paragraph = result.text.strip()
    if not paragraph:
        logger.warning("[morning-brief] LLM returned empty text")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Morning brief generation returned empty response — please use the local fallback.",
        )

    return MorningBriefResponse(paragraph=paragraph)
