# Deploy Runbook — Serverless (Lambda + Fargate)

> **This is the new default deploy path.** The legacy EC2 docker-compose path is
> deprecated but kept as a rollback fallback — see `docs/serverless-rollback.md`.

---

## Overview & Architecture

```
                          ┌──────────────── CloudFront (HTTPS, ACM) ──────────────────┐
  Internet ──►  CF  ──►  │  default /*    → S3 frontend bucket (private, OAI)         │
                          │  /api/*        → API Gateway HTTP API v2                   │
                          └──────────────────────────────┬─────────────────────────────┘
                                                         ▼
                                             API Gateway HTTP API ($default)
                                                         ▼
                                   ┌────── API Lambda (arm64 container) ──────┐
                                   │  FastAPI + Mangum ASGI adapter            │
                                   │  cold-start: secrets → DB engine init     │
                                   │  enqueues async work → SQS                │
                                   └──────┬────────────┬────────────┬──────────┘
                                     S3   │   DynamoDB │  Secrets   │
                                   assets │   KV/TTL   │  Manager   │
                                          │                         │
                                          └──── asyncpg (Neon, TLS) ┘
                                                Neon Postgres (shared DB)

  EventBridge cron ──► GarminFn  (arm64)  daily 09:00 UTC
  EventBridge rate ──► DigestFn  (arm64)  every 6 h
  SQS + DLQ       ──► WorkerFn  (arm64)  async job execution (batch_size=10, ReportBatchItemFailures)

  ECS Fargate (one-shot, arm64, same image)
    entry_point=["python"], command=["-m", "app.aws.migrate"]
    public VPC, no NAT, assignPublicIp=ENABLED → reaches Neon over internet
```

**One image, four entrypoints.** A single `backend/Dockerfile.lambda` image (Lambda base,
`public.ecr.aws/lambda/python:3.11`, arm64/Graviton) is pushed once to ECR and shared by all
four functions and the Fargate migrate task.

| Function | CMD / entrypoint | Timeout | Memory |
|---|---|---|---|
| `ApiFn` | `app.aws.api_handler.handler` | 30 s | 512 MB |
| `GarminFn` | `app.aws.scheduled_handler.garmin_ingest` | 300 s | 1024 MB |
| `DigestFn` | `app.aws.scheduled_handler.rss_digest` | 300 s | 512 MB |
| `WorkerFn` | `app.aws.worker_handler.handler` | 900 s | 1024 MB |
| Fargate migrate | `python -m app.aws.migrate` (entrypoint override) | — | 1024 MB |

---

## Prerequisites

1. **AWS account** with an IAM identity that has `AdministratorAccess` or equivalent.
2. **AWS CLI** configured (`aws configure` or `AWS_PROFILE` / env vars).
3. **OIDC trust** (for GitHub Actions deploy): create an OIDC provider for
   `token.actions.githubusercontent.com` and a role that trusts it; store the role ARN
   in the repo secret `AWS_DEPLOY_ROLE_ARN`.
4. **Node.js 18+** on the machine running CDK.
5. **Docker** running (CDK builds and pushes the container image during `cdk deploy`).
6. **Python 3.11+** and the CDK venv:
   ```bash
   cd infra
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
7. **CDK CLI** (project-local; invoke with `npx cdk`):
   ```bash
   cd infra && npm ci
   ```
8. **Neon Postgres database** already provisioned. You will need:
   - The async URL: `postgresql+asyncpg://user:pass@host/db?ssl=require`
   - The sync migration URL: `postgresql://user:pass@host/db?sslmode=require`
   - The Neon pooled endpoint URL is recommended for the async URL (PgBouncer).

---

## Architecture Note — arm64 / Graviton

The image is built for **`linux/arm64`** (Graviton). The CDK stack sets
`platform=ecr_assets.Platform.LINUX_ARM64` for the `DockerImageAsset`,
`architecture=ARM_64` for all Lambda functions, and
`cpu_architecture=CpuArchitecture.ARM64` for the Fargate task.

Any machine running `cdk deploy` (including CI) must be able to build `linux/arm64`
images. On Apple Silicon this happens natively. On x86_64 CI:

```bash
docker buildx create --use   # enable multi-platform builds
# CDK's asset bundling will pass --platform linux/arm64 automatically
```

**LocalStack Community note:** the local smoke harness (`make local-up` / `bash
infra/local/smoke_deploy.sh`) uses a ZIP Lambda on `python3.12 x86_64` because
LocalStack Community does not support ECR push, container-image Lambda, or HTTP API v2.
The CDK stacks deploy the real arm64 container image and HTTP API v2 against real AWS
without any code change.

---

## Step-by-Step Deploy (real AWS)

All CDK commands run from the `infra/` directory with the venv activated:

```bash
cd infra
source .venv/bin/activate
```

### Step 1 — Bootstrap CDK (once per account/region)

The `cdk.json` sets bootstrap qualifier `lifedash`, so use the matching qualifier:

```bash
npx cdk bootstrap \
  --qualifier lifedash \
  aws://ACCOUNT_ID/us-east-1
```

This creates the CDK staging bucket (`cdk-lifedash-assets-ACCOUNT-us-east-1`),
ECR repo, and CloudFormation execution role.

### Step 2 — Deploy Foundation

Foundation creates the ECR image asset (builds + pushes `backend/Dockerfile.lambda`),
the S3 buckets, DynamoDB table, SQS queue + DLQ, and an **empty** Secrets Manager
secret named `life-dashboard/app`.

```bash
npx cdk deploy LifeDash-Foundation
```

After this step, note the outputs:
- `LifeDash-Foundation.AssetBucketName`
- `LifeDash-Foundation.FrontendBucketName`
- `LifeDash-Foundation.KvTableName`
- `LifeDash-Foundation.JobQueueUrl`
- `LifeDash-Foundation.AppSecretArn`

### Step 3 — Populate the Secret

**This step must be done before deploying Compute, because Lambda cold-start reads the
secret.** The secret is JSON; populate all keys at once:

```bash
aws secretsmanager put-secret-value \
  --secret-id life-dashboard/app \
  --secret-string '{
    "DATABASE_URL":                    "postgresql+asyncpg://user:pass@pooler.neon.tech/db?ssl=require",
    "DATABASE_URL_MIGRATIONS":         "postgresql://user:pass@direct.neon.tech/db?sslmode=require",
    "ADMIN_EMAIL":                     "you@example.com",
    "FRONTEND_URL":                    "https://REPLACE_AFTER_EDGE_DEPLOY.cloudfront.net",
    "GARMIN_PASSWORD_ENCRYPTION_KEY":  "<Fernet key — python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\">",
    "OPENAI_API_KEY":                  "sk-...",
    "READINESS_ADMIN_TOKEN":           "<random token for /api/admin/ingest>",
    "GOOGLE_CLIENT_ID_PROD":           "<Google OAuth client id>",
    "GOOGLE_CLIENT_SECRET_PROD":       "<Google OAuth client secret>",
    "GOOGLE_REDIRECT_URI_PROD":        "https://REPLACE_AFTER_EDGE_DEPLOY.cloudfront.net/api/auth/google/callback",
    "GOOGLE_CALENDAR_REDIRECT_URI_PROD": "https://REPLACE_AFTER_EDGE_DEPLOY.cloudfront.net/api/calendar/google/callback",
    "GOOGLE_CALENDAR_TOKEN_ENCRYPTION_KEY": "<Fernet key for calendar tokens — may reuse Garmin key or generate separately>",
    "APP_ENV":                         "prod"
  }'
```

**Full key reference** (derived from `backend/app/core/config.py` `Settings`):

| Key | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Async DB URL (`postgresql+asyncpg://...?ssl=require`). Use Neon pooled endpoint. |
| `DATABASE_URL_MIGRATIONS` | Yes | Sync migration URL (`postgresql://...?sslmode=require`). Use Neon direct endpoint. |
| `ADMIN_EMAIL` | Yes | Admin user email address; the migrate task seeds this user. |
| `FRONTEND_URL` | Yes | CloudFront URL (e.g. `https://abc123.cloudfront.net`). Required by Settings. Update after Edge deploy. |
| `GARMIN_PASSWORD_ENCRYPTION_KEY` | Yes | Fernet key used to encrypt Garmin credentials in the DB. Generate once and keep safe. |
| `OPENAI_API_KEY` | No | OpenAI API key. Required for AI features; app starts without it but LLM endpoints fail. |
| `READINESS_ADMIN_TOKEN` | No | Bearer token for `/api/admin/ingest`. Set to a random string. |
| `GOOGLE_CLIENT_ID_PROD` | Yes | Google OAuth 2.0 client ID (production OAuth app). Required for login. |
| `GOOGLE_CLIENT_SECRET_PROD` | Yes | Google OAuth 2.0 client secret. |
| `GOOGLE_REDIRECT_URI_PROD` | Yes | Must match Google Cloud Console. Set to `https://<cloudfront>/api/auth/google/callback`. |
| `GOOGLE_CALENDAR_REDIRECT_URI_PROD` | No | Google Calendar OAuth redirect. Defaults to `<FRONTEND_URL>/api/calendar/google/callback` if omitted. |
| `GOOGLE_CALENDAR_TOKEN_ENCRYPTION_KEY` | No | Fernet key for Calendar token encryption. Required if Calendar integration is used. |
| `APP_ENV` | No | Set to `prod` so the app selects `*_PROD` OAuth credentials. Defaults to `local`. |
| `GARMIN_EMAIL` / `GARMIN_PASSWORD` | No | Garmin account credentials (CLI fallback for manual ingest). |
| `GARMIN_PASSWORD_ENCRYPTION_KEY_ID` | No | Key ID for key rotation. Omit unless rotating keys. |
| `GARMIN_PASSWORD_ENCRYPTION_KEY_FALLBACKS` | No | Comma-separated fallback Fernet keys for rotation. |

> **Note:** `FRONTEND_URL` and the `*_PROD` redirect URIs reference the CloudFront domain,
> which is not known until after Step 4. You can set placeholder values now and update the
> secret (plus update-function-configuration) after Step 4. See Step 7.

### Step 4 — Deploy Compute, DataJobs, Edge

```bash
npx cdk deploy LifeDash-Compute LifeDash-DataJobs LifeDash-Edge
```

Or deploy all at once (after Step 3):

```bash
npx cdk deploy --all --require-approval never
```

After this step, note the outputs:
- `LifeDash-Compute.HttpApiUrl` — the API Gateway endpoint (internal; fronted by CloudFront)
- `LifeDash-Edge.DistributionUrl` — the CloudFront HTTPS URL (your app's public URL)
- `LifeDash-DataJobs.ClusterName`
- `LifeDash-DataJobs.MigrateTaskDefArn`
- `LifeDash-DataJobs.PublicSubnetIds`

### Step 5 — Run DB Migrations (Fargate one-shot)

Before the app can serve requests, the database schema must be at head. The Fargate task
reads secrets from Secrets Manager at startup (including `DATABASE_URL_MIGRATIONS`).

First, find the VPC and create a security group that allows all egress (so the Fargate
task can reach Neon over the public internet):

```bash
# Get the VPC that CDK created for the DataJobs stack
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=LifeDash-DataJobs" \
  --query "Vpcs[0].VpcId" \
  --output text)

# Create an egress-only security group in that VPC
SG_ID=$(aws ec2 create-security-group \
  --group-name lifedash-migrate-egress \
  --description "Fargate migrate task — all egress to reach Neon" \
  --vpc-id "$VPC_ID" \
  --query "GroupId" \
  --output text)

# Allow all outbound traffic (Neon Postgres on :5432 over TLS)
aws ec2 authorize-security-group-egress \
  --group-id "$SG_ID" \
  --protocol -1 \
  --cidr 0.0.0.0/0
```

Then run the migrate task using the CDK outputs:

```bash
CLUSTER=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-DataJobs \
  --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue" \
  --output text)

TASK_DEF=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-DataJobs \
  --query "Stacks[0].Outputs[?OutputKey=='MigrateTaskDefArn'].OutputValue" \
  --output text)

SUBNETS=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-DataJobs \
  --query "Stacks[0].Outputs[?OutputKey=='PublicSubnetIds'].OutputValue" \
  --output text | tr ',' ' ')

aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --count 1
```

**What it does:** loads secrets from Secrets Manager → detects fresh vs. existing DB →
either `Base.metadata.create_all() + alembic stamp head` (fresh) or `alembic upgrade head`
(existing) → idempotently upserts the admin user.

Monitor progress:

```bash
aws ecs describe-tasks --cluster "$CLUSTER" --tasks <task-arn>
# Or watch CloudWatch Logs: /ecs/LifeDash-DataJobs/migrate
```

### Step 6 — Build and Deploy the Frontend

The frontend must be built with **`VITE_API_BASE_URL` empty** (or unset). This tells the
Axios client to use same-origin `/api/*` routing — CloudFront's `/api/*` behavior then
forwards those requests to API Gateway without any cross-origin issues.

```bash
cd frontend
VITE_API_BASE_URL= npm run build
# Produces frontend/dist/
```

The `EdgeStack` `BucketDeployment` construct already syncs `frontend/dist` to the
frontend S3 bucket and invalidates CloudFront on every `cdk deploy LifeDash-Edge`.
You can re-run just the Edge stack:

```bash
cd infra
npx cdk deploy LifeDash-Edge
```

Or manually sync and invalidate:

```bash
FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-Foundation \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Origins.Items[*].DomainName, '${FRONTEND_BUCKET}')].Id" \
  --output text)

aws s3 sync frontend/dist "s3://${FRONTEND_BUCKET}" --delete
aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*"
```

### Step 7 — Post-Deploy Config: Update OAuth Redirect URIs

After Step 4 you have the CloudFront domain. Update the secret and Lambda env:

```bash
CF_URL=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-Edge \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionUrl'].OutputValue" \
  --output text)
# e.g. https://abc123.cloudfront.net

# 1. Update the secret with the real CloudFront URL
aws secretsmanager put-secret-value \
  --secret-id life-dashboard/app \
  --secret-string "$(aws secretsmanager get-secret-value \
    --secret-id life-dashboard/app \
    --query SecretString --output text | \
    python3 -c "import json,sys; d=json.load(sys.stdin); \
      d['FRONTEND_URL']='${CF_URL}'; \
      d['GOOGLE_REDIRECT_URI_PROD']='${CF_URL}/api/auth/google/callback'; \
      d['GOOGLE_CALENDAR_REDIRECT_URI_PROD']='${CF_URL}/api/calendar/google/callback'; \
      print(json.dumps(d))")"

# 2. Force a Lambda cold-start to pick up the new secret values
API_FN=$(aws cloudformation describe-stacks \
  --stack-name LifeDash-Compute \
  --query "Stacks[0].Outputs[?OutputKey=='ApiFnName'].OutputValue" \
  --output text)

aws lambda update-function-configuration \
  --function-name "$API_FN" \
  --environment "Variables={FRONTEND_URL=${CF_URL}}"
# Secrets Manager values are reloaded at cold-start, not via env; this FRONTEND_URL
# override ensures Settings() validates correctly even before the next cold-start.
```

3. **Update Google Cloud Console** — add the CloudFront URL to the authorized redirect URIs
   for your OAuth 2.0 client:
   - `https://<cloudfront>/api/auth/google/callback`
   - `https://<cloudfront>/api/calendar/google/callback`

### Step 8 — Verify

```bash
CF_URL=https://abc123.cloudfront.net   # your CloudFront URL

# Health endpoint (no DB)
curl -s "${CF_URL}/health"
# → {"status":"ok"}

# Auth endpoint (DB-backed)
curl -s "${CF_URL}/api/auth/me"
# → {"user":null}

# Load the SPA
open "$CF_URL"
# → React app loads; Google login should work
```

---

## Local Simulation (proven without real AWS)

The full serverless path is proven locally using LocalStack Community + Docker.

### Start the local stack

```bash
make local-up        # starts LocalStack + appdb (Postgres) on Docker
```

### Smoke deploy (API + DB live on LocalStack)

```bash
bash infra/local/smoke_deploy.sh
```

This:
1. Runs DB migrations against the local Postgres (same `app.aws.migrate` code path).
2. Creates Foundation resources (S3, DynamoDB, SQS, Secrets Manager) via AWS CLI.
3. Builds a ZIP Lambda (python3.12, x86_64 — Community limit; see below).
4. Deploys a REST API Gateway v1 (Community limit; see below).
5. Seeds the secret with in-network DB URL.
6. Curls `/health` and `/api/auth/me` — both return 200.

### Adapter integration tests

```bash
make local-test
```

Runs 23 integration tests against real LocalStack (S3BlobStore, DynamoKVStore,
SqsJobQueue, SecretsManagerProvider). Tests skip cleanly when LocalStack is not running.

### Frontend local hosting

```bash
cd frontend && VITE_API_BASE_URL= npm run build
# Then start the Caddy proxy (mirrors CloudFront behaviors):
docker run --rm -p 8090:8090 \
  -v "$(pwd)/infra/local/Caddyfile.local:/etc/caddy/Caddyfile:ro" \
  --network life-dashboard-local_default \
  caddy:2
# → http://localhost:8090/  serves the SPA
# → http://localhost:8090/api/*  routes to LocalStack API Gateway
```

### LocalStack Community limits

The following are **Pro-only** features; the local harness works around them:

| Feature | Status | Workaround |
|---|---|---|
| ECR push | Pro only | ZIP Lambda for local smoke |
| Lambda container image (`PackageType=Image`) | Pro only | ZIP Lambda (python3.12) for local smoke |
| API Gateway v2 (HTTP API) | Pro only | REST API v1 for local smoke |
| ECS / Fargate | Pro only | `docker run --entrypoint python ... -m app.aws.migrate` for local migrate test |
| CloudFront | Pro only | `cdk synth` validation + Caddy reverse proxy for local frontend test |

**The real-AWS CDK stacks (DockerImageAsset + HttpApi + ECS Fargate) are correct as-is**
and require no changes for real deployment. The LocalStack smoke proves the application
logic and the four adapters; real-AWS validation is a deploy step.

### Tear down

```bash
make local-down
```

---

## Custom Domain and TLS (optional)

By default, the app is served at the auto-generated `*.cloudfront.net` domain.
To use a custom domain:

1. Request an ACM certificate in **us-east-1** (required for CloudFront):
   ```bash
   aws acm request-certificate \
     --domain-name dashboard.example.com \
     --validation-method DNS \
     --region us-east-1
   ```
2. Complete DNS validation (add the CNAME in your DNS provider).
3. Update `EdgeStack` to add the certificate ARN and domain aliases:
   ```python
   cf.Distribution(self, "Distribution",
       certificate=acm.Certificate.from_certificate_arn(self, "Cert", cert_arn),
       domain_names=["dashboard.example.com"],
       minimum_protocol_version=cf.SecurityPolicyProtocol.TLS_V1_2_2021,
       ...
   )
   ```
4. Re-deploy `LifeDash-Edge`.
5. Add a Route 53 alias record (or CNAME in external DNS) pointing to the CloudFront domain.
6. Update `FRONTEND_URL` and OAuth redirect URIs to the custom domain.
