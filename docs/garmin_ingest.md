# Garmin Ingest Notes

Internal notes for keeping the manual ingest pipeline predictable and reproducible. These capture the exact Garmin Connect API calls we rely on today and the minimum steps required to refresh data locally.

## 1. Authentication & Tokens

1. In the web app, connect Garmin from the User page. Credentials are stored encrypted and tokens are cached under `GARMIN_TOKENS_DIR/<user_id>`.
2. For CLI/manual ingest, you can still set:
   - `GARMIN_EMAIL`
   - `GARMIN_PASSWORD`
   - `GARMIN_TOKENS_DIR` (defaults to `~/.garminconnect`)
3. Run `scripts/manual_ingest.py` once interactively to seed tokens. The wrapper calls `Garmin.login(...)` and persists both OAuth tokens under the configured directory.
4. Subsequent runs re-use those tokens (no password/MFA needed). We call `Garmin.login(tokenstore=...)` so `display_name` is populated and REST endpoints that require `/.../{displayName}` URIs succeed.

If tokens ever expire, the user can re-auth in the UI or delete the directory and repeat the manual login.

## 2. Data we fetch (per metric)

| Metric | GarminConnect endpoint | python-garminconnect method | Cadence | Notes |
| --- | --- | --- | --- | --- |
| Activities | `/activitylist-service/activities/search/activities` | `get_activities(start, limit)` | Paged (100 per call) until cutoff | Used to upsert workouts + derive fallback training load/volume. |
| HRV | `/hrv-service/hrv/{date}` | `get_hrv_data(date)` | Once per day in lookback window | Returns `hrvSummary` + readings; we normalize to `calendarDate` and `lastNightAvg`. |
| Resting HR | `/userstats-service/wellness/daily/{displayName}` | `get_rhr_day(date)` | Once per day | Requires `display_name` from token profile. We map to `{"date": "...", "value": bpm}`. |
| Sleep | `/wellness-service/wellness/dailySleepData/{displayName}` | `get_sleep_data(date)` | Once per day | Provides raw + summary sleep seconds; doubles as fallback for resting HR if direct endpoint missing. |
| Training load (14d) | `/metrics-service/metrics/trainingstatus/aggregated/{date}` | `get_training_status(date)` | Once per day | Each response contains `acuteTrainingLoadDTO.dailyTrainingLoadAcute`. We pick the primary device entry and emit `{calendarDate, trainingLoad}`. |

We intentionally avoid deprecated helpers (`get_daily_summary`, `get_training_load`, etc.) because they are not implemented in the version of `python-garminconnect` we vendor. Every fetch now hits a real endpoint and produces usable payloads.

## 3. Manual ingest workflow

1. Ensure Postgres + backend services are reachable (Docker compose or local stack).
2. From repo root run:
   ```bash
   python3 scripts/manual_ingest.py
   ```
3. The script:
   - Authenticates once (tokens or password).
   - Fetches each dataset for the last 30 days using the endpoints above.
   - Logs sample counts so it’s obvious if an endpoint returned zero rows.
   - Upserts activities and daily metrics, then regenerates the Vertex insight for today.

## 4. Spot-checking endpoints

Use `scripts/debug_metrics.py` when you need to inspect raw responses. It runs the same client wrapper but dumps one JSON file with a day-by-day breakdown (HRV, RHR, sleep, training status). Handy when Garmin changes payloads: run it, attach the resulting file, and adjust the normalizers without spamming the production DB.

## 5. Minimizing API calls

- HRV, RHR, Sleep, and Training Status are only available per-day, so we loop once per calendar day. There are no redundant fallback calls anymore.
- Activities still paginate (Garmin caps responses at 100 entries), but we stop paging as soon as we reach the cutoff date or receive a short page.
- Training load is taken directly from `acuteTrainingLoadDTO` so we no longer need to deduce it from activity duration unless Garmin omits the metric for that day.

Keep this doc close when touching the ingest pipeline; if a new metric is added, record the endpoint here before wiring it into `GarminClient`.
