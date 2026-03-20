"""Metric ingestion and aggregation services."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from dateutil import parser
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.garmin_client import GarminClient
from app.services.garmin_connection_service import GarminConnectionService
from app.db.models.entities import DailyEnergy, GarminConnection
from app.db.repositories.activity_repository import ActivityRepository
from app.db.repositories.metrics_repository import MetricsRepository
from app.utils.timezone import EASTERN_TZ, ensure_eastern, eastern_now, eastern_today


class MetricsService:
    def __init__(self, session: AsyncSession, garmin: GarminClient | None = None) -> None:
        self.session = session
        self.garmin = garmin
        self.activity_repo = ActivityRepository(session)
        self.metrics_repo = MetricsRepository(session)

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {
            "activities": 0,
            "hrv_entries": 0,
            "rhr_entries": 0,
            "sleep_entries": 0,
            "training_load_entries": 0,
            "energy_entries": 0,
            "metric_changes": {},
        }

    # How many recent days are always fetched regardless of change detection.
    _FRESH_WINDOW_DAYS = 2

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
        start_date = eastern_today() - timedelta(days=lookback_days - 1)
        end_date = eastern_today()
        cutoff_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=EASTERN_TZ)

        if self.garmin is not None:
            garmin = self.garmin
        else:
            connection_service = GarminConnectionService(self.session)
            connection = await connection_service.get_connection(user_id)
            if not connection:
                logger.info("Skipping Garmin ingest for user {} (no connection).", user_id)
                return self._empty_summary()
            if connection.requires_reauth:
                logger.info("Skipping Garmin ingest for user {} (reauth required).", user_id)
                return self._empty_summary()
            try:
                garmin = await connection_service.get_client(user_id)
            except ValueError:
                await connection_service.mark_reauth_required(user_id, True)
                logger.warning(
                    "Skipping Garmin ingest for user {} because stored credentials could not be decrypted.",
                    user_id,
                )
                return self._empty_summary()
            # Release the read-only transaction before long-running Garmin API calls.
            await self.session.rollback()

        try:
            # --- Phase 1: Fetch activities + detect historical changes -------
            if activities is None:
                logger.info("Fetching Garmin activities since {}", cutoff_dt)
                activities = await asyncio.to_thread(garmin.fetch_recent_activities, cutoff_dt)
            activities = self._filter_recent_activities(activities, cutoff_dt)
            ingested = await self.activity_repo.upsert_many(user_id, activities)

            # Determine which date ranges actually need metric fetches.
            fresh_start = end_date - timedelta(days=self._FRESH_WINDOW_DAYS - 1)
            historical_dates = await self._detect_changed_historical_dates(
                user_id, activities, start_date, fresh_start - timedelta(days=1),
            )

            # --- Phase 2: Fetch metrics concurrently -------------------------
            hrv_payload, rhr_payload, sleep_payload, load_payload, energy_payload = (
                await self._fetch_metrics_concurrent(
                    garmin,
                    fresh_start=fresh_start,
                    end_date=end_date,
                    historical_dates=historical_dates,
                    start_date=start_date,
                    hrv_payload=hrv_payload,
                    rhr_payload=rhr_payload,
                    sleep_payload=sleep_payload,
                    load_payload=load_payload,
                    energy_payload=energy_payload,
                )
            )
        except Exception:  # noqa: BLE001
            if self.garmin is None:
                await GarminConnectionService(self.session).mark_reauth_required(user_id, True)
            raise

        if self.garmin is None:
            stmt = select(GarminConnection).where(GarminConnection.user_id == user_id)
            result = await self.session.execute(stmt)
            connection = result.scalar_one_or_none()
            if connection:
                connection.last_sync_at = eastern_now()
                connection.requires_reauth = False

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
        metric_changes: dict[date, set[str]] = defaultdict(set)

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
            _, changed_fields = await self.metrics_repo.upsert_daily_metric(
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
            if changed_fields:
                metric_changes[metric_day].update(changed_fields)

        await self.session.commit()
        return {
            "activities": ingested,
            "hrv_entries": len(hrv_payload),
            "rhr_entries": len(rhr_payload),
            "sleep_entries": len(sleep_payload),
            "training_load_entries": len(load_payload) if load_payload else sum(1 for v in activity_totals.values() if v.get("load") is not None),
            "energy_entries": len(energy_payload),
            "metric_changes": {
                metric_day.isoformat(): sorted(fields) for metric_day, fields in metric_changes.items() if fields
            },
        }

    async def _detect_changed_historical_dates(
        self,
        user_id: int,
        activities: list[dict[str, Any]],
        history_start: date,
        history_end: date,
    ) -> set[date]:
        """Compare fetched activities against DB to find dates with new uploads.

        Returns the set of *historical* dates (before the fresh window) that
        contain activities not yet in the database — e.g. from a late watch sync.
        """
        if history_start > history_end:
            return set()

        known_ids = await self.activity_repo.get_known_garmin_ids(user_id, history_start)
        changed_dates: set[date] = set()
        for payload in activities:
            garmin_id = payload.get("activityId")
            if garmin_id is None:
                continue
            if int(garmin_id) in known_ids:
                continue
            activity_date = self._parse_activity_date(payload)
            if activity_date and history_start <= activity_date <= history_end:
                changed_dates.add(activity_date)

        if changed_dates:
            logger.info(
                "[garmin] detected {} historical dates with new activities: {}",
                len(changed_dates),
                sorted(changed_dates),
            )
        else:
            logger.debug("[garmin] no new historical activities detected, skipping historical metric fetch")
        return changed_dates

    async def _fetch_metrics_concurrent(
        self,
        garmin: GarminClient,
        *,
        fresh_start: date,
        end_date: date,
        historical_dates: set[date],
        start_date: date,
        hrv_payload: list[dict[str, Any]] | None,
        rhr_payload: list[dict[str, Any]] | None,
        sleep_payload: list[dict[str, Any]] | None,
        load_payload: list[dict[str, Any]] | None,
        energy_payload: list[dict[str, Any]] | None,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Fetch all five metric types concurrently.

        The fresh window (today + yesterday) is always fetched.  Historical
        dates are only fetched for days where new activities were detected.
        If *all* payloads are pre-supplied (testing), no Garmin calls are made.
        """
        # Build the list of date ranges to fetch.  Always include the fresh
        # window; add contiguous spans around changed historical dates.
        ranges = self._build_fetch_ranges(fresh_start, end_date, historical_dates, start_date)
        logger.info("[garmin] fetch ranges: {}", [(s.isoformat(), e.isoformat()) for s, e in ranges])

        async def _gather_for_ranges(
            fetcher,
            existing: list[dict[str, Any]] | None,
        ) -> list[dict[str, Any]]:
            if existing is not None:
                return existing
            tasks = [
                asyncio.to_thread(fetcher, rng_start, rng_end)
                for rng_start, rng_end in ranges
            ]
            results = await asyncio.gather(*tasks)
            combined: list[dict[str, Any]] = []
            for batch in results:
                combined.extend(batch)
            return combined

        # Run all five metric fetches concurrently.
        hrv_result, rhr_result, sleep_result, load_result, energy_result = await asyncio.gather(
            _gather_for_ranges(garmin.fetch_daily_hrv, hrv_payload),
            _gather_for_ranges(garmin.fetch_daily_rhr, rhr_payload),
            _gather_for_ranges(garmin.fetch_sleep, sleep_payload),
            _gather_for_ranges(garmin.fetch_training_loads, load_payload),
            _gather_for_ranges(garmin.fetch_daily_energy, energy_payload),
        )
        return hrv_result, rhr_result, sleep_result, load_result, energy_result

    @staticmethod
    def _build_fetch_ranges(
        fresh_start: date,
        end_date: date,
        historical_dates: set[date],
        earliest: date,
    ) -> list[tuple[date, date]]:
        """Merge the fresh window with changed historical dates into contiguous spans."""
        # Start with all dates that need fetching.
        fetch_dates: set[date] = set()
        current = fresh_start
        while current <= end_date:
            fetch_dates.add(current)
            current += timedelta(days=1)
        fetch_dates.update(historical_dates)

        if not fetch_dates:
            return []

        # Collapse into contiguous ranges.
        sorted_dates = sorted(fetch_dates)
        ranges: list[tuple[date, date]] = []
        rng_start = sorted_dates[0]
        rng_end = sorted_dates[0]
        for d in sorted_dates[1:]:
            if d == rng_end + timedelta(days=1):
                rng_end = d
            else:
                ranges.append((rng_start, rng_end))
                rng_start = d
                rng_end = d
        ranges.append((rng_start, rng_end))
        return ranges

    def _filter_recent_activities(self, activities: list[dict[str, Any]], cutoff: datetime) -> list[dict[str, Any]]:
        entries: list[tuple[dict[str, Any], datetime | None]] = []
        dropped = 0
        for payload in activities:
            timestamp = payload.get("startTimeLocal") or payload.get("startTimeGMT")
            if not timestamp:
                entries.append((payload, None))
                continue
            try:
                parsed = parser.isoparse(timestamp)
                normalized = ensure_eastern(parsed)
            except (ValueError, TypeError):
                entries.append((payload, None))
                continue
            if normalized >= cutoff:
                entries.append((payload, normalized))
            else:
                dropped += 1
        if dropped:
            logger.debug("Dropped {} activities older than {}", dropped, cutoff)

        with_timestamps = [(payload, ts) for payload, ts in entries if ts is not None]
        without_timestamps = [payload for payload, ts in entries if ts is None]
        with_timestamps.sort(key=lambda item: item[1], reverse=True)
        limited: list[dict[str, Any]] = [payload for payload, _ in with_timestamps[:6]]
        if len(with_timestamps) > 6:
            logger.debug("Truncated {} activities to keep the latest 6 entries", len(with_timestamps) - 6)
        remaining_slots = max(0, 6 - len(limited))
        limited.extend(without_timestamps[:remaining_slots])
        return limited

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
