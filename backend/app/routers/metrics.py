from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyMetric
from app.db.session import get_session
from app.schemas.metrics import DailyMetricResponse, MetricsOverviewResponse, TimeSeriesPoint

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", response_model=MetricsOverviewResponse)
async def metrics_overview(range_days: int = 14, session: AsyncSession = Depends(get_session)) -> MetricsOverviewResponse:
    cutoff = datetime.utcnow().date() - timedelta(days=range_days - 1)
    stmt = select(DailyMetric).where(DailyMetric.metric_date >= cutoff).order_by(DailyMetric.metric_date)
    result = await session.execute(stmt)
    records = result.scalars().all()
    hrv_series = [
        TimeSeriesPoint(timestamp=datetime.combine(r.metric_date, datetime.min.time()), value=r.hrv_avg_ms)
        for r in records
    ]
    rhr_series = [
        TimeSeriesPoint(timestamp=datetime.combine(r.metric_date, datetime.min.time()), value=r.rhr_bpm)
        for r in records
    ]
    sleep_series = [
        TimeSeriesPoint(
            timestamp=datetime.combine(r.metric_date, datetime.min.time()),
            value=(r.sleep_seconds / 3600 if r.sleep_seconds else None),
        )
        for r in records
    ]
    load_series = [
        TimeSeriesPoint(timestamp=datetime.combine(r.metric_date, datetime.min.time()), value=r.training_load)
        for r in records
    ]
    volume_hours_total = sum((r.training_volume_seconds or 0) / 3600 for r in records)
    training_load_avg = (
        sum(r.training_load or 0 for r in records) / len(records)
        if records
        else None
    )
    return MetricsOverviewResponse(
        generated_at=datetime.utcnow(),
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
async def daily_metrics(range_days: int = 30, session: AsyncSession = Depends(get_session)) -> list[DailyMetricResponse]:
    cutoff = datetime.utcnow().date() - timedelta(days=range_days - 1)
    stmt = select(DailyMetric).where(DailyMetric.metric_date >= cutoff).order_by(DailyMetric.metric_date)
    result = await session.execute(stmt)
    records = result.scalars().all()
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
