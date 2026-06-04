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
