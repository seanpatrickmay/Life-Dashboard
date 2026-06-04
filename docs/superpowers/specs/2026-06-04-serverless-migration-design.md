# Serverless Migration Design — Docker/EC2 → Lambda + Fargate

- **Date:** 2026-06-04
- **Author:** Sean May (with Claude Code)
- **Branch:** `feature/serverless-migration` (worktree)
- **Status:** Approved (direction); driving an autonomous implementation loop

---

## 1. Goal

Refactor the Life Dashboard from a single-EC2 `docker-compose` stack into a serverless
AWS architecture that **maximizes Lambda** and uses **Fargate only for migrations and rare
>15-minute jobs**. The frontend moves to **S3 + CloudFront**. All Infrastructure-as-Code is
authored in **AWS CDK (Python)**. The entire system must be **proven locally** (LocalStack +
Docker) with automated tests. **Actual deployment to the real AWS account is out of scope** —
the deliverable stops at "works on LocalStack" plus a deploy runbook.

### Decisions locked (2026-06-04)

| Decision | Choice |
| --- | --- |
| Finish line | Refactor + IaC + local proof (LocalStack/Docker). No real-AWS deploy. |
| Lambda/Fargate split | Maximize Lambda; Fargate only for migrations + rare >15-min jobs. |
| IaC tool | AWS CDK in Python. |
| Frontend hosting | S3 + CloudFront. |

---

## 2. Current Architecture (as-is)

```
                          ┌─────────────────────────── EC2 instance ───────────────────────────┐
   Internet ── :443 ──►   │  Caddy (TLS, reverse proxy)                                          │
                          │     ├── /          → frontend container (static bundle, Caddy)       │
                          │     └── /api/*      → backend container :8000                         │
                          │  backend: FastAPI (uvicorn, 1 worker) + Alembic-on-start             │
                          │     volume: ../garmin → /data/garmin  (Garmin OAuth tokens)          │
                          │     /tmp/life_dashboard_workspace_assets  (uploads)                   │
                          └──────────────────────────┬──────────────────────────────────────────┘
                                                      │  asyncpg / psycopg2 (sslmode=require)
                                                      ▼
                                          Neon Postgres (external, managed)

  Deploy: GitHub Actions → AWS SSM Run Command → on EC2: git reset --hard + docker compose up --build
```

- **Backend:** FastAPI, async SQLAlchemy + asyncpg, ~102 endpoints across ~18 routers
  (auth, user, metrics, garmin, insights, news, ai_digest, assistant, nutrition, todos,
  projects, journal, workspace, calendar, admin, system, time, imessage).
- **Frontend:** React + Vite + styled-components, built to static assets, served by Caddy.
- **DB:** Neon Postgres (already external). The entrypoint actively **refuses** a local Postgres host.
- **AI:** OpenAI Responses API + `text-embedding-3-small` (embeddings via API, **not** local models).

### Workload inventory (drives the L/F split)

| Workload | Trigger today | Duration | Target |
| --- | --- | --- | --- |
| Web API (all routers) | HTTP | ms–seconds (LLM endpoints up to ~30s) | **API Lambda** |
| Garmin ingest + daily insight | `/api/admin/ingest`, refresh ping, launchd | ~15–45s | **Scheduled Lambda** (EventBridge) |
| RSS digest pipeline | stale check / manual | ~10–30s | **Scheduled Lambda** (EventBridge) |
| Digest LLM enrichment | manual | seconds–minutes (batchable) | **SQS worker Lambda** (chunked) |
| Project suggestions, todo accomplishments, journal summaries | `BackgroundTasks` / `asyncio.create_task` | ~1–15s each | **SQS worker Lambda** |
| Alembic migrations | container entrypoint | seconds | **Fargate one-shot task** |
| Embeddings backfill / rare >15-min batch | manual | minutes | **Fargate task** |
| iMessage sync, Claude Code sync, MCP server | launchd / stdio **on Sean's Mac** | minutes–hours | **Stay on the Mac** (call the API). Not AWS. |

> **Key scoping insight:** The "long-running / always-on" pieces that would normally force
> Fargate (iMessage sync reads `~/Library/Messages/chat.db`; Claude Code sync reads
> `~/.claude/`; MCP server is stdio for the IDE) are **client-side jobs on Sean's Mac**. They
> already call the deployed API or write to the DB. They remain local launchd/stdio jobs and
> are **not** migrated into AWS. This is what makes "maximize Lambda" feasible.

### State hazards (break in a stateless world)

| State | Today | Target |
| --- | --- | --- |
| Garmin OAuth tokens | `/data/garmin` volume (read-write, `garth.dump/login`) | **Postgres** table, encrypted with existing Fernet crypto |
| Workspace asset uploads | `/tmp/life_dashboard_workspace_assets` (≤50MB) | **S3** (presigned GET, streamed PUT) |
| Metrics cache | in-proc `OrderedDict`, 5-min TTL | **DynamoDB** (TTL) via KV adapter; in-memory adapter locally |
| Auth rate-limit | in-proc per-IP dict | **DynamoDB** (TTL) via KV adapter |
| Refresh-throttle (visit/digest cooldowns) | in-proc singleton timestamps | **Postgres** `job_run` table (durable, correctness-critical) |
| Background work | `BackgroundTasks` / `asyncio.create_task` | **SQS** enqueue → worker Lambda |
| Caddy TLS | Caddy `/data` volume | **CloudFront + ACM** |
| Secrets / config | `.env` file on the box | **Secrets Manager** (+ Lambda env injection) |
| Alembic migrations | entrypoint on every container start | **Fargate one-shot task** (decoupled from API cold start) |

---

## 3. Target Architecture (to-be)

```
                                  ┌──────────────── CloudFront (HTTPS, ACM) ─────────────────┐
   Internet ──►  CloudFront  ──►  │  default behavior   → S3 (frontend static bundle, OAC)   │
                                  │  /api/*  behavior   → API Gateway (HTTP API)              │
                                  └───────────────────────────────┬───────────────────────────┘
                                                                  ▼
                                                      API Gateway (HTTP API, $default)
                                                                  ▼
                                              ┌────────── API Lambda (container image) ──────────┐
                                              │  FastAPI app wrapped by Mangum (ASGI adapter)     │
                                              │  enqueues async work → SQS instead of in-proc     │
                                              └───┬───────────────┬───────────────┬──────────────┘
                                                  │ S3            │ Secrets Mgr   │ DynamoDB (KV/TTL)
                                                  ▼               ▼               ▼
                                            asset bucket      app secrets      cache/rate-limit
                                                  │
                                                  ▼  asyncpg (Neon, public + SSL — NO VPC)
                                          Neon Postgres (app data, sessions, garmin tokens, job_run)

   EventBridge (cron) ──► Scheduled Lambdas (same image, job handlers): garmin-ingest, rss-digest
   SQS (+DLQ)          ──► Worker Lambda    (same image, worker handler): suggestions, accomplishments,
                                                                          journal summaries, digest enrich
   ECS Fargate (one-shot, same image)      : alembic migrations; rare >15-min batch jobs
```

### 3.1 One image, four entrypoints

A **single container image** (built once) is reused everywhere. This minimizes drift between
runtimes and means "it built and tested once" applies broadly.

| Runtime | Entrypoint | Purpose |
| --- | --- | --- |
| API Lambda | `app.aws.api_handler.handler` (Mangum) | All HTTP endpoints |
| Scheduled Lambda(s) | `app.aws.scheduled_handler.{garmin,digest}` | EventBridge cron jobs |
| Worker Lambda | `app.aws.worker_handler.handler` | SQS-driven async work |
| Fargate task | `app.aws.migrate` (or existing `entrypoint.sh` path) | `alembic upgrade head`; batch runner |

The image is a **Lambda base image** (`public.ecr.aws/lambda/python:3.11`) with the Lambda
Runtime Interface Client. For Fargate, ECS overrides the container command to run the migration
module directly (the RIC is only used when invoked by Lambda). A thin entrypoint script selects
behavior so the same image runs in both contexts.

### 3.2 Networking & edge

- **No VPC** for Lambda. Neon is reachable over the public internet with TLS, so Lambdas run
  outside a VPC → no NAT Gateway ($$$), faster cold starts, simpler IaC. (If the DB ever moves
  to private RDS, revisit with VPC + RDS Proxy — explicitly out of scope.)
- **CloudFront** is the single public entry point. Default origin = S3 (frontend). A `/api/*`
  cache behavior forwards to API Gateway. This collapses the two origins under one domain, which
  **eliminates browser CORS** for the app's own calls and gives one ACM cert (us-east-1).
- **API Gateway HTTP API** (not REST API): cheaper, lower latency, native proxy to Lambda.

### 3.3 Database connection strategy (the #1 Lambda gotcha)

- Keep async SQLAlchemy + asyncpg. The engine is created **lazily per container** and reused
  across warm invocations (module-level singleton guarded for event-loop safety).
- Use a **small pool** (`pool_size` 1–2, `max_overflow` small) OR `NullPool`, and rely on
  **Neon's built-in connection pooler** (the pooled endpoint / PgBouncer). Driven by env so EC2
  keeps its current pool and Lambda uses the lean profile.
- `pool_pre_ping=True`, short `pool_recycle` to survive Neon idle disconnects.
- Migrations use sync psycopg2 in the Fargate task (unchanged logic).

### 3.4 Abstractions introduced (adapter pattern, env-selected)

Each abstraction has an **in-memory/local** implementation (keeps the 417 tests + EC2 path
working) and an **AWS** implementation (used in Lambda/Fargate). Selected by a `RUNTIME` /
backend env var.

| Interface | Local backend | AWS backend |
| --- | --- | --- |
| `BlobStore` (assets) | local filesystem (current `/tmp` path) | S3 |
| `JobQueue` (async work) | in-process executor (current behavior) | SQS publish |
| `KVStore` (cache, rate-limit) | in-memory dict | DynamoDB (TTL) |
| `SecretsProvider` | env / `.env` (current) | Secrets Manager (cached at cold start) |
| `GarminTokenStore` | DB row (works everywhere; replaces filesystem) | DB row |

> The Garmin token store moves to the DB **for all runtimes** (not env-switched) because the
> filesystem token store is the root cause of a state hazard and the DB works identically
> everywhere. Existing Fernet crypto (`app/core/crypto.py`) encrypts the blob.

---

## 4. Infrastructure as Code (AWS CDK, Python)

New top-level `infra/` directory, isolated from the backend package.

```
infra/
  app.py                      # CDK app entry
  cdk.json
  requirements.txt            # aws-cdk-lib, constructs (separate from backend deps)
  stacks/
    foundation_stack.py       # S3 (assets + frontend), DynamoDB, SQS+DLQ, Secrets Manager, ECR
    compute_stack.py          # Lambda functions (API/scheduled/worker), API Gateway, EventBridge
    edge_stack.py             # CloudFront + ACM + frontend bucket deployment
    data_jobs_stack.py        # ECS cluster + Fargate task def (migrations / batch runner)
  README.md                   # how to synth/deploy + LocalStack usage
```

- Stacks are **independently synthesizable** and ordered by dependency.
- All resource names/ARNs are wired through CDK references (no hardcoding).
- IAM is least-privilege per function (S3 to asset bucket only; SQS to its queue; Secrets read
  to its secret; DynamoDB to its table).

---

## 5. Local Simulation Harness ("simulate locally")

The crux of the deliverable: prove it works without touching real AWS.

```
infra/local/
  docker-compose.localstack.yml  # LocalStack + local Postgres (for the app DB) 
  bootstrap.sh                   # cdklocal bootstrap + deploy stacks into LocalStack
  seed.sh                        # seed secrets, create Neon-substitute DB schema (alembic)
  smoke/                         # integration tests hitting the LocalStack endpoints
```

- **LocalStack (Community)** emulates: Lambda, API Gateway (HTTP API), SQS, S3, EventBridge,
  Secrets Manager, DynamoDB. (**ECS/Fargate and CloudFront are LocalStack Pro — avoided.**)
- **Fargate migration task** is validated by running the **same image** via plain `docker run`
  against the local Postgres (this is exactly what ECS would do — `alembic upgrade head`). No
  Pro features needed.
- **CloudFront** cannot run on LocalStack Community. It is validated two ways: (1) `cdk synth`
  proves the distribution + behaviors + OAC synthesize correctly, and (2) a tiny local reverse
  proxy (Caddy/nginx, or the existing Vite proxy) stands in for the CloudFront routing rules
  (`/` → S3 website endpoint, `/api/*` → API Gateway) so the end-to-end browser path is
  exercised. The real CloudFront is a real-AWS deploy step (runbook).
- **App DB locally** = a Postgres container (Neon stand-in). The entrypoint's "refuse local
  Postgres" guard is relaxed behind an explicit `ALLOW_LOCAL_DB=1` flag for simulation only.
- **CDK → LocalStack** via `cdklocal` (`aws-cdk-local`) + `awslocal`.
- A `make local-up` / `make local-deploy` / `make local-test` flow drives the whole thing.

### Integration test coverage (LocalStack)

1. API Lambda reachable through API Gateway; representative endpoints across routers return 200
   and match direct-ASGI responses (contract check).
2. Auth/session flow works against the DynamoDB-backed rate-limit + Postgres sessions.
3. Workspace asset upload → lands in S3 bucket → GET returns it (presigned).
4. Enqueue path: an endpoint that used `BackgroundTasks` publishes to SQS; the worker Lambda
   consumes it and produces the expected DB side-effect.
5. EventBridge rule triggers the scheduled Lambda; (mocked external APIs) → DB side-effect.
6. Secrets resolve from Secrets Manager at cold start.
7. Migration: `docker run <image> migrate` against local Postgres brings schema to head.
8. Frontend: built bundle uploaded to the S3 (LocalStack) website bucket; the local reverse-proxy
   stand-in serves `index.html` from S3 and routes `/api/*` to API Gateway (CloudFront behavior
   parity). CloudFront itself validated via `cdk synth`.

---

## 6. Testing Strategy

- **Unit (pytest):** keep all 417 passing. Add tests for each new adapter (BlobStore, JobQueue,
  KVStore, SecretsProvider, GarminTokenStore) and each AWS handler (api/scheduled/worker) using
  moto or LocalStack + dependency injection. TDD for all new code.
- **Contract:** Mangum handler output equals direct ASGI output for a sampled set of routes.
- **Integration:** the LocalStack suite in §5.
- **Frontend:** `npm run build` succeeds; routing config (CloudFront behaviors / API base URL)
  validated.
- **Static quality:** `ruff`, `mypy`, `black --check`, `isort --check` per existing config; CDK
  `cdk synth` must succeed and (optionally) `cdk-nag` for security posture.

Every phase ends with: run tests/lint/typecheck → read output → fix → only then advance.
Adversarial/devil's-advocate + security review agents run after each substantive phase
(per project quality standards).

---

## 7. Backward Compatibility & Rollout

- The EC2 `docker-compose` path **keeps working throughout** via the local adapters. We do not
  delete it until the end; instead we mark it deprecated and provide the CDK path as the new
  default. This guarantees a working fallback and a non-destructive migration.
- The GitHub Actions `deploy-prod.yml` (SSM→EC2) is **left intact** and a new
  `deploy-serverless.yml` (CDK deploy, gated/manual) is added but **not wired to auto-run**
  (no real-AWS deploy in scope).

---

## 8. Phase Breakdown (the "parts" the loop iterates)

Detailed steps live in the implementation plan; this is the spine.

- **Phase 0 — Scaffolding & local harness.** `infra/` skeleton, CDK app that synths empty
  stacks, LocalStack docker-compose, local Postgres, `make` targets, CHANGELOG. *Gate: `cdk
  synth` + `localstack` boot + baseline tests green.*
- **Phase 1 — Stateless-ify the app (runtime-agnostic).**
  - 1a `BlobStore` + workspace assets → S3-capable (local fs default).
  - 1b `GarminTokenStore` → DB (encrypted); remove `/data/garmin` dependency.
  - 1c `KVStore` → DynamoDB-capable (cache, rate-limit; in-memory default).
  - 1d `SecretsProvider` → Secrets Manager-capable (env default).
  - 1e `JobQueue` + refactor `BackgroundTasks`/`asyncio.create_task` to enqueue; in-proc runner
       default; add `job_run` table for durable throttle. *Gate: 417 + new unit tests green.*
- **Phase 2 — AWS handlers.** `app/aws/` package: `api_handler` (Mangum), `scheduled_handler`,
  `worker_handler`, `migrate`. Unit-tested with moto. *Gate: handler unit tests green.*
- **Phase 3 — Container image.** Lambda-base Dockerfile + entrypoint selector; build locally;
  smoke-invoke the handler via the Lambda RIC emulator. *Gate: image builds; RIE invoke returns
  200 for a health route.*
- **Phase 4 — CDK stacks.** foundation → compute → edge → data_jobs. *Gate: `cdk synth` for all;
  cdk-nag acceptable.*
- **Phase 5 — LocalStack end-to-end.** `cdklocal` deploy; run the §5 integration suite;
  migration via `docker run`; frontend upload + serve. *Gate: integration suite green.*
- **Phase 6 — Docs, runbook, cost, cleanup.** Deploy runbook for real AWS, cost estimate,
  rollback, README updates, deprecate (not delete) EC2 path, `deploy-serverless.yml`. *Gate:
  docs complete; final full verification + review agents.*

---

## 9. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| LocalStack ≠ real AWS (esp. IAM, CloudFront) | Treat LocalStack as functional proof, not a deploy guarantee; runbook calls out manual verification. cdk-nag for IAM posture. |
| Lambda cold start with native deps | Container image (no zip limit); lean DB pool; lazy engine; keep image slim. |
| Neon connection exhaustion under concurrency | Use Neon pooled endpoint + NullPool/small pool in Lambda. Single-user app → low concurrency. |
| Mangum edge cases (streaming, large bodies) | No SSE/WebSockets in app (verified). Cap body size; asset upload via S3 presigned PUT if needed. |
| Background-task semantics change (at-least-once via SQS) | Make worker handlers idempotent; DLQ for poison messages. |
| Scope creep into real deploy | Hard line: stop at LocalStack + runbook (locked decision). |
| Worktree lacks `.env`/node_modules | `.env` copied; `npm install` run in Phase 0/5 as needed. |

---

## 10. Out of Scope

- Deploying to the real AWS account (credentials, live resources, cost).
- Migrating iMessage sync / Claude Code sync / MCP server into AWS (they stay on the Mac).
- Moving the DB off Neon / introducing RDS + VPC + RDS Proxy.
- Multi-region, blue/green, autoscaling tuning beyond sane defaults.
- Frontend feature/UX changes (hosting change only; no UI changes).

---

## 11. Success Criteria

1. The 417 baseline tests still pass; new unit tests for every adapter/handler pass.
2. `cdk synth` succeeds for all four stacks; cdk-nag posture acceptable.
3. `cdklocal` deploys the stacks to LocalStack; the integration suite (§5) passes end-to-end.
4. The single container image runs as: API Lambda, scheduled Lambda, SQS worker, and (via
   `docker run`) the Fargate migration — all exercised locally.
5. Frontend builds and is served via the local CloudFront/S3 path with `/api/*` routed to the API.
6. A complete, accurate **deploy runbook** + **cost estimate** + **rollback** doc exists.
7. The EC2 path still works (non-destructive migration).
```
