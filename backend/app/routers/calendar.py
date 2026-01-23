from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from dateutil import parser as date_parser
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.models.calendar import CalendarEvent, GoogleCalendar, TodoEventLink
from app.db.models.entities import User
from app.db.session import get_session
from app.schemas.calendar import (
    CalendarEventUpdateRequest,
    CalendarEventsResponse,
    CalendarListResponse,
    CalendarSelectionRequest,
    CalendarStatusResponse,
    CalendarSummary,
    CalendarEventResponse,
)
from app.services.google_calendar_connection_service import (
    GOOGLE_CALENDAR_SCOPES,
    GoogleCalendarConnectionService,
)
from app.services.google_calendar_event_service import GoogleCalendarEventService
from app.services.google_calendar_sync_service import GoogleCalendarSyncService

router = APIRouter(prefix="/calendar", tags=["calendar"])

CALENDAR_OAUTH_STATE_COOKIE = "ld_calendar_oauth_state"
CALENDAR_OAUTH_REDIRECT_COOKIE = "ld_calendar_oauth_redirect"


def _safe_redirect(target: str | None) -> str:
    """Ensure redirect targets stay within the configured frontend origin."""
    if not target:
        return settings.frontend_url
    if target.startswith(settings.frontend_url):
        return target
    return settings.frontend_url


def _oauth_cookie_settings() -> dict[str, object]:
    """Return secure cookie settings for the OAuth flow."""
    return {
        "max_age": 300,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "domain": settings.session_cookie_domain,
    }


def _google_calendar_auth_url(state: str) -> str:
    """Build the Google OAuth URL for Calendar authorization."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_calendar_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def _exchange_code_for_tokens(code: str) -> dict[str, object]:
    """Exchange an OAuth code for Google Calendar tokens."""
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_calendar_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


@router.get("/google/login")
async def google_calendar_login(redirect: str | None = Query(None)) -> Response:
    """Begin the Google Calendar OAuth flow."""
    state = secrets.token_urlsafe(24)
    redirect_url = _safe_redirect(redirect)
    response = RedirectResponse(url=_google_calendar_auth_url(state))
    response.set_cookie(CALENDAR_OAUTH_STATE_COOKIE, state, **_oauth_cookie_settings())
    response.set_cookie(CALENDAR_OAUTH_REDIRECT_COOKIE, redirect_url, **_oauth_cookie_settings())
    return response


@router.get("/google/callback")
async def google_calendar_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    stored_state: str | None = Cookie(None, alias=CALENDAR_OAUTH_STATE_COOKIE),
    stored_redirect: str | None = Cookie(None, alias=CALENDAR_OAUTH_REDIRECT_COOKIE),
) -> Response:
    """Handle the Google Calendar OAuth callback and start initial sync."""
    redirect_url = _safe_redirect(stored_redirect)
    if error:
        return RedirectResponse(url=f"{redirect_url}?calendar_error={error}")
    if not code or not state or not stored_state or state != stored_state:
        return RedirectResponse(url=f"{redirect_url}?calendar_error=invalid_state")

    try:
        tokens = await _exchange_code_for_tokens(code)
    except Exception:
        return RedirectResponse(url=f"{redirect_url}?calendar_error=token_exchange_failed")

    connection_service = GoogleCalendarConnectionService(session)
    try:
        await connection_service.store_tokens(user_id=current_user.id, tokens=tokens)
    except Exception as exc:
        logger.warning("Failed to store Google Calendar tokens: {}", exc)
        return RedirectResponse(url=f"{redirect_url}?calendar_error=token_storage_failed")

    sync_service = GoogleCalendarSyncService(session)
    try:
        await sync_service.sync_calendars(current_user.id)
        await sync_service.ensure_life_dashboard_calendar(current_user.id)
    except Exception as exc:
        logger.warning("Initial Google Calendar sync failed: {}", exc)

    response = RedirectResponse(url=f"{redirect_url}?calendar_connected=1")
    response.delete_cookie(CALENDAR_OAUTH_STATE_COOKIE, domain=settings.session_cookie_domain)
    response.delete_cookie(CALENDAR_OAUTH_REDIRECT_COOKIE, domain=settings.session_cookie_domain)
    return response


@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarStatusResponse:
    """Return the user's Google Calendar connection status."""
    service = GoogleCalendarConnectionService(session)
    connection = await service.get_connection(current_user.id)
    if not connection:
        return CalendarStatusResponse(
            connected=False,
            account_email=None,
            connected_at=None,
            last_sync_at=None,
            requires_reauth=False,
        )
    return CalendarStatusResponse(
        connected=True,
        account_email=connection.account_email,
        connected_at=connection.connected_at,
        last_sync_at=connection.last_sync_at,
        requires_reauth=connection.requires_reauth,
    )


@router.get("/calendars", response_model=CalendarListResponse)
async def list_calendars(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarListResponse:
    """List Google calendars stored for the user."""
    stmt = (
        select(GoogleCalendar)
        .where(GoogleCalendar.user_id == current_user.id)
        .order_by(GoogleCalendar.primary.desc(), GoogleCalendar.summary.asc())
    )
    result = await session.execute(stmt)
    calendars = [
        CalendarSummary(
            google_id=cal.google_id,
            summary=cal.summary,
            selected=cal.selected,
            primary=cal.primary,
            is_life_dashboard=cal.is_life_dashboard,
            color_id=cal.color_id,
            time_zone=cal.time_zone,
        )
        for cal in result.scalars().all()
    ]
    return CalendarListResponse(calendars=calendars)


@router.post("/calendars/selection", response_model=CalendarListResponse)
async def update_calendar_selection(
    payload: CalendarSelectionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarListResponse:
    """Persist which calendars are selected for sync."""
    selected = {google_id for google_id in payload.google_ids}
    stmt = select(GoogleCalendar).where(GoogleCalendar.user_id == current_user.id)
    result = await session.execute(stmt)
    calendars = list(result.scalars().all())
    for calendar in calendars:
        calendar.selected = calendar.google_id in selected or calendar.is_life_dashboard
    await session.commit()
    return CalendarListResponse(
        calendars=[
            CalendarSummary(
                google_id=cal.google_id,
                summary=cal.summary,
                selected=cal.selected,
                primary=cal.primary,
                is_life_dashboard=cal.is_life_dashboard,
                color_id=cal.color_id,
                time_zone=cal.time_zone,
            )
            for cal in calendars
        ]
    )


@router.post("/sync", status_code=202)
async def sync_calendar(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Trigger a manual sync for selected calendars."""
    sync_service = GoogleCalendarSyncService(session)
    await sync_service.sync_calendars(current_user.id)
    await sync_service.ensure_life_dashboard_calendar(current_user.id)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    window_end = now + timedelta(days=30)
    await sync_service.sync_selected_events(
        current_user.id,
        window_start=window_start,
        window_end=window_end,
        force_full=False,
    )
    return Response(status_code=202)


@router.get("/events", response_model=CalendarEventsResponse)
async def list_events(
    start: str = Query(...),
    end: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarEventsResponse:
    """Return deduplicated calendar events for the requested window."""
    try:
        start_dt = date_parser.isoparse(start)
        end_dt = date_parser.isoparse(end)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid start/end format.") from exc

    stmt = (
        select(CalendarEvent, GoogleCalendar)
        .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
        .outerjoin(
            TodoEventLink,
            (TodoEventLink.calendar_id == CalendarEvent.calendar_id)
            & (TodoEventLink.google_event_id == CalendarEvent.google_event_id),
        )
        .where(
            CalendarEvent.user_id == current_user.id,
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_time.is_not(None),
            CalendarEvent.end_time.is_not(None),
            CalendarEvent.start_time <= end_dt,
            CalendarEvent.end_time >= start_dt,
            GoogleCalendar.selected.is_(True),
            TodoEventLink.id.is_(None),
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    events = []
    for event, calendar in rows:
        if _is_declined_attendee(event.attendees):
            continue
        events.append(
            CalendarEventResponse(
                id=event.id,
                calendar_google_id=calendar.google_id,
                calendar_summary=calendar.summary,
                calendar_primary=calendar.primary,
                calendar_is_life_dashboard=calendar.is_life_dashboard,
                google_event_id=event.google_event_id,
                recurring_event_id=event.recurring_event_id,
                ical_uid=event.ical_uid,
                summary=event.summary,
                description=event.description,
                location=event.location,
                start_time=event.start_time,
                end_time=event.end_time,
                is_all_day=event.is_all_day,
                status=event.status,
                visibility=event.visibility,
                transparency=event.transparency,
                hangout_link=event.hangout_link,
                conference_link=event.conference_link,
                organizer=event.organizer,
                attendees=event.attendees,
            )
        )

    deduped = _dedupe_events(events)
    return CalendarEventsResponse(events=deduped)


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: int,
    payload: CalendarEventUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarEventResponse:
    """Update a Google Calendar event and refresh the cache."""
    stmt = (
        select(CalendarEvent, GoogleCalendar)
        .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
        .where(CalendarEvent.id == event_id, CalendarEvent.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found.")
    event, calendar = row
    service = GoogleCalendarEventService(session)
    await service.update_event(
        event,
        calendar,
        summary=payload.summary,
        start_time=payload.start_time,
        end_time=payload.end_time,
        scope=payload.scope,
        time_zone=calendar.time_zone,
        is_all_day=payload.is_all_day,
    )
    await session.refresh(event)
    return CalendarEventResponse(
        id=event.id,
        calendar_google_id=calendar.google_id,
        calendar_summary=calendar.summary,
        calendar_primary=calendar.primary,
        calendar_is_life_dashboard=calendar.is_life_dashboard,
        google_event_id=event.google_event_id,
        recurring_event_id=event.recurring_event_id,
        ical_uid=event.ical_uid,
        summary=event.summary,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        is_all_day=event.is_all_day,
        status=event.status,
        visibility=event.visibility,
        transparency=event.transparency,
        hangout_link=event.hangout_link,
        conference_link=event.conference_link,
        organizer=event.organizer,
        attendees=event.attendees,
    )


@router.post("/google/webhook")
async def google_calendar_webhook(
    response: Response,
    session: AsyncSession = Depends(get_session),
    resource_state: str | None = Header(None, alias="X-Goog-Resource-State"),
    channel_id: str | None = Header(None, alias="X-Goog-Channel-Id"),
) -> Response:
    """Receive Google Calendar webhook notifications and resync."""
    if resource_state == "sync":
        response.status_code = status.HTTP_200_OK
        return response
    if not channel_id:
        response.status_code = status.HTTP_200_OK
        return response
    stmt = select(GoogleCalendar).where(GoogleCalendar.channel_id == channel_id)
    result = await session.execute(stmt)
    calendar = result.scalar_one_or_none()
    if not calendar:
        response.status_code = status.HTTP_200_OK
        return response
    sync_service = GoogleCalendarSyncService(session)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    window_end = now + timedelta(days=30)
    await sync_service.sync_events_for_calendar(
        calendar.user_id,
        calendar,
        window_start=window_start,
        window_end=window_end,
        force_full=False,
    )
    response.status_code = status.HTTP_200_OK
    return response


def _dedupe_events(events: list[CalendarEventResponse]) -> list[CalendarEventResponse]:
    """Collapse duplicate events using iCalUID and start time priority rules."""
    by_key: dict[tuple[str, str], CalendarEventResponse] = {}
    for event in events:
        key_source = event.ical_uid or event.google_event_id
        start_key = event.start_time.isoformat() if event.start_time else ""
        key = (key_source, start_key)
        candidate = by_key.get(key)
        if candidate is None:
            by_key[key] = event
            continue
        if _priority(event) < _priority(candidate):
            by_key[key] = event
    return sorted(
        by_key.values(),
        key=lambda item: item.start_time or datetime.min.replace(tzinfo=timezone.utc),
    )


def _priority(event: CalendarEventResponse) -> int:
    """Return sorting priority for duplicate events."""
    if event.calendar_is_life_dashboard:
        return 0
    if event.calendar_primary or (event.organizer or {}).get("self"):
        return 1
    return 2


def _is_declined_attendee(attendees: list[dict[str, object]] | None) -> bool:
    if not attendees:
        return False
    for attendee in attendees:
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False
