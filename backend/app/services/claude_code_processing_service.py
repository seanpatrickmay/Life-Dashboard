"""Processes Claude Code sessions into project activities and journal entries."""
from __future__ import annotations

import logging
import subprocess
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.claude_code import ProjectActivity
from app.db.models.journal import JournalEntry
from app.db.models.project import Project
from app.prompts.llm_prompts import (
    CLAUDE_CODE_SESSION_SUMMARY_PROMPT,
    CLAUDE_CODE_PROJECT_STATE_PROMPT,
)
from app.services.claude_code_sync_service import SessionContent

logger = logging.getLogger(__name__)


class SessionSummaryResponse(BaseModel):
    summary: str
    files_modified: list[str] = []
    git_branch: str | None = None
    git_commits: list[str] = []
    category: str = "feature"
    key_decisions: list[str] = []
    skip: bool = False


class ProjectStateResponse(BaseModel):
    status: str
    recent_focus: str
    next_steps: list[str] = []


class ClaudeCodeProcessingService:
    """Summarizes Claude Code sessions and creates activities / journal entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._openai = OpenAIResponsesClient()

    async def summarize_session(
        self,
        content: SessionContent,
        *,
        git_log: str = "",
    ) -> dict[str, Any]:
        """Use LLM to summarize a session's content."""
        prompt = CLAUDE_CODE_SESSION_SUMMARY_PROMPT.format(
            user_messages="\n".join(f"- {m}" for m in content.user_messages),
            assistant_texts="\n".join(f"- {t[:500]}" for t in content.assistant_texts),
            tool_uses="\n".join(
                f"- {t.get('name', '?')}: {t.get('file_path', t.get('command', t.get('pattern', '')))}"
                for t in content.tool_uses
            ),
            git_log=git_log or "(no commits found)",
        )

        result = await self._openai.generate_json(
            prompt,
            response_model=SessionSummaryResponse,
            temperature=0.2,
        )
        return result.data.model_dump()

    async def upsert_project_activity(
        self,
        *,
        user_id: int,
        project_id: int,
        session_id: str,
        local_date: date,
        summary: str,
        details_json: dict,
        source_project_path: str,
    ) -> ProjectActivity:
        """Create or update a ProjectActivity for a session."""
        result = await self._session.execute(
            select(ProjectActivity).where(
                and_(
                    ProjectActivity.user_id == user_id,
                    ProjectActivity.session_id == session_id,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.summary = summary
            existing.details_json = details_json
            await self._session.flush()
            return existing

        activity = ProjectActivity(
            user_id=user_id,
            project_id=project_id,
            local_date=local_date,
            session_id=session_id,
            summary=summary,
            details_json=details_json,
            source_project_path=source_project_path,
        )
        self._session.add(activity)
        await self._session.flush()
        return activity

    async def upsert_journal_entry(
        self,
        *,
        user_id: int,
        project_name: str,
        local_date: date,
        summary: str,
        time_zone: str,
    ) -> JournalEntry:
        """Create or update a journal entry for a project's daily work."""
        prefix = f"[Claude Code — {project_name}]"
        text = f"{prefix} {summary}"

        result = await self._session.execute(
            select(JournalEntry).where(
                and_(
                    JournalEntry.user_id == user_id,
                    JournalEntry.local_date == local_date,
                    JournalEntry.source == "claude_code",
                    JournalEntry.text.startswith(prefix),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.text = text
            await self._session.flush()
            return existing

        entry = JournalEntry(
            user_id=user_id,
            local_date=local_date,
            time_zone=time_zone,
            text=text,
            source="claude_code",
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def regenerate_project_state(
        self,
        *,
        user_id: int,
        project_id: int,
    ) -> None:
        """Regenerate a project's state summary from recent activity."""
        result = await self._session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return

        result = await self._session.execute(
            select(ProjectActivity)
            .where(
                and_(
                    ProjectActivity.user_id == user_id,
                    ProjectActivity.project_id == project_id,
                )
            )
            .order_by(ProjectActivity.local_date.desc())
            .limit(20)
        )
        activities = result.scalars().all()

        if not activities:
            return

        activity_log = "\n".join(
            f"- [{a.local_date}] {a.summary}" for a in activities
        )

        prompt = CLAUDE_CODE_PROJECT_STATE_PROMPT.format(
            project_name=project.name,
            activity_log=activity_log,
        )

        state_result = await self._openai.generate_json(
            prompt,
            response_model=ProjectStateResponse,
            temperature=0.2,
        )

        project.state_summary_json = state_result.data.model_dump()
        project.state_updated_at_utc = datetime.now(timezone.utc)
        await self._session.flush()


def get_git_log_for_session(
    project_path: str,
    start_time: str | None,
    end_time: str | None,
) -> str:
    """Get git log for commits made during a session's time range."""
    if not start_time or not project_path:
        return ""
    try:
        cmd = ["git", "-C", project_path, "log", "--oneline", "--no-decorate"]
        if start_time:
            cmd.extend(["--since", start_time])
        if end_time:
            cmd.extend(["--until", end_time])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
