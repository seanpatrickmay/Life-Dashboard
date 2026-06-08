# Serverless Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Life Dashboard from a single-EC2 docker-compose stack into a serverless AWS architecture (maximize Lambda; Fargate only for migrations + rare >15-min jobs; frontend on S3+CloudFront), authored in AWS CDK (Python) and proven end-to-end on LocalStack + Docker. No real-AWS deploy.

**Architecture:** One container image with four entrypoints (API via Mangum, scheduled jobs, SQS workers, Fargate migration). Runtime-agnostic adapters (BlobStore, JobQueue, KVStore, SecretsProvider, GarminTokenStore) selected by env so the EC2 path and the 417-test baseline keep working throughout (strangler-fig). CDK stacks: foundation, compute, edge, data_jobs. LocalStack (Community) emulates Lambda/APIGW/SQS/S3/EventBridge/Secrets/DynamoDB; Fargate validated via `docker run`; CloudFront via `cdk synth` + local reverse-proxy stand-in.

**Tech Stack:** Python 3.11 / FastAPI / async SQLAlchemy + asyncpg / Mangum / boto3 / moto / AWS CDK (aws-cdk-lib, Python) / aws-cdk-local + LocalStack / Docker / Neon Postgres / React+Vite frontend.

**Spec:** `docs/superpowers/specs/2026-06-04-serverless-migration-design.md`

---

## Conventions (read once before starting)

- **Working dir:** the worktree `.worktrees/serverless-migration`. Backend commands run from `backend/`.
- **Runtime/backend selection (env, all default to current behavior so tests + EC2 unchanged):**
  - `LD_BLOB_STORE` = `local` (default) | `s3`
  - `LD_JOB_QUEUE` = `inline` (default) | `sqs`
  - `LD_KV_STORE` = `memory` (default) | `dynamodb`
  - `LD_SECRETS` = `env` (default) | `secretsmanager`
  - `LD_GARMIN_TOKENS` = `db` (default — moves off filesystem for ALL runtimes) | `dir` (legacy fs)
  - `LD_RUNTIME` = `local` (default) | `aws` (sets sane bundles of the above; individual vars still override)
- **TDD always:** write the failing test, run it red, implement minimally, run it green, then commit.
- **Verification each task:** `python3 -m pytest -m "not live_llm" -q` must stay green (baseline 417 + new).
- **Commit cadence:** commit after each task; a phase ends with a phase-summary commit. Branch only: `feature/serverless-migration`. Never push, never `main`.
- **Lint/type before phase-end commit:** `ruff check app`, `black --check app`, `isort --check app`, `mypy app` (match existing config; fix regressions you introduce).
- **No new runtime deps without need.** Add to `backend/pyproject.toml`: `mangum`, `boto3` (runtime); `moto` (dev). CDK deps live in `infra/requirements.txt`, isolated from backend.

---

## Phase 0 — Scaffolding & Local Harness

Goal: an `infra/` CDK app that synths, a LocalStack+Postgres compose that boots, `make` targets, and the runtime-selection config — all without changing app behavior.

### Task 0.1: Add runtime/backend selection settings

**Files:**
- Modify: `backend/app/core/config.py` (add fields to the existing pydantic `Settings`)
- Test: `backend/tests/test_runtime_settings.py`

- [ ] **Step 1: Write the failing test**
```python
# backend/tests/test_runtime_settings.py
from app.core.config import Settings

def test_defaults_preserve_local_behavior():
    s = Settings()
    assert s.ld_blob_store == "local"
    assert s.ld_job_queue == "inline"
    assert s.ld_kv_store == "memory"
    assert s.ld_secrets == "env"
    assert s.ld_garmin_tokens == "db"

def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LD_BLOB_STORE", "s3")
    monkeypatch.setenv("LD_JOB_QUEUE", "sqs")
    s = Settings()
    assert s.ld_blob_store == "s3"
    assert s.ld_job_queue == "sqs"
```
- [ ] **Step 2: Run red** — `python3 -m pytest tests/test_runtime_settings.py -q` → FAIL (no such fields).
- [ ] **Step 3: Implement** — add to `Settings` (use existing pydantic-settings style; read the file first):
```python
    ld_runtime: str = Field(default="local", validation_alias="LD_RUNTIME")
    ld_blob_store: str = Field(default="local", validation_alias="LD_BLOB_STORE")
    ld_job_queue: str = Field(default="inline", validation_alias="LD_JOB_QUEUE")
    ld_kv_store: str = Field(default="memory", validation_alias="LD_KV_STORE")
    ld_secrets: str = Field(default="env", validation_alias="LD_SECRETS")
    ld_garmin_tokens: str = Field(default="db", validation_alias="LD_GARMIN_TOKENS")
    # AWS resource handles (only used when backend == aws variant)
    aws_region: str | None = Field(default=None, validation_alias="AWS_REGION")
    s3_asset_bucket: str | None = Field(default=None, validation_alias="LD_S3_ASSET_BUCKET")
    sqs_queue_url: str | None = Field(default=None, validation_alias="LD_SQS_QUEUE_URL")
    dynamodb_kv_table: str | None = Field(default=None, validation_alias="LD_DDB_KV_TABLE")
    secrets_name: str | None = Field(default=None, validation_alias="LD_SECRETS_NAME")
    aws_endpoint_url: str | None = Field(default=None, validation_alias="AWS_ENDPOINT_URL")  # LocalStack
```
  > Match the file's existing Field/alias convention exactly — if it uses `env=` not `validation_alias=`, follow that. Verify `ld_garmin_tokens` default of `db` does not break existing Garmin tests yet (it will be wired in Task 1.4; until then nothing reads it).
- [ ] **Step 4: Run green** — `python3 -m pytest tests/test_runtime_settings.py -q` → PASS.
- [ ] **Step 5: Full suite** — `python3 -m pytest -m "not live_llm" -q` → 417+2 pass.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat(config): add runtime/backend selection settings (defaults preserve behavior)"`

### Task 0.2: CDK app skeleton that synths empty stacks

**Files:**
- Create: `infra/app.py`, `infra/cdk.json`, `infra/requirements.txt`, `infra/.gitignore`
- Create: `infra/stacks/__init__.py`, `infra/stacks/foundation_stack.py`, `compute_stack.py`, `edge_stack.py`, `data_jobs_stack.py` (empty `Stack` subclasses)
- Create: `infra/README.md`

- [ ] **Step 1:** Install CDK toolchain (Node already present for frontend):
  - Run: `node --version` (expect v20+). `npm i -g aws-cdk aws-cdk-local 2>/dev/null || sudo npm i -g aws-cdk aws-cdk-local` ; `cdk --version`.
- [ ] **Step 2:** `infra/requirements.txt`:
```
aws-cdk-lib==2.150.0
constructs>=10.0.0,<11.0.0
cdk-nag==2.28.0
```
  Run: `python3 -m pip install -r infra/requirements.txt` (or a dedicated venv `infra/.venv`).
- [ ] **Step 3:** `infra/cdk.json`:
```json
{ "app": "python3 app.py", "context": { "@aws-cdk/core:bootstrapQualifier": "lifedash" } }
```
- [ ] **Step 4:** `infra/app.py`:
```python
#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.foundation_stack import FoundationStack
from stacks.compute_stack import ComputeStack
from stacks.edge_stack import EdgeStack
from stacks.data_jobs_stack import DataJobsStack

app = cdk.App()
env = cdk.Environment(region="us-east-1")
foundation = FoundationStack(app, "LifeDash-Foundation", env=env)
compute = ComputeStack(app, "LifeDash-Compute", foundation=foundation, env=env)
EdgeStack(app, "LifeDash-Edge", foundation=foundation, compute=compute, env=env)
DataJobsStack(app, "LifeDash-DataJobs", foundation=foundation, env=env)
app.synth()
```
  Each empty stack initially: `class FoundationStack(cdk.Stack): def __init__(self, scope, id, **kw): super().__init__(scope, id, **{k:v for k,v in kw.items() if k!='foundation' and k!='compute'})` — accept and ignore the extra kwargs until later tasks populate them. (Define clean `__init__` signatures: `FoundationStack(scope, id, *, env)`, `ComputeStack(scope, id, *, foundation, env)`, etc.)
- [ ] **Step 5:** `cd infra && cdk synth >/dev/null && echo SYNTH_OK` → expect `SYNTH_OK`.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "chore(infra): CDK Python skeleton synthesizes empty stacks"`

### Task 0.3: LocalStack + local Postgres compose and Make targets

**Files:**
- Create: `infra/local/docker-compose.localstack.yml`
- Create: `infra/local/bootstrap.sh`, `infra/local/.env.local`
- Modify: `Makefile` (add local-* targets)

- [ ] **Step 1:** `docker-compose.localstack.yml` — services:
  - `localstack` (`localstack/localstack:3`), env `SERVICES=lambda,apigateway,sqs,s3,events,secretsmanager,dynamodb,cloudformation,iam,sts,logs`, `LAMBDA_RUNTIME_EXECUTOR=docker`, volume docker.sock, port 4566.
  - `appdb` (`postgres:16-alpine`), `POSTGRES_PASSWORD`, `POSTGRES_DB=life_dashboard`, port 55432:5432.
- [ ] **Step 2:** `bootstrap.sh`: wait for `:4566/_localstack/health`, `cdklocal bootstrap`, export `AWS_ENDPOINT_URL=http://localhost:4566`, dummy AWS creds.
- [ ] **Step 3:** Makefile targets:
```
local-up:      ; docker compose -f infra/local/docker-compose.localstack.yml up -d
local-down:    ; docker compose -f infra/local/docker-compose.localstack.yml down -v
local-deploy:  ; cd infra && cdklocal deploy --all --require-approval never
local-test:    ; python3 -m pytest backend/tests/integration -q
```
- [ ] **Step 4:** `make local-up`, poll health, then `make local-down`. Expect clean boot/teardown.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "chore(infra): LocalStack + local Postgres harness and make targets"`

### Phase 0 gate
- [ ] `cdk synth` OK; `make local-up`/`down` OK; `python3 -m pytest -m "not live_llm" -q` green; update `CHANGELOG.md` (Phase 0 done); commit `docs: changelog — phase 0 scaffolding complete`.

---

## Phase 1 — Stateless-ify the App (runtime-agnostic adapters)

Goal: remove every local-disk/in-proc state dependency behind adapters, defaults unchanged.

### Task 1.1: BlobStore interface + local & S3 backends

**Files:**
- Create: `backend/app/storage/__init__.py`, `backend/app/storage/blob_store.py`
- Test: `backend/tests/test_blob_store.py`

- [ ] **Step 1: Write failing tests**
```python
# backend/tests/test_blob_store.py
import pytest
from app.storage.blob_store import LocalBlobStore, get_blob_store

@pytest.mark.asyncio
async def test_local_put_get_roundtrip(tmp_path):
    store = LocalBlobStore(root=tmp_path)
    await store.put("a/b.bin", b"hello", content_type="application/octet-stream")
    assert await store.get("a/b.bin") == b"hello"
    assert await store.exists("a/b.bin") is True

@pytest.mark.asyncio
async def test_local_missing_returns_none(tmp_path):
    store = LocalBlobStore(root=tmp_path)
    assert await store.get("nope") is None
    assert await store.exists("nope") is False

def test_factory_defaults_to_local(monkeypatch, tmp_path):
    monkeypatch.setenv("LD_BLOB_STORE", "local")
    assert get_blob_store().__class__.__name__ == "LocalBlobStore"

def test_factory_s3_when_selected(monkeypatch):
    monkeypatch.setenv("LD_BLOB_STORE", "s3")
    monkeypatch.setenv("LD_S3_ASSET_BUCKET", "b")
    assert get_blob_store().__class__.__name__ == "S3BlobStore"
```
- [ ] **Step 2: Run red** → FAIL (module missing).
- [ ] **Step 3: Implement** `blob_store.py`:
```python
from __future__ import annotations
import abc, asyncio, functools
from pathlib import Path
from app.core.config import settings

class BlobStore(abc.ABC):
    @abc.abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...
    @abc.abstractmethod
    async def get(self, key: str) -> bytes | None: ...
    @abc.abstractmethod
    async def exists(self, key: str) -> bool: ...
    async def presigned_get(self, key: str, *, expires: int = 3600) -> str | None:
        return None  # overridden by S3

class LocalBlobStore(BlobStore):
    def __init__(self, root: Path | str):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):  # path-traversal guard
            raise ValueError("invalid key")
        return p
    async def put(self, key, data, *, content_type=None):
        p = self._p(key); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    async def get(self, key):
        p = self._p(key); return p.read_bytes() if p.exists() else None
    async def exists(self, key):
        return self._p(key).exists()

class S3BlobStore(BlobStore):
    def __init__(self, bucket: str, *, client=None):
        import boto3
        self.bucket = bucket
        self._client = client or boto3.client("s3", endpoint_url=settings.aws_endpoint_url)
    async def _run(self, fn, *a, **k):
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *a, **k))
    async def put(self, key, data, *, content_type=None):
        kw = {"Bucket": self.bucket, "Key": key, "Body": data}
        if content_type: kw["ContentType"] = content_type
        await self._run(self._client.put_object, **kw)
    async def get(self, key):
        try:
            r = await self._run(self._client.get_object, Bucket=self.bucket, Key=key)
            return r["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None
    async def exists(self, key):
        try:
            await self._run(self._client.head_object, Bucket=self.bucket, Key=key); return True
        except Exception:
            return False
    async def presigned_get(self, key, *, expires=3600):
        return await self._run(self._client.generate_presigned_url, "get_object",
                               Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires)

@functools.lru_cache(maxsize=1)
def _local_default() -> LocalBlobStore:
    return LocalBlobStore(root="/tmp/life_dashboard_workspace_assets")

def get_blob_store() -> BlobStore:
    if settings.ld_blob_store == "s3":
        return S3BlobStore(bucket=settings.s3_asset_bucket or "")
    return _local_default()
```
- [ ] **Step 4: Run green** → PASS (S3 test only checks class; no network).
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(storage): BlobStore interface with local + S3 backends"`

### Task 1.2: Wire workspace asset upload/serve to BlobStore

**Files:**
- Modify: `backend/app/routers/workspace.py` (replace `/tmp` `write_bytes`/`FileResponse` with `get_blob_store()`; cite ~lines 40, 373, 387, 404-407 — read first)
- Test: `backend/tests/test_workspace_assets_blobstore.py` (and confirm existing `test_workspace_service.py` still passes)

- [ ] **Step 1: Failing test** — upload via the router/service writes through BlobStore and GET returns bytes; use a `LocalBlobStore(tmp_path)` injected/monkeypatched. Assert `WorkspaceAsset.storage_key` is set and bytes round-trip.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — replace `ASSET_STORAGE_ROOT` direct FS calls with `store = get_blob_store()`; on upload `await store.put(storage_key, content, content_type=...)`; on fetch, if S3 backend return a redirect to `presigned_get`, else stream `await store.get(...)`. Keep the 50MB cap and content-type validation.
- [ ] **Step 4: Run green** + full suite green.
- [ ] **Step 5: Commit** — `feat(workspace): serve/store assets via BlobStore (S3-capable)`

### Task 1.3: GarminTokenStore (DB-backed, encrypted)

**Files:**
- Create: `backend/app/models/garmin_token.py` (SQLAlchemy model: `user_id PK`, `token_blob bytea`, `updated_at`)
- Create: `backend/migrations/versions/<rev>_garmin_token_store.py` (Alembic)
- Create: `backend/app/services/garmin_token_store.py`
- Test: `backend/tests/test_garmin_token_store.py`

- [ ] **Step 1: Failing tests** — `save_dir(session, user_id, dir)` tars+encrypts the dir's files into the DB row; `hydrate_dir(session, user_id)` writes them to a fresh temp dir and returns its path; round-trip restores identical file bytes; missing user → `hydrate_dir` returns `None`. Use the existing Fernet crypto (`app/core/crypto.py`) — reuse `encrypt`/`decrypt` helpers (read that module first).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — `garmin_token_store.py`:
```python
import io, tarfile, tempfile
from pathlib import Path
from app.core.crypto import encrypt_bytes, decrypt_bytes  # adapt to actual fn names
from app.models.garmin_token import GarminToken

async def save_dir(session, user_id: int, token_dir: str) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(token_dir, arcname=".")
    blob = encrypt_bytes(buf.getvalue())
    # upsert GarminToken(user_id=user_id, token_blob=blob)

async def hydrate_dir(session, user_id: int) -> str | None:
    row = await session.get(GarminToken, user_id)
    if not row: return None
    out = tempfile.mkdtemp(prefix="garmin_tok_")
    data = decrypt_bytes(row.token_blob)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        tar.extractall(out)
    return out
```
  (Confirm crypto helper names; if module exposes a `Fernet`-based class, wrap it.)
- [ ] **Step 4: Run green.** Run the Alembic migration against a scratch SQLite/PG to confirm it applies.
- [ ] **Step 5: Commit** — `feat(garmin): DB-backed encrypted token store + migration`

### Task 1.4: Wire GarminClient to GarminTokenStore

**Files:**
- Modify: `backend/app/clients/garmin_client.py` (token load/dump path)
- Modify: callers that build `GarminClient` (metrics_service / garmin router) to pass a session + user_id so tokens can hydrate/persist
- Test: extend `backend/tests/test_garmin_crypto.py` / new `test_garmin_client_token_store.py`

- [ ] **Step 1: Failing test** — with `LD_GARMIN_TOKENS=db`, constructing/authenticating the client hydrates the tokens dir from DB (mock `garth.login`) and, after a successful login, persists via `save_dir`. With `LD_GARMIN_TOKENS=dir`, legacy filesystem path is used (existing behavior).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — when `settings.ld_garmin_tokens == "db"`: before `_load_tokens`, call `hydrate_dir(...)` → set `self.tokens_dir` to the temp dir (fallback to a fresh temp dir if no row). After `garth.dump(self.tokens_dir)` in `authenticate`, call `save_dir(...)`. Keep `dir` mode as the current code path. Make DB calls run via the injected async session (the client wrapper gains optional `token_store_ctx`). Keep it minimal & well-isolated.
- [ ] **Step 4: Run green** + full suite.
- [ ] **Step 5: Commit** — `feat(garmin): hydrate/persist tokens via DB store (removes /data/garmin dependency)`

### Task 1.5: KVStore interface + memory & DynamoDB backends

**Files:**
- Create: `backend/app/kv/__init__.py`, `backend/app/kv/kv_store.py`
- Test: `backend/tests/test_kv_store.py`

- [ ] **Step 1: Failing tests** — `MemoryKVStore`: `set(k,v,ttl)`, `get(k)`, TTL expiry (monkeypatch clock), `incr(k, window)` for rate-limit; factory returns Memory by default, Dynamo when `LD_KV_STORE=dynamodb`.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — `KVStore` ABC with `get/set/incr`; `MemoryKVStore` (dict + expiry timestamps, mirrors current OrderedDict cache semantics); `DynamoKVStore` (boto3 resource, `endpoint_url=settings.aws_endpoint_url`, item `{pk, value, expires_at}` with TTL attr; `incr` via `update_item ADD`). `get_kv_store()` factory.
- [ ] **Step 4: Run green.**
- [ ] **Step 5: Commit** — `feat(kv): KVStore with memory + DynamoDB backends`

### Task 1.6: Wire metrics cache + auth rate-limit to KVStore

**Files:**
- Modify: `backend/app/routers/metrics.py` (replace module `OrderedDict` `_cache` w/ KVStore, 5-min TTL)
- Modify: `backend/app/routers/auth.py` (replace `_rate_limit_store` dict w/ `kv.incr(ip, window=60)`)
- Test: extend `backend/tests/test_auth_router.py`; add `test_metrics_cache_kv.py`

- [ ] **Step 1: Failing tests** — auth still rate-limits after N attempts via KVStore (inject MemoryKVStore); metrics cache hit/miss path works through KVStore.
- [ ] **Step 2-4:** Run red → implement (default MemoryKVStore preserves current behavior) → green + full suite.
- [ ] **Step 5: Commit** — `refactor(api): back metrics cache + auth rate-limit with KVStore`

### Task 1.7: SecretsProvider (env + Secrets Manager)

**Files:**
- Create: `backend/app/core/secrets.py`
- Modify: `backend/app/core/config.py` (resolve secrets through provider at load when `LD_SECRETS=secretsmanager`)
- Test: `backend/tests/test_secrets_provider.py` (use `moto` `mock_aws`)

- [ ] **Step 1: Failing tests** — `EnvSecretsProvider.get_all()` returns os.environ subset; `SecretsManagerProvider.get_all()` reads a JSON secret (moto) and returns the dict; `load_secrets_into_env()` populates `os.environ` for keys not already set.
- [ ] **Step 2-4:** Run red → implement (boto3 secretsmanager `get_secret_value`, parse JSON, `setdefault` into env before `Settings()` is constructed) → green.
  > Integration point: handlers call `load_secrets_into_env()` once at cold start *before* importing settings-bound modules.
- [ ] **Step 5: Commit** — `feat(secrets): env + Secrets Manager provider`

### Task 1.8: JobQueue interface + inline & SQS backends + registry

**Files:**
- Create: `backend/app/jobs/__init__.py`, `backend/app/jobs/queue.py`, `backend/app/jobs/registry.py`
- Test: `backend/tests/test_job_queue.py`

- [ ] **Step 1: Failing tests** — register a handler by name; `InlineJobQueue.enqueue(name, payload)` runs it (async, in-proc — mirrors current BackgroundTasks); `SqsJobQueue.enqueue` calls `send_message` with JSON `{name,payload}` (moto SQS); `dispatch(message)` looks up + runs the registered handler. Unknown job name → raises.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**:
```python
# registry.py
_HANDLERS = {}
def job(name):
    def deco(fn): _HANDLERS[name] = fn; return fn
    return deco
def get_handler(name): 
    if name not in _HANDLERS: raise KeyError(f"no job {name}")
    return _HANDLERS[name]

# queue.py
class JobQueue(abc.ABC):
    @abc.abstractmethod
    async def enqueue(self, name: str, payload: dict) -> None: ...
class InlineJobQueue(JobQueue):
    async def enqueue(self, name, payload):
        import asyncio
        from app.jobs.registry import get_handler
        asyncio.create_task(get_handler(name)(payload))  # parity w/ current behavior
class SqsJobQueue(JobQueue):
    def __init__(self, queue_url, client=None):
        import boto3; self.q=queue_url
        self._c=client or boto3.client("sqs", endpoint_url=settings.aws_endpoint_url)
    async def enqueue(self, name, payload):
        import json, asyncio, functools
        await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(self._c.send_message, QueueUrl=self.q,
                                    MessageBody=json.dumps({"name":name,"payload":payload})))
async def dispatch(body: dict):
    from app.jobs.registry import get_handler
    await get_handler(body["name"])(body["payload"])
def get_job_queue():
    return SqsJobQueue(settings.sqs_queue_url) if settings.ld_job_queue=="sqs" else InlineJobQueue()
```
- [ ] **Step 4: Run green.**
- [ ] **Step 5: Commit** — `feat(jobs): JobQueue (inline + SQS) and handler registry`

### Task 1.9: Durable throttle (job_run table) + refactor refresh controllers

**Files:**
- Create: `backend/app/models/job_run.py` (model: `job_name PK`, `last_started_at`, `last_completed_at`, `running`, `last_error`)
- Create: Alembic migration for `job_run`
- Modify: `backend/app/workers/tasks.py` (controllers consult/update `job_run` for cooldown; enqueue work via JobQueue when `LD_JOB_QUEUE=sqs`, else current in-proc)
- Register the refresh + digest pipelines as jobs (`@job("visit_refresh")`, `@job("digest_refresh")`)
- Test: `backend/tests/test_refresh_controller_durable.py`

- [ ] **Step 1: Failing tests** — cooldown enforced via `job_run` row across two `request_refresh` calls (no in-memory reliance); when `LD_JOB_QUEUE=sqs`, `request_refresh` enqueues instead of `create_task` (assert SQS send via moto / injected queue).
- [ ] **Step 2-4:** Run red → implement (keep `RefreshJobStatus` shape identical so routers/responses unchanged; back the timestamps with `job_run`) → green + full suite.
- [ ] **Step 5: Commit** — `refactor(workers): durable throttle via job_run + queue-based dispatch`

### Task 1.10: Route ex-BackgroundTasks through JobQueue

**Files:**
- Modify call sites (read each first): `backend/app/routers/todos.py` (~54,87,193), `backend/app/routers/journal.py` (~56,71), `backend/app/services/async_ai_service.py` (~79), `backend/app/routers/_shared.py` (~31), workspace project-suggestion trigger
- Register the corresponding jobs in a new `backend/app/jobs/handlers.py` (`project_suggestions`, `todo_accomplishment`, `journal_summary`, `digest_enrich`)
- Test: extend `test_todos_router.py`, `test_journal_service.py`

- [ ] **Step 1: Failing tests** — creating a todo enqueues `project_suggestions` (inline default still runs it; assert side-effect unchanged). With `LD_JOB_QUEUE=sqs`, assert a message is enqueued and the handler is NOT run in-proc.
- [ ] **Step 2-4:** Run red → implement (replace `BackgroundTasks.add_task(fn,...)` / `asyncio.create_task(fn(...))` with `await get_job_queue().enqueue("name", payload)`; move `fn` bodies into registered handlers) → green + full suite.
- [ ] **Step 5: Commit** — `refactor(api): enqueue async work via JobQueue (SQS-ready, inline default)`

### Phase 1 gate
- [ ] Full suite green; lint/type clean; grep proves no remaining hard `/tmp`/`/data/garmin` writes outside adapters (`grep -rn "/data/garmin\|/tmp/life_dashboard" backend/app` → only inside LocalBlobStore default + legacy `dir` path). Update CHANGELOG. Commit `docs: changelog — phase 1 stateless-ify complete`. Run devils-advocate + security-reviewer agents on the Phase 1 diff; address findings.

---

## Phase 2 — AWS Handlers (`app/aws/`)

Goal: thin Lambda/Fargate entrypoints over the now-stateless app. Pure adapters, unit-tested with moto.

### Task 2.1: Lazy DB engine for Lambda pool profile

**Files:**
- Modify: `backend/app/db/session.py` (lazy `get_engine()`, env-driven pool; keep `engine`/`AsyncSessionLocal` names working)
- Test: `backend/tests/test_db_session_profile.py`

- [ ] **Step 1: Failing tests** — with `LD_RUNTIME=aws`, engine uses small pool (`pool_size<=2`) / NullPool; with default, current pool (5/5). Engine is created lazily and memoized (same object on second call).
- [ ] **Step 2-4:** Run red → implement `get_engine()` + `get_sessionmaker()` memoized; keep module-level `engine = get_engine()` lazily via `__getattr__` or convert imports — **carefully** preserve existing import sites (`from app.db.session import engine, AsyncSessionLocal`). Safest: keep eager `engine`/`AsyncSessionLocal` for local; add `init_engine()` that handlers call at cold start to rebuild with the AWS profile. → green + full suite.
- [ ] **Step 5: Commit** — `feat(db): lazy, env-profiled engine for Lambda connection strategy`

### Task 2.2: API handler (Mangum)

**Files:**
- Create: `backend/app/aws/__init__.py`, `backend/app/aws/bootstrap.py` (load secrets, init engine), `backend/app/aws/api_handler.py`
- Test: `backend/tests/test_api_handler.py`

- [ ] **Step 1: Failing tests** — `handler(event, ctx)` for an API-GW-v2 GET `/health` event returns `statusCode==200` body `{"status":"ok"}`; a sampled GET route matches direct-ASGI JSON (contract).
- [ ] **Step 2-4:** Run red → implement:
```python
# api_handler.py
from app.aws.bootstrap import cold_start
cold_start()                      # secrets + engine init (idempotent)
from app.main import app
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```
  Use the API-GW v2 event format. Add `mangum` to deps. → green + full suite.
- [ ] **Step 5: Commit** — `feat(aws): Mangum API Lambda handler + cold-start bootstrap`

### Task 2.3: Scheduled handler

**Files:**
- Create: `backend/app/aws/scheduled_handler.py` (`garmin_ingest(event,ctx)`, `rss_digest(event,ctx)`)
- Test: `backend/tests/test_scheduled_handler.py`

- [ ] **Step 1-4:** Failing test asserts `garmin_ingest` calls `MetricsService.ingest` + insight refresh within a fresh session (mock services); `rss_digest` calls `AIDigestService.run_pipeline`. Implement thin handlers running the async pipeline via `asyncio.run`, with `cold_start()`. Green + full suite.
- [ ] **Step 5: Commit** — `feat(aws): EventBridge scheduled handlers (garmin ingest, rss digest)`

### Task 2.4: SQS worker handler

**Files:**
- Create: `backend/app/aws/worker_handler.py`
- Test: `backend/tests/test_worker_handler.py`

- [ ] **Step 1-4:** Failing test feeds an SQS event (`Records[].body` JSON `{name,payload}`) and asserts `jobs.dispatch` runs the registered handler; malformed record → goes to batch-item-failure (return `batchItemFailures`). Implement idempotent dispatch via `asyncio.run`. Green.
- [ ] **Step 5: Commit** — `feat(aws): SQS worker handler with partial-batch-failure reporting`

### Task 2.5: Migration runner module

**Files:**
- Create: `backend/app/aws/migrate.py` (programmatic `alembic upgrade head`)
- Test: `backend/tests/test_migrate_module.py` (runs against scratch SQLite/PG; asserts `alembic_version` advances)

- [ ] **Step 1-5:** Failing test → implement using Alembic's `command.upgrade(Config, "head")` reading `alembic.ini` + sync URL (reuse entrypoint.sh URL-normalization logic). Green. Commit `feat(aws): programmatic migration runner for Fargate task`.

### Phase 2 gate
- [ ] Full suite green; lint/type clean; CHANGELOG; commit `docs: changelog — phase 2 handlers complete`; architecture-checker agent on `app/aws/` boundaries.

---

## Phase 3 — Container Image (one image, four entrypoints)

### Task 3.1: Lambda-base Dockerfile + entrypoint selector

**Files:**
- Create: `backend/Dockerfile.lambda`
- Create: `backend/lambda_entry.sh` (selects: if `$_HANDLER` set → exec RIC; if arg `migrate` → `python -m app.aws.migrate`; if `serve` → uvicorn)

- [ ] **Step 1:** `Dockerfile.lambda`:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main && pip install mangum boto3
COPY backend/app ${LAMBDA_TASK_ROOT}/app
COPY backend/migrations ${LAMBDA_TASK_ROOT}/migrations
COPY backend/alembic.ini ${LAMBDA_TASK_ROOT}/
CMD ["app.aws.api_handler.handler"]
```
- [ ] **Step 2:** Build: `docker build -f backend/Dockerfile.lambda -t lifedash-lambda .` → success.
- [ ] **Step 3: Commit** — `feat(docker): unified Lambda-base image (API/scheduled/worker/migrate)`

### Task 3.2: Smoke-invoke via Lambda RIE

- [ ] **Step 1:** Run image with the AWS Lambda Runtime Interface Emulator (built into the base image): `docker run -p 9000:8080 lifedash-lambda` (set required env: `LD_RUNTIME=aws`, dummy DB to a reachable local PG or a stubbed health path).
- [ ] **Step 2:** `curl -s "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"version":"2.0","rawPath":"/health","requestContext":{"http":{"method":"GET","path":"/health"}},"headers":{}}'` → body contains `"status":"ok"`. (Health route needs no DB; if cold_start requires DB, make health bypass engine init.)
- [ ] **Step 3:** Document the smoke command in `infra/local/README.md`. Commit `test(docker): RIE smoke invoke returns 200 for /health`.

### Task 3.3: Migration via docker run (Fargate parity)

- [ ] **Step 1:** With local PG up (`make local-up`), `docker run --network host -e DATABASE_URL_MIGRATIONS=postgresql://...@localhost:55432/life_dashboard -e ALLOW_LOCAL_DB=1 --entrypoint python lifedash-lambda -m app.aws.migrate` → migrations apply; `alembic_version` set.
  > Add `ALLOW_LOCAL_DB` escape hatch to the entrypoint's "refuse local Postgres" guard (simulation only).
- [ ] **Step 2:** Commit `test(docker): migration runner applies schema against local PG`.

### Phase 3 gate
- [ ] Image builds; RIE smoke green; migration smoke green; CHANGELOG; commit.

---

## Phase 4 — CDK Stacks

> Each task ends with `cd infra && cdk synth <StackName> >/dev/null && echo OK`. Use `aws_cdk` L2 constructs. Image via `aws_cdk.aws_ecr_assets.DockerImageAsset` (built from `backend/Dockerfile.lambda`) reused by all functions + the Fargate task.

### Task 4.1: FoundationStack
- [ ] S3 asset bucket (private, CORS for presigned), S3 frontend bucket (website/OAC), DynamoDB KV table (PK `pk`, TTL attr `expires_at`, on-demand), SQS queue + DLQ (redrive maxReceiveCount=5), Secrets Manager secret (`life-dashboard/app`), `DockerImageAsset`. Export handles. `cdk synth` OK. Commit.

### Task 4.2: ComputeStack
- [ ] `DockerImageFunction` x3 (API/scheduled/worker) from the shared asset with distinct `CMD` overrides (`cmd=[...]`) + env (`LD_RUNTIME=aws`, bucket/queue/table/secret names, `DATABASE_URL` from secret). API: `HttpApi` + `HttpLambdaIntegration` `$default`. Scheduled: `events.Rule` cron → targets. Worker: `SqsEventSource(queue)`. Least-priv grants (`bucket.grant_read_write`, `queue.grant_consume_messages`, `table.grant_read_write_data`, `secret.grant_read`). `cdk synth` OK. Commit.

### Task 4.3: EdgeStack
- [ ] CloudFront distribution: default origin = frontend S3 (OAC); additional behavior `/api/*` → `HttpOrigin(api gateway domain)`; ACM cert optional (default cloudfront cert for sim). `BucketDeployment` of `frontend/dist`. `cdk synth` OK. Commit.

### Task 4.4: DataJobsStack
- [ ] ECS cluster (no EC2; Fargate), `FargateTaskDefinition` with container from the shared `DockerImageAsset`, command `["python","-m","app.aws.migrate"]`, secret + DB env, CloudWatch logs. (No service — run on demand.) `cdk synth` OK. Commit.

### Task 4.5: cdk-nag
- [ ] Add `cdk_nag.AwsSolutionsChecks` aspect in `app.py`; `cdk synth` surfaces findings; suppress-with-justification or fix (e.g., bucket SSL-only, log retention, no wildcard IAM). Commit `chore(infra): cdk-nag posture pass`.

### Phase 4 gate
- [ ] `cdk synth --all` OK; cdk-nag acceptable; CHANGELOG; commit.

---

## Phase 5 — LocalStack End-to-End

> `backend/tests/integration/` holds these; mark `@pytest.mark.integration`; run via `make local-test` after `make local-up && make local-deploy`. External APIs (OpenAI/Garmin) are mocked at the service boundary.

### Task 5.1: Deploy stacks to LocalStack
- [ ] `make local-up`; `cd infra && cdklocal bootstrap && cdklocal deploy LifeDash-Foundation LifeDash-Compute --require-approval never`. `awslocal s3 ls`, `awslocal sqs list-queues`, `awslocal lambda list-functions` show resources. Capture API GW id/url. Commit `test(integration): localstack deploy of foundation+compute`.

### Task 5.2: API contract over API Gateway
- [ ] Integration test hits `http://<apigw>.execute-api.localhost.localstack.cloud:4566/health` → 200; a sampled GET route matches direct-ASGI. Commit.

### Task 5.3: Asset upload → S3
- [ ] Test uploads a workspace asset through the API; assert object exists in the LocalStack asset bucket and GET returns identical bytes. Commit.

### Task 5.4: Enqueue → SQS → worker → DB
- [ ] Test triggers an endpoint that enqueues a job; poll the worker's DB side-effect (or the queue drains + handler effect). Assert idempotency on duplicate delivery. Commit.

### Task 5.5: EventBridge → scheduled Lambda
- [ ] Manually `awslocal events put-events` (or invoke the scheduled fn) with external services mocked; assert DB side-effect. Commit.

### Task 5.6: Secrets at cold start
- [ ] Seed `awslocal secretsmanager create-secret`; assert a function resolves config from it (e.g., a route reflecting a secret-derived setting). Commit.

### Task 5.7: Frontend build + S3 + reverse-proxy routing
- [ ] `cd frontend && npm install && VITE_API_BASE_URL=/api npm run build`; upload `dist/` to LocalStack frontend bucket; start the local reverse-proxy stand-in (Caddy/nginx config in `infra/local/`) routing `/`→S3, `/api/*`→API GW; curl `/` returns `index.html`, `/api/health` returns 200. Commit.

### Task 5.8: Orchestrate `make local-test`
- [ ] One target brings up, deploys, runs the integration suite, tears down; green end-to-end. CHANGELOG. Commit `test(integration): full LocalStack e2e suite green`.

### Phase 5 gate
- [ ] `make local-test` green from clean; performance-profiler agent sanity-checks cold-start/pool; commit.

---

## Phase 6 — Docs, Runbook, Cost, Cleanup

### Task 6.1: Real-AWS deploy runbook
- [ ] `docs/deploy-serverless.md`: prerequisites (AWS acct, CDK bootstrap, ECR), secret population (`aws secretsmanager put-secret-value`), deploy order (Foundation→Compute→DataJobs→Edge), run migration Fargate task, Google OAuth redirect URI update for the CloudFront domain, ACM cert in us-east-1, post-deploy smoke checks, teardown. Commit.

### Task 6.2: Cost estimate
- [ ] `docs/serverless-cost-estimate.md`: per-service monthly estimate for single-user load (Lambda req+GB-s, API GW, CloudFront, S3, DynamoDB on-demand, SQS, Secrets Manager, ECS task-minutes, Neon unchanged). Note "no NAT/no VPC" savings. Commit.

### Task 6.3: Rollback + deprecate EC2 path + README
- [ ] `docs/serverless-rollback.md`; mark `docker/docker-compose.prod.yml` + `deploy/deploy_prod.sh` deprecated (comment header, not deleted — still functional fallback); update `README.md` Architecture/Operations to describe both paths. Commit.

### Task 6.4: Serverless CI workflow (manual)
- [ ] `.github/workflows/deploy-serverless.yml`: `workflow_dispatch` only (no auto-trigger), OIDC role, `cdk deploy --all`, run migration task. Leave `deploy-prod.yml` intact. Commit.

### Task 6.5: Final verification + adversarial review
- [ ] Run: full `pytest -m "not live_llm"`, `ruff/black/isort/mypy`, `cdk synth --all`, `make local-test`. All green.
- [ ] Dispatch in parallel: devils-advocate (whole-branch diff), security-reviewer (IAM, secrets, S3 public access, presigned URLs, CORS), quality-gate (tests/lint/type), architecture-checker (adapter boundaries). Address findings; re-verify.
- [ ] CHANGELOG final entry. Commit `docs: changelog — serverless migration complete`.

### Phase 6 gate (DONE)
- [ ] All success criteria in the spec satisfied. Present summary + deploy runbook to the user; use `superpowers:finishing-a-development-branch` to choose merge/PR/keep.

---

## Self-Review (run after writing; fix inline)

- **Spec coverage:** §3 abstractions → Tasks 1.1–1.10 + 2.1; one image/4 entrypoints → 2.2–2.5 + 3.1; networking/edge → 4.2/4.3; state hazards table → 1.1–1.10 (assets/Garmin/KV/secrets/queue/throttle) + Caddy→4.3; DB strategy → 2.1; IaC stacks → 4.1–4.5; local harness → 0.2/0.3/5.*; testing → every task TDD + Phase 5; backward compat → defaults + 6.3; runbook/cost/rollback → 6.1–6.3; success criteria → Phase 6 gate. No gaps found.
- **Placeholder scan:** code shown for all new modules; edits cite files + the concrete change + exact verify commands. `<rev>` in migration filenames is an Alembic-generated revision id (expected), not a placeholder.
- **Type/name consistency:** factories `get_blob_store/get_kv_store/get_job_queue`; `RefreshJobStatus` shape preserved; `cold_start()`/`init_engine()` referenced consistently across 2.1/2.2/2.3; `dispatch`/`get_handler`/`@job` consistent across 1.8/1.10/2.3.
