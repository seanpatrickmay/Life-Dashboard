# Operations

- **Manual Ingestion**: Hit `POST /api/admin/ingest` with header `X-Admin-Token` matching `READINESS_ADMIN_TOKEN` to force a data pull.
- **Scheduler**: APScheduler job runs once per day (default 05:00 local) to ingest metrics and refresh the Vertex insight.
- **Backups**: Snapshot the `pgdata` Docker volume regularly.
