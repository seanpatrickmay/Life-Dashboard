"""Fetch Garmin daily data for debugging and store results locally."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sys.path.append(str(ROOT / "backend"))

from app.clients.garmin_client import GarminClient  # type: ignore  # noqa: E402
from app.utils.timezone import eastern_today  # type: ignore  # noqa: E402

LOOKBACK_DAYS = int(os.getenv("DEBUG_LOOKBACK_DAYS", 14))
OUTPUT_DIR = Path(os.getenv("DEBUG_OUTPUT_DIR", ROOT / "scripts" / "debug_output"))


def fetch_day(client: GarminClient, metric_day: date) -> Dict[str, Any]:
    result: Dict[str, Any] = {"date": metric_day.isoformat()}
    cdate = metric_day.strftime("%Y-%m-%d")

    def safe_call(name: str, func) -> None:
        try:
            result[name] = func(cdate)
        except Exception as exc:  # noqa: BLE001
            result[name] = {"error": str(exc)}

    safe_call("hrv", client.client.get_hrv_data)
    safe_call("resting_hr", client.client.get_rhr_day)
    safe_call("sleep", client.client.get_sleep_data)
    safe_call("training_status", client.client.get_training_status)

    return result


def main() -> None:
    client = GarminClient()
    client.authenticate()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = eastern_today()
    start_day = today - timedelta(days=LOOKBACK_DAYS - 1)

    payload = {
        "generated_at": today.isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "days": [fetch_day(client, start_day + timedelta(days=i)) for i in range(LOOKBACK_DAYS)],
    }

    timestamp = today.strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"garmin_debug_{timestamp}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"Debug data saved to {out_path}")


if __name__ == "__main__":
    main()
