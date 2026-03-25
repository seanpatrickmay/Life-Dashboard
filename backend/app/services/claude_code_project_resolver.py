"""Resolves Claude Code project paths to Life Dashboard Project records."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)

GENERAL_PROJECT_NAME = "General"

_PROJECT_MARKERS = {".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile"}

# Paths that are parent directories, not real projects
_SKIP_NAMES = {"current projects", "desktop", "archived", "documents", "downloads"}

# Manual aliases for directory names that don't fuzzy-match their merged project.
# Key: normalized directory name → Value: exact project name in the DB.
_ALIASES: dict[str, str] = {
    _normalize("next-chief-of-staff"): "AI Chief of Staff",
    _normalize("seanpatrickmay.github.io"): "Personal Website",
}


def _normalize(name: str) -> str:
    """Normalize a name for fuzzy comparison: lowercase, strip non-alnum."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


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

    candidate = parts[-1]

    # Skip known parent-directory names
    if candidate.lower() in _SKIP_NAMES:
        return GENERAL_PROJECT_NAME

    # Check if path has project markers on disk
    if p.exists() and not any((p / m).exists() for m in _PROJECT_MARKERS):
        if len(parts) < 4:
            return GENERAL_PROJECT_NAME

    return candidate


def encode_project_path(project_path: str) -> str:
    """Encode a project path the same way Claude Code does."""
    return project_path.replace("/", "-").replace(" ", "-").replace(".", "-")


class ClaudeCodeProjectResolver:
    """Maps Claude Code project paths to Life Dashboard Project records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._project_repo = ProjectRepository(session)
        self._cache: dict[str, Project] = {}
        self._all_projects: list[Project] | None = None

    async def _get_all_projects(self, user_id: int) -> list[Project]:
        if self._all_projects is None:
            self._all_projects = await self._project_repo.list_for_user(user_id)
        return self._all_projects

    async def _fuzzy_match(self, user_id: int, name: str) -> Project | None:
        """Find a project by normalized name (ignoring hyphens, spaces, case).

        Tries exact normalized match first, then checks if the directory name
        is a prefix of an existing project name (e.g., 'wildfire-prediction'
        matches 'Wildfire Prediction Capstone').
        """
        norm = _normalize(name)
        projects = await self._get_all_projects(user_id)

        # Exact normalized match
        for p in projects:
            if _normalize(p.name) == norm:
                return p

        # Prefix/contains match — directory name contained in existing project name
        # Only match if the normalized name is at least 6 chars (avoid false positives)
        if len(norm) >= 6:
            for p in projects:
                p_norm = _normalize(p.name)
                if p_norm.startswith(norm) or norm.startswith(p_norm):
                    logger.info("Prefix matched '%s' → '%s'", name, p.name)
                    return p

        return None

    async def resolve(self, *, user_id: int, project_path: str | None) -> Project:
        """Resolve a project path to a Project record, creating if needed."""
        name = extract_project_name(project_path)

        if name in self._cache:
            return self._cache[name]

        # Check static aliases first
        alias_target = _ALIASES.get(_normalize(name))
        if alias_target:
            aliased = await self._project_repo.get_by_name_for_user(user_id, alias_target)
            if aliased:
                logger.info("Alias matched '%s' → '%s'", name, alias_target)
                self._cache[name] = aliased
                return aliased

        # Try exact match first
        existing = await self._project_repo.get_by_name_for_user(user_id, name)
        if existing:
            self._cache[name] = existing
            return existing

        # Try fuzzy match (Life-Dashboard → Life Dashboard, etc.)
        fuzzy = await self._fuzzy_match(user_id, name)
        if fuzzy:
            logger.info("Fuzzy matched '%s' → existing project '%s'", name, fuzzy.name)
            self._cache[name] = fuzzy
            return fuzzy

        logger.info("Auto-creating project '%s' from path: %s", name, project_path)
        new_project = await self._project_repo.create_one(
            user_id=user_id,
            name=name,
            notes=f"Auto-created from Claude Code. Source: {project_path}",
        )
        await self._session.flush()
        self._all_projects = None  # Invalidate cache
        self._cache[name] = new_project
        return new_project
