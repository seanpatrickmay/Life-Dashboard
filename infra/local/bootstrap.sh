#!/usr/bin/env bash
set -euo pipefail

# Export dummy AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

HEALTH_URL="http://localhost:4566/_localstack/health"
MAX_WAIT=60
POLL_INTERVAL=2

echo "==> Waiting for LocalStack to be ready at ${HEALTH_URL} ..."
elapsed=0
while true; do
  if curl -sf "${HEALTH_URL}" > /dev/null 2>&1; then
    echo "==> LocalStack is up!"
    break
  fi
  if [ "${elapsed}" -ge "${MAX_WAIT}" ]; then
    echo "ERROR: LocalStack did not become ready within ${MAX_WAIT}s." >&2
    exit 1
  fi
  echo "    ... waiting (${elapsed}s elapsed)"
  sleep "${POLL_INTERVAL}"
  elapsed=$(( elapsed + POLL_INTERVAL ))
done

# Show health status
echo "==> LocalStack health:"
curl -s "${HEALTH_URL}" | python3 -m json.tool || curl -s "${HEALTH_URL}"
echo ""

# Bootstrap CDK into LocalStack (idempotent)
echo "==> Running CDK bootstrap into LocalStack ..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."
npx cdklocal bootstrap \
  --toolkit-stack-name CDKToolkit \
  aws://000000000000/us-east-1

echo "==> Bootstrap complete."
