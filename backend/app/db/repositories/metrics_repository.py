"""Daily metrics persistence helpers."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyMetric, VertexInsight
from loguru import logger


class MetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_daily_metric(self, user_id: int, metric_date: date, values: dict) -> tuple[DailyMetric, set[str]]:
        stmt = select(DailyMetric).where(DailyMetric.user_id == user_id, DailyMetric.metric_date == metric_date)
        result = await self.session.execute(stmt)
        metric = result.scalar_one_or_none()
        changed_fields: set[str] = set()
        if metric is None:
            metric = DailyMetric(user_id=user_id, metric_date=metric_date, **values)
            self.session.add(metric)
            changed_fields = {key for key, value in values.items() if value is not None}
            logger.info(
                "DailyMetric inserted into DB (user_id={}, date={}, values={})",
                user_id,
                metric_date,
                {k: v for k, v in values.items() if v is not None},
            )
        else:
            for key, value in values.items():
                if value is not None:
                    current = getattr(metric, key)
                    if current != value:
                        setattr(metric, key, value)
                        changed_fields.add(key)
            logger.info(
                "DailyMetric updated in DB (user_id={}, date={}, values={})",
                user_id,
                metric_date,
                {k: v for k, v in values.items() if v is not None},
            )
        return metric, changed_fields

    async def attach_insight(self, metric: DailyMetric, insight: VertexInsight) -> None:
        metric.vertex_insight = insight
        metric.readiness_score = insight.readiness_score  # type: ignore[attr-defined]
        if metric.readiness_label is None:
            metric.readiness_label = insight.response_text.split("\n", 1)[0]
        metric.readiness_narrative = insight.response_text

    async def list_metrics_since(self, user_id: int, start_date: date) -> list[DailyMetric]:
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.user_id == user_id, DailyMetric.metric_date >= start_date)
            .order_by(DailyMetric.metric_date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_metric(self, user_id: int) -> DailyMetric | None:
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.user_id == user_id)
            .order_by(DailyMetric.metric_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_metrics_between(self, user_id: int, start_date: date, end_date: date) -> list[DailyMetric]:
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.user_id == user_id,
                DailyMetric.metric_date >= start_date,
                DailyMetric.metric_date <= end_date,
            )
            .order_by(DailyMetric.metric_date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
