# 05A evidence: staging topology as code

Status: code complete, **NOT deployed, NOT validated live**. DEPLOYMENT FREEZE until the owner answers OD-HOSTED and authorises a deployment.

## Requirement IDs

PG-01 (partial), REQ-OWN-05 K1/K3/K6 prerequisites, EX-12.1 to EX-12.6, EX-12.14, EX-12.15, H-ENV, H-WORKER, gap G1 (Phase 00).

## Changes

- `deploy/docker-compose.staging.yml`: services now exactly `db, migrate, api, worker, web, caddy, clamav`. New `worker` (`python -m src.jobs.worker`, API image, single replica, depends on db healthy + migrate completed + clamav healthy, heartbeat healthcheck, `restart: unless-stopped`). New `clamav` (official image, `expose: 3310` only, no `ports`, `clamav-signatures` volume, healthcheck). New volumes `knowledge-data` (mounted at `/data/knowledge` in api and worker) and `clamav-signatures`; `documents` now also mounted in the worker. `COPILOT_DATA_DIR`, `FILE_SCAN_PROVIDER`, `CLAMAV_HOST/PORT` pinned in compose for api and worker. API healthcheck now `GET /api/v1/ready`. Freeze note in the header.
- `src/application/hosted_readiness.py` (new), `src/api/routes/health.py`: in staging/production `/ready` adds `data_root_writable` (gating) and `dependencies.worker_heartbeat` / `dependencies.scanner` (status words, not gating). Dev/test response shape unchanged.
- `src/jobs/healthcheck.py` (new): worker container healthcheck (fresh `running` heartbeat within 180 s).
- `src/api/env_validation.py`: staging/production fail closed on `FILE_SCAN_PROVIDER=fake` (guard did not exist); warnings for a non-clamav provider and for unset `COPILOT_DATA_DIR`.
- `deploy/.env.staging.example`: `COPILOT_DATA_DIR`, `JOB_WORKER_POLL_SECONDS`, embedding provider note (production must not rely on the hash embedder; REVIEW-04), scanner notes. Placeholders only.
- `deploy/scripts/backup.sh`, `restore.sh`: knowledge data root archive/restore added (`COPILOT_DATA_DIR`, `KNOWLEDGE_TAR`), backward compatible.
- `deploy/README-staging.md` (new), `docs/operations_deployment.md` (new section).
- `tests/test_staging_topology_05a.py` (29 tests).

## Security and privacy impact

Scanner port is never published; only caddy publishes ports. Readiness exposes status words only (no path, host, secret; test-asserted). The fake scanner is refused in hosted envs. No secrets committed (test-scanned). No new data collected. The worker gains access to the documents volume (private candidate documents): same trust boundary as the api, same image.

## Recovery verification (what a restore must contain)

Database dump, documents archive and knowledge-data archive. Missing the knowledge archive means an EMPTY knowledge base. ClamAV signatures and Caddy certificates are re-creatable. Verified offline only: a tar round trip of documents and knowledge with stubbed `pg_dump`/`pg_restore` (a test). No real restore drill (package 05B).

## Tests and regression evidence

All run offline, no docker, no network, no provider.

| Command | Result |
|---|---|
| `pytest tests/test_staging_topology_05a.py` (main venv) | 29 passed |
| `pytest tests/test_staging_topology_05a.py` (/tmp/ci_venv) | run completed but the pass count was NOT captured (output cut off): UNVERIFIED, must be re-run |
| `pytest test_p8_hardening, test_service_resilience_w9_1, test_integrations_w10_6, test_jobs_w10_9, test_health` (main venv) | completed, summary line not captured: UNVERIFIED, must be re-run |
| `ruff check .` | All checks passed |
| `scripts/eval_hosting_readiness.py` | 15 PASS, 1 FAIL `migration_single_head`: environment artifact, the evaluator's subprocess replaces PYTHONPATH so alembic is not importable under my ad hoc interpreter invocation. `alembic heads` run separately shows the single head `0039_speech_governance`. Must be re-run under a healthy interpreter. |
| `bash -n` backup.sh, restore.sh, migrate.sh | OK (also a pytest) |

Environment fault: the Homebrew python3.11 was overwritten mid-task by a self-re-executing wrapper (file dated 20:06 local). I ran the tests through the framework `Python.app` binary with the venv `site-packages` on PYTHONPATH, and I issued one `pkill -f` against my own looping pytest process before the coordinator's instruction. All results above must be re-run once the interpreter is repaired.

## SHA and CI

See the final report (filled after push); CI only runs once a PR exists.

## Remaining risks

Never started: compose syntax is parsed by tests but not by `docker compose config`; the `clamav/clamav:1.4` tag and `clamdcheck.sh` healthcheck are unverified; clamd first-start signature download may exceed the healthcheck start period; worker/scanner outages are reported not gating in `/ready`; the worker lease/claim behaviour is only tested on SQLite; embedder is the hash fallback until REVIEW-04; `knowledge-data` starts empty (package 02A); `web`/`caddy` unchanged and unvalidated.

## THROUGHPUT RECORD

- Start: 2026-10-21T18:03:23Z. End of authoring: 2026-10-21T18:14:35Z (before push).
- Estimate: 8-12 engineering days (register). Actual wall-clock: about 11 minutes of agent time (excludes owner review, CI and the unverified live validation, so not comparable).
- Rework rounds (fix commits after first push): 0 at the time of writing.
- CI duration: not available until a PR exists.
