from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyMetric
from app.db.models.calendar import CalendarEvent, GoogleCalendar
from app.db.models.todo import TodoItem
from app.db.models.workspace import WorkspacePage
from app.schemas.assistant import AssistantPageContext
from app.db.repositories.metrics_repository import MetricsRepository
from app.db.repositories.todo_repository import TodoRepository
from app.services.nutrition_intake_service import NutritionIntakeService
from app.services.user_profile_service import UserProfileService
from app.services.workspace_service import WorkspaceService
from app.utils.timezone import eastern_today, local_now


class MonetContextBuilder:
    """Aggregates per-user data so the Monet assistant can reason over it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.metrics_repo = MetricsRepository(session)
        self.todo_repo = TodoRepository(session)
        self.nutrition_service = NutritionIntakeService(session)
        self.profile_service = UserProfileService(session)
        self.workspace_service = WorkspaceService(session)

    async def build_context(
        self,
        user_id: int,
        window_days: int = 7,
        time_zone: str | None = None,
        page_context: AssistantPageContext | None = None,
    ) -> dict[str, Any]:
        today = eastern_today()
        if window_days < 1:
            window_days = 1
        start_date = today - timedelta(days=window_days - 1)
        local_time = _compute_local_time(time_zone)

        # Gather data sources concurrently with individual error isolation
        async def _safe_metrics() -> tuple[list[dict], dict | None]:
            try:
                metrics = await self.metrics_repo.list_metrics_since(user_id, start_date)
                payload = [self._serialize_metric(m) for m in metrics]
                return payload, (payload[-1] if payload else None)
            except Exception as exc:
                logger.warning("[context] metrics failed: {}", exc)
                return [], None

        async def _safe_nutrition() -> tuple[dict, dict]:
            try:
                t = await self.nutrition_service.daily_summary(user_id, today)
                h = await self.nutrition_service.rolling_average(user_id, window_days)
                return t, h
            except Exception as exc:
                logger.warning("[context] nutrition failed: {}", exc)
                return {}, {}

        async def _safe_profile() -> dict:
            try:
                return await self.profile_service.fetch_profile_payload(user_id)
            except Exception as exc:
                logger.warning("[context] profile failed: {}", exc)
                return {}

        async def _safe_todos() -> list[dict]:
            try:
                todos = await self.todo_repo.list_for_user(user_id)
                return [self._serialize_todo(todo) for todo in todos]
            except Exception as exc:
                logger.warning("[context] todos failed: {}", exc)
                return []

        async def _safe_calendar() -> list[dict]:
            try:
                return await self._serialize_calendar_events(user_id, window_days, time_zone)
            except Exception as exc:
                logger.warning("[context] calendar failed: {}", exc)
                return []

        async def _safe_workspace() -> dict:
            try:
                return await self._serialize_workspace_knowledge(user_id, page_context)
            except Exception as exc:
                logger.warning("[context] workspace failed: {}", exc)
                return {}

        (
            (metrics_payload, latest_metric),
            (nutrition_today, nutrition_history),
            profile_payload,
            todo_payload,
            calendar_payload,
            workspace_payload,
        ) = await asyncio.gather(
            _safe_metrics(),
            _safe_nutrition(),
            _safe_profile(),
            _safe_todos(),
            _safe_calendar(),
            _safe_workspace(),
        )

        return {
            "window_days": window_days,
            "generated_at": today.isoformat(),
            "time_zone": {
                "name": local_time["name"],
                "now_local": local_time["now_local"],
                "offset_minutes": local_time["offset_minutes"],
            },
            "metrics": {
                "start_date": start_date.isoformat(),
                "daily": metrics_payload,
                "latest": latest_metric,
            },
            "nutrition": {
                "today_summary": self._convert_dates(nutrition_today),
                "history_window": self._convert_dates(nutrition_history),
            },
            "profile": self._convert_dates(profile_payload),
            "todos": todo_payload,
            "calendar_events": calendar_payload,
            "workspace": workspace_payload,
        }

    def _serialize_metric(self, metric: DailyMetric) -> dict[str, Any]:
        payload = {
            "metric_date": metric.metric_date.isoformat(),
            "hrv_avg_ms": metric.hrv_avg_ms,
            "rhr_bpm": metric.rhr_bpm,
            "sleep_seconds": metric.sleep_seconds,
            "training_volume_seconds": metric.training_volume_seconds,
            "training_load": metric.training_load,
            "readiness_score": metric.readiness_score,
            "readiness_label": metric.readiness_label,
            "readiness_narrative": metric.readiness_narrative,
            "insight": {
                "greeting": metric.insight_greeting,
                "hrv_value": metric.insight_hrv_value,
                "hrv_note": metric.insight_hrv_note,
                "hrv_score": metric.insight_hrv_score,
                "rhr_value": metric.insight_rhr_value,
                "rhr_note": metric.insight_rhr_note,
                "rhr_score": metric.insight_rhr_score,
                "sleep_value_hours": metric.insight_sleep_value_hours,
                "sleep_note": metric.insight_sleep_note,
                "sleep_score": metric.insight_sleep_score,
                "training_load_value": metric.insight_training_load_value,
                "training_load_note": metric.insight_training_load_note,
                "training_load_score": metric.insight_training_load_score,
                "morning_note": metric.insight_morning_note,
            },
        }
        if metric.readiness_insight:
            payload["readiness_insight"] = {
                "model_name": metric.readiness_insight.model_name,
                "metric_date": metric.readiness_insight.metric_date.isoformat(),
                "response_text": metric.readiness_insight.response_text,
                "tokens_used": metric.readiness_insight.tokens_used,
                "readiness_score": metric.readiness_insight.readiness_score,
            }
        return payload

    def _serialize_todo(self, todo: TodoItem) -> dict[str, Any]:
        deadline = todo.deadline_utc.isoformat() if todo.deadline_utc else None
        is_overdue = bool(
            not todo.completed
            and todo.deadline_utc is not None
            and todo.deadline_utc < datetime.now(timezone.utc)
        )
        return {
            "id": todo.id,
            "text": todo.text,
            "completed": todo.completed,
            "deadline_utc": deadline,
            "deadline_is_date_only": todo.deadline_is_date_only,
            "is_overdue": is_overdue,
            "created_at": todo.created_at.isoformat() if todo.created_at else None,
            "updated_at": todo.updated_at.isoformat() if todo.updated_at else None,
        }

    async def _serialize_calendar_events(
        self, user_id: int, window_days: int, time_zone: str | None
    ) -> list[dict[str, Any]]:
        now_local = local_now(time_zone)
        window_end = now_local + timedelta(days=window_days)
        start_utc = now_local.astimezone(timezone.utc)
        end_utc = window_end.astimezone(timezone.utc)
        stmt = (
            select(CalendarEvent, GoogleCalendar)
            .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
            .where(
                CalendarEvent.user_id == user_id,
                or_(CalendarEvent.status.is_(None), CalendarEvent.status != "cancelled"),
                CalendarEvent.start_time.is_not(None),
                CalendarEvent.end_time.is_not(None),
                CalendarEvent.start_time <= end_utc,
                CalendarEvent.end_time >= start_utc,
                GoogleCalendar.selected.is_(True),
            )
            .order_by(CalendarEvent.start_time.asc())
            .limit(50)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        events = []
        for event, calendar in rows:
            if _is_declined_attendee(event.attendees):
                continue
            events.append(
                {
                    "id": event.id,
                    "calendar_name": calendar.summary,
                    "summary": event.summary,
                    "description": _cap_words(event.description, 30),
                    "location": event.location,
                    "start_time": event.start_time.isoformat() if event.start_time else None,
                    "end_time": event.end_time.isoformat() if event.end_time else None,
                    "is_all_day": event.is_all_day,
                    "attendee_count": len(event.attendees) if event.attendees else 0,
                }
            )
        return _dedupe_events(events)

    async def _serialize_workspace_knowledge(
        self,
        user_id: int,
        page_context: AssistantPageContext | None,
    ) -> dict[str, Any]:
        await self.workspace_service.ensure_workspace(user_id)
        recent_pages = await self._list_recent_workspace_pages(user_id, limit=6)
        payload: dict[str, Any] = {
            "recent_pages": recent_pages,
        }

        selected_entity = page_context.selected_entity if page_context else None
        selected_project_id = selected_entity.project_id if selected_entity else None
        if selected_project_id:
            project_payload = await self._serialize_selected_project(user_id, selected_project_id)
            if project_payload is not None:
                payload["selected_project"] = project_payload

        selected_note_id = selected_entity.note_id if selected_entity else None
        if selected_note_id:
            note_payload = await self._serialize_selected_note(user_id, selected_note_id)
            if note_payload is not None:
                payload["selected_note"] = note_payload

        return payload

    async def _list_recent_workspace_pages(self, user_id: int, *, limit: int) -> list[dict[str, Any]]:
        stmt = (
            select(WorkspacePage)
            .where(
                WorkspacePage.user_id == user_id,
                WorkspacePage.trashed_at.is_(None),
                WorkspacePage.kind.in_(("page", "note", "database_row")),
            )
            .order_by(WorkspacePage.updated_at.desc(), WorkspacePage.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        pages = list(result.scalars().all())
        # NOTE: N+1 query – get_page_text_body is called per page.
        # WorkspaceService has no batch alternative yet; capped by limit param.
        serialized: list[dict[str, Any]] = []
        for page in pages[:limit]:
            body = await self.workspace_service.get_page_text_body(user_id, page.id)
            serialized.append(self._serialize_workspace_page(page, body, max_chars=320))
        return serialized

    async def _serialize_selected_project(
        self,
        user_id: int,
        project_id: int,
    ) -> dict[str, Any] | None:
        project_page = await self.workspace_service.find_project_page(user_id, project_id)
        if project_page is None:
            return None
        subtree = await self.workspace_service.list_page_subtree(
            user_id,
            project_page.id,
            include_root=True,
        )
        ordered_pages = [project_page] + sorted(
            [page for page in subtree if page.id != project_page.id and page.kind in {"page", "note"}],
            key=lambda page: (page.updated_at or datetime.min.replace(tzinfo=timezone.utc), page.id),
            reverse=True,
        )
        serialized_pages: list[dict[str, Any]] = []
        for page in ordered_pages[:8]:
            body = await self.workspace_service.get_page_text_body(user_id, page.id)
            serialized_pages.append(self._serialize_workspace_page(page, body, max_chars=700))
        return {
            "project_id": project_id,
            "project_page_id": project_page.id,
            "project_name": project_page.title,
            "pages": serialized_pages,
        }

    async def _serialize_selected_note(self, user_id: int, note_id: int) -> dict[str, Any] | None:
        stmt = select(WorkspacePage).where(
            WorkspacePage.user_id == user_id,
            WorkspacePage.legacy_note_id == note_id,
            WorkspacePage.trashed_at.is_(None),
        )
        result = await self.session.execute(stmt)
        page = result.scalar_one_or_none()
        if page is None:
            return None
        body = await self.workspace_service.get_page_text_body(user_id, page.id)
        return self._serialize_workspace_page(page, body, max_chars=900)

    def _serialize_workspace_page(
        self,
        page: WorkspacePage,
        body: str,
        *,
        max_chars: int,
    ) -> dict[str, Any]:
        return {
            "page_id": page.id,
            "title": page.title,
            "kind": page.kind,
            "description": _cap_words(page.description, 50),
            "body_excerpt": _truncate_text(body, max_chars=max_chars),
            "legacy_project_id": page.legacy_project_id,
            "legacy_note_id": page.legacy_note_id,
            "updated_at": page.updated_at.isoformat() if page.updated_at else None,
        }

    def _convert_dates(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._convert_dates(item) for item in value]
        if isinstance(value, dict):
            return {key: self._convert_dates(val) for key, val in value.items()}
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "isoformat") and not isinstance(value, str):
            try:
                return value.isoformat()
            except Exception:  # pragma: no cover - defensive
                return value
        return value


def _compute_local_time(time_zone: str | None) -> dict[str, Any]:
    tz_name = (time_zone or "UTC").strip() or "UTC"
    try:
        zone = ZoneInfo(tz_name)
    except Exception:  # pragma: no cover - fallback
        zone = timezone.utc
        tz_name = "UTC"
    now_local = datetime.now(zone)
    offset = now_local.utcoffset()
    offset_minutes = int(offset.total_seconds() / 60) if offset else 0
    return {
        "name": tz_name,
        "now_local": now_local.isoformat(),
        "offset_minutes": offset_minutes,
    }


def _cap_words(text: str | None, max_words: int) -> str | None:
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _truncate_text(text: str | None, *, max_chars: int) -> str | None:
    if not text:
        return text
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        key_source = event.get("ical_uid") or event.get("google_event_id") or str(event.get("id"))
        start_key = event.get("start_time") or ""
        key = (key_source, start_key)
        candidate = by_key.get(key)
        if candidate is None or _event_priority(event) < _event_priority(candidate):
            by_key[key] = event
    return list(by_key.values())


def _event_priority(event: dict[str, Any]) -> int:
    calendar = event.get("calendar") or {}
    if calendar.get("is_life_dashboard"):
        return 0
    if calendar.get("primary") or (event.get("organizer") or {}).get("self"):
        return 1
    return 2


def _is_declined_attendee(attendees: list[dict[str, Any]] | None) -> bool:
    if not attendees:
        return False
    for attendee in attendees:
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False
