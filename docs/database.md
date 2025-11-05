# Database Notes

- PostgreSQL schema features tables for users, activities, daily metrics, sleep sessions, training loads, ingestion runs, and Vertex insights.
- Time-series columns are indexed by date for efficient range queries.
- Activity rows retain raw Garmin payload in JSONB for traceability.
- Alembic migrations live under `backend/migrations/`.
