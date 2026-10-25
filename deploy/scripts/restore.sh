#!/usr/bin/env bash
# Ask4Mo Capstone (P8) — restore into a SAFE (staging/restore) target.
#
# Restores:
#   1. a pg_dump archive (custom format) into TARGET_DATABASE_URL
#   2. a documents tar.gz into DOCUMENT_STORAGE_DIR
#   3. a knowledge/index tar.gz (KNOWLEDGE_TAR) into COPILOT_DATA_DIR
#
# SAFETY GUARD: refuses to run unless the TARGET database name contains "staging"
# or "restore" — this prevents accidentally clobbering production. Override only
# with an explicit FORCE=1 (and know what you are doing).
#
# No secrets inline: everything is read from the environment.
#
# Usage:
#   TARGET_DATABASE_URL=postgresql://user:pass@host:5432/ask4mo_restore \
#   DB_DUMP=/backups/ask4mo-db-<ts>.dump \
#   DOCS_TAR=/backups/ask4mo-documents-<ts>.tar.gz \
#   DOCUMENT_STORAGE_DIR=/data/documents_restore \
#   KNOWLEDGE_TAR=/backups/ask4mo-knowledge-<ts>.tar.gz \
#   COPILOT_DATA_DIR=/data/knowledge_restore \
#   bash deploy/scripts/restore.sh
set -euo pipefail

# Legacy compatibility only. Qualified recovery uses backup_set.py qualified,
# whose empty-target, encryption, signed-head and quarantine controls cannot be bypassed.
case "${API_ENV:-development}" in
  development|dev|local|test|testing) ;;
  *) echo "REFUSING: legacy destructive restore is not a hosted recovery procedure." >&2; exit 1 ;;
esac
if [[ "${ASK4MO_LEGACY_RESTORE_UNSAFE_ACK:-}" != "legacy-unsealed-destructive-restore" ]]; then
  echo "REFUSING: use the qualified recovery runner; legacy restore needs a separate explicit unsafe acknowledgement." >&2
  exit 1
fi

: "${TARGET_DATABASE_URL:?set TARGET_DATABASE_URL (the SAFE db to restore INTO)}"
: "${DB_DUMP:?set DB_DUMP (path to the pg_dump archive to restore)}"

# pg_restore needs a plain libpq URL; drop any SQLAlchemy driver suffix.
target_url="${TARGET_DATABASE_URL/postgresql+psycopg:/postgresql:}"

# Extract the target database name (the path component after the last '/',
# without any ?query string) for the safety check.
db_name="${target_url##*/}"
db_name="${db_name%%\?*}"

echo "==> [restore] target database: ${db_name}"

if [[ "${db_name}" != *staging* && "${db_name}" != *restore* ]]; then
  if [[ "${FORCE:-0}" != "1" ]]; then
    echo "REFUSING: target db '${db_name}' does not contain 'staging' or 'restore'." >&2
    echo "          This guard prevents clobbering production. Set FORCE=1 to override." >&2
    exit 1
  fi
  echo "WARNING: FORCE=1 set — restoring into non-staging/non-restore db '${db_name}'." >&2
fi

if [[ ! -f "${DB_DUMP}" ]]; then
  echo "ERROR: DB_DUMP '${DB_DUMP}' not found." >&2
  exit 1
fi

echo "==> [restore] restoring database from ${DB_DUMP}"
# --clean --if-exists drops existing objects first so the restore is idempotent.
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="${target_url}" "${DB_DUMP}"

# Documents restore is optional (only if a tar + target dir are provided).
if [[ -n "${DOCS_TAR:-}" ]]; then
  : "${DOCUMENT_STORAGE_DIR:?set DOCUMENT_STORAGE_DIR to restore documents into}"
  if [[ ! -f "${DOCS_TAR}" ]]; then
    echo "ERROR: DOCS_TAR '${DOCS_TAR}' not found." >&2
    exit 1
  fi
  echo "==> [restore] restoring documents from ${DOCS_TAR} into ${DOCUMENT_STORAGE_DIR}"
  mkdir -p "${DOCUMENT_STORAGE_DIR}"
  # Extract INTO the parent so the archived top dir lands at DOCUMENT_STORAGE_DIR.
  tar -xzf "${DOCS_TAR}" -C "$(dirname "${DOCUMENT_STORAGE_DIR}")"
else
  echo "==> [restore] DOCS_TAR not set — skipping documents restore."
fi

# Knowledge/index restore is optional (only if a tar + target dir are provided).
if [[ -n "${KNOWLEDGE_TAR:-}" ]]; then
  : "${COPILOT_DATA_DIR:?set COPILOT_DATA_DIR to restore the knowledge/index data into}"
  if [[ ! -f "${KNOWLEDGE_TAR}" ]]; then
    echo "ERROR: KNOWLEDGE_TAR '${KNOWLEDGE_TAR}' not found." >&2
    exit 1
  fi
  echo "==> [restore] restoring knowledge/index data from ${KNOWLEDGE_TAR} into ${COPILOT_DATA_DIR}"
  mkdir -p "${COPILOT_DATA_DIR}"
  tar -xzf "${KNOWLEDGE_TAR}" -C "$(dirname "${COPILOT_DATA_DIR}")"
else
  echo "==> [restore] KNOWLEDGE_TAR not set — skipping knowledge restore (knowledge base will be EMPTY)."
fi

echo
echo "==> [restore] done. Verify:"
echo "    Tables : psql \"${target_url}\" -c '\\dt' | head"
echo "    Row spot-check : psql \"${target_url}\" -c 'SELECT count(*) FROM accounts;'"
echo "    App readiness against the restored DB : curl -fsS <api>/api/v1/ready"
echo "    Knowledge : ls -la \"${COPILOT_DATA_DIR:-<not restored>}\" | head"
echo "    Documents : ls -la \"${DOCUMENT_STORAGE_DIR:-<not restored>}\" | head"
