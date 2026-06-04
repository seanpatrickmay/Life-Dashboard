"""Job handlers for fire-and-forget async work.

Each handler is decorated with ``@job("<name>")`` so it is registered in the
global handler registry.  Handlers receive a **JSON-serializable payload dict**
(ids / primitives only — never ORM objects or sessions) and open their own
``AsyncSessionLocal`` session to perform the work.

Import order note: to avoid circular imports the heavy service modules are
imported lazily inside each handler function (same pattern as
``app.workers.tasks``).
"""
from __future__ import annotations

from datetime import date

from loguru import logger

from app.db.session import AsyncSessionLocal
from app.jobs.registry import job


@job("project_suggestions")
async def _handle_project_suggestions(payload: dict) -> None:
    """Run project-suggestion inference for a list of todo IDs.

    Payload: ``{"user_id": int, "todo_ids": [int, ...]}``
    """
    user_id: int = payload["user_id"]
    todo_ids: list[int] = payload["todo_ids"]
    if not todo_ids:
        return
    try:
        from app.services.todo_project_suggestion_service import TodoProjectSuggestionService  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            service = TodoProjectSuggestionService(session)
            await service.process_todo_ids(user_id=user_id, todo_ids=todo_ids)
    except Exception as exc:  # noqa: BLE001
        logger.warning("project_suggestions job failed for user_id={}: {}", user_id, exc)


@job("todo_accomplishment")
async def _handle_todo_accomplishment(payload: dict) -> None:
    """Generate accomplishment text for a completed todo.

    Payload: ``{"todo_id": int, "user_id": int, "todo_text": str}``
    """
    todo_id: int = payload["todo_id"]
    user_id: int = payload["user_id"]
    todo_text: str = payload["todo_text"]
    if len(todo_text) > 10_000:
        todo_text = todo_text[:10_000]
    try:
        from app.services.async_ai_service import AsyncAIService  # noqa: PLC0415

        await AsyncAIService.generate_accomplishment_async(todo_id, user_id, todo_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("todo_accomplishment job failed for todo_id={}: {}", todo_id, exc)


@job("journal_summary")
async def _handle_journal_summary(payload: dict) -> None:
    """Compile a journal day summary for a past date.

    Payload: ``{"user_id": int, "date": "YYYY-MM-DD", "time_zone": str}``
    """
    user_id: int = payload["user_id"]
    local_date: date = date.fromisoformat(payload["date"])
    time_zone: str = payload["time_zone"]
    try:
        from app.services.journal_service import JournalService  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            service = JournalService(session)
            await service._ensure_summary(user_id=user_id, local_date=local_date, time_zone=time_zone)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("journal_summary job failed for user_id={} date={}: {}", user_id, local_date, exc)


@job("insight_refresh")
async def _handle_insight_refresh(payload: dict) -> None:
    """Refresh the daily readiness insight for a user.

    Payload: ``{"user_id": int}``
    """
    user_id: int = payload["user_id"]
    try:
        from app.services.insight_service import InsightService  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            service = InsightService(session)
            await service.refresh_daily_insight(user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("insight_refresh job failed for user_id={}: {}", user_id, exc)
