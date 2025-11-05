"""Generates readiness insights using Vertex AI."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vertex_client import VertexClient
from app.core.config import settings
from app.db.models.entities import DailyMetric, VertexInsight


class InsightService:
    def __init__(self, session: AsyncSession, vertex: VertexClient | None = None) -> None:
        self.session = session
        self.vertex = vertex or VertexClient()

    async def refresh_daily_insight(self, user_id: int, metric_date: date | None = None) -> VertexInsight:
        metric_date = metric_date or date.today()
        metric = await self._fetch_metric(user_id, metric_date)
        history = await self._fetch_metric_history(user_id, metric_date, days=14)
        existing_insight = await self._fetch_insight(user_id, metric_date)
        logger.debug(
            "Insight refresh context for user %s @ %s -> metric_found=%s, history_days=%s, existing_insight=%s",
            user_id,
            metric_date,
            metric is not None,
            len(history),
            existing_insight.id if existing_insight else None,
        )
        fallback_narrative = existing_insight.response_text if existing_insight else None
        fallback_score = existing_insight.readiness_score if existing_insight else None

        prompt = self._build_prompt(metric, history)
        logger.debug("Vertex prompt for {}:\n{}", metric_date, prompt)
        try:
            narrative, tokens = await self.vertex.generate_text(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vertex insight generation failed: {}. Storing placeholder.", exc)
            narrative = fallback_narrative or (
                "Insight generation is temporarily unavailable. "
                "Your readiness score will return once connectivity is restored."
            )
            tokens = None
            readiness_score = fallback_score if fallback_score is not None else 5
        else:
            readiness_score = self._extract_score(narrative)

        logger.debug(
            "Vertex narrative received (len={}, tokens={}):\n{}",
            len(narrative or ""),
            tokens,
            narrative,
        )

        preview = narrative.replace("\n", " ") if narrative else ""
        logger.info(
            "Vertex insight preview for {} -> score {} (tokens={}): {}",
            metric_date,
            readiness_score,
            tokens,
            preview[:200],
        )

        if existing_insight:
            insight = existing_insight
            insight.model_name = settings.vertex_model_name
            insight.prompt = prompt
            insight.response_text = narrative
            insight.tokens_used = tokens
            insight.readiness_score = readiness_score
        else:
            insight = VertexInsight(
                user_id=user_id,
                metric_date=metric_date,
                model_name=settings.vertex_model_name,
                prompt=prompt,
                response_text=narrative,
                tokens_used=tokens,
                readiness_score=readiness_score,
            )
            self.session.add(insight)

        if metric:
            metric.vertex_insight = insight
            metric.readiness_score = readiness_score
            metric.readiness_label = self._label_from_score(readiness_score)
            metric.readiness_narrative = narrative
        await self.session.commit()
        logger.debug(
            "Post-commit metric snapshot for user %s @ %s -> readiness_score=%s, label=%s, narrative_len=%s",
            user_id,
            metric_date,
            metric.readiness_score if metric else None,
            metric.readiness_label if metric else None,
            len(metric.readiness_narrative or "") if metric else 0,
        )
        logger.debug(
            "Stored Vertex insight for {} (len={}):\n{}",
            metric_date,
            len(narrative or ""),
            narrative,
        )
        logger.info("Stored Vertex insight for {}", metric_date)
        return insight

    async def _fetch_metric(self, user_id: int, metric_date: date) -> DailyMetric | None:
        stmt = select(DailyMetric).where(DailyMetric.user_id == user_id, DailyMetric.metric_date == metric_date)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _fetch_metric_history(self, user_id: int, metric_date: date, days: int) -> list[DailyMetric]:
        start_date = metric_date - timedelta(days=days - 1)
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.user_id == user_id,
                DailyMetric.metric_date >= start_date,
                DailyMetric.metric_date <= metric_date,
            )
            .order_by(DailyMetric.metric_date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_insight(self, user_id: int, metric_date: date) -> VertexInsight | None:
        stmt = (
            select(VertexInsight)
            .where(
                VertexInsight.user_id == user_id,
                VertexInsight.metric_date == metric_date,
            )
            .order_by(VertexInsight.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    def _build_prompt(self, metric: DailyMetric | None, history: list[DailyMetric]) -> str:
        today = date.today()

        def series(attr: str, formatter: callable[[float], float] | None = None) -> str:
            items: list[str] = []
            for entry in history:
                raw = getattr(entry, attr)
                value = "null"
                if raw is not None:
                    formatted = formatter(raw) if formatter else raw
                    value = f"{formatted:.2f}" if isinstance(formatted, float) else str(formatted)
                items.append(
                    f'{{"date": "{entry.metric_date.isoformat()}", "value": {value}}}'
                )
            return "[" + ", ".join(items) + "]"

        hrv_series = series("hrv_avg_ms")
        rhr_series = series("rhr_bpm")
        sleep_series = series("sleep_seconds", lambda v: v / 3600.0)
        load_series = series("training_load")
        volume_series = series("training_volume_seconds", lambda v: v / 3600.0)

        persona = (
            "You are Claude Monet reincarnated, a relaxed and calming presence. "
            "Speak with serene, impressionistic language that soothes the athlete while staying clear and actionable."
        )

        score_guidance = """
Readiness Score Guide (1-10):
- 9-10: Radiant Dawn — strong upward HRV trends, low resting HR, and restorative sleep. Encourage ambitious training with joyful imagery.
- 7-8: Gentle Sunrise — metrics are stable with mild fatigue. Suggest purposeful training with mindful recovery.
- 4-6: Fading Light — mixed signals (HRV dip, elevated resting HR, fragmented sleep). Recommend easy sessions, mobility, active recovery.
- 1-3: Evening Fog — pronounced signs of strain or poor recovery. Advocate rest, hydration, nourishing food, and mental reset.
Penalty cues: downward HRV streaks, rising resting HR, short sleep, heavy training load should tilt the score lower. Positive cues should lift it.
"""

        response_instructions = (
            "Structure your response as:\n"
            "1. A calming readiness overview in Monet-inspired prose.\n"
            "2. Explicit Readiness Score (e.g., 'Readiness Score: 7/10 – Gentle Sunrise').\n"
            "3. 3-4 bullet tips referencing the metrics (e.g., HRV trends, resting HR shifts, sleep hours, training load).\n"
            "Keep the tone empathetic, encouraging, and grounded in the provided data."
        )

        data_block = (
            "Historical metrics (most recent first where applicable):\n"
            f"HRV_MS_SERIES = {hrv_series}\n"
            f"RESTING_HR_BPM_SERIES = {rhr_series}\n"
            f"SLEEP_HOURS_SERIES = {sleep_series}  # hours per night\n"
            f"TRAINING_LOAD_ROLLING14_SERIES = {load_series}\n"
            f"TRAINING_VOLUME_HOURS_SERIES = {volume_series}\n"
        )

        def format_value(value: float | None, suffix: str = "", precision: int = 2) -> str:
            if value is None:
                return "unknown"
            if isinstance(value, (int, float)):
                return f"{value:.{precision}f}{suffix}"
            return f"{value}{suffix}"

        sleep_hours = None
        if metric and metric.sleep_seconds:
            sleep_hours = metric.sleep_seconds / 3600.0

        snapshot_lines = [
            f"Today's snapshot ({today.isoformat()}):",
            f"- HRV avg: {format_value(metric.hrv_avg_ms if metric else None, ' ms', 1)}",
            f"- Resting HR: {format_value(metric.rhr_bpm if metric else None, ' bpm', 1)}",
            f"- Sleep hours: {format_value(sleep_hours, ' h', 2)}",
            f"- 14-day training load sum: {format_value(metric.training_load if metric else None, '', 1)}",
            f"- 14-day training volume hours: {format_value((metric.training_volume_seconds / 3600.0) if metric and metric.training_volume_seconds else None, ' h', 2)}",
        ]

        today_snapshot = "\n".join(snapshot_lines)

        return "\n\n".join(
            [
                persona,
                score_guidance.strip(),
                data_block,
                today_snapshot,
                response_instructions,
            ]
        )

    def _extract_score(self, narrative: str) -> int:
        for token in narrative.split():
            if token.isdigit():
                value = int(token)
                if 1 <= value <= 10:
                    return value
        return 5

    def _label_from_score(self, score: int) -> str:
        if score >= 8:
            return "Fully Recovered"
        if score >= 6:
            return "Ready with Caution"
        if score >= 4:
            return "Focus on Recovery"
        return "Rest Day Recommended"
