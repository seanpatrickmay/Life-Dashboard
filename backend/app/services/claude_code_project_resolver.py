"""Resolves Claude Code project paths to Life Dashboard Project records."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)

GENERAL_PROJECT_NAME = "General"

_PROJECT_MARKERS = {".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile"}


def extract_project_name(project_path: str | None) -> str:
    """Extract a project name from a filesystem path.

    Returns the last path segment for paths that look like real project
    directories. Returns 'General' for missing, shallow, or non-project paths.
    """
    if not project_path:
        return GENERAL_PROJECT_NAME

    p = Path(project_path)
    parts = [part for part in p.parts if part != "/"]

    if len(parts) < 3:
        return GENERAL_PROJECT_NAME

    # Check if path has project markers on disk
    if p.exists() and not any((p / m).exists() for m in _PROJECT_MARKERS):
        # No project markers — treat as non-project unless it's deep enough
        # to be a real project (some projects just don't have markers)
        if len(parts) < 4:
            return GENERAL_PROJECT_NAME

    return parts[-1]


def encode_project_path(project_path: str) -> str:
    """Encode a project path the same way Claude Code does.

    Replaces /, spaces, and dots with hyphens.
    """
    return project_path.replace("/", "-").replace(" ", "-").replace(".", "-")


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
