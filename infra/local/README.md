# Local Development — Lambda Image & Smoke Tests

This document covers the unified Lambda container image: how to build it, how to smoke-test
the API handler via the Lambda Runtime Interface Emulator (RIE), and how to run the Fargate
migrate task locally.

---

## Build the image

Build context is `backend/`. Run from the repo root:

```bash
docker build -f backend/Dockerfile.lambda -t lifedash-lambda backend/
```

**Architecture note:** on Apple Silicon (arm64) this produces an `arm64` image. The real
Lambda/Fargate deploy must pin the platform to match the target architecture. Add
`--platform linux/amd64` (or `linux/arm64` for Graviton) to the build command in the Phase 4
CI pipeline / CDK asset bundling configuration.

---

## How the four entrypoints are selected

The image has a single default CMD (`app.aws.api_handler.handler`). Each function selects its
handler by overriding CMD; the migrate task overrides the entire entrypoint.

| Function | Mechanism | Value |
|---|---|---|
| API Lambda (Mangum) | Default CMD | `app.aws.api_handler.handler` |
| Garmin ingest (EventBridge) | CMD override | `app.aws.scheduled_handler.garmin_ingest` |
| RSS digest (EventBridge) | CMD override | `app.aws.scheduled_handler.rss_digest` |
| SQS worker | CMD override | `app.aws.worker_handler.handler` |
| Fargate migrate task | Entrypoint override | `python -m app.aws.migrate` |

In CDK (Phase 4), each Lambda function sets `handler:` to the appropriate dotted path. The
ECS task definition overrides the entrypoint with `["python", "-m", "app.aws.migrate"]`.

---

## Task 3.2 — RIE smoke-invoke the API handler

Start the container (the RIE is bundled in the base image and listens on port 8080):

```bash
docker run -d --name ld_rie -p 9000:8080 \
  -e DATABASE_URL='postgresql+asyncpg://u:p@localhost/db' \
  -e ADMIN_EMAIL='a@b.com' \
  -e FRONTEND_URL='http://x' \
  -e GARMIN_PASSWORD_ENCRYPTION_KEY='k' \
  -e OPENAI_API_KEY='k' \
  -e READINESS_ADMIN_TOKEN='t' \
  -e SESSION_SECRET='s' \
  lifedash-lambda
```

> `DATABASE_URL` only needs to be parseable — `create_async_engine` does not connect at
> import time. `/health` issues no DB query, so no real DB is required for this smoke test.
> `LD_RUNTIME` is intentionally not set so `_validate_runtime()` no-ops and SQS is not
> required.

Invoke GET /health (API Gateway HTTP API v2 event):

```bash
sleep 2
curl -s "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"version":"2.0","routeKey":"GET /health","rawPath":"/health","rawQueryString":"","headers":{"host":"x"},"requestContext":{"http":{"method":"GET","path":"/health","sourceIp":"1.2.3.4"}},"isBase64Encoded":false}'
```

Expected response: `{"statusCode": 200, "body": "{\"status\":\"ok\"}", ...}`

Clean up:

```bash
docker rm -f ld_rie
```

---

## Task 3.3 — Migrate runner via docker run (proves the Fargate path)

The `--entrypoint python ... -m app.aws.migrate` override is exactly what the ECS Fargate
one-shot task definition does — so this local test proves the Fargate migrate path without
needing ECS.

First, bring up the local Postgres (port 55432):

```bash
make local-up
```

On macOS, containers reach the host via `host.docker.internal`.

### First run (fresh DB): create_all + stamp head

```bash
docker run --rm --entrypoint python \
  -e DATABASE_URL_MIGRATIONS='postgresql://life:life@host.docker.internal:55432/life_dashboard' \
  -e DATABASE_URL='postgresql+asyncpg://life:life@host.docker.internal:55432/life_dashboard' \
  -e ADMIN_EMAIL='admin@example.com' \
  -e FRONTEND_URL='http://localhost:3000' \
  -e GARMIN_PASSWORD_ENCRYPTION_KEY='<key>' \
  lifedash-lambda -m app.aws.migrate
```

Expected output: `migrate: fresh DB detected → create_all + stamp head` then `migrate: complete — schema=created+stamped`.

### Second run (existing DB): upgrade head (no-op)

Run the same command again. Expected output: `migrate: existing DB detected → upgrade head`
then `migrate: complete — schema=upgraded`.

### Verify tables

```bash
docker exec life-dashboard-local-appdb-1 psql -U life -d life_dashboard -c "\dt" | grep -E "garmin_token|job_run"
```

Teardown:

```bash
make local-down
```

---

## Required environment variables

| Variable | Used by | Notes |
|---|---|---|
| `DATABASE_URL` | API Lambda, cold_start, Settings | `postgresql+asyncpg://...` |
| `DATABASE_URL_MIGRATIONS` | migrate task | sync `postgresql://...` (no +asyncpg) |
| `ADMIN_EMAIL` | all | admin user email |
| `FRONTEND_URL` | API Lambda | CORS / settings validation |
| `GARMIN_PASSWORD_ENCRYPTION_KEY` | API Lambda, migrate | required by Settings |
| `OPENAI_API_KEY` | API Lambda (optional) | can be a dummy value for smoke |
| `LD_RUNTIME` | bootstrap | omit (or set to `local`) to skip SQS validation |
