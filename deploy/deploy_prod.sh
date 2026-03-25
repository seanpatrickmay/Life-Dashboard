#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"

remote="${DEPLOY_REMOTE:-origin}"
branch="${DEPLOY_BRANCH:-main}"

cd "$repo_root"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: $repo_root is not a git repository." >&2
  exit 1
fi

if [ ! -f "docker/docker-compose.prod.yml" ]; then
  echo "ERROR: Missing docker/docker-compose.prod.yml (are you in the repo root?)." >&2
  exit 1
fi

echo "Deploying $(basename "$repo_root") from ${remote}/${branch}..."

git fetch --prune "$remote"
git reset --hard "${remote}/${branch}"

docker_cmd=()
if docker info >/dev/null 2>&1; then
  docker_cmd=(docker)
elif sudo -n docker info >/dev/null 2>&1; then
  docker_cmd=(sudo docker)
else
  echo "ERROR: Cannot run docker (no access to Docker daemon)." >&2
  exit 1
fi

compose_cmd=()
if "${docker_cmd[@]}" compose version >/dev/null 2>&1; then
  compose_cmd=("${docker_cmd[@]}" compose)
elif command -v docker-compose >/dev/null 2>&1; then
  if docker-compose version >/dev/null 2>&1; then
    compose_cmd=(docker-compose)
  elif sudo -n docker-compose version >/dev/null 2>&1; then
    compose_cmd=(sudo docker-compose)
  fi
fi

if [ "${#compose_cmd[@]}" -eq 0 ]; then
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
fi

"${compose_cmd[@]}" --env-file "$repo_root/.env" -f docker/docker-compose.prod.yml up -d --build

if [ "${DEPLOY_PRUNE_IMAGES:-1}" = "1" ]; then
  "${docker_cmd[@]}" image prune -f
fi

echo "Waiting for health check..."
# Backend port 8000 is only exposed internally; check via Caddy on port 80,
# or directly via docker exec if the reverse proxy isn't ready yet.
health_url="${DEPLOY_HEALTH_URL:-http://localhost/health}"
for i in $(seq 1 15); do
  if curl -sf "$health_url" > /dev/null 2>&1; then
    echo "Health check passed!"
    echo "Deploy complete."
    exit 0
  fi
  # Also try direct container check in case Caddy isn't routing yet
  if "${compose_cmd[@]}" --env-file "$repo_root/.env" -f docker/docker-compose.prod.yml exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "Health check passed (direct container)!"
    echo "Deploy complete."
    exit 0
  fi
  echo "  Attempt $i/15 failed, retrying in 3s..."
  sleep 3
done

echo "Health check failed! Backend logs:"
"${compose_cmd[@]}" --env-file "$repo_root/.env" -f docker/docker-compose.prod.yml logs --tail=30 backend
exit 1
