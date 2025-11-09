"""Domain models for activities, metrics, and insights."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from .base import Base


class User(Base):
    email: Mapped[str]
    display_name: Mapped[str | None]

    activities: Mapped[list["Activity"]] = relationship(back_populates="user")
    daily_metrics: Mapped[list["DailyMetric"]] = relationship(back_populates="user")
    nutrition_intakes: Mapped[list["NutritionIntake"]] = relationship(back_populates="user")
    nutrition_goals: Mapped[list["NutritionUserGoal"]] = relationship(back_populates="user")


class Activity(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    garmin_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
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
