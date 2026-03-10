# Backend

FastAPI application powering Garmin ingestion, data aggregation, and OpenAI-backed readiness insights.

## Layout

- `app/core` — config, logging, security helpers.
- `app/clients` — Garmin + LLM API wrappers.
- `app/db` — SQLAlchemy models, sessions, and repositories.
- `app/services` — ingestion and analytics services.
- `app/routers` — FastAPI routers for metrics, insights, and admin utilities.
- `app/workers` — background/scheduled jobs.
- `mcp_server` — private MCP server for workspace, project, and task tools. See `mcp_server/README.md`.
