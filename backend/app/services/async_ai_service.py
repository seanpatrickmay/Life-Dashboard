"""Async AI service for non-blocking AI operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional
from loguru import logger

from app.db.session import AsyncSessionLocal
from app.db.repositories.todo_repository import TodoRepository
from app.services.todo_accomplishment_agent import TodoAccomplishmentAgent


class AsyncAIService:
    """Handles AI operations asynchronously without blocking the main request."""

    # Simple in-memory cache for accomplishment text
    _accomplishment_cache: Dict[str, str] = {}
    CACHE_MAX_SIZE = 100

    @classmethod
    def get_cached_accomplishment(cls, todo_text: str) -> Optional[str]:
        """Get cached accomplishment text if available."""
        return cls._accomplishment_cache.get(todo_text.lower().strip())

    @classmethod
    def cache_accomplishment(cls, todo_text: str, accomplishment: str) -> None:
        """Cache accomplishment text."""
        # Simple LRU-like behavior - remove oldest if cache is full
        if len(cls._accomplishment_cache) >= cls.CACHE_MAX_SIZE:
            # Remove first item (oldest)
            first_key = next(iter(cls._accomplishment_cache))
            del cls._accomplishment_cache[first_key]

        cls._accomplishment_cache[todo_text.lower().strip()] = accomplishment

    @classmethod
    async def generate_accomplishment_async(cls, todo_id: int, user_id: int, todo_text: str) -> None:
        """Generate accomplishment text asynchronously in the background."""
        try:
            # Check cache first
            cached = cls.get_cached_accomplishment(todo_text)

            async with AsyncSessionLocal() as session:
                repo = TodoRepository(session)
                todo = await repo.get_for_user(user_id, todo_id)

                if not todo or not todo.completed:
                    return

                if cached:
                    # Use cached version
                    todo.accomplishment_text = cached
                    todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)
                    logger.debug(f"[async_ai] Used cached accomplishment for todo {todo_id}")
                else:
                    # Generate new accomplishment
                    agent = TodoAccomplishmentAgent()
                    accomplishment = await agent.rewrite(todo_text)

                    # Cache it
                    cls.cache_accomplishment(todo_text, accomplishment)

                    # Update the todo
                    todo.accomplishment_text = accomplishment
                    todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)
                    logger.debug(f"[async_ai] Generated new accomplishment for todo {todo_id}")

                await session.commit()

        except Exception as exc:
            logger.error(f"[async_ai] Failed to generate accomplishment for todo {todo_id}: {exc}")

    @classmethod
    async def schedule_accomplishment_generation(cls, todo_id: int, user_id: int, todo_text: str) -> None:
        """Schedule accomplishment generation via job queue.

        The call site in todos.py already uses ``get_job_queue().enqueue(...)``
        directly, so this method is kept only for backward-compat with any
        direct callers.  It delegates to the job queue so that inline tests
        exercise the same code path and SQS routing works in Phase 2.
        """
        from app.jobs.queue import get_job_queue  # noqa: PLC0415

        await get_job_queue().enqueue(
            "todo_accomplishment",
            {"todo_id": todo_id, "user_id": user_id, "todo_text": todo_text},
        )
        logger.debug(f"[async_ai] Enqueued todo_accomplishment for todo {todo_id}")