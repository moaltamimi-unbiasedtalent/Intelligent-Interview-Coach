#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: the Docker Compose plugin is not available (docker compose version failed)." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: the Docker daemon is not reachable." >&2
  exit 1
fi

if [ ! -f docker-compose.yml ]; then
  echo "ERROR: docker-compose.yml was not found in $repo_root." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: $repo_root is not a Git worktree; deployment metadata cannot be resolved." >&2
  exit 1
fi

commit="$(git rev-parse HEAD)"
branch="$(git branch --show-current 2>/dev/null || true)"
deployed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
tags="branch:${branch:-detached},image:ask4mo-local-web"

for tag in $(git tag --points-at HEAD); do
  tags="${tags},git:${tag}"
done
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  tags="${tags},worktree-dirty"
fi

export APP_GIT_SHA="$commit"
export APP_BUILD_TIME="$deployed_at"
export APP_DEPLOY_TAGS="$tags"

for name in APP_GIT_SHA APP_BUILD_TIME APP_DEPLOY_TAGS; do
  if [ -z "${!name:-}" ]; then
    echo "ERROR: deployment metadata variable $name is empty." >&2
    exit 1
  fi
done

args=("$@")
if [ "${#args[@]}" -eq 0 ]; then
  args=(up -d --build)
fi

compose_global_args=()
is_deploy=false
for arg in "${args[@]}"; do
  if [ "$arg" = "up" ]; then
    is_deploy=true
    break
  fi
  compose_global_args+=("$arg")
done

if [ "$is_deploy" = false ]; then
  exec docker compose "${args[@]}"
fi

if ! docker compose "${compose_global_args[@]}" config --quiet; then
  echo "ERROR: docker compose configuration validation failed." >&2
  exit 1
fi

docker compose "${args[@]}"

container_id="$(docker compose "${compose_global_args[@]}" ps -q web)"
if [ -z "$container_id" ]; then
  echo "ERROR: deployment verification failed: no running web container was found." >&2
  exit 1
fi

deployed_commit="$(docker inspect "$container_id" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
current_commit="$(git rev-parse HEAD)"

if [ "$deployed_commit" != "$current_commit" ]; then
  echo "ERROR: deployed commit '${deployed_commit:-unknown}' does not match current Git commit '$current_commit'." >&2
  exit 1
fi

echo "Deployment verified: deployed commit $deployed_commit matches current Git commit."
