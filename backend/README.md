# Backend

FastAPI application powering Garmin ingestion, data aggregation, and Vertex AI readiness insights.

## Layout

- `app/core` — config, logging, security helpers.
- `app/clients` — Garmin + Vertex AI wrappers.
- `app/db` — SQLAlchemy models, sessions, and repositories.
- `app/services` — ingestion and analytics services.
- `app/routers` — FastAPI routers for metrics, insights, and admin utilities.
- `app/workers` — background/scheduled jobs.
