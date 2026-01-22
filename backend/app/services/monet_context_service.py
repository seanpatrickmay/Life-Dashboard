from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyMetric
from app.db.models.calendar import CalendarEvent, GoogleCalendar
from app.db.models.todo import TodoItem
from app.db.repositories.metrics_repository import MetricsRepository
from app.db.repositories.todo_repository import TodoRepository
from app.services.nutrition_intake_service import NutritionIntakeService
from app.services.user_profile_service import UserProfileService
from app.utils.timezone import eastern_today, local_now


class MonetContextBuilder:
    """Aggregates per-user data so the Monet assistant can reason over it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.metrics_repo = MetricsRepository(session)
        self.todo_repo = TodoRepository(session)
        self.nutrition_service = NutritionIntakeService(session)
        self.profile_service = UserProfileService(session)

    async def build_context(
        self, user_id: int, window_days: int = 7, time_zone: str | None = None
    ) -> dict[str, Any]:
        today = eastern_today()
        if window_days < 1:
            window_days = 1
        start_date = today - timedelta(days=window_days - 1)
        local_time = _compute_local_time(time_zone)

        metrics = await self.metrics_repo.list_metrics_since(user_id, start_date)
        metrics_payload = [self._serialize_metric(metric) for metric in metrics]
        latest_metric = metrics_payload[-1] if metrics_payload else None

        nutrition_today = await self.nutrition_service.daily_summary(user_id, today)
        nutrition_history = await self.nutrition_service.rolling_average(user_id, window_days)

        profile_payload = await self.profile_service.fetch_profile_payload(user_id)

        todos = await self.todo_repo.list_for_user(user_id)
        todo_payload = [self._serialize_todo(todo) for todo in todos]
        calendar_payload = await self._serialize_calendar_events(user_id, window_days, time_zone)

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
        if metric.vertex_insight:
            payload["vertex_insight"] = {
                "model_name": metric.vertex_insight.model_name,
                "metric_date": metric.vertex_insight.metric_date.isoformat(),
                "response_text": metric.vertex_insight.response_text,
                "tokens_used": metric.vertex_insight.tokens_used,
                "readiness_score": metric.vertex_insight.readiness_score,
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
                CalendarEvent.status != "cancelled",
                CalendarEvent.start_time.is_not(None),
                CalendarEvent.end_time.is_not(None),
                CalendarEvent.start_time <= end_utc,
                CalendarEvent.end_time >= start_utc,
                GoogleCalendar.selected.is_(True),
            )
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
                    "calendar": {
                        "id": calendar.google_id,
                        "summary": calendar.summary,
                        "primary": calendar.primary,
                        "is_life_dashboard": calendar.is_life_dashboard,
                    },
                    "google_event_id": event.google_event_id,
                    "recurring_event_id": event.recurring_event_id,
                    "ical_uid": event.ical_uid,
                    "summary": event.summary,
                    "description": _cap_words(event.description, 100),
                    "location": event.location,
                    "start_time": event.start_time.isoformat() if event.start_time else None,
                    "end_time": event.end_time.isoformat() if event.end_time else None,
                    "is_all_day": event.is_all_day,
                    "status": event.status,
                    "visibility": event.visibility,
                    "transparency": event.transparency,
                    "hangout_link": event.hangout_link,
                    "conference_link": event.conference_link,
                    "organizer": event.organizer,
                    "attendees": event.attendees,
                }
            )
        return _dedupe_events(events)

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
