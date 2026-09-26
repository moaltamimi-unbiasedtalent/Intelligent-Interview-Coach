#!/usr/bin/env bash
# Ask4Mo Capstone (P8) — database migration step (STAGING).
#
# Applies Alembic migrations to head, then asserts EXACTLY ONE head so a bad merge
# (two divergent heads) cannot silently ship. This is the ONLY place migrations
# run; the API image never auto-migrates on boot (avoids the multi-replica race).
#
# Run from the repo root (or the api image, whose WORKDIR is /app and which
# contains alembic.ini + migrations/). DATABASE_URL must be exported.
#
# Usage:
#   DATABASE_URL=postgresql+psycopg://... bash deploy/scripts/migrate.sh
set -euo pipefail

echo "==> [migrate] Ask4Mo staging migration"
echo "    REMINDER: take a fresh backup BEFORE migrating (deploy/scripts/backup.sh)."
echo "    Destructive migrations are forward-fix only — never auto-downgrade in staging/prod."

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  exit 1
fi

# Apply all pending migrations up to the latest revision.
echo "==> [migrate] alembic upgrade head"
alembic upgrade head

# Assert a single head. `alembic heads` prints one line per head revision; more
# than one line means the migration graph diverged and must be merged first.
echo "==> [migrate] asserting a single Alembic head"
if ! test "$(alembic heads | wc -l)" -eq 1; then
  echo "ERROR: expected exactly 1 Alembic head." >&2
  echo "       Resolve divergent heads with 'alembic merge' before deploying." >&2
  alembic heads >&2
  exit 1
fi

echo "==> [migrate] OK — single head, database is at latest revision."
