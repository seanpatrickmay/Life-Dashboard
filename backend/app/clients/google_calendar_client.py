"""Google Calendar API client wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


GOOGLE_CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"


@dataclass
class GoogleCalendarError(Exception):
    """Raised when Google Calendar API calls fail."""

    status_code: int
    message: str
    payload: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"GoogleCalendarError(status={self.status_code}, message={self.message})"


class GoogleCalendarClient:
    """Lightweight async client for Google Calendar API calls."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    async def list_calendars(self) -> list[dict[str, Any]]:
        """Return the authenticated user's calendar list."""
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            payload = await self._request(
                "GET",
                "/users/me/calendarList",
                params={"pageToken": page_token, "showHidden": True} if page_token else {"showHidden": True},
            )
            items.extend(payload.get("items", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return items

    async def create_calendar(self, summary: str, description: str | None = None) -> dict[str, Any]:
        """Create a new calendar and return the API payload."""
        body = {"summary": summary}
        if description:
            body["description"] = description
        return await self._request("POST", "/calendars", json=body)

    async def list_events(
        self,
        calendar_id: str,
        *,
        time_min: str | None = None,
        time_max: str | None = None,
        sync_token: str | None = None,
    ) -> dict[str, Any]:
        """Return events for the specified calendar within a window or sync token."""
        params: dict[str, Any] = {
            "singleEvents": True,
            "showDeleted": True,
            "maxResults": 2500,
        }
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params["orderBy"] = "startTime"
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
        calendar_path = _encode_path_segment(calendar_id)
        return await self._request(
            "GET", f"/calendars/{calendar_path}/events", params=params
        )

    async def insert_event(self, calendar_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new event into the specified calendar."""
        calendar_path = _encode_path_segment(calendar_id)
        return await self._request("POST", f"/calendars/{calendar_path}/events", json=payload)

    async def patch_event(
        self,
        calendar_id: str,
        event_id: str,
        payload: dict[str, Any],
        *,
        send_updates: str | None = None,
    ) -> dict[str, Any]:
        """Patch an existing event and return the updated payload."""
        calendar_path = _encode_path_segment(calendar_id)
        event_path = _encode_path_segment(event_id)
        params = {"sendUpdates": send_updates} if send_updates else None
        return await self._request(
            "PATCH",
            f"/calendars/{calendar_path}/events/{event_path}",
            params=params,
            json=payload,
        )

    async def get_event(self, calendar_id: str, event_id: str) -> dict[str, Any]:
        """Fetch a single event by id."""
        calendar_path = _encode_path_segment(calendar_id)
        event_path = _encode_path_segment(event_id)
        return await self._request("GET", f"/calendars/{calendar_path}/events/{event_path}")

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Delete an event from the specified calendar."""
        calendar_path = _encode_path_segment(calendar_id)
        event_path = _encode_path_segment(event_id)
        await self._request("DELETE", f"/calendars/{calendar_path}/events/{event_path}")

    async def watch_events(
        self, calendar_id: str, *, channel_id: str, address: str, token: str | None = None
    ) -> dict[str, Any]:
        """Create a webhook channel for calendar event changes."""
        calendar_path = _encode_path_segment(calendar_id)
        body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": address,
        }
        if token:
            body["token"] = token
        return await self._request("POST", f"/calendars/{calendar_path}/events/watch", json=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{GOOGLE_CALENDAR_BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, url, params=params, json=json, headers=headers)
        if response.status_code >= 400:
            payload = None
            try:
                payload = response.json()
            except Exception:
                payload = None
            raise GoogleCalendarError(response.status_code, response.text, payload)
        if not response.text:
            return {}
        return response.json()


def _encode_path_segment(value: str) -> str:
    """Encode path segments so calendar/event IDs with # or @ do not break URLs."""
    return quote(value, safe="")
