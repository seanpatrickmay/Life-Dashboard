"""Domain models for activities, metrics, and insights."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from .base import Base
from app.utils.timezone import eastern_now


class PreferredUnits(str, Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None]
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            values_callable=lambda cls: [m.value for m in cls],
            create_type=False,
        ),
        default=UserRole.USER,
        nullable=False,
    )

    activities: Mapped[list["Activity"]] = relationship(back_populates="user")
    todos: Mapped[list["TodoItem"]] = relationship(back_populates="user")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="user")
    journal_summaries: Mapped[list["JournalDaySummary"]] = relationship(back_populates="user")
    daily_metrics: Mapped[list["DailyMetric"]] = relationship(back_populates="user")
    nutrition_intakes: Mapped[list["NutritionIntake"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    measurements: Mapped[list["UserMeasurement"]] = relationship(back_populates="user")
    daily_energy: Mapped[list["DailyEnergy"]] = relationship(back_populates="user")
    scaling_rules: Mapped[list["UserNutrientScalingRule"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
    garmin_connection: Mapped["GarminConnection | None"] = relationship(
        back_populates="user", uselist=False
    )
    chat_usages: Mapped[list["ChatUsage"]] = relationship(back_populates="user")
    calendar_connection: Mapped["GoogleCalendarConnection | None"] = relationship(
        back_populates="user", uselist=False
    )
    calendars: Mapped[list["GoogleCalendar"]] = relationship(back_populates="user")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="user")
    todo_event_links: Mapped[list["TodoEventLink"]] = relationship(back_populates="user")


class Activity(Base):
    __table_args__ = (UniqueConstraint("user_id", "garmin_id", name="uq_activity_user_garmin"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    garmin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str | None]
    type: Mapped[str | None]
    start_time: Mapped[datetime]
    duration_sec: Mapped[float]
    distance_m: Mapped[float]
    calories: Mapped[float | None]
    raw_payload: Mapped[dict] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="activities")


class DailyMetric(Base):
    id: Mapped[date] = mapped_column("metric_date", primary_key=True)
    metric_date = synonym("id")

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    hrv_avg_ms: Mapped[float | None]
    rhr_bpm: Mapped[float | None]
    sleep_seconds: Mapped[int | None]
    training_volume_seconds: Mapped[int | None]
    training_load: Mapped[float | None]
    readiness_score: Mapped[int | None]
    readiness_label: Mapped[str | None]
    readiness_narrative: Mapped[str | None] = mapped_column(Text)
    insight_greeting: Mapped[str | None] = mapped_column(Text)
    insight_hrv_value: Mapped[float | None]
    insight_hrv_note: Mapped[str | None] = mapped_column(Text)
    insight_hrv_score: Mapped[float | None]
    insight_rhr_value: Mapped[float | None]
    insight_rhr_note: Mapped[str | None] = mapped_column(Text)
    insight_rhr_score: Mapped[float | None]
    insight_sleep_value_hours: Mapped[float | None]
    insight_sleep_note: Mapped[str | None] = mapped_column(Text)
    insight_sleep_score: Mapped[float | None]
    insight_training_load_value: Mapped[float | None]
    insight_training_load_note: Mapped[str | None] = mapped_column(Text)
    insight_training_load_score: Mapped[float | None]
    insight_morning_note: Mapped[str | None] = mapped_column(Text)
    vertex_insight_id: Mapped[int | None] = mapped_column(ForeignKey("vertexinsight.id"))

    user: Mapped[User] = relationship(back_populates="daily_metrics")
    vertex_insight: Mapped["VertexInsight"] = relationship(back_populates="daily_metric", lazy="joined")


class SleepSession(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    metric_date: Mapped[date]
    duration_seconds: Mapped[int]
    quality_score: Mapped[int | None]
    raw_payload: Mapped[dict] = mapped_column(JSON)


class VertexInsight(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    metric_date: Mapped[date]
    model_name: Mapped[str]
    prompt: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[int | None]
    readiness_score: Mapped[int | None]

    daily_metric: Mapped[DailyMetric] = relationship(back_populates="vertex_insight", uselist=False)


class IngestionRun(Base):
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    status: Mapped[str]
    message: Mapped[str | None]
    activities_ingested: Mapped[int] = mapped_column(default=0)


class UserProfile(Base):
    __tablename__ = "user_profile"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profile_user_id"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16))
    height_cm: Mapped[float | None]
    current_weight_kg: Mapped[float | None]
    preferred_units: Mapped[PreferredUnits] = mapped_column(
        SAEnum(
            PreferredUnits,
            name="preferred_units",
            values_callable=lambda cls: [m.value for m in cls],
            create_type=False,
        ),
        default=PreferredUnits.METRIC,
    )
    daily_energy_delta_kcal: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="profile", lazy="joined")


class UserMeasurement(Base):
    __tablename__ = "user_measurement"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)
    weight_kg: Mapped[float]

    user: Mapped[User] = relationship(back_populates="measurements")


class DailyEnergy(Base):
    __tablename__ = "daily_energy"
    __table_args__ = (UniqueConstraint("user_id", "metric_date", name="uq_daily_energy_user_date"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    active_kcal: Mapped[float | None]
    bmr_kcal: Mapped[float | None]
    total_kcal: Mapped[float | None]
    source: Mapped[str | None] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)

    user: Mapped[User] = relationship(back_populates="daily_energy")


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_session_token"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class GarminConnection(Base):
    __tablename__ = "garmin_connection"
    __table_args__ = (UniqueConstraint("user_id", name="uq_garmin_connection_user"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    garmin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_store_path: Mapped[str] = mapped_column(String(512), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_reauth: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="garmin_connection")


class ChatUsage(Base):
    __tablename__ = "chat_usage"
    __table_args__ = (UniqueConstraint("user_id", "usage_date", name="uq_chat_usage_user_date"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(default=0)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="chat_usages")
