# Staging topology notes (package 05A)

## DEPLOYMENT FREEZE

`deploy/docker-compose.staging.yml` is the staging topology **as code only**. It has never been started
(`docker compose up` has not been run, no image has been built from it, no provider has been contacted).
**Do not deploy it** until the owner answers decision **OD-HOSTED** and explicitly authorises a deployment.
Nothing in this file or in the tests claims the topology works live.

## Services

| Service | Purpose | Notes |
|---|---|---|
| `db` | PostgreSQL 16, `db-data` volume | Internal only; healthcheck `pg_isready`. |
| `migrate` | One-shot `alembic upgrade head` | The only place migrations run; `restart: "no"`. |
| `api` | FastAPI/uvicorn `:8000` | Waits for `db` healthy, `migrate` completed, `clamav` healthy. Healthcheck is the readiness route `GET /api/v1/ready`. |
| `worker` | `python -m src.jobs.worker` (same image) | **Single replica.** Same `DATABASE_URL`, same `COPILOT_DATA_DIR`, same `documents` volume as the api. Healthcheck `python -m src.jobs.healthcheck 180` (a running worker heartbeat fresher than 180 s). |
| `clamav` | Official `clamav/clamav` image, clamd on TCP 3310 | **Not published to the host** (`expose` only). Signatures in the `clamav-signatures` volume. First start downloads signatures (minutes) and needs outbound access to the ClamAV mirrors. |
| `web` | Next.js `:3000` | After the api is healthy. |
| `caddy` | TLS edge, routes `/` to web and the API domain to api | The only service that publishes ports (80, 443). |

`COPILOT_DATA_DIR`, `FILE_SCAN_PROVIDER`, `CLAMAV_HOST` and `CLAMAV_PORT` are pinned in the compose `environment`
of both `api` and `worker` (they override `deploy/.env.staging`) so the two can never disagree about the
knowledge/index root or the scanner.

## Volumes and backup

| Volume | Content | Backed up |
|---|---|---|
| `db-data` | PostgreSQL | Yes: `pg_dump` (`deploy/scripts/backup.sh`) |
| `documents` | Private candidate documents (`/data/documents`) | Yes: tar |
| `knowledge-data` | Knowledge/index data root (`/data/knowledge`: Chroma index, knowledge stores) | Yes: tar (`COPILOT_DATA_DIR`) |
| `clamav-signatures` | Virus signatures | No (re-downloaded) |
| `caddy-data`, `caddy-config` | TLS certificates | No (re-issued by ACME) |

A restore is complete only when all three of database, documents and knowledge archives are restored
(`restore.sh` with `DB_DUMP`, `DOCS_TAR`, `KNOWLEDGE_TAR`). A restore without the knowledge archive leaves an
EMPTY knowledge base.

## Backup sets, restore drills and rollback (package 05B)

`backup.sh` and `restore.sh` remain the simple tar and `pg_dump` helpers. The checksummed, manifest-described, optionally sealed backup SET (database, private documents and
governed knowledge as one consistent unit, dry-run default, refusals instead of overwrites, tamper detection, encryption at rest required in hosted environments), the restore
drill, the backup-erasure procedure and the migration rollback rehearsal are `scripts/backup_set.py`, `scripts/restore_drill.py` and `scripts/rollback_rehearsal.py`; the procedure is
[`docs/production/BACKUP_RESTORE_RUNBOOK.md`](../docs/production/BACKUP_RESTORE_RUNBOOK.md). Drill records: `docs/production/execution/evidence/drills/`. Needed topology changes (a backup
runner, `pg_dump` in the image, an image tag pointer, a restore profile) are listed in section 9 of the runbook and are NOT made in the compose file (05A owns it). **No live drill
has been run on staging (OD-HOSTED).**

## Readiness

`GET /api/v1/ready` always checks the database and configuration. In staging and production it also reports
`data_root_writable` (gates readiness: 503 when the data root cannot be written) and, under `dependencies`, the
`worker_heartbeat` (`ok`, `stale`, `unknown`) and `scanner` (`reachable`, `unreachable`, `not_configured`) status
words. The worker and scanner are reported, not gating: a worker or scanner outage does not take the API out of
rotation, and uploads already fail closed when the scanner is unreachable (`MALWARE_SCAN_REQUIRED=true`). No path,
host or secret appears in the response.

## Configuration guards

Staging and production refuse to boot with `FILE_SCAN_PROVIDER=fake`. A hosted environment without `clamav` or
without `COPILOT_DATA_DIR` boots with a warning.

## NOT VALIDATED live (be explicit)

- No `docker compose up`, image build, volume mount, healthcheck or restart behaviour has been exercised.
- ClamAV scanning, signature download, the TCP 3310 path and `clamdcheck.sh` health inside the official image are
  untested. The image tag (`clamav/clamav:1.4`) should be confirmed at the first authorised deployment.
- The worker heartbeat healthcheck and the multi-process data-root sharing are tested offline only.
- Backup and restore were exercised only as a tar round trip with stubbed `pg_dump`/`pg_restore`; no real restore drill.
- The embedding provider is undecided (REVIEW-04): production must not rely on the hash/local embedder.
- `knowledge-data` starts empty: building or restoring the index is a separate step (package 02A).
