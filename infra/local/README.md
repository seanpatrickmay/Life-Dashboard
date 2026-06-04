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

---

## Task 5.7 — Frontend build + S3 static hosting + CloudFront-parity reverse proxy

This section documents the local proof of the production hosting model: the React/Vite SPA
is built as static files, served from S3, and `/api/*` is routed to the API — all
same-origin.

### API base URL — why `VITE_API_BASE_URL` must be empty (or unset)

The axios client in `frontend/src/services/api.ts` uses `resolveApiBaseUrl()`:

```ts
const baseURL = resolveApiBaseUrl();   // reads VITE_API_BASE_URL at build time

export const api = axios.create({ baseURL, ... });
```

Every API call in the file uses route paths that **already include the `/api` prefix**:

```ts
api.get('/api/auth/me')
api.get('/api/garmin/status')
api.post('/api/todos', payload)
```

Axios concatenates `baseURL + path`. For same-origin routing the result must be `/api/...`
(relative). That requires `baseURL = ''`.

`resolveApiBaseUrl()` returns `''` only when:
- `VITE_API_BASE_URL` is unset or empty **and** `window.location.hostname` is NOT
  `localhost`/`127.0.0.1` — in which case it returns `location.origin` (which yields
  `https://myapp.com` + `/api/...` = same-origin). ✓ correct for prod.

For the **local static build** (served via the Caddy proxy on `:8090`, not `localhost:4173`
dev server), the same logic applies: when `VITE_API_BASE_URL` is empty and the page is
accessed via a non-localhost origin (e.g. the proxy), Axios routes to `origin + /api/...`.

**Build command:**

```bash
cd frontend && VITE_API_BASE_URL= npm run build
```

Or equivalently, omit `VITE_API_BASE_URL` entirely — the default code-path for
non-localhost origins is identical.

The built `dist/index.html` loads assets from absolute `/assets/...` paths — those are
served correctly by any origin-preserving proxy (Caddy, CloudFront).

### Step 1 — Build the frontend

```bash
# From repo root
cd frontend && VITE_API_BASE_URL= npm run build
# Produces frontend/dist/index.html + assets/
```

`frontend/dist` is gitignored and is never committed.

### Step 2 — Upload to LocalStack S3

Bring up LocalStack first:

```bash
make local-up
```

Create bucket, enable website hosting, upload:

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566

aws s3 mb s3://ld-frontend-test
aws s3api put-bucket-website --bucket ld-frontend-test \
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}'
aws s3api put-bucket-acl --bucket ld-frontend-test --acl public-read
aws s3 sync frontend/dist s3://ld-frontend-test --acl public-read
```

Verify directly (S3 website endpoint — returns `index.html` 200):

```bash
curl -si "http://ld-frontend-test.s3-website.localhost.localstack.cloud:4566/" | head -5
# → HTTP/1.1 200 OK  +  <!doctype html> ...
```

Path-style access also works:

```bash
curl -si "http://localhost:4566/ld-frontend-test/index.html" | head -5
# → HTTP/1.1 200 OK
```

### Step 3 — CloudFront-parity reverse proxy (Caddy)

`infra/local/Caddyfile.local` defines a Caddy server on `:8090` that mirrors the two
EdgeStack CloudFront behaviors:

| CloudFront behavior (prod) | Local proxy behavior |
|---|---|
| Default (`/*`) → S3 website origin | `/` → LocalStack S3 bucket website |
| `/api/*` → API GW execute-api origin | `/api/*` → LocalStack API Gateway |

Run the proxy (must be on the same Docker network as LocalStack):

```bash
docker run --rm -p 8090:8090 \
  -v "$(pwd)/infra/local/Caddyfile.local:/etc/caddy/Caddyfile:ro" \
  --network life-dashboard-local_default \
  caddy:2
```

Test the static leg:

```bash
curl -si http://localhost:8090/
# → HTTP/1.1 200 OK  Via: 1.1 Caddy  +  <!doctype html>...Life Dashboard
```

The `/api/*` leg routes to LocalStack API Gateway. After `make local-deploy` the Gateway
URL can be passed via `APIGW_URL`:

```bash
docker run --rm -p 8090:8090 \
  -e APIGW_URL=http://localstack:4566/restapis/<id>/local/_user_request_ \
  -v "$(pwd)/infra/local/Caddyfile.local:/etc/caddy/Caddyfile:ro" \
  --network life-dashboard-local_default \
  caddy:2
```

The `/api/*` routing rule is the key parity claim; the Gateway → Lambda path was proven
live in Task 5.1 (GET /health returned 200 via API GW → Lambda).

### Teardown

```bash
docker rm -f ld_caddy_proxy  # if running named
make local-down              # removes LocalStack + volumes
```
