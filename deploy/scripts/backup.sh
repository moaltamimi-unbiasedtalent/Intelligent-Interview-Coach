#!/usr/bin/env bash
# Ask4Mo Capstone (P8) — backup (STAGING).
#
# Produces TWO timestamped artifacts in BACKUP_DIR:
#   1. a PostgreSQL logical dump (pg_dump, custom format) of DATABASE_URL
#   2. a tar.gz of the private document storage (DOCUMENT_STORAGE_DIR)
#
# No secrets are inline: DATABASE_URL / DOCUMENT_STORAGE_DIR / BACKUP_DIR come
# from the environment. pg_dump reads credentials from the DATABASE_URL only.
#
# Usage:
#   DATABASE_URL=postgresql://...  DOCUMENT_STORAGE_DIR=/data/documents \
#   BACKUP_DIR=/backups  bash deploy/scripts/backup.sh
#
# Note: pg_dump wants a libpq URL. If DATABASE_URL uses the SQLAlchemy driver
# form (postgresql+psycopg://), this script strips the +psycopg for pg_dump.
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL}"
: "${DOCUMENT_STORAGE_DIR:?set DOCUMENT_STORAGE_DIR (e.g. /data/documents)}"
: "${BACKUP_DIR:?set BACKUP_DIR (where backups are written)}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_DIR}"

# pg_dump needs a plain libpq URL; drop any SQLAlchemy driver suffix.
pg_url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

db_dump="${BACKUP_DIR}/ask4mo-db-${timestamp}.dump"
docs_tar="${BACKUP_DIR}/ask4mo-documents-${timestamp}.tar.gz"

echo "==> [backup] database -> ${db_dump}"
# Custom format (-Fc) supports selective/parallel restore via pg_restore.
pg_dump --format=custom --no-owner --no-privileges --file="${db_dump}" "${pg_url}"

echo "==> [backup] documents (${DOCUMENT_STORAGE_DIR}) -> ${docs_tar}"
if [[ -d "${DOCUMENT_STORAGE_DIR}" ]]; then
  tar -czf "${docs_tar}" -C "$(dirname "${DOCUMENT_STORAGE_DIR}")" "$(basename "${DOCUMENT_STORAGE_DIR}")"
else
  echo "WARNING: DOCUMENT_STORAGE_DIR '${DOCUMENT_STORAGE_DIR}' not found — skipping docs tar." >&2
fi

echo
echo "==> [backup] done. Artifacts:"
ls -lh "${db_dump}" "${docs_tar}" 2>/dev/null || true
echo
echo "==> Verify the backups:"
echo "    DB dump   : pg_restore --list \"${db_dump}\" | head    # lists archive TOC without restoring"
echo "    Docs tar  : tar -tzf \"${docs_tar}\" | head             # lists archive contents"
echo "    (For a real restore drill, restore into a throwaway 'restore' DB with restore.sh.)"
