"""Reads Claude Code conversation logs and manages sync cursors."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.claude_code import ClaudeCodeSyncCursor
from app.services.claude_code_project_resolver import encode_project_path

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = [
    re.compile(r"(?i)(\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*)\s*=\s*\S+"),
    re.compile(r"(?i)DATABASE_URL\s*=\s*\S+"),
    re.compile(r"://[^/\s]*:[^@/\s]*@"),
]

_SENSITIVE_FILE_PATTERNS = {".env", "credentials", "secrets", ".pem", ".key"}


@dataclass
class SessionInfo:
    session_id: str
    project_path: str
    last_timestamp_ms: int


@dataclass
class SessionContent:
    session_id: str
    project_path: str
    git_branch: str | None = None
    user_messages: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tool_uses: list[dict] = field(default_factory=list)
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    entry_count: int = 0


def discover_sessions_from_history(claude_dir: Path) -> list[SessionInfo]:
    """Read history.jsonl and return session info for each unique session."""
    history_file = claude_dir / "history.jsonl"
    if not history_file.exists():
        logger.warning("No history.jsonl found at %s", history_file)
        return []

    sessions: dict[str, SessionInfo] = {}
    for line in history_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        session_id = entry.get("sessionId")
        if not session_id:
            continue

        project_path = entry.get("project", "")
        timestamp = entry.get("timestamp", 0)

        if session_id not in sessions:
            sessions[session_id] = SessionInfo(
                session_id=session_id,
                project_path=project_path,
                last_timestamp_ms=timestamp,
            )
        else:
            if timestamp > sessions[session_id].last_timestamp_ms:
                sessions[session_id].last_timestamp_ms = timestamp

    return list(sessions.values())


def discover_sessions_from_directories(claude_dir: Path, known_ids: set[str]) -> list[SessionInfo]:
    """Scan projects/ directory for session files not in history.jsonl."""
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []

    found: list[SessionInfo] = []
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl_file in proj_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            if session_id in known_ids:
                continue
            # Read first entry for cwd
            project_path = ""
            try:
                first_line = jsonl_file.open().readline().strip()
                if first_line:
                    entry = json.loads(first_line)
                    project_path = entry.get("cwd", "")
            except (json.JSONDecodeError, OSError):
                pass
            if project_path:
                found.append(SessionInfo(
                    session_id=session_id,
                    project_path=project_path,
                    last_timestamp_ms=0,
                ))
                known_ids.add(session_id)

    return found


def find_session_file(claude_dir: Path, session_info: SessionInfo) -> Path | None:
    """Locate the session JSONL file on disk."""
    if not session_info.project_path:
        return None

    encoded = encode_project_path(session_info.project_path)
    proj_dir = claude_dir / "projects" / encoded
    if not proj_dir.exists():
        return None

    session_file = proj_dir / f"{session_info.session_id}.jsonl"
    return session_file if session_file.exists() else None


def is_session_active(claude_dir: Path, session_id: str) -> bool:
    """Check if a session is currently active."""
    sessions_dir = claude_dir / "sessions"
    if not sessions_dir.exists():
        return False

    for pid_file in sessions_dir.glob("*.json"):
        try:
            meta = json.loads(pid_file.read_text())
            if meta.get("sessionId") != session_id:
                continue
            pid = meta.get("pid")
            if pid is None:
                continue
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            continue
        except (json.JSONDecodeError, OSError):
            continue

    return False


def filter_sensitive_content(text: str) -> str:
    """Remove secrets and credentials from text before LLM submission."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def _is_sensitive_file(file_path: str) -> bool:
    """Check if a file path matches sensitive file patterns."""
    lower = file_path.lower()
    return any(p in lower for p in _SENSITIVE_FILE_PATTERNS)


def extract_session_content(
    session_file: Path,
    *,
    max_tokens_approx: int = 8000,
) -> SessionContent:
    """Extract relevant content from a session JSONL file."""
    content = SessionContent(session_id=session_file.stem, project_path="")

    entries = []
    for line in session_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    content.entry_count = len(entries)

    git_branch = None
    first_ts = None
    last_ts = None
    user_messages: list[str] = []
    assistant_texts: list[str] = []
    tool_uses: list[dict] = []

    for entry in entries:
        entry_type = entry.get("type")
        ts = entry.get("timestamp")
        if ts and not first_ts:
            first_ts = ts
        if ts:
            last_ts = ts

        if not git_branch and entry.get("gitBranch"):
            git_branch = entry["gitBranch"]
        if not content.project_path and entry.get("cwd"):
            content.project_path = entry["cwd"]

        if entry_type == "user":
            msg = entry.get("message", {})
            msg_content = msg.get("content", "")
            if isinstance(msg_content, str) and msg_content.strip():
                user_messages.append(msg_content.strip())

        elif entry_type == "assistant":
            msg = entry.get("message", {})
            msg_content = msg.get("content", [])
            if isinstance(msg_content, list):
                for block in msg_content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text"):
                        assistant_texts.append(block["text"].strip())
                    elif block.get("type") == "tool_use":
                        tool_input = block.get("input", {})
                        if not isinstance(tool_input, dict):
                            continue
                        file_path = tool_input.get("file_path", "")
                        if file_path and _is_sensitive_file(file_path):
                            continue
                        tool_summary: dict = {"name": block.get("name", "")}
                        if file_path:
                            tool_summary["file_path"] = file_path
                        if "command" in tool_input:
                            cmd = tool_input["command"]
                            tool_summary["command"] = cmd[:200] if isinstance(cmd, str) else ""
                        if "pattern" in tool_input:
                            tool_summary["pattern"] = tool_input["pattern"]
                        tool_uses.append(tool_summary)

    # Token budget: ~4 chars per token
    char_budget = max_tokens_approx * 4
    total_chars = (
        sum(len(m) for m in user_messages)
        + sum(len(t) for t in assistant_texts)
        + sum(len(json.dumps(t)) for t in tool_uses)
    )

    if total_chars > char_budget:
        if len(user_messages) > 6:
            user_messages = user_messages[:3] + user_messages[-3:]
        if len(assistant_texts) > 6:
            assistant_texts = assistant_texts[:3] + assistant_texts[-3:]
        git_tools = [t for t in tool_uses if "git" in json.dumps(t).lower()]
        other_tools = [t for t in tool_uses if t not in git_tools]
        if len(other_tools) > 10:
            other_tools = other_tools[:5] + other_tools[-5:]
        tool_uses = git_tools + other_tools

    content.user_messages = [filter_sensitive_content(m) for m in user_messages]
    content.assistant_texts = [filter_sensitive_content(t) for t in assistant_texts]
    content.tool_uses = tool_uses
    content.git_branch = git_branch
    content.first_timestamp = first_ts
    content.last_timestamp = last_ts

    return content


class ClaudeCodeSyncService:
    """Manages sync cursors and coordinates session reading."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_cursor(self, user_id: int, session_id: str) -> ClaudeCodeSyncCursor | None:
        result = await self._session.execute(
            select(ClaudeCodeSyncCursor).where(
                ClaudeCodeSyncCursor.user_id == user_id,
                ClaudeCodeSyncCursor.session_id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_cursor(
        self,
        *,
        user_id: int,
        session_id: str,
        project_path: str,
        entry_count: int,
        file_mtime: float,
    ) -> ClaudeCodeSyncCursor:
        cursor = await self.get_cursor(user_id, session_id)
        if cursor:
            cursor.entry_count = entry_count
            cursor.file_mtime = file_mtime
        else:
            cursor = ClaudeCodeSyncCursor(
                user_id=user_id,
                session_id=session_id,
                project_path=project_path,
                entry_count=entry_count,
                file_mtime=file_mtime,
            )
            self._session.add(cursor)
        await self._session.flush()
        return cursor

    async def find_unprocessed_sessions(
        self,
        *,
        user_id: int,
        claude_dir: Path,
    ) -> list[tuple[SessionInfo, Path]]:
        """Find sessions that are new or have been updated since last sync."""
        history_sessions = discover_sessions_from_history(claude_dir)
        known_ids = {s.session_id for s in history_sessions}
        dir_sessions = discover_sessions_from_directories(claude_dir, known_ids)
        all_sessions = history_sessions + dir_sessions

        result = []
        for session_info in all_sessions:
            if is_session_active(claude_dir, session_info.session_id):
                logger.debug("Skipping active session %s", session_info.session_id)
                continue

            session_file = find_session_file(claude_dir, session_info)
            if not session_file:
                continue

            try:
                file_mtime = os.path.getmtime(session_file)
            except OSError:
                continue

            cursor = await self.get_cursor(user_id, session_info.session_id)
            if cursor and cursor.file_mtime >= file_mtime:
                continue

            result.append((session_info, session_file))

        return result
