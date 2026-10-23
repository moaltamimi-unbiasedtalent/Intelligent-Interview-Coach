# 05B evidence: persistence, backup, restore and rollback drills (PG-09)

Branch `feat/05b-backup-restore-drills` from `origin/main` f5cf7cb. Status: **tooling, procedure and offline drills delivered; NOT run on hosted staging (OD-HOSTED); PostgreSQL-only tests written but NOT RUN in this delivery (no disposable PostgreSQL was available)**. No migration (none needed: no schema change; alembic head untouched, verified by `tests/_alembic_head.py`).

## Requirement mapping

| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| PG-09 backup, restore, rollback drills repeatable and recorded offline | Yes, offline | `scripts/backup_set.py`, `scripts/restore_drill.py`, `scripts/rollback_rehearsal.py`; records in `docs/production/execution/evidence/drills/` | Hosted verification is explicitly open |
| EX-12.7 / EX-12.8 backup of database, private files and indexes as one restorable set | Yes, offline | `src/backup_set/engine.py` builds ONE manifest-described set (database snapshot, private documents, 02A governed knowledge backup); restore into a separate environment with post-restore verification | `pg_dump`/`pg_restore` through the set is tested only with stub binaries (argv, environment, refusals) and in `tests/test_pg_05b.py` (NOT RUN); legacy curated stores under the data root are not in the set (rebuildable) |
| EX-12.9 / EX-12.10 rollback rehearsal | Yes, on SQLite | `src/backup_set/rollback.py`: upgrade, fail-closed refused downgrade (revision and every row count unchanged), clean one-revision downgrade, re-upgrade, restore of the pre-migration set; record `rollback-...-offline-sqlite` | PostgreSQL DDL branches (test written, NOT RUN); application rollback by image tag is DOCUMENTATION only (runbook section 6), never executed; timing at volume |
| H-BACKUP | Yes, offline | dry-run default, never overwrite or delete, refuses non-empty target and active jobs, checksums, tamper detection, source-unchanged check | hosted run; off-site copy; restore time at real volume |
| PRIV-BACKUP erasure from backups within a stated window | Yes, procedure and tooling | `src/backup_set/erasure.py`: window stated (35 days, an engineering default awaiting owner and legal confirmation), hash-chained ledger, plan, rewrite with the ONE deletion engine, operator attestation, post-restore re-deletion | Backups outside this tool (provider snapshots, replicas); PostgreSQL set rewrite is a manual procedure NOT exercised; the tool cannot verify media destruction; legal confirmation of the window |
| Encryption at rest stated and checked | Yes | Required in every hosted `API_ENV` (unknown values included): execute refused unless the set is sealed (AES-256-GCM, signed) or storage encryption is attested; `verify --require-encryption`; key handling in the runbook and `src/backup_set/crypto.py` | Attestation is not verified by the tool; key custody, rotation and escrow are operator processes, not exercised |
| H-PG-MULTI (job claim `FOR UPDATE SKIP LOCKED`) | Test written | `tests/test_pg_05b.py`: 4 concurrent workers claim 24 jobs exactly once; a held row lock is skipped, never waited on | **NOT RUN** (skipped without `TEST_DATABASE_URL`) |
| H-PG-QUERY (audit-trigger DDL) | Test written | trigger and function exist in the catalogue; UPDATE, DELETE and a JSON context change are refused; the actor-to-NULL anonymisation (FK `SET NULL`) is allowed | **NOT RUN** (first live execution of that DDL; it was only rendered and unit-checked before) |
| H-PG-SECRETS (managed secrets table) | Test written | ciphertext-only (`bytea`), unique slot, revision check constraint, optimistic concurrency, wrong master key yields no value | **NOT RUN** |
| R-96a / R-96b (restore and rollback records) | Offline records | the two committed records | hosted records |

## Changes

New package `src/backup_set/` (`engine`, `crypto`, `erasure`, `drill`, `rollback`, `fixture`, `runtime`); scripts `backup_set.py`, `restore_drill.py`, `rollback_rehearsal.py`; runbook `docs/production/BACKUP_RESTORE_RUNBOOK.md` (includes the needed compose, image and tag changes: NOT made, `deploy/docker-compose.staging.yml` is untouched); pointers in `deploy/README-staging.md`, `deploy/scripts/backup.sh` (comment only) and `docs/operations_deployment.md`; tests `tests/test_backup_set_05b.py` (41), `tests/test_rollback_rehearsal_05b.py` (6), `tests/test_pg_05b.py` (7, skipped without a disposable PostgreSQL); two drill records. Existing 02A recovery code and the 05A scripts are reused unchanged.

## Security and privacy impact

Operator tooling only: no API route, no candidate surface, no provider call, no new permission (registry stays 44). A backup set holds candidate personal data and managed-credential ciphertext, so the tool requires sealing or an explicit attestation in hosted environments, never accepts a key on the command line, and never writes a key, path, URL or credential to a manifest, report, log or drill record (tests scan manifests, reports, records, CLI output and every byte of a sealed set). Credentials for `pg_dump`/`pg_restore` go through the child environment and the child's stderr is discarded. Restore never overwrites or deletes; the erasure ledger stores only numeric account ids and refuses extension when its hash chain is broken. The deletion engine is reused, not duplicated.

## Tests (exact commands and results)

All offline; no docker, no network, no provider, no PostgreSQL.

| Command | Result |
|---|---|
| `pytest -p no:cacheprovider tests/test_backup_set_05b.py tests/test_rollback_rehearsal_05b.py tests/test_pg_05b.py`, repo venv | 49 passed, 7 skipped (the 7 are `tests/test_pg_05b.py`: "TEST_DATABASE_URL not set: no disposable PostgreSQL for this run (05B PostgreSQL-only paths NOT EXERCISED)") |
| same, fresh-dependency canary `~/.cache/ask4mo/ci_venv` | 49 passed, 7 skipped |
| `ruff check .` (both venvs) | All checks passed |
| `python scripts/ci_test_shards.py verify --shards 4` | OK: 303 test files, each in exactly one of 4 shards |
| 47 CI evaluators (every `scripts/eval_*.py` in `.github/workflows/ci.yml`), repo venv and canary | all exit 0 (47 of 47 on each); working tree clean afterwards |
| `pytest -p no:cacheprovider -n 3 --dist loadfile -q` (FULL backend suite, repo venv, once before the final push, merged with origin/main f5cf7cb which had not moved) | 6374 tests, 0 failures, 0 errors, 48 skipped (7 are `tests/test_pg_05b.py`; the other 41 are existing skips). A first run had one failure, `tests/test_language_readiness_06a.py::test_committed_audit_table_is_current_and_labels_every_language_unqualified`, only because the worktree had no `frontend/node_modules` (the locale-inventory helper needs `esbuild`); with the uncommitted symlink to the main checkout's `node_modules` that test passes and the full re-run above is clean. Not a code defect |

Negative and refusal cases covered: non-empty or inside-source backup target, active jobs, source changed during copy (no manifest), modified/missing/unlisted file, unsafe manifest path, symlink in a set, edited signed manifest, wrong key, swapped or truncated sealed file, unencrypted set in four hosted environment names, non-empty restore target (pre-existing file intact), tampered set restore (nothing written), row-count mismatch, ledger edit/deletion/reordering, attestation of a set still present, expiry attestation before retention age, absent set without attestation, unregistered set, restored old backup re-deleted by the ledger, a seeder that fails to make the downgrade refuse (rehearsal turns FAIL).

## Drill records (offline, synthetic; hosted NOT RUN)

* `drill-20261022T122512Z-offline-sealed`: PASS (16 checks: set verified, dry run writes nothing, restore into a separate environment, second restore refused, schema revision, 93 tables / 36 rows, 4 documents, knowledge files, index checksum against manifest and live source, retrieval probe parity, tamper file, unlisted file, edited manifest, restore of tampered set refused, source unchanged). Sealed with a throwaway key (never stored) and signed.
* `rollback-20261022T122512Z-offline-sqlite`: PARTIAL by design: all six executed steps PASS; application rollback by image tag and the PostgreSQL DDL branches are recorded NOT_RUN.

## Risks and limits

* The synthetic drill proves the tool and procedure, not hosted infrastructure, data volume, restore time or object-storage behaviour.
* Chroma segment files change mtime when a collection is merely opened, so the index directory is fingerprinted by file names and sizes only during the copy; index writes are otherwise excluded by the active-jobs check. A rewritten set carries the shared knowledge unchanged.
* An unsigned, unsealed manifest can be edited together with its files: record `manifest_sha256` out of band or sign. The drill reports that case as PARTIAL.
* The 35-day retention and erasure window is a stated engineering default; it is not a legal statement and the tool never claims more than operator attestation supports.
* `AccountDeletionService` is applied to a scratch SQLite restore; billing-retained accounts keep only the anonymised shell, as in the live path. Agent checkpoint threads in a separate store are not in the set.
* Rewrites of PostgreSQL sets and the whole PostgreSQL path through the set are untested here (stub binaries only).

## Still missing: human, live-staging and gate evidence

* Hosted staging drill (backup, restore, rollback, erasure) with a sealed set: OD-HOSTED (NOT RUN).
* `TEST_DATABASE_URL` run of `tests/test_pg_05b.py` against a disposable PostgreSQL (with `pg_dump`/`pg_restore` on PATH): NOT RUN. Behaviours not exercised: `FOR UPDATE SKIP LOCKED` claim exclusivity and non-blocking, the PostgreSQL append-only trigger function, the managed secrets table constraints on PostgreSQL, `pg_dump`/`pg_restore` through the set, PostgreSQL FK branches of the head migration downgrade, PostgreSQL set rewrite.
* Owner and legal confirmation of the retention and erasure window; key custody and escrow decision; backup runner, `pg_dump` in the image, image tag pointer and restore profile in the staging compose (runbook section 9, owned by 05A).
* No independent, legal or security review has been done; none is implied.

## SHA and throughput

Implementation commits 092f99b3 (code, tests, runbook), e51bde4c (drill records), 3d5e656a (evidence), all on `feat/05b-backup-restore-drills`; compare URL https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/05b-backup-restore-drills (the head after this evidence follow-up is in the final report, verified with `git ls-remote`). CI: no PR exists (the lead opens it); CI result NOT AVAILABLE.
Start 2026-10-22T05:22Z; first push: 2026-10-22T12:40Z (about 7 h 18 min wall clock, dominated by full-suite and 94 evaluator runs); rework rounds before first push: 4 (source-fingerprint mtime false positive found by the rewrite test, fixture approver was a deletion subject, three test-assertion fixes); fix commits after first push: none (one evidence-only follow-up commit for the SHA and timing).
