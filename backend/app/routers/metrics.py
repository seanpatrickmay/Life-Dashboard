from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.repositories.metrics_repository import MetricsRepository
from app.db.session import get_session
from app.db.models.entities import User
from app.schemas.metrics import (
    DailyMetricResponse,
    MetricsOverviewResponse,
    ReadinessMetricsSummary,
    MetricDelta,
    TimeSeriesPoint,
)
from app.utils.timezone import eastern_midnight, eastern_now, eastern_today

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", response_model=MetricsOverviewResponse)
async def metrics_overview(
    range_days: int = 14,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MetricsOverviewResponse:
    cutoff = eastern_today() - timedelta(days=range_days - 1)
    repo = MetricsRepository(session)
    records = await repo.list_metrics_since(current_user.id, cutoff)
    hrv_series = [
        TimeSeriesPoint(timestamp=eastern_midnight(r.metric_date), value=r.hrv_avg_ms)
        for r in records
    ]
    rhr_series = [
        TimeSeriesPoint(timestamp=eastern_midnight(r.metric_date), value=r.rhr_bpm)
        for r in records
    ]
    sleep_series = [
        TimeSeriesPoint(
            timestamp=eastern_midnight(r.metric_date),
            value=(r.sleep_seconds / 3600 if r.sleep_seconds else None),
        )
        for r in records
    ]
    load_series = [
        TimeSeriesPoint(timestamp=eastern_midnight(r.metric_date), value=r.training_load)
        for r in records
    ]
    volume_hours_total = sum((r.training_volume_seconds or 0) / 3600 for r in records)
    training_load_avg = (
        sum(r.training_load or 0 for r in records) / len(records)
        if records
        else None
    )
    return MetricsOverviewResponse(
        generated_at=eastern_now(),
        range_label=f"last {range_days} days",
        training_volume_hours=round(volume_hours_total, 2),
        training_volume_window_days=range_days,
        training_load_avg=training_load_avg,
        training_load_trend=load_series,
        hrv_trend_ms=hrv_series,
        rhr_trend_bpm=rhr_series,
        sleep_trend_hours=sleep_series,
    )


@router.get("/daily", response_model=list[DailyMetricResponse])
async def daily_metrics(
    range_days: int = 30,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DailyMetricResponse]:
    cutoff = eastern_today() - timedelta(days=range_days - 1)
    repo = MetricsRepository(session)
    records = await repo.list_metrics_since(current_user.id, cutoff)
    return [
        DailyMetricResponse(
            date=r.metric_date,
            hrv_avg_ms=r.hrv_avg_ms,
            rhr_bpm=r.rhr_bpm,
            sleep_hours=r.sleep_seconds / 3600 if r.sleep_seconds else None,
            training_load=r.training_load,
            training_volume_hours=(r.training_volume_seconds / 3600) if r.training_volume_seconds else None,
            readiness_score=r.readiness_score,
            readiness_label=r.readiness_label,
            readiness_narrative=r.readiness_narrative,
        )
        for r in records
    ]


def _average(values: list[float | None]) -> float | None:
    numeric = [v for v in values if v is not None]
    return sum(numeric) / len(numeric) if numeric else None


def _metric_delta(
    *,
    value: float | None,
    value_unit: str,
    reference_value: float | None,
    reference_label: str,
    delta: float | None,
    delta_unit: str,
) -> MetricDelta:
    return MetricDelta(
        value=value,
        value_unit=value_unit,
        reference_value=reference_value,
        reference_label=reference_label,
        delta=delta,
        delta_unit=delta_unit,
    )


@router.get("/readiness-summary", response_model=ReadinessMetricsSummary)
async def readiness_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReadinessMetricsSummary:
    repo = MetricsRepository(session)
    latest = await repo.get_latest_metric(current_user.id)
    if not latest:
        raise HTTPException(status_code=404, detail="No metrics available.")

    window_days = 14
    start = latest.metric_date - timedelta(days=window_days - 1)
    history = await repo.list_metrics_between(current_user.id, start, latest.metric_date)

    hrv_avg = _average([m.hrv_avg_ms for m in history])
    rhr_avg = _average([m.rhr_bpm for m in history])
    sleep_avg = _average(
        [(m.sleep_seconds / 3600.0) if m.sleep_seconds is not None else None for m in history]
    )

    hrv_value = latest.hrv_avg_ms
    rhr_value = latest.rhr_bpm
    sleep_value = (latest.sleep_seconds / 3600.0) if latest.sleep_seconds is not None else None
    training_value = latest.training_load

    hrv_delta = (
        ((hrv_value - hrv_avg) / hrv_avg) * 100 if hrv_value is not None and hrv_avg not in (None, 0) else None
    )
    rhr_delta = (rhr_value - rhr_avg) if rhr_value is not None and rhr_avg is not None else None
    sleep_delta = (
        (sleep_value - sleep_avg) * 60 if sleep_value is not None and sleep_avg is not None else None
    )

    # Training load vs yesterday
    previous = next((m for m in reversed(history) if m.metric_date < latest.metric_date), None)
    previous_load = previous.training_load if previous else None
    training_delta = (
        ((training_value - previous_load) / previous_load) * 100
        if training_value is not None and previous_load not in (None, 0)
        else None
    )

    return ReadinessMetricsSummary(
        date=latest.metric_date,
        hrv=_metric_delta(
            value=hrv_value,
            value_unit="ms",
            reference_value=hrv_avg,
            reference_label=f"{window_days}-day avg",
            delta=hrv_delta,
            delta_unit="%",
        ),
        rhr=_metric_delta(
            value=rhr_value,
            value_unit="bpm",
            reference_value=rhr_avg,
            reference_label=f"{window_days}-day avg",
            delta=rhr_delta,
            delta_unit="bpm",
        ),
        sleep=_metric_delta(
            value=sleep_value,
            value_unit="h",
            reference_value=sleep_avg,
            reference_label=f"{window_days}-day avg",
            delta=sleep_delta,
            delta_unit="min",
        ),
        training_load=_metric_delta(
            value=training_value,
            value_unit="pts",
            reference_value=previous_load,
            reference_label="yesterday",
            delta=training_delta,
            delta_unit="%",
        ),
    )
