# Staging topology notes (package 05A)

> 27 October 2026: PR273 merged with seven green main workflows; actual offline full-stack campaign29/0/6. **Deployment freeze remains.** The [Task08 owner authorization/readiness preflight](../docs/production/execution/WAVE4_TASK08_AUTHORIZATION_PREFLIGHT.md) supersedes dated qualification-gap descriptions below for current offline engineering. No hosted deployment or gate acceptance is inferred; this documentation grants no execution permission.

## DEPLOYMENT FREEZE

`deploy/docker-compose.staging.yml` is the full staging topology **as code only**, not a deployment. Its
application images and isolated disposable test stacks have been exercised in Wave 4; the full hosted topology
has never been started. These tests do not establish hosted readiness.
**Do not deploy it** until the owner answers decision **OD-HOSTED** and explicitly authorises a deployment.
Nothing in this file or in the tests claims the topology works live.

## Immutable application releases (Wave 4 Task 03)

The base file remains the build/topology template. **Do not deploy it with `up --build` or layer it onto a
release profile.** Use the manifest-verified, image-only profiles from `scripts/release_images.py` after
separate hosting authorization. API, worker and migrate use one immutable local Docker image ID; web uses
the matching image from the same Git SHA. No registry upload is assumed or implemented.

[Local build, verification, offline transfer, promotion and application rollback procedure](../docs/production/execution/WAVE4_TASK03_IMMUTABLE_RELEASE.md).
The helper prepares files and refuses incompatible/unsettled rollback; it never starts services or executes
migrations. Runtime secrets stay in an explicitly supplied external env file, never the image/manifest.

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
runner, `pg_dump` in the image, and a restore profile) are listed in section 9 of the runbook and are NOT made in the compose file (05A owns it). **No live drill
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

- The full hosted topology, persistent-volume/healthcheck/restart behavior and proxy path have not been exercised.
  Local image builds, metadata/Compose verification and isolated migration/admission/frontend tests are separate engineering evidence.
- ClamAV scanning, signature download, the TCP 3310 path and `clamdcheck.sh` health inside the official image are
  untested. The image tag (`clamav/clamav:1.4`) should be confirmed at the first authorised deployment.
- The worker heartbeat healthcheck and the multi-process data-root sharing are tested offline only.
- Backup and restore were exercised only as a tar round trip with stubbed `pg_dump`/`pg_restore`; no real restore drill.
- The embedding provider is undecided (REVIEW-04): production must not rely on the hash/local embedder.
- `knowledge-data` starts empty: building or restoring the index is a separate step (package 02A).

## Optional shared Redis preparation

Task 04 adds optional internal or managed Redis through the existing immutable release generator, without changing the default single-process template or deploying anything. Read the [decision record](../docs/production/execution/WAVE4_TASK04_REDIS_DECISIONS.md) and [complete bucket audit](../docs/production/execution/WAVE4_TASK04_REDIS_AUDIT.md). H-REDIS-POLICY and OD-HOSTED remain OPEN. Do not combine generated profiles with a Redis overlay. The internal fragment is not a standalone deployment file. Required-shared profiles gate readiness on actual shared enforcement; existing per-bucket local/deny behavior is preserved.


## Task 05 budget boundary (no activation)

Hosted API/worker refuse inference without the existing production governor in
`AI_BUDGET_MODE=enforce`, an owner-authored approved JSON, matching private marker,
current pricing, healthy PostgreSQL ledger, permitted category and inactive kill.
No supplied template or generated plan constitutes approval. Keep kill engaged.
Use the existing release prepare command with optional
`--budget-config-file <absolute-private-owner-JSON>` to mount the same read-only
file for API/worker. The generator copies no JSON/marker and makes no provider call.
Absent that option, AI remains closed. Qualify actual file access for UID 10001;
protect it from unrelated host users and do not use a writable bind mount.
Configuration/period changes require authorized reconciliation; counters, unknown
outcomes and kill state never reset on release or application rollback. Incapable
old images are refused. Redis request limiting is separate from monetary limits.
See `docs/production/execution/WAVE4_TASK05_BUDGET_AUDIT.md` and the OPEN
`OD_BUDGET_SPECIFICATION_TASK05.md`. Original development databases stay untouched.

## Enforced page CSP and rendering (POST272-03)

Next.js middleware generates a fresh 256-bit nonce for each page request, replaces
untrusted request nonce/CSP headers, and supplies the same enforced policy to SSR
and the response. Framework/bootstrap scripts and the two developer-authored
inline scripts receive this nonce. `script-src` retains `self` and permits only
that response's nonced inline scripts; no `unsafe-inline`/`unsafe-eval` script
exception, wildcard, report-only mode or test bypass is introduced. The existing
style policy is unchanged. API HTTPS/WSS origins come from the validated public
API build setting; no request Host/Forwarded header can choose an allowed origin.

Caddy retains HSTS, frame/permissions/MIME/referrer protection and trusted API
proxy handling. Its deferred default CSP applies only when the upstream has no
policy (assets/upstream errors); it must not overwrite or append a second static
page policy. The API continues to own its independent CSP and CORS restrictions.

All pages explicitly render dynamically. Nonce-bearing HTML is private/no-store:
do not add HTML/CDN caching, ISR, static export or partial prerendering to this
profile. Static bundles, fonts and image assets retain their ordinary caching.
This trades page-generation work for per-response script authorization. Review
capacity before any separately authorized deployment; no hosting is activated.

`scripts/csp/qualify.py --execute-disposable` is a focused Linux/local-Docker-host
before/after browser check using the existing immutable release manifest, a pinned
original-main frontend, actual Caddy internal TLS, real FastAPI/PG authentication,
and memory-captured email. See `docs/production/execution/POST272_03_CSP_REMEDIATION.md`.
It is not the full PR #273 campaign, which retains its failed historical evidence.
