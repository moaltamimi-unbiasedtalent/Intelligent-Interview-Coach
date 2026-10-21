#!/usr/bin/env bash
# Ask4Mo Capstone (P8) — backup (STAGING).
#
# Produces THREE timestamped artifacts in BACKUP_DIR:
#   1. a PostgreSQL logical dump (pg_dump, custom format) of DATABASE_URL
#   2. a tar.gz of the private document storage (DOCUMENT_STORAGE_DIR)
#   3. a tar.gz of the knowledge/index data root (COPILOT_DATA_DIR, the `knowledge-data` volume)
# (ClamAV signatures and Caddy certificates are re-creatable and are not backed up.)
#
# No secrets are inline: DATABASE_URL / DOCUMENT_STORAGE_DIR / BACKUP_DIR come
# from the environment. pg_dump reads credentials from the DATABASE_URL only.
#
# Usage:
#   DATABASE_URL=postgresql://...  DOCUMENT_STORAGE_DIR=/data/documents \
#   BACKUP_DIR=/backups  bash deploy/scripts/backup.sh
#
# COPILOT_DATA_DIR is optional for backward compatibility; when unset the knowledge tar is
# SKIPPED with a warning (a restore without it has an EMPTY knowledge base).
#
# Note: pg_dump wants a libpq URL. If DATABASE_URL uses the SQLAlchemy driver
# form (postgresql+psycopg://), this script strips the +psycopg for pg_dump.
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL}"
: "${DOCUMENT_STORAGE_DIR:?set DOCUMENT_STORAGE_DIR (e.g. /data/documents)}"
: "${BACKUP_DIR:?set BACKUP_DIR (where backups are written)}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_DIR}"
COPILOT_DATA_DIR="${COPILOT_DATA_DIR:-}"

# pg_dump needs a plain libpq URL; drop any SQLAlchemy driver suffix.
pg_url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

db_dump="${BACKUP_DIR}/ask4mo-db-${timestamp}.dump"
docs_tar="${BACKUP_DIR}/ask4mo-documents-${timestamp}.tar.gz"
knowledge_tar="${BACKUP_DIR}/ask4mo-knowledge-${timestamp}.tar.gz"

echo "==> [backup] database -> ${db_dump}"
# Custom format (-Fc) supports selective/parallel restore via pg_restore.
pg_dump --format=custom --no-owner --no-privileges --file="${db_dump}" "${pg_url}"

echo "==> [backup] documents (${DOCUMENT_STORAGE_DIR}) -> ${docs_tar}"
if [[ -d "${DOCUMENT_STORAGE_DIR}" ]]; then
  tar -czf "${docs_tar}" -C "$(dirname "${DOCUMENT_STORAGE_DIR}")" "$(basename "${DOCUMENT_STORAGE_DIR}")"
else
  echo "WARNING: DOCUMENT_STORAGE_DIR '${DOCUMENT_STORAGE_DIR}' not found — skipping docs tar." >&2
fi

echo "==> [backup] knowledge/index data root (${COPILOT_DATA_DIR:-<unset>}) -> ${knowledge_tar}"
if [[ -n "${COPILOT_DATA_DIR}" && -d "${COPILOT_DATA_DIR}" ]]; then
  tar -czf "${knowledge_tar}" -C "$(dirname "${COPILOT_DATA_DIR}")" "$(basename "${COPILOT_DATA_DIR}")"
else
  echo "WARNING: COPILOT_DATA_DIR is unset or not found — skipping knowledge tar (a restore will have an EMPTY knowledge base)." >&2
fi

echo
echo "==> [backup] done. Artifacts:"
ls -lh "${db_dump}" "${docs_tar}" "${knowledge_tar}" 2>/dev/null || true
echo
echo "==> Verify the backups:"
echo "    DB dump   : pg_restore --list \"${db_dump}\" | head    # lists archive TOC without restoring"
echo "    Docs tar  : tar -tzf \"${docs_tar}\" | head             # lists archive contents"
echo "    Knowledge : tar -tzf \"${knowledge_tar}\" | head        # lists the knowledge/index archive"
echo "    (For a real restore drill, restore into a throwaway 'restore' DB with restore.sh.)"
