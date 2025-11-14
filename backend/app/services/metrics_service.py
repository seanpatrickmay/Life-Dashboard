"""Metric ingestion and aggregation services."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.garmin_client import GarminClient
from app.db.models.entities import DailyEnergy
from app.db.repositories.activity_repository import ActivityRepository
from app.db.repositories.metrics_repository import MetricsRepository
from app.utils.timezone import eastern_now, eastern_today


class MetricsService:
    def __init__(self, session: AsyncSession, garmin: GarminClient | None = None) -> None:
        self.session = session
        self.garmin = garmin or GarminClient()
        self.activity_repo = ActivityRepository(session)
        self.metrics_repo = MetricsRepository(session)

    async def ingest(
        self,
        user_id: int,
        lookback_days: int = 30,
        *,
        activities: list[dict[str, Any]] | None = None,
        hrv_payload: list[dict[str, Any]] | None = None,
        rhr_payload: list[dict[str, Any]] | None = None,
        sleep_payload: list[dict[str, Any]] | None = None,
        load_payload: list[dict[str, Any]] | None = None,
        energy_payload: list[dict[str, Any]] | None = None,
    ) -> dict:
        now = eastern_now()
        cutoff_dt = now - timedelta(days=lookback_days)
        if activities is None:
            logger.info("Fetching Garmin activities since {}", cutoff_dt)
            activities = self.garmin.fetch_recent_activities(cutoff_dt)

        ingested = await self.activity_repo.upsert_many(user_id, activities)

        start_date = eastern_today() - timedelta(days=lookback_days - 1)
        end_date = eastern_today()
        if hrv_payload is None:
            hrv_payload = self.garmin.fetch_daily_hrv(start_date, end_date)
        if rhr_payload is None:
            rhr_payload = self.garmin.fetch_daily_rhr(start_date, end_date)
        if sleep_payload is None:
            sleep_payload = self.garmin.fetch_sleep(start_date, end_date)
        if load_payload is None:
            load_payload = []
        if energy_payload is None:
            energy_payload = self.garmin.fetch_daily_energy(start_date, end_date)

        hrv_map = self._map_hrv(hrv_payload)
        rhr_map = self._map_rhr(rhr_payload)
        sleep_map = self._map_sleep(sleep_payload)
        load_map = self._map_training_loads(load_payload)
        activity_totals = self._aggregate_activity_totals(activities)
        await self._persist_daily_energy(
            user_id,
            start_date,
            end_date,
            energy_payload,
            activity_totals,
        )
        if not rhr_map:
            rhr_map = self._extract_rhr_from_sleep(sleep_payload)

        hrv_map = self._impute_missing_series(hrv_map, start_date, end_date)
        rhr_map = self._impute_missing_series(rhr_map, start_date, end_date)
        sleep_map = self._impute_missing_series(sleep_map, start_date, end_date)

        def sample(map_: dict[date, float | int], label: str) -> None:
            items = sorted(map_.items()) if map_ else []
            preview = items[:5]
            logger.debug("{} entries: {} sample={}", label, len(map_), preview)

        sample(hrv_map, "HRV map")
        sample(rhr_map, "RHR map")
        sample(sleep_map, "Sleep map")

        rolling_window_days = 14
        daily_loads: dict[date, float] = {}

        for offset in range(lookback_days):
            metric_day = start_date + timedelta(days=offset)
            base_load = load_map.get(metric_day)
            activity_stats = activity_totals.get(metric_day, {})
            if base_load is None:
                base_load = activity_stats.get("load")
            base_load = float(base_load) if base_load is not None else 0.0
            daily_loads[metric_day] = base_load
            window_start = metric_day - timedelta(days=rolling_window_days - 1)
            window_values = [
                load for day, load in daily_loads.items() if window_start <= day <= metric_day
            ]
            rolling_avg = (
                sum(window_values) / len(window_values) if window_values else 0.0
            )
            training_load = rolling_avg if rolling_avg > 0 else None
            duration_total = activity_stats.get("duration")
            training_volume_seconds = duration_total if duration_total else None
            sleep_value = sleep_map.get(metric_day)
            sleep_seconds = int(round(sleep_value)) if sleep_value else None
            await self.metrics_repo.upsert_daily_metric(
                user_id=user_id,
                metric_date=metric_day,
                values={
                    "hrv_avg_ms": hrv_map.get(metric_day),
                    "rhr_bpm": rhr_map.get(metric_day),
                    "sleep_seconds": sleep_seconds,
                    "training_load": training_load,
                    "training_volume_seconds": training_volume_seconds,
                },
            )

        await self.session.commit()
        return {
            "activities": ingested,
            "hrv_entries": len(hrv_payload),
            "rhr_entries": len(rhr_payload),
            "sleep_entries": len(sleep_payload),
            "training_load_entries": len(load_payload) if load_payload else sum(1 for v in activity_totals.values() if v.get("load") is not None),
            "energy_entries": len(energy_payload),
        }

    def _map_hrv(self, payload: list[dict]) -> dict[date, float]:
        result: dict[date, float] = {}
        for entry in payload:
            summary = self._hrv_summary(entry)
            if not summary:
                continue
            metric_day = (
                self._extract_date(summary)
                or self._parse_iso_date(str(summary.get("calendarDate")))
                or self._parse_iso_date(str(summary.get("startDate")))
            )
            if not metric_day:
                metric_day = (
                    self._parse_iso_date(str(entry.get("startTimestampLocal")))
                    or self._parse_iso_date(str(entry.get("startTimestampGMT")))
                )
            if not metric_day:
                continue
            value_candidates = [
                summary.get("lastNightAvg"),
                summary.get("dailyAvg"),
                summary.get("weeklyAvg"),
                summary.get("hrvDailyAvg"),
                summary.get("hrvAverage"),
                summary.get("average"),
            ]
            value = next((v for v in value_candidates if v is not None), None)
            if value is None:
                continue
            try:
                result[metric_day] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    def _map_rhr(self, payload: list[dict]) -> dict[date, float]:
        result: dict[date, float] = {}
        for entry in payload:
            metric_day = self._extract_date(entry)
            if not metric_day and "date" in entry:
                metric_day = self._parse_iso_date(entry["date"])
            if not metric_day:
                continue
            value = entry.get("value") or entry.get("restingHeartRate")
            if value is None and isinstance(entry.get("summary"), dict):
                value = entry["summary"].get("restingHeartRate")
            if value is not None:
                try:
                    result[metric_day] = float(value)
                except (TypeError, ValueError):
                    continue
        return result

    def _map_sleep(self, payload: list[dict]) -> dict[date, int]:
        result: dict[date, int] = {}

        def store(seconds: float | int | None, metric_day: date | None) -> None:
            if seconds is None or metric_day is None:
                return
            try:
                result[metric_day] = int(float(seconds))
            except (TypeError, ValueError):
                return

        def extract_seconds(summary: dict[str, Any]) -> float | None:
            if not isinstance(summary, dict):
                return None
            candidates = [
                summary.get("totalSleepSeconds"),
                summary.get("overallSleepSeconds"),
                summary.get("sleepDurationInSeconds"),
                summary.get("durationInSeconds"),
                summary.get("sleepTimeSeconds"),
                summary.get("duration"),
            ]
            for candidate in candidates:
                if candidate is not None:
                    return candidate
            minutes = summary.get("totalSleepMinutes") or summary.get("sleepTimeMinutes")
            if minutes is not None:
                try:
                    return float(minutes) * 60
                except (TypeError, ValueError):
                    return None
            return None

        for entry in payload:
            if not isinstance(entry, dict):
                continue
            metric_day = self._extract_date(entry)
            if not metric_day:
                nested_sources = [
                    entry.get("dailySleepDTO"),
                    entry.get("sleepSummary"),
                    entry.get("summary"),
                    entry.get("sleepSummaryDTO"),
                ]
                for nested in nested_sources:
                    if isinstance(nested, dict):
                        metric_day = self._extract_date(nested)
                        if not metric_day and nested.get("calendarDate"):
                            metric_day = self._parse_iso_date(str(nested.get("calendarDate")))
                        if metric_day:
                            break
            if not metric_day:
                for key in ("sleepDate", "calendarDate", "date", "day"):
                    if key in entry:
                        metric_day = self._parse_iso_date(str(entry[key]))
                        if metric_day:
                            break

            summaries = [
                entry,
                entry.get("sleepSummary"),
                entry.get("dailySleepDTO"),
                entry.get("summary"),
                entry.get("sleepSummaryDTO"),
            ]
            seconds = None
            for summary in summaries:
                seconds = extract_seconds(summary if isinstance(summary, dict) else {})
                if seconds is not None:
                    break

            if seconds is not None:
                store(seconds, metric_day)
                continue

            sleep_list = entry.get("sleepData") or entry.get("dailySleepDTOList")
            if isinstance(sleep_list, list):
                for sleep_entry in sleep_list:
                    sleep_day = metric_day
                    if isinstance(sleep_entry, dict):
                        if sleep_day is None:
                            sleep_day = self._parse_iso_date(
                                str(
                                    sleep_entry.get("sleepDate")
                                    or sleep_entry.get("calendarDate")
                                    or sleep_entry.get("date")
                                )
                            )
                        seconds = extract_seconds(sleep_entry)
                        if seconds is None:
                            seconds = extract_seconds(sleep_entry.get("sleepSummary") or {})
                    else:
                        continue
                    store(seconds, sleep_day)

        return result

    def _map_training_loads(self, payload: list[dict]) -> dict[date, float]:
        result: dict[date, float] = {}
        for entry in payload:
            metric_day = self._extract_date(entry)
            if not metric_day:
                continue
            value = entry.get("trainingLoad") or entry.get("load")
            summary = entry.get("summary") or entry.get("dailySummary") or {}
            if value is None and isinstance(summary, dict):
                value = summary.get("trainingLoad") or summary.get("load")
            if value is None:
                stats = entry.get("trainingStatus") or entry.get("trainingStats") or {}
                if isinstance(stats, dict):
                    value = stats.get("trainingLoad")
            if value is None:
                continue
            try:
                result[metric_day] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    def _extract_rhr_from_sleep(self, payload: list[dict]) -> dict[date, float]:
        result: dict[date, float] = {}
        for entry in payload:
            metric_day = self._extract_date(entry)
            if not metric_day:
                nested = entry.get("dailySleepDTO") or entry.get("summary") or {}
                if isinstance(nested, dict):
                    metric_day = self._extract_date(nested)
                if not metric_day and isinstance(nested, dict) and nested.get("calendarDate"):
                    metric_day = self._parse_iso_date(str(nested.get("calendarDate")))
            if not metric_day:
                continue
            candidates = [
                entry.get("restingHeartRate"),
                entry.get("avgHeartRate"),
            ]
            if isinstance(entry.get("dailySleepDTO"), dict):
                dto = entry["dailySleepDTO"]
                candidates.extend(
                    [
                        dto.get("restingHeartRate"),
                        dto.get("avgHeartRate"),
                    ]
                )
            value = next((c for c in candidates if c is not None), None)
            if value is None:
                continue
            try:
                result[metric_day] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    def _aggregate_activity_totals(self, activities: list[dict[str, Any]]) -> dict[date, dict[str, float]]:
        totals: dict[date, dict[str, float]] = {}
        for activity in activities:
            metric_day = self._parse_activity_date(activity)
            if metric_day is None:
                continue
            stats = totals.setdefault(
                metric_day,
                {"duration": 0.0, "distance": 0.0, "load": 0.0, "calories": 0.0},
            )
            duration = self._safe_float(activity.get("duration") or activity.get("summaryDTO", {}).get("duration"))
            distance = self._safe_float(activity.get("distance") or activity.get("summaryDTO", {}).get("distance"))
            load = self._extract_activity_training_load(activity)
            calories = self._safe_float(
                activity.get("calories") or activity.get("summaryDTO", {}).get("calories")
            )
            stats["duration"] += duration
            stats["distance"] += distance
            stats["load"] += load
            stats["calories"] += calories
        return totals

    async def _persist_daily_energy(
        self,
        user_id: int,
        start: date,
        end: date,
        energy_payload: list[dict[str, Any]],
        activity_totals: dict[date, dict[str, float]],
    ) -> None:
        energy_map = self._map_daily_energy(energy_payload)
        current = start
        while current <= end:
            entry = energy_map.get(current)
            source = "garmin"
            if entry is None:
                calories = activity_totals.get(current, {}).get("calories")
                if calories:
                    entry = {
                        "total": calories,
                        "active": calories,
                        "bmr": None,
                    }
                    source = "activities"
            if entry:
                stmt = select(DailyEnergy).where(
                    DailyEnergy.user_id == user_id,
                    DailyEnergy.metric_date == current,
                )
                result = await self.session.execute(stmt)
                record = result.scalar_one_or_none()
                if record is None:
                    record = DailyEnergy(
                        user_id=user_id,
                        metric_date=current,
                        total_kcal=entry["total"],
                        active_kcal=entry.get("active"),
                        bmr_kcal=entry.get("bmr"),
                        source=source,
                    )
                    self.session.add(record)
                else:
                    record.total_kcal = entry["total"]
                    record.active_kcal = entry.get("active")
                    record.bmr_kcal = entry.get("bmr")
                    record.source = source
                    record.ingested_at = eastern_now()
            current += timedelta(days=1)

    def _map_daily_energy(self, payload: list[dict[str, Any]]) -> dict[date, dict[str, float | None]]:
        result: dict[date, dict[str, float | None]] = {}
        for entry in payload:
            metric_day = self._extract_date(entry) or self._parse_iso_date(
                str(entry.get("calendarDate"))
            )
            if not metric_day:
                continue
            total = self._optional_float(
                entry.get("totalKilocalories") or entry.get("totalCalories")
            )
            if total is None or total <= 0:
                continue
            result[metric_day] = {
                "total": total,
                "active": self._optional_float(
                    entry.get("activeKilocalories") or entry.get("activeCalories")
                ),
                "bmr": self._optional_float(
                    entry.get("bmrKilocalories") or entry.get("bmrCalories")
                ),
            }
        return result

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_activity_training_load(activity: dict[str, Any]) -> float:
        candidates = [
            activity.get("trainingLoad"),
            activity.get("activityTrainingLoad"),
            activity.get("trainingEffect"),
            activity.get("load"),
        ]
        summary = activity.get("summaryDTO") or activity.get("activitySummary") or {}
        if isinstance(summary, dict):
            candidates.extend(
                [
                    summary.get("trainingLoad"),
                    summary.get("activityTrainingLoad"),
                    summary.get("trainingEffect"),
                ]
            )
        for candidate in candidates:
            try:
                if candidate is not None:
                    return float(candidate)
            except (TypeError, ValueError):
                continue
        duration = activity.get("duration") or 0.0
        try:
            return float(duration) / 60.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _impute_missing_series(series: dict[date, float], start: date, end: date) -> dict[date, float]:
        if not series:
            return {}

        result: dict[date, float] = dict(series)
        window: list[float] = []
        current = start
        while current <= end:
            raw = result.get(current)
            value = raw
            if value is None or value == 0:
                if window:
                    value = sum(window) / len(window)
                    result[current] = value
                else:
                    result[current] = value
            try:
                numeric = float(result[current]) if result[current] is not None else None
            except (TypeError, ValueError):
                numeric = None
            if numeric is not None and numeric != 0:
                window.append(numeric)
                if len(window) > 7:
                    window.pop(0)
            current += timedelta(days=1)
        return result

    @staticmethod
    def _hrv_summary(entry: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        if "hrvSummary" in entry and isinstance(entry["hrvSummary"], dict):
            return entry["hrvSummary"]
        if "summary" in entry and isinstance(entry["summary"], dict):
            return entry["summary"]
        if "hrvDailySummary" in entry and isinstance(entry["hrvDailySummary"], dict):
            return entry["hrvDailySummary"]
        return entry if "calendarDate" in entry or "lastNightAvg" in entry else None

    @staticmethod
    def _parse_activity_date(activity: dict) -> date | None:
        timestamp = activity.get("startTimeLocal") or activity.get("startTimeGMT")
        if not timestamp:
            return None
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.date()

    @staticmethod
    def _extract_date(entry: dict) -> date | None:
        for key in ("calendarDate", "calendar_date", "date", "summaryDate", "day"):
            if key in entry:
                parsed = MetricsService._parse_iso_date(entry[key])
                if parsed:
                    return parsed
        return None

    @staticmethod
    def _parse_iso_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
