# Claude Code History Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hourly sync job reads Claude Code conversation logs, LLM-summarizes sessions into project activities and journal entries, with auto project recognition and project state summaries displayed on the projects page.

**Architecture:** Cursor-based sync reads `~/.claude/` JSONL files directly from disk (no intermediate DB storage of raw messages). LLM extracts summaries → creates `ProjectActivity` records + `JournalEntry` per project per day. Project state regenerated from recent activity. Frontend adds activity feed and state summary to existing projects page.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, OpenAI Responses API (gpt-5-mini), React/TypeScript, TanStack Query, styled-components

**Spec:** `docs/superpowers/specs/2026-03-25-claude-code-history-integration-design.md`

---

### Task 1: Database Models

**Files:**
- Create: `backend/app/db/models/claude_code.py`
- Modify: `backend/app/db/models/project.py`
- Modify: `backend/app/db/models/journal.py`
- Modify: `backend/app/db/models/entities.py`

- [ ] **Step 1: Create ClaudeCodeSyncCursor and ProjectActivity models**

Create `backend/app/db/models/claude_code.py`:

```python
"""Models for Claude Code sync tracking and project activity."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClaudeCodeSyncCursor(Base):
    __tablename__ = "claude_code_sync_cursor"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_cc_cursor_user_session"),
        Index("ix_cc_cursor_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    last_processed_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_mtime: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    user = relationship("User", back_populates="claude_code_sync_cursors")


class ProjectActivity(Base):
    __tablename__ = "project_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_project_activity_user_session"),
        Index("ix_project_activity_user_project_date", "user_id", "project_id", "local_date"),
        Index("ix_project_activity_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id"), nullable=False
    )
    local_date: Mapped[date] = mapped_column(nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    source_project_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    user = relationship("User", back_populates="project_activities")
    project = relationship("Project", back_populates="activities")
```

- [ ] **Step 2: Add `source` column to JournalEntry**

In `backend/app/db/models/journal.py`, add after the `text` field:

```python
source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 3: Add `state_summary_json` and `state_updated_at_utc` to Project**

In `backend/app/db/models/project.py`, add after the `sort_order` field:

```python
state_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
state_updated_at_utc: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Add import for `datetime` and `JSON` and `DateTime` at top if not present.

- [ ] **Step 4: Add relationships to Project and User models**

In `backend/app/db/models/project.py`, add relationship:

```python
activities: Mapped[list["ProjectActivity"]] = relationship(back_populates="project")
```

In `backend/app/db/models/entities.py`, add to the User class:

```python
claude_code_sync_cursors: Mapped[list["ClaudeCodeSyncCursor"]] = relationship(
    back_populates="user"
)
project_activities: Mapped[list["ProjectActivity"]] = relationship(
    back_populates="user"
)
```

- [ ] **Step 5: Register models in `__init__`**

Check if there's a model registry file (e.g., `backend/app/db/models/__init__.py`) and add imports for the new models so Alembic discovers them.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models/claude_code.py backend/app/db/models/project.py backend/app/db/models/journal.py backend/app/db/models/entities.py
git commit -m "feat: add ClaudeCodeSyncCursor and ProjectActivity models, source column on JournalEntry"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `backend/migrations/versions/20260325_claude_code_history.py`

- [ ] **Step 1: Generate the migration**

```bash
cd backend && alembic revision -m "claude_code_history"
```

Then edit the generated file to match this content (use the generated revision ID):

```python
"""claude_code_history"""

from alembic import op
import sqlalchemy as sa

revision = "20260325_claude_code_history"
down_revision = "20260324_ingredient_name_per_user"

def upgrade() -> None:
    op.create_table(
        "claude_code_sync_cursor",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("project_path", sa.Text, nullable=False),
        sa.Column("last_processed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_mtime", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "session_id", name="uq_cc_cursor_user_session"),
    )
    op.create_index("ix_cc_cursor_user_id", "claude_code_sync_cursor", ["user_id"])

    op.create_table(
        "project_activity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id"), nullable=False),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("source_project_path", sa.Text, nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "session_id", name="uq_project_activity_user_session"),
    )
    op.create_index("ix_project_activity_user_id", "project_activity", ["user_id"])
    op.create_index(
        "ix_project_activity_user_project_date",
        "project_activity",
        ["user_id", "project_id", "local_date"],
    )

    op.add_column("project", sa.Column("state_summary_json", sa.JSON, nullable=True))
    op.add_column("project", sa.Column("state_updated_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("journal_entry", sa.Column("source", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("journal_entry", "source")
    op.drop_column("project", "state_updated_at_utc")
    op.drop_column("project", "state_summary_json")
    op.drop_index("ix_project_activity_user_project_date", table_name="project_activity")
    op.drop_index("ix_project_activity_user_id", table_name="project_activity")
    op.drop_table("project_activity")
    op.drop_index("ix_cc_cursor_user_id", table_name="claude_code_sync_cursor")
    op.drop_table("claude_code_sync_cursor")
```

- [ ] **Step 2: Run the migration**

```bash
cd backend && alembic upgrade head
```

Expected: Migration applies cleanly.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/20260325_claude_code_history.py
git commit -m "feat: add migration for claude_code_sync_cursor, project_activity tables"
```

---

### Task 3: Claude Code Project Resolver

**Files:**
- Create: `backend/app/services/claude_code_project_resolver.py`
- Test: `backend/tests/test_claude_code_project_resolver.py`

- [ ] **Step 1: Write tests for project path extraction and resolution**

Create `backend/tests/test_claude_code_project_resolver.py`:

```python
"""Tests for ClaudeCodeProjectResolver."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.claude_code_project_resolver import (
    extract_project_name,
    encode_project_path,
    ClaudeCodeProjectResolver,
)


class TestExtractProjectName:
    def test_standard_project_path(self):
        path = "/Users/seanmay/Desktop/Current Projects/Life-Dashboard"
        assert extract_project_name(path) == "Life-Dashboard"

    def test_nested_project_path(self):
        path = "/Users/seanmay/Desktop/Current Projects/news-scraping"
        assert extract_project_name(path) == "news-scraping"

    def test_home_directory_returns_general(self):
        path = "/Users/seanmay"
        assert extract_project_name(path) == "General"

    def test_empty_path_returns_general(self):
        assert extract_project_name("") == "General"
        assert extract_project_name(None) == "General"

    def test_root_path_returns_general(self):
        assert extract_project_name("/") == "General"


class TestEncodeProjectPath:
    def test_encodes_slashes_spaces_dots(self):
        path = "/Users/seanmay/Desktop/Current Projects/Life-Dashboard"
        encoded = encode_project_path(path)
        assert encoded == "-Users-seanmay-Desktop-Current-Projects-Life-Dashboard"

    def test_encodes_dots(self):
        path = "/Users/seanmay/seanpatrickmay.github.io"
        encoded = encode_project_path(path)
        assert encoded == "-Users-seanmay-seanpatrickmay-github-io"


class TestClaudeCodeProjectResolver:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_project_repo(self):
        repo = MagicMock()
        repo.get_by_name_for_user = AsyncMock(return_value=None)
        repo.create_one = AsyncMock()
        repo.ensure_inbox_project = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_resolve_existing_project(self, mock_session, mock_project_repo):
        existing_project = MagicMock(id=5, name="Life-Dashboard")
        mock_project_repo.get_by_name_for_user = AsyncMock(return_value=existing_project)

        resolver = ClaudeCodeProjectResolver(mock_session)
        resolver._project_repo = mock_project_repo

        result = await resolver.resolve(
            user_id=1,
            project_path="/Users/seanmay/Desktop/Current Projects/Life-Dashboard",
        )
        assert result.id == 5
        mock_project_repo.create_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_creates_new_project(self, mock_session, mock_project_repo):
        new_project = MagicMock(id=10, name="news-scraping")
        mock_project_repo.create_one = AsyncMock(return_value=new_project)

        resolver = ClaudeCodeProjectResolver(mock_session)
        resolver._project_repo = mock_project_repo

        result = await resolver.resolve(
            user_id=1,
            project_path="/Users/seanmay/Desktop/Current Projects/news-scraping",
        )
        assert result.id == 10
        mock_project_repo.create_one.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_claude_code_project_resolver.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement ClaudeCodeProjectResolver**

Create `backend/app/services/claude_code_project_resolver.py`:

```python
"""Resolves Claude Code project paths to Life Dashboard Project records."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)

GENERAL_PROJECT_NAME = "General"

# Paths at or above this depth are treated as non-project directories
_MIN_PROJECT_DEPTH = 3  # e.g., /Users/seanmay/something


def extract_project_name(project_path: str | None) -> str:
    """Extract a project name from a filesystem path.

    Returns the last path segment, or 'General' for missing/shallow paths.
    """
    if not project_path:
        return GENERAL_PROJECT_NAME

    p = Path(project_path)
    parts = [part for part in p.parts if part != "/"]

    if len(parts) < _MIN_PROJECT_DEPTH:
        return GENERAL_PROJECT_NAME

    return parts[-1]


def encode_project_path(project_path: str) -> str:
    """Encode a project path the same way Claude Code does (for locating files on disk).

    Replaces /, spaces, and dots with hyphens.
    """
    encoded = project_path.replace("/", "-").replace(" ", "-").replace(".", "-")
    return encoded


class ClaudeCodeProjectResolver:
    """Maps Claude Code project paths to Life Dashboard Project records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._project_repo = ProjectRepository(session)
        self._cache: dict[str, Project] = {}

    async def resolve(self, *, user_id: int, project_path: str | None) -> Project:
        """Resolve a project path to a Project record, creating if needed."""
        name = extract_project_name(project_path)

        if name in self._cache:
            return self._cache[name]

        existing = await self._project_repo.get_by_name_for_user(user_id, name)
        if existing:
            self._cache[name] = existing
            return existing

        logger.info("Auto-creating project '%s' from path: %s", name, project_path)
        new_project = await self._project_repo.create_one(
            user_id=user_id,
            name=name,
            notes=f"Auto-created from Claude Code. Source: {project_path}",
        )
        await self._session.flush()
        self._cache[name] = new_project
        return new_project
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_claude_code_project_resolver.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/claude_code_project_resolver.py backend/tests/test_claude_code_project_resolver.py
git commit -m "feat: add ClaudeCodeProjectResolver with path-based project recognition"
```

---

### Task 4: Claude Code Sync Service

**Files:**
- Create: `backend/app/services/claude_code_sync_service.py`
- Test: `backend/tests/test_claude_code_sync_service.py`

- [ ] **Step 1: Write tests for session discovery and content extraction**

Create `backend/tests/test_claude_code_sync_service.py`:

```python
"""Tests for ClaudeCodeSyncService."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.claude_code_sync_service import (
    ClaudeCodeSyncService,
    SessionInfo,
    discover_sessions_from_history,
    extract_session_content,
    is_session_active,
    filter_sensitive_content,
)


@pytest.fixture
def tmp_claude_dir(tmp_path):
    """Create a mock ~/.claude/ directory structure."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "sessions").mkdir()
    (claude_dir / "projects").mkdir()

    # Create history.jsonl
    history = claude_dir / "history.jsonl"
    entries = [
        {
            "display": "Fix the journal bug",
            "timestamp": 1774449849341,
            "project": "/Users/test/projects/Life-Dashboard",
            "sessionId": "aaaa-bbbb-cccc-dddd",
        },
        {
            "display": "Add news scraper",
            "timestamp": 1774449900000,
            "project": "/Users/test/projects/news-scraping",
            "sessionId": "eeee-ffff-0000-1111",
        },
        {
            "display": "Quick fix",
            "timestamp": 1774449950000,
            "project": "/Users/test/projects/Life-Dashboard",
            # No sessionId
        },
    ]
    history.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    # Create project directory with session file
    proj_dir = claude_dir / "projects" / "-Users-test-projects-Life-Dashboard"
    proj_dir.mkdir(parents=True)
    session_file = proj_dir / "aaaa-bbbb-cccc-dddd.jsonl"
    session_entries = [
        {
            "type": "user",
            "message": {"role": "user", "content": "Fix the journal page load bug"},
            "timestamp": "2026-03-25T10:00:00.000Z",
            "sessionId": "aaaa-bbbb-cccc-dddd",
            "cwd": "/Users/test/projects/Life-Dashboard",
            "gitBranch": "fix/journal-perf",
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix the journal page load performance."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "backend/app/routers/journal.py"}},
                ],
            },
            "timestamp": "2026-03-25T10:01:00.000Z",
            "sessionId": "aaaa-bbbb-cccc-dddd",
        },
    ]
    session_file.write_text("\n".join(json.dumps(e) for e in session_entries) + "\n")

    return claude_dir


class TestDiscoverSessionsFromHistory:
    def test_discovers_sessions_with_ids(self, tmp_claude_dir):
        sessions = discover_sessions_from_history(tmp_claude_dir)
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert "aaaa-bbbb-cccc-dddd" in ids
        assert "eeee-ffff-0000-1111" in ids

    def test_skips_entries_without_session_id(self, tmp_claude_dir):
        sessions = discover_sessions_from_history(tmp_claude_dir)
        for s in sessions:
            assert s.session_id is not None


class TestExtractSessionContent:
    def test_extracts_user_and_assistant_text(self, tmp_claude_dir):
        proj_dir = tmp_claude_dir / "projects" / "-Users-test-projects-Life-Dashboard"
        session_file = proj_dir / "aaaa-bbbb-cccc-dddd.jsonl"
        content = extract_session_content(session_file)
        assert "Fix the journal page load bug" in content.user_messages[0]
        assert "fix the journal page load performance" in content.assistant_texts[0].lower()

    def test_extracts_tool_use_summaries(self, tmp_claude_dir):
        proj_dir = tmp_claude_dir / "projects" / "-Users-test-projects-Life-Dashboard"
        session_file = proj_dir / "aaaa-bbbb-cccc-dddd.jsonl"
        content = extract_session_content(session_file)
        assert len(content.tool_uses) >= 1
        assert content.tool_uses[0]["name"] == "Edit"

    def test_extracts_metadata(self, tmp_claude_dir):
        proj_dir = tmp_claude_dir / "projects" / "-Users-test-projects-Life-Dashboard"
        session_file = proj_dir / "aaaa-bbbb-cccc-dddd.jsonl"
        content = extract_session_content(session_file)
        assert content.git_branch == "fix/journal-perf"


class TestFilterSensitiveContent:
    def test_strips_api_keys(self):
        text = "Set OPENAI_API_KEY=sk-abc123 in .env"
        filtered = filter_sensitive_content(text)
        assert "sk-abc123" not in filtered

    def test_strips_database_urls(self):
        text = "DATABASE_URL=postgresql://user:pass@localhost/db"
        filtered = filter_sensitive_content(text)
        assert "pass@localhost" not in filtered

    def test_preserves_normal_text(self):
        text = "Fixed the journal page load performance"
        filtered = filter_sensitive_content(text)
        assert filtered == text


class TestIsSessionActive:
    def test_no_session_file_means_inactive(self, tmp_claude_dir):
        assert not is_session_active(tmp_claude_dir, "nonexistent-session-id")

    def test_stale_pid_means_inactive(self, tmp_claude_dir):
        sessions_dir = tmp_claude_dir / "sessions"
        session_meta = sessions_dir / "99999.json"
        session_meta.write_text(json.dumps({
            "pid": 99999,
            "sessionId": "aaaa-bbbb-cccc-dddd",
            "cwd": "/tmp",
            "startedAt": 1774449849341,
            "kind": "interactive",
        }))
        # PID 99999 is very unlikely to be running
        assert not is_session_active(tmp_claude_dir, "aaaa-bbbb-cccc-dddd")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_claude_code_sync_service.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement ClaudeCodeSyncService**

Create `backend/app/services/claude_code_sync_service.py`:

```python
"""Reads Claude Code conversation logs and manages sync cursors."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.claude_code import ClaudeCodeSyncCursor
from app.services.claude_code_project_resolver import encode_project_path

logger = logging.getLogger(__name__)

# Privacy filters
_SECRET_PATTERNS = [
    re.compile(r"(?i)(\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*)\s*=\s*\S+"),
    re.compile(r"(?i)DATABASE_URL\s*=\s*\S+"),
    re.compile(r"://[^/\s]*:[^@/\s]*@"),  # credentials in URLs
]

_SENSITIVE_FILE_PATTERNS = {".env", "credentials", "secrets", ".pem", ".key"}

# Staleness threshold for active session detection (6 hours in seconds)
_STALE_SESSION_THRESHOLD = 6 * 60 * 60


@dataclass
class SessionInfo:
    session_id: str
    project_path: str
    last_timestamp_ms: int  # Unix ms from history.jsonl
    encoded_dir_name: str | None = None


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


def find_session_file(claude_dir: Path, session_info: SessionInfo) -> Path | None:
    """Locate the session JSONL file on disk."""
    if not session_info.project_path:
        return None

    encoded = encode_project_path(session_info.project_path)
    proj_dir = claude_dir / "projects" / encoded
    if not proj_dir.exists():
        return None

    session_file = proj_dir / f"{session_info.session_id}.jsonl"
    if session_file.exists():
        return session_file

    return None


def is_session_active(claude_dir: Path, session_id: str) -> bool:
    """Check if a session is currently active (running Claude Code process)."""
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
            # Check if PID is running
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            # PID not running or not accessible
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


def extract_session_content(
    session_file: Path,
    *,
    max_tokens_approx: int = 8000,
) -> SessionContent:
    """Extract relevant content from a session JSONL file.

    Parses user messages, assistant text, and tool use summaries.
    Applies token budget limiting for long sessions.
    """
    content = SessionContent(
        session_id=session_file.stem,
        project_path="",
    )

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

    user_messages = []
    assistant_texts = []
    tool_uses = []

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
                    if isinstance(block, dict):
                        if block.get("type") == "text" and block.get("text"):
                            assistant_texts.append(block["text"].strip())
                        elif block.get("type") == "tool_use":
                            tool_summary = {
                                "name": block.get("name", ""),
                            }
                            tool_input = block.get("input", {})
                            if isinstance(tool_input, dict):
                                if "file_path" in tool_input:
                                    tool_summary["file_path"] = tool_input["file_path"]
                                if "command" in tool_input:
                                    cmd = tool_input["command"]
                                    # Truncate long commands
                                    tool_summary["command"] = cmd[:200] if isinstance(cmd, str) else ""
                                if "pattern" in tool_input:
                                    tool_summary["pattern"] = tool_input["pattern"]
                            tool_uses.append(tool_summary)

    # Apply token budget: rough estimate 1 token ≈ 4 chars
    char_budget = max_tokens_approx * 4
    total_chars = (
        sum(len(m) for m in user_messages)
        + sum(len(t) for t in assistant_texts)
        + sum(len(json.dumps(t)) for t in tool_uses)
    )

    if total_chars > char_budget:
        # Keep first 3 + last 3 user messages
        if len(user_messages) > 6:
            user_messages = user_messages[:3] + user_messages[-3:]
        # Keep first 3 + last 3 assistant texts
        if len(assistant_texts) > 6:
            assistant_texts = assistant_texts[:3] + assistant_texts[-3:]
        # Keep only git-related tool uses + first/last few
        git_tools = [t for t in tool_uses if "git" in json.dumps(t).lower()]
        other_tools = [t for t in tool_uses if t not in git_tools]
        if len(other_tools) > 10:
            other_tools = other_tools[:5] + other_tools[-5:]
        tool_uses = git_tools + other_tools

    # Apply privacy filter
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
        last_processed_at_utc: datetime,
        entry_count: int,
        file_mtime: float,
    ) -> ClaudeCodeSyncCursor:
        cursor = await self.get_cursor(user_id, session_id)
        now = datetime.now(timezone.utc)
        if cursor:
            cursor.last_processed_at_utc = last_processed_at_utc
            cursor.entry_count = entry_count
            cursor.file_mtime = file_mtime
            cursor.updated_at_utc = now
        else:
            cursor = ClaudeCodeSyncCursor(
                user_id=user_id,
                session_id=session_id,
                project_path=project_path,
                last_processed_at_utc=last_processed_at_utc,
                entry_count=entry_count,
                file_mtime=file_mtime,
                created_at_utc=now,
                updated_at_utc=now,
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
        all_sessions = discover_sessions_from_history(claude_dir)
        result = []

        for session_info in all_sessions:
            # Skip active sessions
            if is_session_active(claude_dir, session_info.session_id):
                logger.debug("Skipping active session %s", session_info.session_id)
                continue

            session_file = find_session_file(claude_dir, session_info)
            if not session_file:
                continue

            # Check staleness for active session fallback
            try:
                file_mtime = os.path.getmtime(session_file)
            except OSError:
                continue

            # Check cursor
            cursor = await self.get_cursor(user_id, session_info.session_id)
            if cursor and cursor.file_mtime >= file_mtime:
                # File hasn't changed
                continue

            result.append((session_info, session_file))

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_claude_code_sync_service.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/claude_code_sync_service.py backend/tests/test_claude_code_sync_service.py
git commit -m "feat: add ClaudeCodeSyncService for session discovery and content extraction"
```

---

### Task 5: LLM Prompts

**Files:**
- Modify: `backend/app/prompts/llm_prompts.py`

- [ ] **Step 1: Add prompt constants for session summarization and project state**

Append to `backend/app/prompts/llm_prompts.py`:

```python
CLAUDE_CODE_SESSION_SUMMARY_PROMPT = """You are summarizing a Claude Code (AI coding assistant) session for a personal productivity dashboard.

Given the conversation content below, produce a JSON response with:
- "summary": 1-3 sentence plain-language description of what was accomplished
- "files_modified": list of file paths that were edited or created
- "git_branch": the git branch name if mentioned (or null)
- "git_commits": list of commit messages if any commits were made (or [])
- "category": one of "feature", "bugfix", "refactor", "debugging", "planning", "research", "config"
- "key_decisions": list of important decisions or trade-offs made (or [])

Focus on OUTCOMES — what was built, fixed, or decided — not the process.

USER MESSAGES:
{user_messages}

ASSISTANT RESPONSES:
{assistant_texts}

TOOL USAGE (files/commands):
{tool_uses}

GIT LOG (commits during session):
{git_log}
"""

CLAUDE_CODE_PROJECT_STATE_PROMPT = """You are generating a project status summary for a personal productivity dashboard.

Given the recent activity log for this project, produce a JSON response with:
- "status": 1-2 sentence description of what this project is and its current state
- "recent_focus": 1-2 sentences about what's been worked on recently
- "next_steps": list of 2-4 concrete next steps inferred from the activity (things discussed but not yet done, open questions, planned work)

Be concise and concrete. Use plain language.

PROJECT NAME: {project_name}

RECENT ACTIVITY (newest first):
{activity_log}
"""
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/prompts/llm_prompts.py
git commit -m "feat: add LLM prompts for Claude Code session summarization and project state"
```

---

### Task 6: Claude Code Processing Service

**Files:**
- Create: `backend/app/services/claude_code_processing_service.py`
- Test: `backend/tests/test_claude_code_processing_service.py`

- [ ] **Step 1: Write tests for processing service**

Create `backend/tests/test_claude_code_processing_service.py`:

```python
"""Tests for ClaudeCodeProcessingService."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.claude_code_processing_service import ClaudeCodeProcessingService
from app.services.claude_code_sync_service import SessionContent


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.generate_json = AsyncMock(return_value=MagicMock(
        data={
            "summary": "Fixed journal page load performance by making summary compilation non-blocking.",
            "files_modified": ["backend/app/routers/journal.py"],
            "git_branch": "fix/journal-perf",
            "git_commits": ["Fix journal page load performance"],
            "category": "bugfix",
            "key_decisions": ["Made summary compilation non-blocking"],
        },
        total_tokens=500,
    ))
    return client


@pytest.fixture
def sample_content():
    return SessionContent(
        session_id="aaaa-bbbb-cccc-dddd",
        project_path="/Users/test/projects/Life-Dashboard",
        git_branch="fix/journal-perf",
        user_messages=["Fix the journal page load bug"],
        assistant_texts=["I'll fix the journal page load performance by making summary non-blocking."],
        tool_uses=[{"name": "Edit", "file_path": "backend/app/routers/journal.py"}],
        first_timestamp="2026-03-25T10:00:00.000Z",
        last_timestamp="2026-03-25T10:30:00.000Z",
        entry_count=20,
    )


class TestProcessSession:
    @pytest.mark.asyncio
    async def test_creates_project_activity(self, mock_session, mock_openai_client, sample_content):
        service = ClaudeCodeProcessingService(mock_session)
        service._openai = mock_openai_client

        mock_project = MagicMock(id=5)
        result = await service.summarize_session(sample_content)

        assert result is not None
        assert "journal page load" in result["summary"].lower()
        assert result["category"] == "bugfix"

    @pytest.mark.asyncio
    async def test_builds_llm_prompt_from_content(self, mock_session, mock_openai_client, sample_content):
        service = ClaudeCodeProcessingService(mock_session)
        service._openai = mock_openai_client

        await service.summarize_session(sample_content)

        # Verify generate_json was called with content from the session
        call_args = mock_openai_client.generate_json.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "Fix the journal page load bug" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_claude_code_processing_service.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement ClaudeCodeProcessingService**

Create `backend/app/services/claude_code_processing_service.py`:

```python
"""Processes Claude Code sessions into project activities and journal entries."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.claude_code import ProjectActivity
from app.db.models.journal import JournalEntry
from app.db.models.project import Project
from app.db.repositories.project_repository import ProjectRepository
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


class ProjectStateResponse(BaseModel):
    status: str
    recent_focus: str
    next_steps: list[str] = []


class ClaudeCodeProcessingService:
    """Summarizes Claude Code sessions and creates activities/journal entries."""

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
        now = datetime.now(timezone.utc)

        if existing:
            existing.summary = summary
            existing.details_json = details_json
            existing.updated_at_utc = now
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
            created_at_utc=now,
            updated_at_utc=now,
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
        text = f"[Claude Code — {project_name}] {summary}"

        # Find existing claude_code entry for this project+date
        result = await self._session.execute(
            select(JournalEntry).where(
                and_(
                    JournalEntry.user_id == user_id,
                    JournalEntry.local_date == local_date,
                    JournalEntry.source == "claude_code",
                    JournalEntry.text.contains(f"[Claude Code — {project_name}]"),
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
        # Fetch project
        result = await self._session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return

        # Fetch recent activities (last 20)
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
            f"- [{a.local_date}] {a.summary}"
            for a in activities
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_claude_code_processing_service.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/claude_code_processing_service.py backend/tests/test_claude_code_processing_service.py
git commit -m "feat: add ClaudeCodeProcessingService for LLM summarization and activity creation"
```

---

### Task 7: Sync Script and Scheduling

**Files:**
- Create: `scripts/sync_claude_code.py`
- Create: `scripts/run_claude_code_sync.sh`
- Create: `scripts/com.life_dashboard.claude_code_sync.plist.template`

- [ ] **Step 1: Create the sync script**

Create `scripts/sync_claude_code.py`:

```python
#!/usr/bin/env python3
"""Claude Code conversation log sync + processing runner."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load .env before anything else
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

sys.path.append(str(ROOT / "backend"))

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.claude_code_sync_service import (  # noqa: E402
    ClaudeCodeSyncService,
    extract_session_content,
)
from app.services.claude_code_processing_service import (  # noqa: E402
    ClaudeCodeProcessingService,
    get_git_log_for_session,
)
from app.services.claude_code_project_resolver import ClaudeCodeProjectResolver  # noqa: E402
from app.utils.timezone import local_today  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_claude_code")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Claude Code history")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--time-zone", type=str, default="America/New_York")
    parser.add_argument(
        "--claude-dir",
        type=str,
        default=os.path.expanduser("~/.claude"),
        help="Path to Claude Code data directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    claude_dir = Path(args.claude_dir)

    if not claude_dir.exists():
        logger.error("Claude directory not found: %s", claude_dir)
        sys.exit(1)

    logger.info(
        "Starting Claude Code sync: user_id=%d, claude_dir=%s",
        args.user_id,
        claude_dir,
    )

    async with AsyncSessionLocal() as session:
        sync_service = ClaudeCodeSyncService(session)
        processing_service = ClaudeCodeProcessingService(session)
        resolver = ClaudeCodeProjectResolver(session)

        # Find unprocessed sessions
        unprocessed = await sync_service.find_unprocessed_sessions(
            user_id=args.user_id,
            claude_dir=claude_dir,
        )
        logger.info("Found %d unprocessed/updated sessions", len(unprocessed))

        if not unprocessed:
            logger.info("Nothing to process. Done.")
            return

        projects_with_new_activity: set[int] = set()
        today = local_today(args.time_zone)

        for session_info, session_file in unprocessed:
            try:
                logger.info(
                    "Processing session %s (project: %s)",
                    session_info.session_id,
                    session_info.project_path,
                )

                # Extract content
                content = extract_session_content(session_file)
                if not content.user_messages:
                    logger.info("Session %s has no user messages, skipping", session_info.session_id)
                    continue

                # Use project path from content (cwd) if available, else from history
                project_path = content.project_path or session_info.project_path

                # Resolve project
                project = await resolver.resolve(
                    user_id=args.user_id,
                    project_path=project_path,
                )

                # Get git log for the session time range
                git_log = get_git_log_for_session(
                    project_path,
                    content.first_timestamp,
                    content.last_timestamp,
                )

                # LLM summarize
                summary_data = await processing_service.summarize_session(
                    content, git_log=git_log
                )

                # Determine local date from session timestamp
                session_date = today  # Default to today
                if content.first_timestamp:
                    try:
                        ts = datetime.fromisoformat(
                            content.first_timestamp.replace("Z", "+00:00")
                        )
                        session_date = ts.date()
                    except (ValueError, AttributeError):
                        pass

                if not args.dry_run:
                    # Upsert ProjectActivity
                    await processing_service.upsert_project_activity(
                        user_id=args.user_id,
                        project_id=project.id,
                        session_id=session_info.session_id,
                        local_date=session_date,
                        summary=summary_data["summary"],
                        details_json=summary_data,
                        source_project_path=project_path,
                    )

                    # Upsert JournalEntry (one per project per day)
                    # Aggregate: collect all summaries for this project+date
                    await processing_service.upsert_journal_entry(
                        user_id=args.user_id,
                        project_name=project.name,
                        local_date=session_date,
                        summary=summary_data["summary"],
                        time_zone=args.time_zone,
                    )

                    # Update cursor
                    file_mtime = os.path.getmtime(session_file)
                    last_ts = datetime.now(timezone.utc)
                    if content.last_timestamp:
                        try:
                            last_ts = datetime.fromisoformat(
                                content.last_timestamp.replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            pass

                    await sync_service.upsert_cursor(
                        user_id=args.user_id,
                        session_id=session_info.session_id,
                        project_path=project_path,
                        last_processed_at_utc=last_ts,
                        entry_count=content.entry_count,
                        file_mtime=file_mtime,
                    )

                    projects_with_new_activity.add(project.id)
                    await session.commit()

                logger.info(
                    "Processed session %s → %s: %s",
                    session_info.session_id,
                    project.name,
                    summary_data["summary"][:100],
                )

            except Exception:
                logger.exception(
                    "Failed to process session %s", session_info.session_id
                )
                await session.rollback()
                continue

        # Regenerate project state for affected projects
        if not args.dry_run and projects_with_new_activity:
            logger.info(
                "Regenerating state for %d projects", len(projects_with_new_activity)
            )
            for project_id in projects_with_new_activity:
                try:
                    await processing_service.regenerate_project_state(
                        user_id=args.user_id,
                        project_id=project_id,
                    )
                    await session.commit()
                except Exception:
                    logger.exception(
                        "Failed to regenerate state for project %d", project_id
                    )
                    await session.rollback()

    logger.info("Claude Code sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create the shell wrapper**

Create `scripts/run_claude_code_sync.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_DIR="/tmp/life_dashboard_claude_code_sync.lock"

cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another claude code sync is already running. Exiting."
    exit 0
fi

cd "$ROOT/backend"
PYTHON_BIN="$(poetry env info --path)/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Python not found at $PYTHON_BIN"
    exit 1
fi

"$PYTHON_BIN" "$ROOT/scripts/sync_claude_code.py" --user-id 1 --time-zone America/New_York "$@"
```

- [ ] **Step 3: Create the launchd plist template**

Create `scripts/com.life_dashboard.claude_code_sync.plist.template`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.life_dashboard.claude_code_sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>__REPO_ROOT__/scripts/run_claude_code_sync.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/life_dashboard_claude_code_sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/life_dashboard_claude_code_sync.err.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

- [ ] **Step 4: Make shell script executable**

```bash
chmod +x scripts/run_claude_code_sync.sh
```

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_claude_code.py scripts/run_claude_code_sync.sh scripts/com.life_dashboard.claude_code_sync.plist.template
git commit -m "feat: add sync script, shell wrapper, and launchd plist for Claude Code history sync"
```

---

### Task 8: Pydantic Schemas and API Endpoints

**Files:**
- Modify: `backend/app/schemas/projects.py`
- Modify: `backend/app/routers/projects.py`

- [ ] **Step 1: Add new schemas**

In `backend/app/schemas/projects.py`, add:

```python
class ProjectActivityResponse(BaseModel):
    id: int
    project_id: int
    project_name: str | None = None
    local_date: date
    session_id: str
    summary: str
    details_json: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectStateSummary(BaseModel):
    status: str
    recent_focus: str
    next_steps: list[str] = []
```

Add `date` to imports from `datetime`.

Update `ProjectResponse` to include:

```python
state_summary_json: dict | None = None
state_updated_at_utc: datetime | None = None
```

- [ ] **Step 2: Add activity endpoints to projects router**

In `backend/app/routers/projects.py`, add two new endpoints:

```python
@router.get("/{project_id}/activities", response_model=list[ProjectActivityResponse])
async def get_project_activities(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    since: date | None = None,
    until: date | None = None,
    page: int = 1,
    per_page: int = 50,
):
    """Get activity feed for a specific project."""
    query = (
        select(ProjectActivity)
        .where(
            ProjectActivity.user_id == current_user.id,
            ProjectActivity.project_id == project_id,
        )
        .order_by(ProjectActivity.local_date.desc(), ProjectActivity.created_at_utc.desc())
    )
    if since:
        query = query.where(ProjectActivity.local_date >= since)
    if until:
        query = query.where(ProjectActivity.local_date <= until)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await session.execute(query)
    activities = result.scalars().all()

    return [
        ProjectActivityResponse(
            id=a.id,
            project_id=a.project_id,
            local_date=a.local_date,
            session_id=a.session_id,
            summary=a.summary,
            details_json=a.details_json,
            created_at=a.created_at_utc,
        )
        for a in activities
    ]


@router.get("/activities/all", response_model=list[ProjectActivityResponse])
async def get_all_activities(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    since: date | None = None,
    until: date | None = None,
    page: int = 1,
    per_page: int = 50,
):
    """Get unified activity feed across all projects."""
    query = (
        select(ProjectActivity, Project.name)
        .join(Project, ProjectActivity.project_id == Project.id)
        .where(ProjectActivity.user_id == current_user.id)
        .order_by(ProjectActivity.local_date.desc(), ProjectActivity.created_at_utc.desc())
    )
    if since:
        query = query.where(ProjectActivity.local_date >= since)
    if until:
        query = query.where(ProjectActivity.local_date <= until)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await session.execute(query)
    rows = result.all()

    return [
        ProjectActivityResponse(
            id=activity.id,
            project_id=activity.project_id,
            project_name=project_name,
            local_date=activity.local_date,
            session_id=activity.session_id,
            summary=activity.summary,
            details_json=activity.details_json,
            created_at=activity.created_at_utc,
        )
        for activity, project_name in rows
    ]
```

Add necessary imports at top of router file:

```python
from app.db.models.claude_code import ProjectActivity
from app.schemas.projects import ProjectActivityResponse
```

- [ ] **Step 3: Update the board endpoint to include state fields**

The `ProjectResponse` schema update (step 1) should automatically include the new fields since it uses `from_attributes = True`. Verify the board endpoint returns them by checking the query includes the project model fields.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/projects.py backend/app/routers/projects.py
git commit -m "feat: add project activity API endpoints and updated schemas"
```

---

### Task 9: Frontend — API Types and Hooks

**Files:**
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/hooks/useProjectActivities.ts`

- [ ] **Step 1: Add API types and functions**

In `frontend/src/services/api.ts`, add types and API functions:

```typescript
export type ProjectActivity = {
  id: number;
  project_id: number;
  project_name?: string;
  local_date: string;
  session_id: string;
  summary: string;
  details_json: {
    files_modified?: string[];
    git_branch?: string;
    git_commits?: string[];
    category?: string;
    key_decisions?: string[];
  } | null;
  created_at: string;
};

export type ProjectStateSummary = {
  status: string;
  recent_focus: string;
  next_steps: string[];
};
```

Update `ProjectItem` to add:

```typescript
state_summary_json: ProjectStateSummary | null;
state_updated_at_utc: string | null;
```

Add API functions:

```typescript
export const fetchProjectActivities = async (
  projectId: number,
  params?: { since?: string; until?: string; page?: number; per_page?: number }
): Promise<ProjectActivity[]> => {
  const { data } = await api.get(`/api/projects/${projectId}/activities`, { params });
  return data as ProjectActivity[];
};

export const fetchAllActivities = async (
  params?: { since?: string; until?: string; page?: number; per_page?: number }
): Promise<ProjectActivity[]> => {
  const { data } = await api.get('/api/projects/activities/all', { params });
  return data as ProjectActivity[];
};
```

- [ ] **Step 2: Create useProjectActivities hook**

Create `frontend/src/hooks/useProjectActivities.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchProjectActivities, fetchAllActivities, type ProjectActivity } from '../services/api';

const STALE_TIME = 5 * 60 * 1000; // 5 minutes

export const projectActivityKeys = {
  all: ['projectActivities'] as const,
  byProject: (projectId: number) => ['projectActivities', projectId] as const,
  allProjects: () => ['projectActivities', 'all'] as const,
};

export function useProjectActivities(projectId: number | null) {
  return useQuery<ProjectActivity[]>({
    queryKey: projectId
      ? projectActivityKeys.byProject(projectId)
      : projectActivityKeys.allProjects(),
    queryFn: () =>
      projectId
        ? fetchProjectActivities(projectId)
        : fetchAllActivities(),
    staleTime: STALE_TIME,
    enabled: true,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/hooks/useProjectActivities.ts
git commit -m "feat: add frontend API types, functions, and hook for project activities"
```

---

### Task 10: Frontend — Projects Page Activity Feed and State Summary

**Files:**
- Modify: `frontend/src/pages/Projects.tsx`

This task modifies the existing 4340-line Projects page. The changes are additive — we add new components for the activity feed and state summary rendered within the existing project view.

- [ ] **Step 1: Read the existing Projects.tsx to understand the project detail rendering area**

Identify where the selected project's content is rendered (likely a content/main panel area). We'll add the state summary and activity feed components here.

- [ ] **Step 2: Add styled components for the activity feed and state summary**

Add within `Projects.tsx` (or a new file if the page is already modularized):

```typescript
// --- Project State Summary ---
const StateSummaryCard = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  border: 1px solid ${({ theme }) => theme.colors.border};
`;

const StateSection = styled.div`
  margin-bottom: 12px;
  &:last-child { margin-bottom: 0; }
`;

const StateSectionLabel = styled.div`
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-bottom: 4px;
`;

const StateFreshness = styled.span<{ $stale: boolean }>`
  font-size: 11px;
  color: ${({ $stale, theme }) => $stale ? theme.colors.textTertiary : theme.colors.textSecondary};
  font-style: ${({ $stale }) => $stale ? 'italic' : 'normal'};
`;

// --- Activity Feed ---
const ActivityFeed = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ActivityDateGroup = styled.div`
  margin-bottom: 16px;
`;

const ActivityDateHeader = styled.div`
  font-size: 13px;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

const ActivityCard = styled.div`
  padding: 12px 16px;
  background: ${({ theme }) => theme.colors.surface};
  border-radius: 8px;
  border: 1px solid ${({ theme }) => theme.colors.border};
`;

const ActivitySummary = styled.div`
  font-size: 14px;
  color: ${({ theme }) => theme.colors.text};
  line-height: 1.5;
`;

const CategoryBadge = styled.span<{ $category: string }>`
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 8px;
  background: ${({ $category, theme }) => {
    const map: Record<string, string> = {
      feature: theme.colors.accent || '#4a9eff',
      bugfix: '#ff6b6b',
      refactor: '#ffd93d',
      debugging: '#ff8c42',
      planning: '#a78bfa',
      research: '#67d5b5',
      config: '#888',
    };
    return map[$category] || '#888';
  }};
  color: white;
`;

const ActivityDetails = styled.div`
  margin-top: 8px;
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textSecondary};
`;
```

- [ ] **Step 3: Create ProjectStateView and ProjectActivityFeed components**

Add inline components (or extract to separate files if preferred):

```typescript
function ProjectStateView({ project }: { project: ProjectItem }) {
  if (!project.state_summary_json) return null;

  const state = project.state_summary_json;
  const updatedAt = project.state_updated_at_utc
    ? new Date(project.state_updated_at_utc)
    : null;
  const isStale = updatedAt
    ? Date.now() - updatedAt.getTime() > 7 * 24 * 60 * 60 * 1000
    : true;

  return (
    <StateSummaryCard>
      <StateSection>
        <StateSectionLabel>Status</StateSectionLabel>
        <div>{state.status}</div>
      </StateSection>
      <StateSection>
        <StateSectionLabel>Recent Focus</StateSectionLabel>
        <div>{state.recent_focus}</div>
      </StateSection>
      {state.next_steps.length > 0 && (
        <StateSection>
          <StateSectionLabel>Next Steps</StateSectionLabel>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {state.next_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </StateSection>
      )}
      {updatedAt && (
        <StateFreshness $stale={isStale}>
          Updated {formatRelativeTime(updatedAt)}
        </StateFreshness>
      )}
    </StateSummaryCard>
  );
}

function ProjectActivityFeed({ projectId }: { projectId: number | null }) {
  const { data: activities, isLoading } = useProjectActivities(projectId);

  if (isLoading) return <div>Loading activity...</div>;
  if (!activities?.length) return <div style={{ color: '#888', padding: '16px' }}>No activity yet</div>;

  // Group by date
  const grouped = activities.reduce<Record<string, ProjectActivity[]>>((acc, a) => {
    (acc[a.local_date] ||= []).push(a);
    return acc;
  }, {});

  return (
    <ActivityFeed>
      {Object.entries(grouped).map(([dateStr, items]) => (
        <ActivityDateGroup key={dateStr}>
          <ActivityDateHeader>{formatDate(dateStr)}</ActivityDateHeader>
          {items.map((activity) => (
            <ActivityCard key={activity.id}>
              <ActivitySummary>
                {activity.details_json?.category && (
                  <CategoryBadge $category={activity.details_json.category}>
                    {activity.details_json.category}
                  </CategoryBadge>
                )}
                {activity.project_name && <strong>{activity.project_name}: </strong>}
                {activity.summary}
              </ActivitySummary>
              {activity.details_json && (
                <ActivityDetails>
                  {activity.details_json.git_branch && (
                    <div>Branch: {activity.details_json.git_branch}</div>
                  )}
                  {activity.details_json.files_modified?.length ? (
                    <div>{activity.details_json.files_modified.length} files modified</div>
                  ) : null}
                </ActivityDetails>
              )}
            </ActivityCard>
          ))}
        </ActivityDateGroup>
      ))}
    </ActivityFeed>
  );
}

function formatRelativeTime(d: Date): string {
  const diff = Date.now() - d.getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return 'Today';
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}
```

- [ ] **Step 4: Integrate components into the project detail view**

Find the project detail rendering section in `Projects.tsx` and add:

```typescript
{/* Inside the selected project's content area */}
<ProjectStateView project={selectedProject} />

<h3>Activity</h3>
<ProjectActivityFeed projectId={selectedProject.id} />

<h3>Todos</h3>
{/* existing todo rendering */}
```

Add import for `useProjectActivities` at top of file.

- [ ] **Step 5: Verify the frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Projects.tsx frontend/src/hooks/useProjectActivities.ts
git commit -m "feat: add project state summary and activity feed to projects page"
```

---

### Task 11: End-to-End Verification

- [ ] **Step 1: Run the migration and verify DB**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 2: Run the sync script in dry-run mode**

```bash
cd backend && python ../scripts/sync_claude_code.py --user-id 1 --time-zone America/New_York --dry-run
```

Expected: Discovers sessions, logs what it would process, no DB writes.

- [ ] **Step 3: Run the sync script for real**

```bash
cd backend && python ../scripts/sync_claude_code.py --user-id 1 --time-zone America/New_York
```

Expected: Processes sessions, creates ProjectActivity records, creates JournalEntry records, regenerates project state.

- [ ] **Step 4: Verify via API**

```bash
curl http://localhost:8000/api/projects/board | python -m json.tool | head -50
curl http://localhost:8000/api/projects/activities/all | python -m json.tool | head -50
```

Expected: Board response includes `state_summary_json`. Activities endpoint returns activity records.

- [ ] **Step 5: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Run linting and type checking**

```bash
cd backend && python -m ruff check . && cd ../frontend && npm run lint && npm run typecheck
```

Expected: Clean.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete Claude Code history integration — sync, processing, API, and frontend"
```
