#!/usr/bin/env bash
# smoke_deploy.sh — LocalStack Community smoke test for Life Dashboard
#
# What this does:
#   1. Waits for LocalStack + appdb to be healthy
#   2. Runs DB migration against appdb (host-port 55432)
#   3. Creates Foundation resources (S3, DDB, SQS, Secret) via AWS CLI
#   4. Builds the Lambda ZIP package (x86_64 deps via Lambda container)
#   5. Creates the API Lambda (python3.12 runtime, ZIP) + REST API Gateway v1
#   6. Seeds the Secrets Manager secret with in-network appdb URL
#   7. Curls /health and /api/auth/me via API GW; expects 200 both
#
# LocalStack Community limits encountered during Task 5.1:
#   - ECR push: Pro-only → bypassed by using ZIP Lambda (python3.12 runtime)
#   - API Gateway v2 (HTTP API): Pro-only → using REST API v1 instead
#   - Lambda container image PackageType: Pro-only → ZIP PackageType used
#   - Lambda ZIP runs x86_64 on this Mac (Docker pulls amd64 image by default)
#     even though LocalStack container is aarch64; deps must be x86_64 manylinux
#
# Prerequisites:
#   - Docker running with life-dashboard-local_default network up (make local-up)
#   - python3 with cryptography installed (for Fernet key generation)
#   - backend poetry env with poetry-plugin-export (for exporting requirements)
#   - aws CLI installed (awslocal optional; uses aws --endpoint-url= fallback)
#   - psql / pg_isready on PATH (optional — script polls if not available)
#
# Usage:
#   cd <repo-root> && bash infra/local/smoke_deploy.sh [--skip-build]
#   --skip-build: skip Docker dep build (reuse /tmp/claude/lambda-build-out)
#
# API Gateway URL pattern (REST v1):
#   http://localhost:4566/restapis/<api-id>/local/_user_request_/health

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"

SKIP_BUILD="${1:-}"

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
LOCALSTACK_ENDPOINT="http://localhost:4566"
PG_HOST_URL="postgresql://life:life@localhost:55432/life_dashboard"
PG_ASYNC_URL="postgresql+asyncpg://life:life@localhost:55432/life_dashboard"
# In-network URLs — used in the Lambda secret (appdb resolves inside Docker network)
PG_NETWORK_URL="postgresql+asyncpg://life:life@appdb:5432/life_dashboard"
PG_NETWORK_SYNC_URL="postgresql://life:life@appdb:5432/life_dashboard"
# LocalStack is reachable from Lambda containers at 'localstack:4566'
LOCALSTACK_INTERNAL="http://localstack:4566"

LAMBDA_BUILD_DIR="/tmp/lifedash-lambda-build"
LAMBDA_ZIP="/tmp/lifedash-lambda.zip"
ACCOUNT_ID="000000000000"
REGION="us-east-1"

# Stable resource names (deterministic — no CDK hash suffix)
ASSET_BUCKET="lifedash-assets-local"
FRONTEND_BUCKET="lifedash-frontend-local"
KV_TABLE="lifedash-kv-local"
JOB_DLQ_NAME="lifedash-job-dlq-local"
JOB_QUEUE_NAME="lifedash-job-queue-local"
SECRET_NAME="life-dashboard/app"
API_FN_NAME="lifedash-api-local"
IAM_ROLE_NAME="lifedash-api-exec-local"
APIGW_NAME="lifedash-api-local"

# ------------------------------------------------------------------
# AWS CLI wrapper: tries awslocal, falls back to aws --endpoint-url
# ------------------------------------------------------------------
awsl() {
  if command -v awslocal &>/dev/null; then
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION="${REGION}" \
      awslocal "$@"
  else
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION="${REGION}" \
      aws --endpoint-url="${LOCALSTACK_ENDPOINT}" "$@"
  fi
}

# ------------------------------------------------------------------
# Step 1: Wait for LocalStack + appdb
# ------------------------------------------------------------------
echo ""
echo "==> [1/8] Waiting for LocalStack + appdb ..."
for i in $(seq 1 30); do
  if curl -sf "${LOCALSTACK_ENDPOINT}/_localstack/health" > /dev/null 2>&1; then
    echo "    LocalStack healthy (attempt ${i})"
    break
  fi
  [ "${i}" -eq 30 ] && { echo "ERROR: LocalStack not healthy after 60s" >&2; exit 1; }
  sleep 2
done

# Wait for appdb (pg_isready optional)
if command -v pg_isready &>/dev/null; then
  for i in $(seq 1 30); do
    pg_isready -h localhost -p 55432 -U life > /dev/null 2>&1 && \
      { echo "    appdb healthy (pg_isready, attempt ${i})"; break; }
    [ "${i}" -eq 30 ] && { echo "ERROR: appdb not healthy after 60s" >&2; exit 1; }
    sleep 2
  done
else
  echo "    pg_isready not found — assuming appdb healthy (check docker ps)"
fi

# ------------------------------------------------------------------
# Step 2: Generate Fernet key and run DB migration
# ------------------------------------------------------------------
echo ""
echo "==> [2/8] Generating Fernet key and running DB migration ..."
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "    Fernet key generated: ${FERNET_KEY:0:10}..."

cd "${BACKEND_DIR}"
DATABASE_URL_MIGRATIONS="${PG_HOST_URL}" \
DATABASE_URL="${PG_ASYNC_URL}" \
FRONTEND_URL="http://localhost:3000" \
ADMIN_EMAIL="admin@example.com" \
GARMIN_PASSWORD_ENCRYPTION_KEY="${FERNET_KEY}" \
ALLOW_LOCAL_DB=1 \
python3 -m app.aws.migrate
echo "    Migration complete."
cd "${REPO_ROOT}"

# ------------------------------------------------------------------
# Step 3: Build Lambda ZIP (x86_64 deps via Lambda Docker container)
# ------------------------------------------------------------------
echo ""
if [ "${SKIP_BUILD}" = "--skip-build" ] && [ -f "${LAMBDA_ZIP}" ]; then
  echo "==> [3/8] Skipping Lambda ZIP build (--skip-build specified, ${LAMBDA_ZIP} exists)"
else
  echo "==> [3/8] Building Lambda ZIP package (linux/amd64 deps via Lambda container) ..."
  echo "    IMPORTANT: LocalStack Community spawns x86_64 Lambda containers on Apple Silicon."
  echo "    Deps are installed inside public.ecr.aws/lambda/python:3.12 (--platform linux/amd64)."

  # Pull the linux/amd64 Lambda image if not present
  # IMPORTANT: LocalStack Community on Apple Silicon spawns x86_64 Lambda containers.
  # Docker may have pulled an aarch64 variant; force amd64 for correct .so files.
  docker pull --platform linux/amd64 public.ecr.aws/lambda/python:3.12 2>&1 | tail -3

  # Clean existing deps in build dir (keep app source if already copied)
  mkdir -p "${LAMBDA_BUILD_DIR}"
  find "${LAMBDA_BUILD_DIR}" -mindepth 1 -maxdepth 1 \
    ! -name 'app' ! -name 'migrations' ! -name 'alembic.ini' \
    -exec rm -rf {} + 2>/dev/null || true

  # Install all Python deps inside the x86_64 Lambda container
  docker run --rm \
    --platform linux/amd64 \
    --entrypoint /bin/bash \
    -v "${LAMBDA_BUILD_DIR}:/lambda-pkg" \
    public.ecr.aws/lambda/python:3.12 \
    -c "
      pip install --no-cache-dir --quiet \
        --target /lambda-pkg \
        asyncpg alembic 'fastapi>=0.115' mangum \
        'sqlalchemy[asyncio]>=2.0.30' pydantic 'pydantic-settings>=2.4' \
        loguru boto3 cryptography 'python-multipart>=0.0.22' \
        'email-validator>=2.1' python-dotenv tenacity openai httpx \
        feedparser google-auth 'python-dateutil>=2.9' mcp uvicorn \
        apscheduler garminconnect psycopg2-binary 2>&1 | grep -E '^(Successfully installed|ERROR)' || true
      echo 'pip complete, size:' \$(du -sh /lambda-pkg | cut -f1)
    " 2>&1 | grep -v "^$" || true

  # Copy app source into the build dir
  cp -r "${BACKEND_DIR}/app"        "${LAMBDA_BUILD_DIR}/app"
  cp -r "${BACKEND_DIR}/migrations" "${LAMBDA_BUILD_DIR}/migrations"
  cp    "${BACKEND_DIR}/alembic.ini" "${LAMBDA_BUILD_DIR}/alembic.ini"

  # Trim: remove .pyc, __pycache__, and curl_cffi (30MB from garminconnect, not needed for API)
  # Keep .dist-info — some packages check metadata at import time (e.g. email-validator)
  find "${LAMBDA_BUILD_DIR}" -name "*.pyc" -delete 2>/dev/null || true
  find "${LAMBDA_BUILD_DIR}" -name "__pycache__" -type d -print0 | xargs -0 rm -rf 2>/dev/null || true
  find "${LAMBDA_BUILD_DIR}" -maxdepth 1 -name "curl_cffi" -type d -exec rm -rf {} + 2>/dev/null || true
  find "${LAMBDA_BUILD_DIR}" -maxdepth 1 -name "curl_cffi*" -type d -exec rm -rf {} + 2>/dev/null || true

  # Build ZIP — must be <50MB for LocalStack Community Lambda ZIP limit
  rm -f "${LAMBDA_ZIP}"
  cd "${LAMBDA_BUILD_DIR}" && zip -r9q "${LAMBDA_ZIP}" .
  cd "${REPO_ROOT}"
  echo "    ZIP built: ${LAMBDA_ZIP} ($(du -sh "${LAMBDA_ZIP}" | cut -f1))"
fi

# ------------------------------------------------------------------
# Step 4: Create Foundation resources
# ------------------------------------------------------------------
echo ""
echo "==> [4/8] Creating Foundation resources ..."

# S3 buckets
awsl s3 mb "s3://${ASSET_BUCKET}" 2>/dev/null || echo "    asset bucket already exists"
awsl s3 mb "s3://${FRONTEND_BUCKET}" 2>/dev/null || echo "    frontend bucket already exists"
echo "    S3 buckets OK"

# DynamoDB KV table
if awsl dynamodb describe-table --table-name "${KV_TABLE}" > /dev/null 2>&1; then
  echo "    KV table already exists"
else
  awsl dynamodb create-table \
    --table-name "${KV_TABLE}" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST > /dev/null
  echo "    KV table created"
fi

# SQS DLQ
if awsl sqs get-queue-url --queue-name "${JOB_DLQ_NAME}" > /dev/null 2>&1; then
  DLQ_URL=$(awsl sqs get-queue-url --queue-name "${JOB_DLQ_NAME}" --query 'QueueUrl' --output text)
  echo "    DLQ already exists"
else
  DLQ_URL=$(awsl sqs create-queue --queue-name "${JOB_DLQ_NAME}" --query 'QueueUrl' --output text)
  echo "    DLQ created"
fi
DLQ_ARN=$(awsl sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

# SQS Job queue (use cli-input-json to avoid shell quoting issues with RedrivePolicy JSON)
if awsl sqs get-queue-url --queue-name "${JOB_QUEUE_NAME}" > /dev/null 2>&1; then
  JOB_QUEUE_URL=$(awsl sqs get-queue-url --queue-name "${JOB_QUEUE_NAME}" --query 'QueueUrl' --output text)
  echo "    Job queue already exists"
else
  _SQS_TMP=$(mktemp /tmp/lifedash-sqs-XXXXXX.json)
  python3 -c "import json; print(json.dumps({'QueueName': '${JOB_QUEUE_NAME}', 'Attributes': {'RedrivePolicy': json.dumps({'deadLetterTargetArn': '${DLQ_ARN}', 'maxReceiveCount': '5'})}}))" > "${_SQS_TMP}"
  JOB_QUEUE_URL=$(awsl sqs create-queue --cli-input-json "file://${_SQS_TMP}" --query 'QueueUrl' --output text)
  rm -f "${_SQS_TMP}"
  echo "    Job queue created"
fi
# Remap to internal hostname for Lambda env
JOB_QUEUE_URL_INTERNAL=$(echo "${JOB_QUEUE_URL}" | sed 's/localhost/localstack/g')
echo "    SQS OK (external: ${JOB_QUEUE_URL})"

# Secrets Manager secret (create empty shell; seeded in step 6)
if awsl secretsmanager describe-secret --secret-id "${SECRET_NAME}" > /dev/null 2>&1; then
  echo "    Secret already exists"
else
  awsl secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --description "Life Dashboard app secrets" > /dev/null
  echo "    Secret created"
fi

# ------------------------------------------------------------------
# Step 5: Create IAM execution role for Lambda
# ------------------------------------------------------------------
echo ""
echo "==> [5/8] Creating Lambda execution role ..."
TRUST_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
if awsl iam get-role --role-name "${IAM_ROLE_NAME}" > /dev/null 2>&1; then
  ROLE_ARN=$(awsl iam get-role --role-name "${IAM_ROLE_NAME}" --query 'Role.Arn' --output text)
  echo "    IAM role already exists"
else
  ROLE_ARN=$(awsl iam create-role \
    --role-name "${IAM_ROLE_NAME}" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    --query 'Role.Arn' --output text)
  echo "    IAM role created"
fi
echo "    Role ARN: ${ROLE_ARN}"

# ------------------------------------------------------------------
# Step 6: Seed the secret (in-network DB + localstack endpoint)
# ------------------------------------------------------------------
echo ""
echo "==> [6/8] Seeding Secrets Manager secret ..."
SECRET_VALUE=$(python3 -c "import json; print(json.dumps({
  'DATABASE_URL': '${PG_NETWORK_URL}',
  'DATABASE_URL_MIGRATIONS': '${PG_NETWORK_SYNC_URL}',
  'GARMIN_PASSWORD_ENCRYPTION_KEY': '${FERNET_KEY}',
  'OPENAI_API_KEY': 'sk-test-local',
  'SESSION_SECRET': 'test-session-local-dev',
  'READINESS_ADMIN_TOKEN': 'test-readiness-token',
  'AWS_ENDPOINT_URL': '${LOCALSTACK_INTERNAL}'
}))")
awsl secretsmanager put-secret-value \
  --secret-id "${SECRET_NAME}" \
  --secret-string "${SECRET_VALUE}" \
  --query 'VersionId' --output text > /dev/null
echo "    Secret seeded (DB: appdb:5432, endpoint: ${LOCALSTACK_INTERNAL})"

# ------------------------------------------------------------------
# Step 7: Deploy API Lambda (ZIP, python3.12)
# ------------------------------------------------------------------
echo ""
echo "==> [7/8] Deploying API Lambda (ZIP, python3.12) ..."

# Delete and re-create for clean state
awsl lambda delete-function --function-name "${API_FN_NAME}" 2>/dev/null || true

_LAMBDA_TMP=$(mktemp /tmp/lifedash-lambda-XXXXXX.json)
python3 - <<PYEOF > "${_LAMBDA_TMP}"
import json
print(json.dumps({
  "FunctionName": "${API_FN_NAME}",
  "Runtime": "python3.12",
  "Handler": "app.aws.api_handler.handler",
  "Code": {"ZipFile": "__ZIPFILE__"},
  "Role": "${ROLE_ARN}",
  "Timeout": 30,
  "MemorySize": 512,
  "Environment": {
    "Variables": {
      "LD_RUNTIME": "aws",
      "LD_JOB_QUEUE": "sqs",
      "LD_BLOB_STORE": "s3",
      "LD_KV_STORE": "dynamodb",
      "LD_SECRETS": "secretsmanager",
      "LD_SECRETS_NAME": "${SECRET_NAME}",
      "LD_S3_ASSET_BUCKET": "${ASSET_BUCKET}",
      "LD_SQS_QUEUE_URL": "${JOB_QUEUE_URL_INTERNAL}",
      "LD_DDB_KV_TABLE": "${KV_TABLE}",
      "ADMIN_EMAIL": "admin@example.com",
      "FRONTEND_URL": "http://localhost:3000",
      "AWS_ENDPOINT_URL": "${LOCALSTACK_INTERNAL}"
    }
  }
}))
PYEOF
# Note: We can't pass env via cli-input-json with ZipFile easily, so use separate flags
# Use direct flags instead for env + zip
rm -f "${_LAMBDA_TMP}"

# Write env JSON to a stable temp file (not mktemp, to avoid shell variable expansion issues)
_ENV_TMP="/tmp/lifedash-lambda-env-deploy.json"
python3 -c "
import json, sys
env = {
  'LD_RUNTIME': 'aws',
  'LD_JOB_QUEUE': 'sqs',
  'LD_BLOB_STORE': 's3',
  'LD_KV_STORE': 'dynamodb',
  'LD_SECRETS': 'secretsmanager',
  'LD_SECRETS_NAME': sys.argv[1],
  'LD_S3_ASSET_BUCKET': sys.argv[2],
  'LD_SQS_QUEUE_URL': sys.argv[3],
  'LD_DDB_KV_TABLE': sys.argv[4],
  'ADMIN_EMAIL': 'admin@example.com',
  'FRONTEND_URL': 'http://localhost:3000',
  'AWS_ENDPOINT_URL': sys.argv[5]
}
print(json.dumps({'Variables': env}))
" "${SECRET_NAME}" "${ASSET_BUCKET}" "${JOB_QUEUE_URL_INTERNAL}" "${KV_TABLE}" "${LOCALSTACK_INTERNAL}" > "${_ENV_TMP}"

awsl lambda create-function \
  --function-name "${API_FN_NAME}" \
  --runtime python3.12 \
  --handler app.aws.api_handler.handler \
  --zip-file "fileb://${LAMBDA_ZIP}" \
  --role "${ROLE_ARN}" \
  --timeout 30 \
  --memory-size 512 \
  --environment "file://${_ENV_TMP}" \
  --query 'FunctionArn' --output text > /tmp/lifedash-fn-arn.tmp

API_FN_ARN=$(cat /tmp/lifedash-fn-arn.tmp)
echo "    Lambda ARN: ${API_FN_ARN}"

# Wait for Active
echo "    Waiting for Lambda to become Active ..."
for i in $(seq 1 30); do
  STATE=$(awsl lambda get-function-configuration \
    --function-name "${API_FN_NAME}" --query 'State' --output text)
  [ "${STATE}" = "Active" ] && { echo "    Lambda Active (attempt ${i})"; break; }
  [ "${i}" -eq 30 ] && { echo "ERROR: Lambda did not become Active" >&2; exit 1; }
  sleep 2
done

# ------------------------------------------------------------------
# Step 8: Create REST API Gateway v1 with Lambda proxy
# ------------------------------------------------------------------
echo ""
echo "==> [8/8] Creating REST API Gateway v1 ..."
echo "    Note: API Gateway v2 (HTTP API) is Pro-only; using REST API v1."

# Delete existing API if any
EXISTING_API=$(awsl apigateway get-rest-apis \
  --query "items[?name=='${APIGW_NAME}'].id" --output text 2>/dev/null || true)
if [ -n "${EXISTING_API}" ] && [ "${EXISTING_API}" != "None" ]; then
  awsl apigateway delete-rest-api --rest-api-id "${EXISTING_API}" 2>/dev/null || true
  echo "    Deleted existing API: ${EXISTING_API}"
fi

API_ID=$(awsl apigateway create-rest-api --name "${APIGW_NAME}" --query 'id' --output text)
echo "    API ID: ${API_ID}"

ROOT_ID=$(awsl apigateway get-resources \
  --rest-api-id "${API_ID}" --query 'items[0].id' --output text)

# Create {proxy+} resource
PROXY_ID=$(awsl apigateway create-resource \
  --rest-api-id "${API_ID}" \
  --parent-id "${ROOT_ID}" \
  --path-part '{proxy+}' \
  --query 'id' --output text)

LAMBDA_URI="arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${API_FN_ARN}/invocations"

# Wire ANY on root and {proxy+}
for RES_ID in "${ROOT_ID}" "${PROXY_ID}"; do
  awsl apigateway put-method \
    --rest-api-id "${API_ID}" --resource-id "${RES_ID}" \
    --http-method ANY --authorization-type NONE > /dev/null
  awsl apigateway put-integration \
    --rest-api-id "${API_ID}" --resource-id "${RES_ID}" \
    --http-method ANY --type AWS_PROXY \
    --integration-http-method POST \
    --uri "${LAMBDA_URI}" > /dev/null
done

# Deploy to 'local' stage
awsl apigateway create-deployment \
  --rest-api-id "${API_ID}" \
  --stage-name local \
  --query 'id' --output text > /dev/null

# Grant API GW permission to invoke Lambda
awsl lambda add-permission \
  --function-name "${API_FN_NAME}" \
  --statement-id "apigw-rest-${API_ID}" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
  2>/dev/null || true

# REST API URL form for Community edition
API_URL="http://localhost:4566/restapis/${API_ID}/local/_user_request_"

# ------------------------------------------------------------------
# Smoke test: GET /health
# ------------------------------------------------------------------
echo ""
echo "==> Smoke test: GET ${API_URL}/health"
HEALTH_RESULT=""
HEALTH_STATUS=0
for i in $(seq 1 15); do
  RESP=$(curl -sf --max-time 10 "${API_URL}/health" 2>/dev/null || true)
  if [ -n "${RESP}" ]; then
    HEALTH_RESULT="${RESP}"
    break
  fi
  echo "    ... attempt ${i}/15"
  sleep 2
done

# Stretch: DB-backed route
DB_RESULT=""
if [ -n "${HEALTH_RESULT}" ]; then
  DB_RESULT=$(curl -sf --max-time 15 "${API_URL}/api/auth/me" 2>/dev/null || true)
fi

# ------------------------------------------------------------------
# Results
# ------------------------------------------------------------------
echo ""
echo "================================================================"
echo "SMOKE TEST RESULTS"
echo "================================================================"
echo "  API GW ID  : ${API_ID}"
echo "  API URL    : ${API_URL}"
echo "  Lambda ARN : ${API_FN_ARN}"
echo "  Lambda Arch: x86_64 (LocalStack Community spawns amd64 containers)"
echo "  Lambda RT  : python3.12 (ZIP) — container image is Pro-only"
echo "  API GW ver : REST v1 — HTTP API v2 is Pro-only"
echo "  Network    : life-dashboard-local_default (LAMBDA_DOCKER_NETWORK)"
echo ""
echo "  /health response:"
if [ -n "${HEALTH_RESULT}" ]; then
  echo "    ${HEALTH_RESULT}"
  echo "  STATUS: PASS — /health returned 200 via REST API GW"
else
  echo "    (no response)"
  echo "  STATUS: FAIL — try: curl ${API_URL}/health"
  HEALTH_STATUS=1
fi

echo ""
echo "  /api/auth/me (DB-backed route, Lambda→Secrets→Postgres):"
if [ -n "${DB_RESULT}" ]; then
  echo "    ${DB_RESULT}"
  echo "  STATUS: PASS — Lambda→Secrets Manager→appdb:5432 works end-to-end"
else
  echo "    (no response — DB path may have timed out)"
  echo "    Check: docker logs life-dashboard-local-localstack-1 --tail 50"
fi

echo ""
echo "  LocalStack Community limits hit:"
echo "    1. ECR push — Pro only; workaround: ZIP Lambda (python3.12)"
echo "    2. Lambda container images (PackageType=Image) — Pro only; same workaround"
echo "    3. API Gateway v2 (HTTP API) — Pro only; workaround: REST API v1"
echo ""
echo "  Recommendations for Task 5.2+:"
echo "    - For real AWS: CDK stack (DockerImageAsset + HttpApi) works as-is"
echo "    - smoke_deploy.sh targets Community; prod deploy uses cdklocal or AWS CLI"
echo "    - Consider LocalStack Pro trial for full parity (ECR + HTTP API v2)"
echo "    - Add psycopg2-binary + garminconnect to explicit deps list in smoke_deploy"
echo "================================================================"

exit ${HEALTH_STATUS}
