"""Wrapper around python-garminconnect for easier dependency injection."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from garminconnect import Garmin
from loguru import logger

from app.core.config import settings


class GarminClient:
    def __init__(self) -> None:
        candidate_paths = [
            settings.garmin_tokens_dir_host,
            settings.garmin_tokens_dir,
        ]
        for path_str in candidate_paths:
            if not path_str:
                continue
            path = Path(path_str).expanduser()
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.debug("Unable to use Garmin tokens directory {}: {}", path, exc)
                continue
            self.tokens_dir = path
            break
        else:
            raise RuntimeError("Unable to determine a writable Garmin tokens directory.")
        self.client = Garmin()

    def authenticate(self) -> None:
        if self._load_tokens():
            return
        if not settings.garmin_email or not settings.garmin_password:
            raise RuntimeError("Garmin email/password missing and tokens unavailable")
        logger.info("Logging into Garmin with provided credentials")
        self.client = Garmin(email=settings.garmin_email, password=settings.garmin_password, return_on_mfa=True)
        res1, _ = self.client.login()
        if res1 == "needs_mfa":
            raise RuntimeError("Garmin MFA required. Please seed tokens manually.")
        self.client.garth.dump(self.tokens_dir)

    def _load_tokens(self) -> bool:
        try:
            self.client.garth.load(self.tokens_dir)
            self.client.get_user_profile()
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to load Garmin tokens: {}", exc)
            return False

    def fetch_recent_activities(self, cutoff: datetime) -> list[dict[str, Any]]:
        self.authenticate()
        activities: list[dict[str, Any]] = []
        start = 0
        while start < settings.garmin_max_activities:
            batch_size = min(settings.garmin_page_size, settings.garmin_max_activities - start)
            batch = self.client.get_activities(start, batch_size)
            if not batch:
                break
            activities.extend(batch)
            start += len(batch)
            last_activity = batch[-1]
            last_dt = self._parse_dt(last_activity.get("startTimeLocal") or last_activity.get("startTimeGMT"))
            if len(batch) < batch_size or (last_dt and last_dt <= cutoff):
                break
        return activities

    def fetch_daily_hrv(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        self.authenticate()
        results: list[dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            raw: Any | None = None
            if hasattr(self.client, "get_hrv_data"):
                try:
                    raw = self.client.get_hrv_data(current.isoformat(), current.isoformat())
                except TypeError:
                    raw = self.client.get_hrv_data(current.isoformat())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Garmin HRV fetch failed for {}: {}", current, exc)
                    raw = None
            daily_entries = self._normalize_hrv_payload(raw, current)
            if not daily_entries:
                logger.debug("Garmin HRV returned no data for %s", current)
            else:
                logger.debug("Garmin HRV normalized entries for %s: %s", current, len(daily_entries))
                results.extend(daily_entries)
            current += timedelta(days=1)
        logger.debug("Garmin HRV total entries=%s for range %s -> %s", len(results), start_date, end_date)
        return results

    def fetch_daily_rhr(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        self.authenticate()
        results = []
        current = start_date
        while current <= end_date:
            iso = current.isoformat()
            resting_value: float | None = None

            # Attempt known API variants in order of availability
            try:
                if hasattr(self.client, "get_daily_summary"):
                    summary = self.client.get_daily_summary(iso)
                    resting_value = self._extract_resting_hr(summary)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to fetch daily summary for {}: {}", iso, exc)

            if resting_value is None and hasattr(self.client, "get_daily_stats"):
                try:
                    stats = self.client.get_daily_stats(iso)
                    resting_value = self._extract_resting_hr(stats)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to fetch daily stats for {}: {}", iso, exc)

            if resting_value is None and hasattr(self.client, "get_wellness_data"):
                try:
                    wellness = self.client.get_wellness_data(iso, iso)
                    resting_value = self._extract_resting_hr(wellness)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to fetch wellness data for {}: {}", iso, exc)

            if resting_value is not None:
                results.append({"date": iso, "value": resting_value})
            current += timedelta(days=1)
        return results

    def fetch_training_loads(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        self.authenticate()
        if hasattr(self.client, "get_training_load"):
            try:
                load_data = self.client.get_training_load(start_date.isoformat(), end_date.isoformat())
                if isinstance(load_data, list):
                    return load_data
                if isinstance(load_data, dict):
                    for key in ("trainingLoadData", "trainingLoadDailySummaries"):
                        if key in load_data and isinstance(load_data[key], list):
                            return load_data[key]
                    return [load_data]
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to fetch training load: {}", exc)
        return []

    def fetch_sleep(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        self.authenticate()
        results = []
        current = start_date
        while current <= end_date:
            try:
                day_data = self.client.get_sleep_data(current.isoformat())
            except TypeError:
                day_data = self.client.get_sleep_data(current.isoformat(), current.isoformat())
            if day_data:
                results.append(day_data)
            current += timedelta(days=1)
        return results

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        from dateutil import parser

        try:
            return parser.isoparse(value)
        except ValueError:
            return None

    @staticmethod
    def _normalize_hrv_payload(payload: Any, fallback_date: date) -> list[dict[str, Any]]:
        """Normalize varying Garmin HRV payloads to a list of dict entries with calendarDate."""
        if payload is None:
            return []

        def ensure_date(entry: dict[str, Any]) -> dict[str, Any]:
            if "calendarDate" not in entry:
                entry["calendarDate"] = fallback_date.isoformat()
            summary = entry.get("hrvSummary") if isinstance(entry.get("hrvSummary"), dict) else None
            if summary and "calendarDate" not in summary:
                summary["calendarDate"] = fallback_date.isoformat()
            return entry

        if isinstance(payload, list):
            normalized: list[dict[str, Any]] = []
            for item in payload:
                if isinstance(item, dict):
                    normalized.append(ensure_date(dict(item)))
                else:
                    normalized.append(ensure_date({"value": item}))
            return normalized

        if isinstance(payload, dict):
            for key in ("hrvData", "hrvDailyData", "hrvDailySummaries", "hrvSummaries"):
                if key in payload and isinstance(payload[key], list):
                    return [ensure_date(dict(item)) for item in payload[key] if isinstance(item, dict)]
            return [ensure_date(dict(payload))]

        return [ensure_date({"value": payload})]

    @staticmethod
    def _extract_resting_hr(payload: Any) -> float | None:
        """Pull resting heart rate from various Garmin payload shapes."""
        if not payload:
            return None

        def _from_dict(data: dict[str, Any]) -> float | None:
            candidates = [
                data.get("restingHeartRate"),
                data.get("restingHeartRateInBeatsPerMinute"),
            ]
            summary = data.get("summary") or data.get("dailySummary") or {}
            candidates.extend(
                [
                    summary.get("restingHeartRate"),
                    summary.get("restingHeartRateInBeatsPerMinute"),
                ]
            )
            for candidate in candidates:
                if candidate is None:
                    continue
                try:
                    return float(candidate)
                except (TypeError, ValueError):
                    continue
            return None

        if isinstance(payload, dict):
            resting = _from_dict(payload)
            if resting is not None:
                return resting
            if "dailySummaries" in payload and isinstance(payload["dailySummaries"], list):
                for entry in payload["dailySummaries"]:
                    resting = _from_dict(entry)
                    if resting is not None:
                        return resting
        elif isinstance(payload, list):
            for entry in payload:
                if isinstance(entry, dict):
                    resting = _from_dict(entry)
                    if resting is not None:
                        return resting
        return None
