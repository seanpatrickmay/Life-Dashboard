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

## Phase 4 — CDK stacks ✅ (DONE)

All four stacks synthesize; cdk-nag clean (suppressed with justifications). ARM64/Graviton throughout.

- 4.1 `f5e8174` **FoundationStack**: asset S3 bucket (RETAIN, CORS GET), frontend S3 bucket (DESTROY+autodelete, OAI target), DynamoDB KV (PAY_PER_REQUEST, TTL `expires_at`), SQS queue (960s visibility) + DLQ (maxReceiveCount 5), Secrets Manager `life-dashboard/app` (placeholder; runbook populates), `DockerImageAsset` (`../backend`/`Dockerfile.lambda`, LINUX_ARM64). All exposed as `self.*`.
- 4.2 `7b63b37` **ComputeStack**: 4 `DockerImageFunction`s sharing the image via `from_ecr(repo, tag, cmd=[...])` (api 30s/512, garmin 300s/1024, digest 300s/512, worker 900s/1024); `HttpApi` ($default → api_fn); EventBridge crons (garmin daily 09:00 UTC, digest every 6h); `SqsEventSource(report_batch_item_failures=True, batch_size=10)`; least-priv IAM grants; full `LD_*` env (secrets via Secrets Manager at cold-start, NOT plaintext env; no reserved `AWS_REGION`).
- 4.3 `12c567b` **EdgeStack**: single CloudFront dist — default→S3 SPA (OAI; 2.150 predates L2 OAC), `/api/*`→API GW (`HttpOrigin`, CACHING_DISABLED, ALL_VIEWER_EXCEPT_HOST_HEADER); SPA fallback (403/404→/index.html); `BucketDeployment` with placeholder-source fallback when `frontend/dist` absent.
- 4.4 `4ac4e75` **DataJobsStack**: ECS Fargate migrate task (shared image, entrypoint override `python -m app.aws.migrate`), ARM64, no-NAT public VPC (Fargate reaches Neon via public IP). Synth-validated only (LocalStack Community has no ECS; Fargate proven via docker run in Phase 3).
- 4.5 `91e5e3b` **cdk-nag** `AwsSolutionsChecks`: 40 findings, all suppressed with specific reasons (WAF/flow-logs/rotation/OAC/access-logging = runbook hardening for a single-user app; IAM4/5 = CDK framework/grant wildcards scoped to single resources; APIG4 = auth is in-app). `synth` exits 0.

**Gate:** `cdk synth --all` OK; cdk-nag 0 unsuppressed errors.

**Next:** Phase 5 — deploy Foundation+Compute to LocalStack via `cdklocal`; integration suite (API via APIGW, asset→S3, enqueue→SQS→worker→DB, scheduled→DB, secrets); frontend build+S3+reverse-proxy. (Edge CloudFront + DataJobs ECS are Pro-only on LocalStack → synth-validated, runbook-deployed.)

---

## Phase 5 — LocalStack end-to-end ✅ (DONE)

**Gate:** core path proven live (5.1); 4 adapters proven vs real LocalStack (5.2, +1 real bug fixed); frontend hosting
proven (5.7); unit suite 589 passed + 23 integration (skip when LocalStack down). Full-loop-through-deployed-worker-Lambda
is covered in parts (SQS adapter live + worker handler moto-tested + DB connectivity live) and is a real-AWS verification
step in the runbook (container-image worker Lambda needs LocalStack Pro to deploy). **Next:** Phase 6 — docs/runbook/cost/cleanup.

- 5.1 `9c72e02` **CORE PROOF achieved.** Deployed to LocalStack and proved live: API GW → Lambda `/health` → 200;
  `/api/auth/me` → 200 `{"user":null}` = **full path Lambda cold-start → Secrets Manager → DATABASE_URL → asyncpg →
  `appdb:5432` (via `LAMBDA_DOCKER_NETWORK=life-dashboard-local_default`) → FastAPI query → response.** Secret seeded
  with in-network `appdb:5432` URL. Repeatable via `infra/local/smoke_deploy.sh`.
  - **MAJOR FINDING — LocalStack Community can't deploy the exact CDK stacks:** ECR push, container-image Lambdas
    (`PackageType=Image`), and **API Gateway v2 (HTTP API)** are all **Pro-only** (plus the known ECS/CloudFront Pro
    gaps). The smoke used a functionally-equivalent **ZIP Lambda (python3.12) + REST API v1** deployed by CLI to prove
    the flow. The **CDK stacks are real-AWS-ready as-is** (DockerImageAsset→real ECR, HttpApi→real HTTP API v2) — no
    code change needed for real deploy. Also: LocalStack on Apple Silicon spawns **x86_64** Lambda containers (real
    deploy uses arm64/Graviton — CI build platform must match the CDK `architecture`).
  - Fixes: `aws-cdk-local`→3.0.4 (compat with cdk 2.1126/Node 24); `ssm` added to LocalStack SERVICES (CDK bootstrap);
    stable compose network name.
- 5.2 `84e2a57` **23 adapter integration tests vs REAL LocalStack** (S3BlobStore, DynamoKVStore, SqsJobQueue,
  SecretsManagerProvider) — all pass; skip cleanly when LocalStack is down (unit suite stays 589 passed + 23 skipped).
  Wired to `make local-test`. **Found+fixed a REAL bug moto masked:** `DynamoKVStore.incr` stored the counter as a
  *String* then `ADD`'d a *Number* → real DynamoDB rejects (`ValidationException`); moto silently accepted. Fix: store
  `value` as Number, coerce `get()` return via `str()` (Decimal→str). **This would have broken the auth rate-limiter on
  real AWS** — exactly the moto≠LocalStack gap this task targeted.
- 5.7 `db0e174` **frontend build → S3 → reverse-proxy parity.** Built with `VITE_API_BASE_URL=` (empty) — correct: the
  axios client's route paths already include `/api`, so empty base → same-origin `/api/*` (CloudFront `/api/*` behavior
  parity); `/api` would double-prefix. Served from LocalStack S3 (200, index.html). `infra/local/Caddyfile.local`
  reverse proxy (`/`→S3, `/api/*`→API) committed; `/` leg proven e2e. Maps 1:1 to EdgeStack CloudFront behaviors.

**Phase 5 honesty boundary:** proven LIVE on LocalStack = app logic + Lambda runtime + Secrets + Postgres networking +
API routing + (5.2) the four AWS adapters. Synth-validated + real-AWS-ready + separately smoke-proven (RIE/docker-run in
Phase 3) = the exact container-image stacks, HTTP API v2, ECS Fargate migrate, CloudFront. Real `cdklocal deploy` of the
container stacks needs LocalStack Pro.

---

## Phase 6 — Docs, runbook, cost, cleanup ✅ (DONE)

- 6.1–6.4 `217b8ff` **docs**: `docs/deploy-serverless.md` (8-step real-AWS runbook with the exact Secrets Manager key list
  derived from `config.py`, incl. `APP_ENV=prod`→`*_PROD` OAuth, verified `/api/auth/google/callback`),
  `docs/serverless-cost-estimate.md` (~$1–4/mo single-user vs ~$10–15/mo EC2; no-NAT savings),
  `docs/serverless-rollback.md`; README "Deployment Paths" (serverless default + EC2 deprecated fallback); deprecation
  headers on `docker/docker-compose.prod.yml` + `deploy/deploy_prod.sh` (kept, not deleted); `deploy-serverless.yml`
  (`workflow_dispatch`-only; `deploy-prod.yml` untouched).
- 6.5 **final whole-system review** (security-reviewer + devils-advocate over the full `44fa789..HEAD` diff) → fixes
  `7bcb6ad`:
  - **CRITICAL: worker Lambda cold-start ordering** — `worker_handler.py` imported `app.jobs.handlers`/`app.workers.tasks`
    (→ `config.py` module-level `Settings()` requiring `DATABASE_URL`) BEFORE `cold_start()` loaded the secret → would
    crash every worker invocation on real AWS. Fixed by calling `cold_start()` at module level before those imports
    (mirrors api_handler). Regression test: subprocess + moto secret, `DATABASE_URL` removed from env → imports cleanly.
  - CI arm64: added QEMU + buildx to `deploy-serverless.yml` (ubuntu x86_64 runner builds the arm64 image).
  - Runbook env-wipe: removed the destructive `update-function-configuration --environment` (replaced whole env);
    moved `ADMIN_EMAIL`/`FRONTEND_URL` out of the CDK placeholder env INTO the Secrets Manager secret.
  - SQS `SQS_MANAGED` encryption (queue + DLQ); Fargate egress-only SG (443/5432) + output + runbook run-task update.
  - Health check → `/api/auth/me` (CloudFront rewrites `/health` + API 4xx to index.html — documented limitation).
  - HSTS header added; `Dockerfile.lambda` arch comment corrected (arm64); runbook "Hardening (post-MVP)" section.
  - **Security advisory (not a code defect):** the user's pre-existing `.env` (copied into the worktree in Phase 0)
    holds LIVE secrets (Neon pw, OpenAI key, Google OAuth secrets, Garmin pw + Fernet key). It is gitignored and was
    NEVER committed; the redundant worktree copy was deleted. Recommend rotating those values if any exposure is
    suspected (independent of this migration).

**Final state:** **590 unit tests + 23 LocalStack integration tests** pass; `cdk synth` all 4 stacks + cdk-nag clean;
one container image runs all 4 runtimes (RIE + docker-run + LocalStack ZIP smoke proven); frontend builds + serves;
runbook/cost/rollback complete; EC2 path intact as fallback.

---

## Success Criteria scorecard (spec §11)

1. **Baseline tests pass + adapter/handler tests** — ✅ MET (417 → **590** unit, +23 integration).
2. **`cdk synth` all 4 stacks + cdk-nag** — ✅ MET (clean, suppressions justified).
3. **`cdklocal` deploys stacks + integration suite e2e** — ⚠️ PARTIAL (documented): LocalStack **Community** can't deploy
   container-image Lambda / HTTP API v2 / ECR / ECS / CloudFront (all Pro). Proven instead: API+DB live via ZIP smoke,
   4 adapters via 23 live integration tests, frontend via Caddy proxy; CDK confirmed real-AWS-ready.
4. **One image runs all 4 runtimes** — ✅ MET (API via RIE 200; migrate via docker-run both paths; scheduled+worker
   handlers unit-tested + worker cold-start bug fixed; all via per-function CMD / entrypoint override).
5. **Frontend served via local CloudFront/S3 path, `/api/*` routed** — ✅ MET (build + S3 + Caddy parity).
6. **Deploy runbook + cost + rollback** — ✅ MET.
7. **EC2 path still works** — ✅ MET (untouched; deprecated-but-functional fallback).

**Verdict: deploy-ready for real AWS**, modulo the documented LocalStack-Pro fidelity caveats (run the runbook on a real
account to complete criterion 3 live).

---

## LIVE DEPLOYMENT — real AWS ✅ (2026-06-04)

Deployed to AWS account **650516323474** (us-east-1) via the `seanmay` CLI profile. **App is live at
https://d2txkslflj6cu8.cloudfront.net** and verified end-to-end.

- `cdk bootstrap` (qualifier `lifedash`) + `cdk deploy --all` → Foundation, Compute, DataJobs succeeded;
  the arm64 image built + pushed to ECR natively (Apple Silicon, no QEMU).
- **EdgeStack fix:** the initial Edge deploy failed — CDK 2.150's `BucketDeployment` custom-resource
  Lambda crashes (`urllib3` PEP 604 `X | Y` on its Python<3.10 runtime). **Removed `BucketDeployment`**;
  frontend now uploaded via `aws s3 sync` + CloudFront invalidation (runbook updated). Edge redeployed OK.
- Secrets Manager `life-dashboard/app` populated from `.env` (15 keys; `APP_ENV=prod`; `FRONTEND_URL` +
  `GOOGLE_REDIRECT_URI_PROD` → the CloudFront domain).
- **Fargate migrate task** ran against live Neon → `existing DB detected → upgrade head` (additive
  `garmin_token` + `job_run`), admin seeded (`maypatricksean@gmail.com`). Exit 0.
- **Verified:** `/health`→200, `/api/auth/me`→200 `{"user":null}` (via API GW AND via CloudFront `/api/*`);
  `/`→200 SPA; hashed assets→200.
- **REMAINING (user-only):** add `https://d2txkslflj6cu8.cloudfront.net/api/auth/google/callback` to the
  Google Cloud Console OAuth authorized redirect URIs (Google login won't complete until then).
- **Hardening reminders:** deployed with ROOT access keys (switch to a scoped IAM principal); rotate the
  `.env`-sourced secrets if exposure is suspected; see the runbook "Hardening (post-MVP)" section.

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
