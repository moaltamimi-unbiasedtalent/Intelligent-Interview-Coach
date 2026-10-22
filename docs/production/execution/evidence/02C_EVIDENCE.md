# 02C Evidence: real malware scanning for uploads (REQ-OWN-05 K6)

Branch `feat/02c-clamav-scanning`, from `origin/main` f9a06a9 (Alembic head `0040_knowledge_alert_categories`, unchanged: NO migration). Scope: a real clamd client (zINSTREAM) with fail-closed behaviour for BOTH candidate document uploads and governed knowledge uploads. No real clamd or docker was run; every test uses a fake clamd TCP server on 127.0.0.1 with an ephemeral port.

## Requirement mapping
| Item | Covered | How | NOT covered |
|---|---|---|---|
| REQ-OWN-05 K6 real scan, fail closed | Covered in code and offline tests | `ClamdClient` + `ClamAvScanner` (`src/documents/file_security.py`); `enforce_scan` fail-closed for candidate and governed paths | A real clamd in staging (see Remaining operational evidence) |
| clamd INSTREAM protocol | Covered | `zINSTREAM\0`, 4-byte big-endian length-prefixed chunks (64 KiB), terminating zero chunk; replies `stream: OK`, `stream: <sig> FOUND`, `... ERROR`; `zPING` and `zVERSION` | Behaviour against genuine clamd versions |
| Bounded timeouts, chunk size, maximum stream | Covered | connect timeout 3 s and total wall-clock deadline 30 s per scan (env `CLAMAV_CONNECT_TIMEOUT_SECONDS`, `CLAMAV_SCAN_TIMEOUT_SECONDS`); chunk 64 KiB; max stream 25 MiB (`CLAMAV_MAX_STREAM_BYTES`, refused locally as too_large before any byte is sent); reply read capped at 4 KiB | |
| Strictly typed results | Covered | `ScanStatus`: clean, infected, unavailable, error, too_large, timeout. `ScanResult` gains `status` and `signature` (backward compatible; clean and status must agree). Signature name is charset-restricted (`[A-Za-z0-9._+-/]`, max 64) else `unnamed-signature`; no content, path or raw reply is retained | |
| Fail closed everywhere | Covered | Non-clean never passes. Outage, timeout, error, malformed or empty reply raise `FileScanUnavailable` (503), infection raises `FileRejected` (422), over-limit raises `FileTooLarge` (413). In the governed worker any non-clean result sets state `failed` before any parse, index or serve | |
| Outage distinguishable from infection | Covered | Candidate routes: 503 `scan_unavailable` vs 422 `scan_infected` vs 413 `scan_too_large` in the existing error envelope (`error.code`). Governed: `scan_status` `scan_unavailable` vs `scan_failed` and `failure_category` of the same names | |
| Outage in readiness and in-app alert | Covered | `/ready` (hosted) reports `dependencies.scanner` (existing) plus `scanner_signatures` (fresh/stale/unknown, only for a reachable scanner) and `scan_records: untrusted` (only when present). Alert reuses the existing `job_failed` category with dedupe keys `scanner_unavailable` and `scanner_signatures_stale` (no new category, no migration); raised by upload failures, governed scan jobs and readiness; resolved when the scanner is seen healthy | Admin integrations panel was not changed (no frontend change); `probe_malware_scanner` already uses `available()` which is now a real clamd PING |
| Scan results recorded where the lifecycle records them | Covered | Existing `knowledge_source_versions.scan_status` (DB-constrained vocabulary `not_scanned/scan_passed/scan_failed/scan_unavailable`) and `scanner_name`. The vocabulary can represent every outcome (infected and too_large map to `scan_failed`; unavailable, timeout and error map to `scan_unavailable`), so no extension and no migration | |
| Approval blocked unless a passed real-scanner result | Covered | `KnowledgeAdminService.blockers` (used by approve, index, activate, replace): a passed status with scanner `null` is refused everywhere; in hosted environments a `fake`, `null`, empty or missing scanner name is refused | Candidate documents have no stored scan column (a candidate upload is accepted only after the scan passes, then stored) |
| Hosted environments reject fake scanner | Covered | Existing boot guard (05A) unchanged; additionally `enforce_scan` refuses the fake and null scanners when `API_ENV` is staging or production, and `scan_required()` is always true there | |
| K9 residual: fake-scanner content in a hosted registry | Detected and reported, blocked from approval | `count_untrusted_scan_records` (`environment.py`) surfaced in hosted `/ready` as `scan_records: untrusted`; approval and activation refuse such records | NOT added as a serving-guard blocking finding: the merged 02A tests assert the hosted guard has zero findings while their harness uses the fake scanner, and weakening them was not permitted. The owner may later choose to make it a blocking guard finding together with an update of those fixtures |
| Re-scan on reindex or replace | Not required, not done | | |

## Changes
- `src/documents/file_security.py` (rewritten): `ScanStatus`, extended `ScanResult`, `FileTooLarge`, `ClamdClient`, `parse_clamd_reply`, `parse_signature_age_days`, real `ClamAvScanner` (+ `health()`), `scanner_health`, hosted guards in `enforce_scan`/`scan_required`, `fake_scanner_forbidden`. The fake scanner docstring now says it is a development simulation.
- `src/api/routes/documents.py`: `_scan_or_reject` maps outcomes to 503/422/413 with stable error codes and drives the alert (upload and replace).
- `src/knowledge_admin/runtime.py`, `alerts.py` (`observe_scanner`), `service.py` (`blockers`), `environment.py` (`count_untrusted_scan_records`).
- `src/application/hosted_readiness.py`, `src/api/routes/health.py`: signature freshness, untrusted-record report, alert hook.
- Tests: `tests/_fake_clamd.py` (fake clamd; EICAR assembled at runtime from two fragments, never written to disk or committed whole by the new code) and `tests/test_clamav_scanning_02c.py` (52+ tests).
- Not edited: `deploy/docker-compose.staging.yml`, `src/knowledge_admin/contracts.py`, migrations, the tracker, the register.

## Security and privacy impact
- Candidate content is never logged, returned or stored in a scan result; the candidate sees only a fixed message, never a signature name. Signature names never reach any response, alert row or audit payload (alert rows hold only the code-defined title, category and source id `malware_scanner`).
- A scanner outage can never let a file through (also when scanning is "optional": a real scanner that cannot scan always raises). An infected or too-large file is rejected before storage (candidate) or before parsing (governed).
- Unsolicited consequence: a hosted environment can no longer run with the fake or null scanner at all (503 on every upload) rather than silently skipping scanning.
- No network is contacted by any code path other than the configured clamd host and port; tests only use loopback.

## Tests and commands
- Targeted: `/tmp/ci_venv/bin/python -m pytest tests/test_clamav_scanning_02c.py -p no:cacheprovider` -> 54 passed. Same file plus `test_knowledge_admin_w10_8`, `test_staging_topology_05a`, `tests/contracts`, `test_integrations_w10_6`, `test_documents_api` under BOTH the repo venv and the CI canary venv: 282 passed each.
- `ruff check .` -> All checks passed. `python scripts/ci_test_shards.py verify --shards 4` -> OK (281 test files in exactly one shard before adding mine; the new file is picked up by the shard script automatically, re-verified after adding it).
- All 46 evaluators referenced by `.github/workflows/ci.yml` were run once before the final push with the CI canary venv: all exit 0.
- Full backend suite once (`/tmp/ci_venv/bin/python -m pytest tests -n 3 --dist loadfile -q -p no:cacheprovider`): 3 failures, none caused by this change. (1) the stale 02A scope lock above (identical failure on main). (2) `tests/test_language_readiness_06a.py::test_committed_audit_table_is_current_and_labels_every_language_unqualified`: the worktree has no `frontend/node_modules`, so the node helper cannot run (identical failure on a clean `origin/main` worktree). (3) `tests/test_global_eval_p10cg.py::test_runs_are_deterministic_and_dispose_of_their_temporary_stores`: it compares `p10cg_*` directories in the shared system temp directory, so concurrent runs by other agents on this machine make it fail; it passes (22 passed) when rerun alone and on main. The pytest summary line was not printed by the quiet configuration, so the pass count is not quoted.
- Known pre-existing failure, not caused by this change: `tests/test_knowledge_persistence_02a_identity.py::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` diffs against the historical branch `origin/feat/02k-knowledge-contract` and fails locally on `src/agent/*` and `ci.yml` regardless of this change (it also lists `src/documents/file_security.py`, which this wave owns). It is a stale branch-relative scope lock; it needs the lead's attention, I did not touch it.

## Risks and limitations
- The clamd client is verified against a protocol-faithful fake, not a real clamd. Real-daemon behaviour (version/timeouts under load, `StreamMaxLength` mismatch with `CLAMAV_MAX_STREAM_BYTES`, reply framing) is UNVERIFIED.
- clamd's own `StreamMaxLength` must be at least `CLAMAV_MAX_STREAM_BYTES`, and the compose clamav service config must permit TCP 3310 internally; if staging changes are needed they belong to 05A (compose not edited here).
- Each readiness probe opens up to three short loopback or internal connections (PING, PING, VERSION) and each upload one PING plus one scan connection.
- The in-app alert reuses the `job_failed` category, so its title reads "A background job failed terminally" for a scanner outage; the source id `malware_scanner` and the dedupe key distinguish it. A dedicated category would need a migration (not done).
- Signature freshness is derived from clamd's VERSION build date (default threshold 3 days, `CLAMAV_MAX_SIGNATURE_AGE_DAYS`); it detects a stale database only if freshclam is expected to update it.
- A governed scan outage marks the version failed with `scan_unavailable` (existing behaviour, permanent job failure, explicit reprocess re-queues). It is not auto-retried.

## Remaining human or operational evidence (BLOCKED on OD-HOSTED)
1. A real clamd container in staging (the 05A topology service) and an EICAR test through it end to end (the register's required "dedicated CI job with a real clamd container" and EX-12 #13): NOT RUN, no docker allowed here.
2. Signature freshness in staging: freshclam running, `/ready` `scanner_signatures: fresh`, and the stale-signature alert observed.
3. A scanner outage drill in staging (stop clamd, observe 503 `scan_unavailable` and the Admin alert, restart, observe resolution).
4. Confirmation that clamd `StreamMaxLength` and the app limits agree, and that the staging compose needs no change (otherwise a 05A change).

## Throughput record
Start 2026-10-22T01:23 (local clock). First push: see final report. Rework rounds: 2 (hosted-guard finding downgraded to a readiness report to keep the merged 02A tests unmodified; shared-database pollution in the readiness tests fixed with a per-test database). CI: not available until a PR exists.
