#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

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

is_deploy=false
for arg in "$@"; do
  if [ "$arg" = "up" ]; then
    is_deploy=true
    break
  fi
done

if [ "$is_deploy" = false ]; then
  exec docker compose "$@"
fi

docker compose "$@"

container_id="$(docker compose ps -q web)"
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
