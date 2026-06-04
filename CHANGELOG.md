# Serverless Migration — Progress Log

Session memory for the Docker/EC2 → Lambda + Fargate migration. Survives context compaction.
Spec: `docs/superpowers/specs/2026-06-04-serverless-migration-design.md`
Plan: `docs/superpowers/plans/2026-06-04-serverless-migration.md`
Branch: `feature/serverless-migration` (worktree at `.worktrees/serverless-migration`, off `main`/HEAD 44fa789).

Baseline at start: **417 passed, 64 deselected** (live tests), 0 failures.

---

## Phase 0 — Scaffolding & local harness ✅ (DONE)

**What was done:**
- Task 0.1 (`e15ef27`): Added 12 runtime/backend selection settings to `backend/app/core/config.py`
  (`ld_runtime`, `ld_blob_store`, `ld_job_queue`, `ld_kv_store`, `ld_secrets`, `ld_garmin_tokens`,
  plus AWS handles). All default to current local behavior. Matches existing `Field(default, env=...)`
  convention. Tests: 419 passed.
- Task 0.2 (`a1b48c3`): CDK Python skeleton under `infra/` — `app.py` + 4 empty stacks
  (Foundation/Compute/Edge/DataJobs) with locked constructor signatures. aws-cdk-lib 2.150.0,
  CDK CLI 2.1126.0 (project-local via `infra/node_modules`, invoke with `npx cdk`), cdk-nag 2.28.0,
  venv at `infra/.venv` (cdk.json `app` = `.venv/bin/python3 app.py`). `cdk synth` → SYNTH_OK offline.
- Task 0.3 (`5066b2b`, rename `553f2d0`): LocalStack 3.8.1 + Postgres 16 compose at
  `infra/local/docker-compose.localstack.yml`; `infra/local/sim.env` (throwaway sim creds, renamed
  from `.env.local` to respect the env gitignore); `infra/local/bootstrap.sh`; Makefile targets
  `local-up/down/bootstrap/deploy/test`. Verified: LocalStack boots with lambda/apigateway/sqs/s3/
  events/secretsmanager/dynamodb/cloudformation/iam/sts/logs all `available`; appdb healthy; clean
  teardown.

**What was found:**
- Environment: Docker 28.5.1, Node 24, AWS CLI present, PyPI reachable. ECS/Fargate + CloudFront are
  LocalStack **Pro** — confirmed avoided (Fargate via `docker run`; CloudFront via `cdk synth` + local
  reverse proxy). LocalStack edition here is **community**.
- Backend `on_event("startup")` does an admin-user upsert on every start — must stay idempotent / be
  guarded for Lambda cold start (handled in Phase 2 bootstrap).

**Gate:** `cdk synth` OK; LocalStack up/down OK; backend 419 passed; lint/type untouched (no app code beyond config).

**Next:** Phase 1 — stateless-ify the app behind runtime-agnostic adapters (BlobStore→S3, GarminTokenStore→DB,
KVStore→DynamoDB, SecretsProvider, JobQueue→SQS, job_run throttle), defaults preserving EC2 behavior.

---

## Phase 1 — Stateless-ify the app (adapters) ✅ (DONE)

**Tests: 417 → 531 passing** (114 added across the phase), 0 failures.

**What was done (commits):**
- 1.1 `7a6cb5b` BlobStore (local + S3), path-traversal guarded.
- 1.2 `e27025d` workspace assets served via BlobStore (local bytes / S3 307 presigned), `storage_key` now a portable relative key.
- 1.3 `a09d367` + fix `1a4584d` GarminToken DB model + encrypted store; **migration drift-guard test pattern** established (apply real migration, assert column parity). Hardened `env.py` (VARCHAR(64) alembic_version).
- 1.4 `67fe1d1` GarminClient hydrates/persists tokens via DB through `get_client_ctx()`; legacy `dir` mode preserved; removes `/data/garmin` dependency.
- 1.5 `bc15497` KVStore (memory + DynamoDB, TTL, fixed-window incr).
- config fix `a74c896` **`validation_alias`** so `LD_*` env vars actually map (pydantic-settings v2 ignored `env=`).
- 1.6 `47fbf9b` metrics cache + auth rate-limit backed by KVStore (found+fixed: old rate-limiter was a silent no-op).
- 1.7 `cb460fb` SecretsProvider (env + Secrets Manager), env-wins, cold-start loader (wired in Phase 2).
- 1.8 `c6e2b50` JobQueue (inline + SQS) + handler registry.
- 1.9 `6366f0a` durable throttle `job_run` table; refresh/digest controllers DB-backed + queue-dispatched; reused drift-guard.
- 1.10 `d53aaf5` all `BackgroundTasks`/`asyncio.create_task` sites (todos, journal, insights, workspace×4, projects) → JobQueue with JSON payloads; handlers in `app/jobs/handlers.py` (imported in main.py).
- hardening `239410f` review fixes: tar `filter="data"`, `dispatch()` poison-msg handling, `is_relative_to` path guard, atomic DynamoDB `incr` (ConditionExpression), presigned `no-store`, **job_run stale-lock timeout (30min)**, Garmin persist-failure non-fatal, `populate_by_name=True`, DynamoKVStore singleton, `Settings()` consistency, +tests.

**Reviews run (3 parallel agents):** security-reviewer, devils-advocate, architecture-checker. Genuine findings fixed in `239410f`. Dismissed as false positive: "models missing created_at" (they inherit from Base; drift-guard tests prove parity). Deferred (single-user-acceptable): concurrent-Garmin token clobber, pre-existing metrics aggregation in handlers, cosmetic tz defaults.

**Gate:** 531 tests green; ruff 73 errors (baseline was 75 — net −2, project never ruff-clean, no CI lint gate); residual local-disk writes only the intended fallbacks (LocalBlobStore default root, legacy `garmin_tokens_dir`).

**Next:** Phase 2 — AWS handlers (`app/aws/`: lazy DB engine, Mangum api_handler, scheduled_handler, worker_handler, migrate).

---

## Phase 2 — AWS handlers ✅ (DONE)

**Tests: 531 → 589 passing.** New package `app/aws/`.

**What was done (commits):**
- 2.1 `1a3c527` lazy, env-profiled DB engine (`get_engine`/`get_sessionmaker`/`init_engine`, PEP 562 `__getattr__` backward-compat for `engine`/`AsyncSessionLocal`).
- 2.1b `d64a955` **NullPool** for the AWS profile (avoids asyncpg cross-loop connection reuse under per-invocation `asyncio.run`).
- 2.2 `5fa44de` `bootstrap.cold_start()` (secrets → runtime validation → init_engine) + Mangum `api_handler` (`lifespan="off"`); `_validate_runtime` HARD-raises if `LD_RUNTIME=aws` and `LD_JOB_QUEUE!=sqs`; `_client_ip` XFF helper.
- 2.3 `e4ffa6c` EventBridge `scheduled_handler` (garmin_ingest, rss_digest); extracted DRY `run_metrics_refresh` shared with the visit_refresh job.
- 2.4 `893636a` SQS `worker_handler` (single-loop batch, partial-batch-failure `{batchItemFailures}`, imports handler modules to populate the registry).
- 2.5 `11bcf1d` `migrate.py` runner — fresh DB → `create_all`+`stamp head`; existing → `upgrade head`; **seeds admin user** (no longer run under Mangum lifespan=off). Verified BOTH paths on real Postgres.
- hardening `4a080f1` (review): **lazy `get_sessionmaker()()` in worker chain** (tasks.py/handlers.py — fixes stale import-time engine capture before cold_start), dropped dead `pool_pre_ping` from NullPool branch, migrate guard against stamping a half-initialized DB.

**Review (devils-advocate):** confirmed solid — NullPool reasoning, `_COLD_STARTED` ordering, single-loop batch, engine safe to build outside a loop. Genuine bug (worker import-time session capture) fixed. Deferred (justified): import-time `cold_start` in api_handler (Lambda self-heals INIT on transient failure; fail-fast on config errors is desired); `_client_ip` XFF nuance (single-user-acceptable; CloudFront-always-present topology).

**Gate:** 589 tests green; `app/aws/` ruff clean.

**Next:** Phase 3 — container image (one Lambda-base image, four entrypoints: api/scheduled/worker/migrate).

---

## Phase 3 — Container image ✅ (DONE)

Commit `26f858a`. One Lambda-base image (`public.ecr.aws/lambda/python:3.11`), four entrypoints.

**What was done:**
- `backend/Dockerfile.lambda` (context=`backend/`): `poetry install --only main` into the base image, COPY `app`/`migrations`/`alembic.ini`, default `CMD ["app.aws.api_handler.handler"]`. `backend/.dockerignore` excludes tests/caches.
- **Regenerated `backend/poetry.lock`** — it was stale vs pyproject (boto3/mangum/moto added in Phases 1-2 weren't locked); the first build silently skipped app packages until relocked.
- Smoke-proven locally: (a) **RIE `/health` → `{"statusCode":200,"body":"{\"status\":\"ok\"}"}`** (cold start ~2.1s); (b) **migrate via `docker run --entrypoint python ... -m app.aws.migrate`** against local PG — fresh (create_all+stamp) then existing (upgrade no-op), both exit 0, `garmin_token`+`job_run` present. The entrypoint override is exactly what the Fargate task does.
- Image size ~1.47 GB (well under Lambda's 10 GB container limit).
- Entrypoint selection: API=default CMD; scheduled=`app.aws.scheduled_handler.{garmin_ingest,rss_digest}`; worker=`app.aws.worker_handler.handler`; migrate=entrypoint override `python -m app.aws.migrate`.

**Carry-forward to Phase 4:** built arm64 on this Mac — CDK `DockerImageAsset`/`platform` must pin the target arch (Lambda `architecture` + Fargate `runtimePlatform` must match the image). The migrate task env must include `DATABASE_URL`, `FRONTEND_URL`, `GARMIN_PASSWORD_ENCRYPTION_KEY` (Settings requires them) in addition to `DATABASE_URL_MIGRATIONS`.

**Gate:** image builds; RIE smoke 200; migrate docker both paths; 589 tests green.

**Next:** Phase 4 — CDK stacks (Foundation, Compute, Edge, DataJobs) + cdk-nag.

---

## Carry-forward / known issues (MUST address in later phases)

1. **Migration chain is NOT replayable on a fresh DB** (pre-existing, discovered in Task 1.3).
   `migrations/versions/20251217_initial_reset` calls `Base.metadata.create_all()` using *current*
   models, so a clean `alembic upgrade head` later fails at `20260323_todo_time_horizon`
   (`DuplicateColumn time_horizon`). Production Neon is unaffected (advanced incrementally), but the
   **Fargate migration runner (Task 2.5)** and **LocalStack e2e (Phase 5)** target FRESH DBs.
   **Decision for `app/aws/migrate.py`:** detect DB state — if `alembic_version` is empty/absent and no
   app tables exist → `Base.metadata.create_all()` + `alembic stamp head`; if an existing revision is
   present → `alembic upgrade head`. Do NOT rewrite the historical chain.
2. **`env.py` was extended** in Task 1.3 to pre-create `alembic_version` as `VARCHAR(64)` +
   `version_num_type=String(64)` (hardening for long revision ids / fresh-DB bootstrap). Keep; revisit
   if it interacts with the migrate runner.
3. **Model/migration drift guard pattern** (from Task 1.3 fix): new tables get a test that applies the
   real migration (not `create_all`) and asserts column parity with the model. Reuse for `job_run`
   (Task 1.9). ✅ done for both garmin_token and job_run.
4. **Auth rate-limit client IP behind API Gateway/CloudFront** (from Phase 1 review). `request.client.host`
   is the TCP peer = the API GW/CloudFront internal IP, not the real client → rate-limit becomes
   all-one-IP. **Phase 2 (`api_handler`/`auth.py`):** derive client IP from the API GW event
   (`requestContext.http.sourceIp`) or trusted `X-Forwarded-For` (leftmost is client-spoofable; the
   correct value is N-from-right behind N trusted proxies). For single-user this is low-severity but wire
   it when the API GW context is concrete.
5. **`LD_RUNTIME=aws ⇒ LD_JOB_QUEUE=sqs` assertion** (from Phase 1 review — BLOCKING risk). InlineJobQueue
   uses `asyncio.create_task` (fire-and-forget) which is silently dropped under Lambda. **Phase 2
   `bootstrap.cold_start()`:** if `LD_RUNTIME=="aws"` and `LD_JOB_QUEUE!="sqs"`, raise at cold start
   (convert silent data-loss into a loud deploy failure). Likewise consider asserting `LD_BLOB_STORE=s3`,
   `LD_KV_STORE=dynamodb`, `LD_SECRETS=secretsmanager` under aws runtime. CDK must set all of these.
   ✅ DONE in Task 2.2 (`_validate_runtime` raises on LD_JOB_QUEUE!=sqs; warns on the others). Items 1 & 5 resolved.

### Phase 4 (CDK) requirements derived from Phase 2:
6. **Lambda env vars CDK MUST set** on all function (api/scheduled/worker) + the Fargate migrate task:
   `LD_RUNTIME=aws`, `LD_JOB_QUEUE=sqs`, `LD_BLOB_STORE=s3`, `LD_KV_STORE=dynamodb`, `LD_SECRETS=secretsmanager`,
   `LD_SECRETS_NAME=<secret>`, `LD_S3_ASSET_BUCKET`, `LD_SQS_QUEUE_URL`, `LD_DDB_KV_TABLE`, `AWS_REGION`.
   Also set `DATABASE_URL`/`ADMIN_EMAIL` as env (belt-and-suspenders; the lazy-session fix makes secrets-only also work,
   but env is simplest). Migrate task needs `DATABASE_URL_MIGRATIONS` (sync URL) + `LD_SECRETS*`.
7. **SQS event source mapping MUST enable `ReportBatchItemFailures`** (the worker returns `{batchItemFailures}`); set
   a DLQ with `maxReceiveCount` (~5). Otherwise partial-batch-failure is ignored and whole batches re-run.
8. **CloudFront topology is assumed** by `_client_ip` (rate limit) — keep CloudFront in front of API Gateway so the
   viewer IP reaches the app via XFF; rate-limit is best-effort for the single user regardless.
