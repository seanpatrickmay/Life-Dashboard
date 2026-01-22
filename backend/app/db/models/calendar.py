"""Google Calendar connection, calendars, events, and todo links."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.timezone import eastern_now

from .base import Base


class GoogleCalendarConnection(Base):
    """Per-user OAuth connection for Google Calendar access."""

    __tablename__ = "google_calendar_connection"
    __table_args__ = (UniqueConstraint("user_id", name="uq_google_calendar_connection_user"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_reauth: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="calendar_connection")
    calendars: Mapped[list["GoogleCalendar"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class GoogleCalendar(Base):
    """Google Calendar metadata stored per user."""

    __tablename__ = "google_calendar"
    __table_args__ = (UniqueConstraint("user_id", "google_id", name="uq_google_calendar_user_google"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("google_calendar_connection.id"))
    google_id: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_life_dashboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_resource_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="calendars")
    connection: Mapped[GoogleCalendarConnection | None] = relationship(back_populates="calendars")
    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
    todo_links: Mapped[list["TodoEventLink"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )


class CalendarEvent(Base):
    """Cached Google Calendar events for fast UI rendering and chatbot context."""

    __tablename__ = "calendar_event"
    __table_args__ = (UniqueConstraint("calendar_id", "google_event_id", name="uq_calendar_event_google"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("google_calendar.id"), nullable=False, index=True)
    google_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    recurring_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ical_uid: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    visibility: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transparency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at_google: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    html_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hangout_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    conference_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    organizer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attendees: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="calendar_events")
    calendar: Mapped["GoogleCalendar"] = relationship(back_populates="events")


class TodoEventLink(Base):
    """Links a todo item to a Google Calendar event (1:1)."""

    __tablename__ = "todo_event_link"
    __table_args__ = (
        UniqueConstraint("todo_id", name="uq_todo_event_link_todo"),
        UniqueConstraint("calendar_id", "google_event_id", name="uq_todo_event_link_event"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    todo_id: Mapped[int] = mapped_column(ForeignKey("todo_item.id"), nullable=False)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("google_calendar.id"), nullable=False)
    google_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ical_uid: Mapped[str | None] = mapped_column(String(256), nullable=True)
    event_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="todo_event_links")
    calendar: Mapped[GoogleCalendar] = relationship(back_populates="todo_links")
    todo: Mapped["TodoItem"] = relationship(back_populates="calendar_link")
