"""Generates readiness insights using OpenAI."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.core.config import settings
from app.db.models.calendar import CalendarEvent, GoogleCalendar
from app.db.models.entities import DailyEnergy, DailyMetric, ReadinessInsight
from app.db.models.journal import JournalEntry
from app.db.models.todo import TodoItem
from app.prompts.llm_prompts import (
    READINESS_PERSONA,
    READINESS_RESPONSE_INSTRUCTIONS,
    READINESS_SCORE_GUIDANCE,
)
from app.schemas.llm_outputs import ReadinessInsightOutput
from app.utils.timezone import eastern_today


class InsightService:
    def __init__(self, session: AsyncSession, client: OpenAIResponsesClient | None = None) -> None:
        self.session = session
        self._client = client

    async def refresh_daily_insight(self, user_id: int, metric_date: date | None = None) -> ReadinessInsight:
        metric_date = metric_date or eastern_today()
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

        life_context = await self._gather_life_context(user_id, metric_date)
        prompt = self._build_prompt(metric, history, life_context=life_context)
        logger.debug("Readiness prompt for {}:\n{}", metric_date, prompt)
        try:
            client = await self._get_client()
            result = await client.generate_json(
                prompt,
                response_model=ReadinessInsightOutput,
                temperature=0.3,
                max_output_tokens=30000,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Readiness insight generation failed: {}. Storing placeholder.", exc)
            narrative = fallback_narrative or (
                "Insight generation is temporarily unavailable. "
                "Your readiness score will return once connectivity is restored."
            )
            tokens = None
            readiness_score = fallback_score if fallback_score is not None else 50
        else:
            structured = result.data
            narrative = json.dumps(structured.model_dump(), ensure_ascii=False)
            tokens = result.total_tokens
            readiness_score = self._normalize_score(structured.overall_readiness.score_100) or self._extract_score(narrative)

        logger.debug(
            "Readiness narrative received (len={}, tokens={}):\n{}",
            len(narrative or ""),
            tokens,
            narrative,
        )

        preview = narrative.replace("\n", " ") if narrative else ""
        logger.info(
            "Readiness insight preview for {} -> score {} (tokens={}): {}",
            metric_date,
            readiness_score,
            tokens,
            preview[:200],
        )

        if existing_insight:
            insight = existing_insight
            insight.model_name = settings.openai_model_name
            insight.prompt = prompt
            insight.response_text = narrative
            insight.tokens_used = tokens
            insight.readiness_score = readiness_score
        else:
            insight = ReadinessInsight(
                user_id=user_id,
                metric_date=metric_date,
                model_name=settings.openai_model_name,
                prompt=prompt,
                response_text=narrative,
                tokens_used=tokens,
                readiness_score=readiness_score,
            )
            self.session.add(insight)

        if metric:
            metric.readiness_insight = insight
            metric.readiness_narrative = narrative
            metric.readiness_score = readiness_score
            structured = self._maybe_parse_structured(narrative)
            structured_score = None
            structured_label = None
            if structured:
                structured_score, structured_label = self._apply_structured_fields(metric, structured)
                normalized = self._normalize_score(structured_score)
                if normalized is not None:
                    readiness_score = normalized
                    metric.readiness_score = readiness_score
                    insight.readiness_score = readiness_score
            metric.readiness_label = structured_label or self._label_from_score(metric.readiness_score or readiness_score)
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
            "Stored readiness insight for {} (len={}):\n{}",
            metric_date,
            len(narrative or ""),
            narrative,
        )
        logger.info("Stored readiness insight for {}", metric_date)
        return insight

    async def _get_client(self) -> OpenAIResponsesClient:
        if self._client is None:
            self._client = OpenAIResponsesClient()
        return self._client

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

    async def fetch_latest_completed_metric(self, user_id: int) -> DailyMetric | None:
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.user_id == user_id,
                DailyMetric.readiness_narrative.is_not(None),
            )
            .order_by(DailyMetric.metric_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        metric = result.scalar_one_or_none()
        if metric and metric.readiness_narrative:
            structured = self._maybe_parse_structured(metric.readiness_narrative)
            if structured:
                fields_missing = self._structured_fields_missing(metric)
                before_snapshot = self._structured_snapshot(metric)
                structured_score, structured_label = self._apply_structured_fields(metric, structured)
                after_snapshot = self._structured_snapshot(metric)
                dirty = fields_missing or before_snapshot != after_snapshot
                normalized = self._normalize_score(structured_score)
                if normalized is not None:
                    if metric.readiness_score != normalized:
                        metric.readiness_score = normalized
                        dirty = True
                    if metric.readiness_insight and metric.readiness_insight.readiness_score != normalized:
                        metric.readiness_insight.readiness_score = normalized
                        dirty = True
                if structured_label:
                    if metric.readiness_label != structured_label:
                        metric.readiness_label = structured_label
                        dirty = True
                elif metric.readiness_score is not None:
                    derived = self._label_from_score(metric.readiness_score)
                    if metric.readiness_label != derived:
                        metric.readiness_label = derived
                        dirty = True

                if dirty:
                    await self.session.commit()
                    logger.info(
                        "Backfilled structured insight fields for user %s @ %s from stored narrative JSON.",
                        metric.user_id,
                        metric.metric_date,
                    )
        return metric

    async def _fetch_insight(self, user_id: int, metric_date: date) -> ReadinessInsight | None:
        stmt = (
            select(ReadinessInsight)
            .where(
                ReadinessInsight.user_id == user_id,
                ReadinessInsight.metric_date == metric_date,
            )
            .order_by(ReadinessInsight.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _gather_life_context(self, user_id: int, metric_date: date) -> dict:
        """Gather cross-system context to enrich the readiness insight."""
        import asyncio

        async def _safe(key: str, coro):
            try:
                return key, await coro
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not gather {} context for insight: {}", key, exc)
                return key, None

        results = await asyncio.gather(
            _safe("todos", self._gather_todo_context(user_id, metric_date)),
            _safe("nutrition", self._gather_nutrition_context(user_id, metric_date)),
            _safe("calendar", self._gather_calendar_context(user_id, metric_date)),
            _safe("energy", self._gather_energy_context(user_id, metric_date)),
            _safe("journal", self._gather_journal_context(user_id, metric_date)),
        )
        return {key: value for key, value in results if value is not None}

    async def _gather_todo_context(self, user_id: int, metric_date: date) -> dict:
        now_utc = datetime.now(timezone.utc)
        stmt = select(
            func.count().label("total"),
            func.count().filter(TodoItem.completed.is_(True)).label("completed"),
            func.count().filter(
                TodoItem.deadline_utc.is_not(None),
                TodoItem.deadline_utc < now_utc,
                TodoItem.completed.is_(False),
            ).label("overdue"),
        ).where(TodoItem.user_id == user_id)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_active": row.total,
            "completed": row.completed,
            "overdue": row.overdue,
        }

    async def _gather_nutrition_context(self, user_id: int, metric_date: date) -> dict | None:
        from app.services.nutrition_intake_service import NutritionIntakeService
        svc = NutritionIntakeService(self.session)

        key_slugs = (
            "energy_kcal", "protein_g", "carbohydrate_g", "fat_g",
            "fiber_g", "vitamin_d_mcg", "iron_mg", "calcium_mg",
        )

        # Today's intake
        summary = await svc.daily_summary(user_id, metric_date)
        nutrients = summary.get("nutrients", [])
        context: dict = {}
        for n in nutrients:
            if n["slug"] in key_slugs:
                context[n["slug"]] = {
                    "today": n["amount"],
                    "goal": n["goal"],
                    "today_pct": n["percent_of_goal"],
                }

        # 7-day rolling average for trend detection
        rolling = await svc.rolling_average(user_id, days=7)
        for n in rolling.get("nutrients", []):
            if n["slug"] in key_slugs and n["slug"] in context:
                context[n["slug"]]["avg_7d"] = n["average_amount"]
                context[n["slug"]]["avg_7d_pct"] = n["percent_of_goal"]

        return context if context else None

    async def _gather_calendar_context(self, user_id: int, metric_date: date) -> dict:
        from app.utils.timezone import EASTERN_TZ
        start_utc = datetime.combine(metric_date, datetime.min.time(), tzinfo=EASTERN_TZ)
        end_utc = start_utc + timedelta(days=1)
        stmt = (
            select(func.count().label("count"))
            .select_from(CalendarEvent)
            .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
            .where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time >= start_utc,
                CalendarEvent.start_time < end_utc,
                GoogleCalendar.selected.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return {"events_today": count}

    async def _gather_energy_context(self, user_id: int, metric_date: date) -> dict | None:
        stmt = select(DailyEnergy).where(
            DailyEnergy.user_id == user_id,
            DailyEnergy.metric_date == metric_date,
        )
        result = await self.session.execute(stmt)
        energy = result.scalar_one_or_none()
        if not energy:
            return None
        return {
            "active_kcal": energy.active_kcal,
            "bmr_kcal": energy.bmr_kcal,
            "total_kcal": energy.total_kcal,
        }

    async def _gather_journal_context(self, user_id: int, metric_date: date) -> list[str] | None:
        stmt = (
            select(JournalEntry.text)
            .where(
                JournalEntry.user_id == user_id,
                JournalEntry.local_date == metric_date,
            )
            .order_by(JournalEntry.created_at.desc())
            .limit(10)
        )
        result = await self.session.execute(stmt)
        texts = [row[0] for row in result.all() if row[0] and row[0].strip()]
        return texts if texts else None

    def _build_life_context_block(self, context: dict) -> str:
        """Format cross-system context into a structured analytical prompt block."""
        sections: list[str] = []

        # --- Nutrition analysis (today + 7-day trends) ---
        nutrition = context.get("nutrition")
        if nutrition:
            nutr_lines = ["=== NUTRITION ANALYSIS ==="]
            nutr_lines.append("Analyze how nutrition intake affects recovery and readiness:")
            for slug, data in nutrition.items():
                label = slug.replace("_g", "").replace("_kcal", "").replace("_mcg", "").replace("_mg", "").replace("_", " ").title()
                today_val = data.get("today", 0)
                goal_val = data.get("goal", 0)
                today_pct = data.get("today_pct")
                avg_7d = data.get("avg_7d")
                avg_7d_pct = data.get("avg_7d_pct")

                line = f"- {label}: {today_val:.0f}/{goal_val:.0f}"
                if today_pct is not None:
                    line += f" ({today_pct:.0f}% of goal)"
                if avg_7d is not None and avg_7d_pct is not None:
                    line += f" | 7-day avg: {avg_7d:.0f} ({avg_7d_pct:.0f}%)"
                    if avg_7d_pct < 60:
                        line += " ⚠ chronically low"
                    elif avg_7d_pct > 130:
                        line += " ⚠ consistently over goal"
                nutr_lines.append(line)

            # Caloric balance if energy expenditure available
            energy = context.get("energy")
            if energy and energy.get("total_kcal") is not None and "energy_kcal" in nutrition:
                intake_kcal = nutrition["energy_kcal"].get("today", 0)
                expenditure_kcal = energy["total_kcal"]
                balance = intake_kcal - expenditure_kcal
                sign = "+" if balance >= 0 else ""
                nutr_lines.append(f"- Caloric balance: {sign}{balance:.0f} kcal (intake {intake_kcal:.0f} − expenditure {expenditure_kcal:.0f})")
                if balance < -500:
                    nutr_lines.append("  → Significant deficit: may impair recovery, especially with training load")
                elif balance < -200:
                    nutr_lines.append("  → Moderate deficit: monitor energy levels during activity")

            sections.append("\n".join(nutr_lines))

        # --- Cognitive load / productivity ---
        todos = context.get("todos")
        calendar = context.get("calendar")
        has_todo_data = todos and (todos.get("total_active", 0) > 0 or todos.get("overdue", 0) > 0)
        calendar_count = calendar.get("events_today", 0) if calendar else 0
        if has_todo_data or calendar_count > 0:
            load_lines = ["=== COGNITIVE LOAD ==="]
            load_lines.append("Consider how task burden and schedule density affect mental recovery:")
            if has_todo_data:
                load_lines.append(
                    f"- Tasks: {todos['total_active']} active, {todos['completed']} completed, {todos['overdue']} overdue"
                )
                if todos["overdue"] > 5:
                    load_lines.append("  → Heavy backlog: likely cognitive stress and reduced recovery quality")
                elif todos["overdue"] > 2:
                    load_lines.append("  → Growing backlog: may contribute to background stress")
            if calendar_count > 0:
                load_lines.append(f"- Calendar: {calendar_count} event{'s' if calendar_count != 1 else ''} today")
                if calendar_count >= 6:
                    load_lines.append("  → Very dense schedule: limited recovery windows between obligations")
                elif calendar_count >= 4:
                    load_lines.append("  → Moderately busy: balance focused work with recovery breaks")
            sections.append("\n".join(load_lines))

        # --- Energy expenditure (standalone if not already used in nutrition) ---
        energy = context.get("energy")
        if energy and not nutrition:
            energy_lines = ["=== ENERGY EXPENDITURE ==="]
            parts = []
            if energy.get("active_kcal") is not None:
                parts.append(f"Active: {energy['active_kcal']:.0f} kcal")
            if energy.get("bmr_kcal") is not None:
                parts.append(f"BMR: {energy['bmr_kcal']:.0f} kcal")
            if energy.get("total_kcal") is not None:
                parts.append(f"Total: {energy['total_kcal']:.0f} kcal")
            if parts:
                energy_lines.append(f"- {', '.join(parts)}")
            sections.append("\n".join(energy_lines))

        # --- Journal / qualitative context ---
        journal = context.get("journal")
        if journal:
            journal_lines = ["=== JOURNAL CONTEXT ==="]
            journal_lines.append("Recent journal entries that may reflect the user's state of mind:")
            for entry_text in journal[:5]:
                truncated = entry_text[:200] + "..." if len(entry_text) > 200 else entry_text
                journal_lines.append(f"- {truncated}")
            sections.append("\n".join(journal_lines))

        if not sections:
            return ""
        header = "Lifestyle & cross-system analysis (integrate these factors into your readiness assessment):"
        return header + "\n\n" + "\n\n".join(sections)

    def _build_prompt(self, metric: DailyMetric | None, history: list[DailyMetric], life_context: dict | None = None) -> str:
        today = eastern_today()

        def avg(values: list[float | None]) -> float | None:
            numeric = [v for v in values if v is not None]
            return sum(numeric) / len(numeric) if numeric else None

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

        total_volume_hours = 0.0
        if history:
            total_volume_hours = sum((entry.training_volume_seconds or 0) for entry in history) / 3600.0
        window_days = len(history) if history else 0
        window_label = f"{window_days}-day avg" if window_days else "recent avg"

        def sleep_hours_value(entry: DailyMetric | None) -> float | None:
            if entry and entry.sleep_seconds:
                return entry.sleep_seconds / 3600.0
            return None

        hrv_value = metric.hrv_avg_ms if metric else None
        rhr_value = metric.rhr_bpm if metric else None
        sleep_value = sleep_hours_value(metric)
        training_value = metric.training_load if metric else None

        hrv_avg = avg([entry.hrv_avg_ms for entry in history])
        rhr_avg = avg([entry.rhr_bpm for entry in history])
        sleep_avg = avg([sleep_hours_value(entry) for entry in history])

        hrv_delta_pct = (
            ((hrv_value - hrv_avg) / hrv_avg) * 100 if hrv_value is not None and hrv_avg not in (None, 0) else None
        )
        rhr_delta_bpm = (rhr_value - rhr_avg) if rhr_value is not None and rhr_avg is not None else None
        sleep_delta_minutes = (
            (sleep_value - sleep_avg) * 60 if sleep_value is not None and sleep_avg is not None else None
        )

        previous_load = None
        if metric:
            for entry in reversed(history):
                if entry.metric_date < metric.metric_date and entry.training_load is not None:
                    previous_load = entry.training_load
                    break
        training_delta_pct = (
            ((training_value - previous_load) / previous_load) * 100
            if training_value is not None and previous_load not in (None, 0)
            else None
        )

        def rounded(value: float | None, digits: int = 2) -> float | None:
            if value is None:
                return None
            return round(value, digits)

        metric_summary = {
            "window_label": window_label,
            "hrv": {
                "value_ms": hrv_value,
                "reference_ms": hrv_avg,
                "reference_label": window_label,
                "delta_percent_vs_reference": rounded(hrv_delta_pct, 2),
            },
            "rhr": {
                "value_bpm": rhr_value,
                "reference_bpm": rhr_avg,
                "reference_label": window_label,
                "delta_bpm_vs_reference": rounded(rhr_delta_bpm, 1),
            },
            "sleep": {
                "value_hours": sleep_value,
                "reference_hours": sleep_avg,
                "reference_label": window_label,
                "delta_minutes_vs_reference": rounded(sleep_delta_minutes, 1),
            },
            "training_load": {
                "value": training_value,
                "reference_value": previous_load,
                "reference_label": "yesterday" if previous_load is not None else None,
                "delta_percent_vs_reference": rounded(training_delta_pct, 2),
            },
        }
        metric_summary_block = (
            "Metric delta summary (use these exact numbers when describing trends):\n"
            + json.dumps(metric_summary, ensure_ascii=False, indent=2)
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

        def format_delta(value: float | None, unit: str) -> str:
            if value is None:
                return "n/a"
            sign = "+" if value >= 0 else "−"
            magnitude = abs(value)
            if unit == "%":
                return f"{sign}{magnitude:.1f}%"
            if unit == "bpm":
                return f"{sign}{magnitude:.1f} bpm"
            if unit == "min":
                return f"{sign}{magnitude:.0f} min"
            return f"{sign}{magnitude:.1f}{unit}"

        snapshot_lines = [
            f"Today's snapshot ({today.isoformat()}):",
            f"- HRV avg: {format_value(metric.hrv_avg_ms if metric else None, ' ms', 1)}",
            f"- Resting HR: {format_value(metric.rhr_bpm if metric else None, ' bpm', 1)}",
            f"- Sleep hours: {format_value(sleep_hours, ' h', 2)}",
            f"- 14-day training load sum: {format_value(metric.training_load if metric else None, '', 1)}",
            f"- 14-day training volume hours: {format_value(total_volume_hours, ' h', 2)}",
        ]

        if window_days:
            snapshot_lines.insert(
                1,
                f"- HRV delta: {format_delta(hrv_delta_pct, '%')} vs {window_label} ({format_value(hrv_avg, ' ms', 1)})",
            )
            snapshot_lines.insert(
                3,
                f"- Resting HR delta: {format_delta(rhr_delta_bpm, 'bpm')} vs {window_label} ({format_value(rhr_avg, ' bpm', 1)})",
            )
            snapshot_lines.insert(
                5,
                f"- Sleep delta: {format_delta(sleep_delta_minutes, 'min')} vs {window_label} ({format_value(sleep_avg, ' h', 2)})",
            )
        if previous_load is not None:
            snapshot_lines.insert(
                7,
                f"- Training load delta: {format_delta(training_delta_pct, '%')} vs yesterday ({format_value(previous_load, '', 1)})",
            )

        today_snapshot = "\n".join(snapshot_lines)

        blocks = [
            READINESS_PERSONA,
            READINESS_SCORE_GUIDANCE.strip(),
            data_block,
            metric_summary_block,
            today_snapshot,
        ]

        if life_context:
            context_block = self._build_life_context_block(life_context)
            if context_block:
                blocks.append(context_block)

        blocks.append(READINESS_RESPONSE_INSTRUCTIONS)
        return "\n\n".join(blocks)

    def _maybe_parse_structured(self, narrative: str | None) -> dict | None:
        if not narrative:
            return None
        text = narrative.strip()
        attempts = [text]
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            attempts.append(text[start:end])
        if "```" in text:
            fenced = "".join(line for line in text.splitlines() if not line.strip().startswith("```"))
            attempts.append(fenced)

        for candidate in attempts:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:  # noqa: BLE001
                continue

        logger.warning("Failed to parse structured insight JSON. Raw payload begins: {}", text[:200])
        return None

    @staticmethod
    def _safe_number(section: dict | None, key: str) -> float | None:
        if not isinstance(section, dict):
            return None
        value = section.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_text(section: dict | None, key: str) -> str | None:
        if not isinstance(section, dict):
            return None
        value = section.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return None

    @staticmethod
    def _structured_fields_missing(metric: DailyMetric) -> bool:
        fields = [
            metric.insight_greeting,
            metric.insight_hrv_value,
            metric.insight_hrv_note,
            metric.insight_rhr_value,
            metric.insight_rhr_note,
            metric.insight_sleep_value_hours,
            metric.insight_sleep_note,
            metric.insight_training_load_value,
            metric.insight_training_load_note,
            metric.insight_morning_note,
        ]
        return all(value is None for value in fields)

    @staticmethod
    def _structured_snapshot(metric: DailyMetric) -> tuple:
        return (
            metric.insight_greeting,
            metric.insight_hrv_value,
            metric.insight_hrv_note,
            metric.insight_rhr_value,
            metric.insight_rhr_note,
            metric.insight_sleep_value_hours,
            metric.insight_sleep_note,
            metric.insight_training_load_value,
            metric.insight_training_load_note,
            metric.insight_morning_note,
        )

    def _apply_structured_fields(self, metric: DailyMetric, structured: dict) -> tuple[float | None, str | None]:
        metric.insight_greeting = structured.get("greeting")

        def section(name: str) -> dict | None:
            candidate = structured.get(name)
            return candidate if isinstance(candidate, dict) else None

        def section_score(block: dict | None) -> float | None:
            if not isinstance(block, dict):
                return None
            return self._safe_number(block, "score") or self._safe_number(block, "score_10")

        hrv = section("hrv")
        rhr = section("rhr")
        sleep = section("sleep")
        load = section("training_load")
        nutrition = section("nutrition")
        productivity = section("productivity")

        metric.insight_hrv_score = section_score(hrv)
        metric.insight_hrv_note = self._safe_text(hrv, "insight")
        metric.insight_hrv_value = metric.hrv_avg_ms

        metric.insight_rhr_score = section_score(rhr)
        metric.insight_rhr_note = self._safe_text(rhr, "insight")
        metric.insight_rhr_value = metric.rhr_bpm

        metric.insight_sleep_score = section_score(sleep)
        metric.insight_sleep_note = self._safe_text(sleep, "insight")
        metric.insight_sleep_value_hours = (metric.sleep_seconds / 3600.0) if metric.sleep_seconds else None

        metric.insight_training_load_score = section_score(load)
        metric.insight_training_load_note = self._safe_text(load, "insight")
        metric.insight_training_load_value = metric.training_load

        # New pillars — stored in the narrative JSON, extracted at read time
        self._last_nutrition_pillar = {
            "score": section_score(nutrition),
            "note": self._safe_text(nutrition, "insight"),
        } if nutrition else None
        self._last_productivity_pillar = {
            "score": section_score(productivity),
            "note": self._safe_text(productivity, "insight"),
        } if productivity else None

        readiness = structured.get("overall_readiness") or structured.get("morning_readiness")
        readiness = readiness if isinstance(readiness, dict) else None
        metric.insight_morning_note = self._safe_text(readiness, "insight")
        score = self._safe_number(readiness, "score_100") or self._safe_number(readiness, "score")
        label = self._safe_text(readiness, "label")
        return score, label

    def _extract_score(self, narrative: str) -> int:
        for token in narrative.split():
            if token.isdigit():
                value = int(token)
                if 1 <= value <= 100:
                    return value
        return 50

    def _label_from_score(self, score: int) -> str:
        if score >= 80:
            return "Fully Recovered"
        if score >= 60:
            return "Ready with Caution"
        if score >= 40:
            return "Focus on Recovery"
        return "Rest Day Recommended"

    @staticmethod
    def _normalize_score(score: float | None) -> int | None:
        if score is None:
            return None
        try:
            value = int(round(float(score)))
        except (TypeError, ValueError):
            return None
        return max(1, min(100, value))
