# 02A Evidence: permanent Knowledge Source reliability (REQ-OWN-05)

Branch `feat/02a-knowledge-persistence`, stacked on `origin/feat/02k-knowledge-contract` (f5eb3dc). Two commits: part 1 (identity, configuration, lifecycle) and part 2 (recovery, alerts, migration 0040, evidence). The PR targets `main` after 02K merges (or stacked on 02K until then). Passes the 02K conformance suite; `contracts.py` is untouched.

## Requirement mapping (REQ-OWN-05, K1 to K9)
| ID | Covered | How | NOT covered |
|---|---|---|---|
| K1 persistent registry, durable private files, persistent indexes | Yes, in code and tests | Registry is SQL. Private files no longer default to the system temp directory: they live in `<data root>/knowledge_private` (same volume as the Chroma index, which 05A mounts at `/data/knowledge`). Hosted guard blocks temp-directory placement of files, index or data root. Restart and new-interpreter tests prove registry, bytes, chunks and retrieval survive. | Hosted volume behaviour is not run (no deployment): OD-HOSTED / 05B drills. |
| K2 separate labelled curated and governed views | Yes | Readiness `views.curated` / `views.governed` plus two labelled panels; counts are never merged. | |
| K3 safe diagnostics, API and worker use compatible configuration | Yes | One `KnowledgeRuntimeConfig` (no second source of truth); worker identity recorded through its `job_workers` heartbeat id; `KnowledgeServingGuard`; `environment` block in the readiness response and the Admin page. | Worker identity covers data root, database and embedding settings (fingerprints), not chunk counts. |
| K4 manifests persist embedding identity and checksums | Partly | Registry-derived `IndexManifestV2` (collection checksum, per-source checksums) in diagnostics; backup manifest embeds one per collection. Provider/model/dimensions come from the runtime identity; `version` and so the compatibility hash stay unknown. | Embedding fields enforcement and refusal: 02B. |
| K5 lifecycle incl. replace, retire, reindex | Yes | `POST .../replace` (supersedes, idempotent), `POST .../reindex` (new `knowledge_reindex` job, id-only payload, deterministic chunk ids, no state change), retire made idempotent. Audited with new canonical event names. Licence/provenance/scan gates untouched. | |
| K6 real malware scanner | No | 02C. | all |
| K7 alerts, backup/restore | Yes | Alerts: four new in-app categories + existing `job_failed`; backup/restore CLI. "Retry/rebuild/rollback": reindex job, `--rebuild-index`, nothing destructive. | Incompatible-embedding alert: mechanism and test exist, the producer is 02B. |
| K8 restart, redeploy, separate-environment restore, provenance | Yes (offline) | See drills below. | Real redeploy and hosted restore drill (05B). |
| K9 UI never silently on an empty local demo DB; no invented counts | Yes | Hosted environment on SQLite is a BLOCKING guard finding (retrieval and uploads refused, readiness `configuration_error`); counts come only from the registry (test asserts 0 when empty). Hosted unknown `API_ENV` fails closed. | Detecting fake-scanner (demonstration) content in a hosted registry is left to 02C. |
Also: DEMO-01, H-WORKER (worker identity, hosted guard needs a worker to be comparable, `worker_not_seen` reported), H-KB-INGEST (uploads refused when the environment cannot serve).

## Changes
- New: `src/knowledge_admin/{config,environment,recovery,alerts}.py`, `scripts/knowledge_backup.py`, `migrations/versions/0040_knowledge_alert_categories.py`, tests `test_knowledge_persistence_02a_{identity,restart}.py`, `test_knowledge_recovery_02a.py`, `test_knowledge_alerts_02a.py`, harness `tests/_knowledge_env_02a.py`, `frontend/e2e/admin-knowledge-identity.spec.ts`, `frontend/tests/knowledge-identity-02a.test.tsx`.
- Modified: knowledge `wiring/service/runtime/jobs/policy/readiness/retriever`, `src/jobs/worker.py` (identity-bearing worker id), `src/api/{dependencies,routes/admin_knowledge,schemas/admin}.py`, audit names, alert definitions and categories, `KnowledgeReadiness.tsx`, `types.ts`; head string `0039` to `0040` in 26 test files plus README/CLAUDE.md; two registry-set assertions (`test_jobs_w10_9`, `test_knowledge_admin_w10_8` route set); one speech migration test now downgrades 0040 first.
- Not touched: the forbidden files (a test asserts it), `deploy/docker-compose.staging.yml`, the tracker, 02K contract.
- Migration 0040 is the ONLY schema change and is strictly necessary: `admin_notifications.category` is pinned by a CHECK. Data-preserving, fail-closed downgrade, single head.

## Security and privacy impact
No secret, URL, credential, absolute path or vector in any response, report or manifest (asserted on JSON text including the CLI output). Worker id carries only 12/8/6-hex fingerprints. Admin permission registry unchanged (44); reindex needs `knowledge.manage`, replace `knowledge.approve`; readiness stays `knowledge.read`. Unapproved knowledge still cannot reach candidate retrieval (tests for review-required, indexed-not-active, retired, reindex of non-active). Backup never deletes or overwrites, restore targets must be empty, tampered backups are refused before any write, no provider call (rebuild uses the local embedder and is refused when the source was not local).

## Recovery drills and results (all offline, temp directories only)
1. Restart persistence: build, register, approve, index, activate; discard every object; re-open engine, Chroma client, stores, worker over the same files: registry rows, file bytes, chunk count and candidate-facing evidence (title, source and version id, publisher, authority, language, chunk ids) identical; a new version then replaces the old one and survives a further restart. PASS.
2. Queued job survives restart and is completed by the new worker. PASS.
3. Redeployment: a brand-new Python interpreter over the same volumes returns identical evidence, chunk count, readiness and guard result. PASS.
4. Separate-environment restore: backup (2 sources, 3 versions, 2 built indexes), dry-run (writes nothing), execute into a new root, restored registry, every private file byte-identical, collection checksum equal, evidence equal to the source's; the source tree is byte-identical afterwards; changing the restored environment does not touch the source. PASS.
5. Disaster drill: source directory destroyed, restore from backup alone, same evidence. PASS.
6. Refusals: non-empty backup target, active jobs, non-empty restore target (second restore over the first changes nothing), unrelated existing files untouched, tampered file/registry/chunks/index detected, approval evidence with no actor in the target (explicit `--fallback-user-id` required; a restored approval is never attributed to an invented user). PASS.
7. CLI round trip (dry-run default, execute, verify, restore, refused re-run, fixed error codes, no paths). PASS.
8. Migration 0040: upgrade, constraint accepts the four categories and refuses unknown, fail-closed downgrade preserves data, re-upgrade. PASS.

Finding made by the drill: the restored registry must satisfy the `ck_ksv_approval_evidence` CHECK, which needs an approver; hence the explicit restorer-of-record rule above rather than silently clearing or inventing actors.

## Tests and commands
| Check | Result |
|---|---|
| 02A suites (identity 29, restart 4, recovery 17, alerts 11) | 61 passed (.venv); 22+ passed with p10cg under /tmp/ci_venv (83 total with p10cg) |
| Full `pytest tests`, .venv | 5216 passed, 41 skipped, 1 failed (`test_global_eval_p10cg::test_runs_are_deterministic...`) |
| Full `pytest tests`, /tmp/ci_venv | 5214 passed, 43 skipped, same 1 failed |
| Failing test re-run alone | passes in both venvs. The two full runs were executed concurrently on one machine and that test inspects shared temporary stores; treated as a concurrency artefact, to be confirmed by CI |
| First full run (before the head-string fixes) | 10 failures, all caused by head `0039` literals in evaluators, the release matrix and one retriever test double; fixed in the part 2 commit |
| `ruff check .`, `ci_test_shards.py verify --shards 4` | pass, 270 files |
| Frontend `tsc`, `eslint`, full vitest | clean, 1087 passed; Playwright (E2E_PORT=3155) identity spec 3 + admin knowledge specs 3 passed |
| `eval_admin_knowledge.py`, `eval_admin_jobs.py` | PASS, 0 paid calls |
Commands: `pytest tests/test_knowledge_persistence_02a_identity.py tests/test_knowledge_persistence_02a_restart.py tests/test_knowledge_recovery_02a.py tests/test_knowledge_alerts_02a.py` (60 tests plus the K9 test), existing knowledge suites (`test_knowledge_admin_w10_8`, `test_knowledge_readiness_w12_4a`, `tests/contracts`, `test_jobs_w10_9`), `scripts/eval_admin_knowledge.py` and `eval_admin_jobs.py` (PASS, 0 paid calls), `ruff check .`, `scripts/ci_test_shards.py verify --shards 4`, frontend `tsc`, `eslint`, vitest, Playwright (`E2E_PORT=3155`).

## Remaining risks
- Worker identity rides in `job_workers.worker_id` (30 chars) to avoid a migration; it is a fingerprint comparison, and a worker started by an older build shows `unrecorded` (a warning, never a match).
- File-level copy of the Chroma directory assumes a quiesced index (the tool refuses while knowledge jobs are active and marks forced backups inconsistent); `--rebuild-index` is the fallback for local-embedder sources only.
- Chroma's native client can abort an interpreter at exit intermittently (seen once in several runs before the harness released clients); the suite releases clients after each simulated process and 10 consecutive runs of the recovery file exited 0.
- Guard result is cached 15 s; an operator sees a change after at most that time.
- Hosted behaviour (real volumes, PostgreSQL, multi-worker) is unvalidated until 05A/05B drills.
- Embedding enforcement, malware scanning and demonstration-scanner detection belong to 02B and 02C.

## Throughput record
Start 2026-10-21 18:34 UTC. End: see final report. Estimate 10-15 engineering days; actual wall-clock about 1.5 hours of agent time. Rework rounds (fix commits after first push): 0 at time of writing. CI duration: pending (CI runs only once a PR exists).

## Addendum: integration fix (evaluator head literals)
Four more evaluators still asserted head 0039 (`eval_w11_integrated`, `eval_rc_p10_003`, `eval_admin_security`, `eval_admin_qualification`); bumped to 0040 (count 39 to 40), historical artifacts and RC manifests untouched. All four PASS under both venvs. Full backend suite re-run SEQUENTIALLY: .venv 5217 passed, 41 skipped; /tmp/ci_venv 5215 passed, 43 skipped. The earlier `test_global_eval_p10cg` failure did not recur, confirming it was a concurrent-run artefact. Rework rounds after first push: 1.
