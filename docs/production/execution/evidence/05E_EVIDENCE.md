# 05E Evidence: privacy, legal and data-rights readiness, PR 1 (engineering safeguards)

Branch `feat/05e-privacy-safeguards`, from `origin/main` f5cf7cb4 (Alembic head `0043_story_bank_completion`). **No migration was added** (see "Why no migration"). This file covers PR 1. PR 2 (`feat/05e-legal-review-pack`, evidence in `05E_LEGAL_PACK_EVIDENCE.md`) holds the review-ready legal material; the legal page copy is unchanged in both PRs.

**Claim discipline.** Everything here is an engineering safeguard verified by offline tests and evaluators. Nothing here is a GDPR or other legal-compliance claim, none of it is independent or legal sign-off, and **legal review (LG-10, PG-04) stays open: counsel is a long lead and no sign-off exists.** Hosted verification: **NOT RUN.**

## Requirement mapping

| Id | Requirement | Covered here | NOT covered |
|---|---|---|---|
| W9.8-D10 | Additional account-deletion safeguards | Deletion is complete across every column that references a user (derived from the schema), verified by a residual check, idempotent, resumable after a crash, and fail-closed on a private-file failure (`src/privacy/erasure.py`, `account_deletion_service.py`, `privacy/runtime.py`, route 503 `deletion_incomplete`) | Re-authentication or a cooling-off or recovery window for self-service deletion (owner decision, see "Decisions"); hosted backups (see the 05B interface note) |
| W9.8-D1a | Preparation-chat ownership index | Audit and tests: every production agent service is built with the index, new runs are indexed before the checkpoint exists, nothing lists or scans the saver, a deleted owner's leftover rows are found by one indexed JOIN and purged by a dry-run-default script, the privacy job purges runs in ANY state (fixes a loop on crash residue) | A chat that was never indexed and never referenced cannot be found (stated limit, unchanged); chat CONTENT is not in the export (listed in the DSAR record) |
| W9.8-D2 | Consent and legal-acceptance version history | `GET /privacy/legal/history` (own history: version, baseline flag, hash and effective date where present, source, current or superseded), export carries version identity, never back-filled, states it is not consent; tests for isolation, immutability, idempotency, deletion | Re-acceptance enforcement and the `signup` source stay unwired (owner policy); baseline versions have no hash or effective date (history cannot prove a baseline text) |
| W9.8-D9 | Audit context allow-list enforcement | One `before_insert` checkpoint for `audit_events.context` and `incident_events.meta` (`src/audit_allowlist.py`); strict in tests and evaluators; static scan of every key the source can emit; free-text-name guard | An allow-listed key's VALUE is bounded in shape, not proven free of personal data (e.g. `reason` is an operator reason of at most 200 characters) |
| W10.10-AUDIT-CTX | Privacy workflow cross-store atomicity | Files-first ordering removes the unrecoverable window; the residual check gates completion; orphan sweep and the any-state purge make the SQL-then-checkpoint sequence resumable | No distributed transaction (SQL and the checkpoint store cannot be atomic; the safe order and the retry path are what exist) |
| PRIV-DIFF | Report differencing | Nested-window guard and total-versus-bucket rule, attack tests on the W10.12 service and the 03E1 builder, residual risk documented in code and here | See "Residual risk" |
| PRIV-DSAR | DSAR path decision | `docs/production/execution/PRIV_DSAR_DECISION_RECORD.md`: options, effort, risk, recommendation; owner decides | No export path was built (by design) |
| K-GDPR | No GDPR or compliance claim | None made; tests scan the new documentation for compliance claims | Remains DEFERRED; needs qualified review |
| K-PRIV, PRIV-LEGAL, K-AIGUID | Counsel review of Privacy, Terms, AI-transparency and AI-guidance wording | PR 2 supplies the review-ready package | **Counsel review: NOT DONE** |

## Changes

New: `src/privacy/erasure.py`, `src/audit_allowlist.py`, `src/reporting/differencing.py`, `scripts/privacy_sweep_orphan_runs.py`, `docs/production/execution/PRIV_DSAR_DECISION_RECORD.md`, tests `test_erasure_05e.py`, `test_audit_allowlist_05e.py`, `test_consent_history_05e.py`, `test_differencing_05e.py`, helpers `_erasure_world_05e.py`, `_audit_scan_05e.py`.

Modified (minimal): `src/application/account_deletion_service.py` (sweep, files-first, summary fields), `src/privacy/runtime.py` (any-state purge, residual gate, `DeletionIncomplete` mapped to a retry), `src/privacy/preparation.py` (`orphaned_runs`, `sweep_orphaned_runs`), `src/privacy/legal.py` and `src/api/routes/privacy.py` and `src/api/schemas/privacy.py` (history), `src/api/routes/auth.py` (503 on `DeletionIncomplete`), `src/persistence.py` (3 lines: install the allow-list), `src/reporting/suppression.py`, `service.py`, `report_builder.py` (guard hooks, bucket scopes, hidden-group rule), `scripts/eval_privacy_controls.py` (5 new invariants), `tests/conftest.py` (one line: `AUDIT_CONTEXT_STRICT=1`), `docs/privacy.md`, `CLAUDE.md`, and extended `tests/test_reporting_w10_12.py`, `tests/test_report_builder_03e1.py`.

**Shared test amended (lead to review): `tests/test_command_center_03d1.py::test_the_frozen_03k_contract_files_are_untouched`.** It pinned `src/reporting/service.py` and `suppression.py` against `origin/main` (a check for the 03D1 package itself). 05E is explicitly briefed to add the differencing mitigation there, so those two files are removed from that pin; `contract.py`, `metricContract.ts`, `metricContract.schema.json` and `definitions.py` stay pinned and unchanged. Decision for the lead: accept, or move the mitigation elsewhere (it needs hooks inside `suppression.metric` and `partition`).

## Why no migration

The acceptance history exposes data that already exists (acceptance rows carry the version and the version row carries the hash and effective date). The erasure and audit work add no column. A migration would have touched candidate privacy tables (`legal_acceptances`) and needed an entry in the reviewed list of `scripts/eval_privacy_controls.py`; none was needed, so none was added and the guard is untouched. Alembic head stays `0043_story_bank_completion`.

## Security and privacy impact

- Deletion: stronger. The sweep removes or clears references in tables the explicit code did not know (found by the new test: `report_configurations`, `email_attempts`, operator columns such as `knowledge_sources.created_by_user_id` kept a dangling id on SQLite). Files are deleted before the commit, so an interrupted deletion can no longer orphan files.
- A failed file deletion now FAILS the deletion (503, nothing removed) instead of completing with `files_failed > 0`. This is a behaviour change: a candidate whose storage is unavailable cannot delete until it recovers. The alternative (complete anyway) was the orphaning path.
- The privacy-request job no longer records `deletion_performed` while any reference to the account remains, or while an indexed run remains in any state.
- Audit: a free-text key can no longer be persisted. In a hosted environment an unlisted entry is dropped (and counted as `dropped_keys`) rather than failing the audited operation; in tests it raises.
- Reporting: some wider-window figures that were visible are now suppressed when they differ from a narrower window by a small group (a utility cost, intended).
- New route `GET /privacy/legal/history`: authenticated, owner-scoped by the session (a client-supplied id is ignored), `extra=forbid` schema, no identifier, IP or device field.
- No new permission (registry stays 44), no new Admin route, no live or paid call.

## Residual risk (reporting differencing)

Not prevented, and stated in `src/reporting/differencing.py`: (1) repeated requests for the SAME window at different moments can be subtracted (windows are relative to request time; a test pins this as a known limitation); (2) the builder's disjoint `previous_period` comparison can be summed by the reader; (3) partitions whose buckets overlap make the hidden-group check an upper bound; (4) the 03D1 Command Center computes its own tiles and is not covered by the guard; (5) several Admin readers can pool what each saw. Mitigations outside the code: aggregate-only, read-only, permission-gated and audited reports. The cohort floor (5) is an engineering control, not anonymisation.

## Tests and commands

| Check | Result |
|---|---|
| New suites: `test_erasure_05e.py` (23), `test_audit_allowlist_05e.py` (35), `test_consent_history_05e.py` (11), `test_differencing_05e.py` (18) plus 2 added to the W10.12 and 03E1 files | 89 passed (repo venv) |
| Existing suites touched or related: privacy W10.10, P8 hardening, account closure, story bank, invitations, preparation pack, billing W10.5, opportunity (275 tests) and reporting W10.12, builder 03E1, command center 03D1, integrated W11 | 275 passed (privacy and related) and all of the reporting, builder and command-center suites passed unchanged (the only edit to an existing assertion is the 03D1 pin, above) |
| Fresh-dependency canary (`$HOME/.cache/ask4mo/ci_venv`): the four new suites | 87 passed |
| Full backend suite (`pytest tests -n 3 --dist loadfile`, repo venv, final tree) | **6366 passed, 41 skipped, 0 failed** (10 min 31 s). The skips are pre-existing; 05E added none. An EARLIER full run of the same tree before one fix had 2 failures: `workspace.member_removed` was rejected by the allow-list (a real defect of this PR: `target_role` is a workspace role there; fixed, pinned by a test) and `test_test_isolation` aborted on a native `libc++abi recursive_mutex` error at the exit of a subprocess evaluator after printing PASS (passes alone and in the final run: an environment flake, not caused by 05E) |
| Silent-rejection check | A scratch plugin (not committed) logged every allow-list rejection across the whole final suite, including those a best-effort audit writer would have swallowed: the only rejections are the deliberate ones in the new tests and the evaluator they trigger |
| Baseline for comparison: the same suite on `origin/main` f5cf7cb4 in a scratch worktree | one failure, `test_language_readiness_06a` (the scratch worktree had no `frontend/node_modules`, so the catalogue helper could not run); all else passed |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4` | pass; 304 test files, each in exactly one shard |
| All CI evaluators (`scripts/eval_*.py` and the coverage and corpus scripts listed in `.github/workflows/ci.yml`, with the arguments CI passes), once on the final tree | 49 commands, every exit code 0 (46 evaluators plus `gen_product_coverage_cases` and two coverage and baseline scripts); the working tree stayed clean; 0 paid or live calls. `eval_privacy_controls` now has 5 more invariants (erasure inventory complete, deletion leaves no reference to the account, allow-list enforced, acceptance history not back-filled or consent) |

Frontend: no frontend source file changed, so `tsc`, `lint`, `vitest` and Playwright (reserved port 3124) were NOT run for this PR. The Data & Privacy screen already shows its localized failure message for any non-409 error, which covers the new 503 `deletion_incomplete`; no UI string was added.

Commands: `pytest tests/test_erasure_05e.py tests/test_audit_allowlist_05e.py tests/test_consent_history_05e.py tests/test_differencing_05e.py -p no:cacheprovider` (both venvs); `pytest tests -n 3 --dist loadfile -q -p no:cacheprovider`; `ruff check .`; `python scripts/ci_test_shards.py verify --shards 4`; `python scripts/eval_<name>.py` for each evaluator in CI. Audit-key discovery: a throwaway pytest plugin (not committed) recorded every audit and incident key written by the whole suite on `main` (9,353 audit and 36 incident inserts); the static scan found one more key (`reason_category`), and the allow-list is the union.

## Backups interface note for 05B (hosting)

05E cannot erase hosted backups and does not claim to. What 05B must define for the deletion story to be true end to end:

1. **Inventory:** which stores are backed up (application database, checkpoint database, private-file volume, Chroma index) and where.
2. **Retention:** a stated schedule per backup, so the Privacy text's "age out on that schedule" can be made precise (PF-19 in the PR 2 fact map is NOT_VERIFIED until then).
3. **Restore re-erasure:** a backup restore resurrects deleted accounts. The record of erasures (`account.deleted` audit events, `privacy_requests` completions) lives in the same database that is restored, so it is lost for anything after the backup point. A restore procedure needs an erasure ledger that survives a restore (user ids only) and a step that re-applies it (`AccountDeletionService` is idempotent) and then runs `scripts/privacy_sweep_orphan_runs.py --execute`. Not built.
4. **Private files:** the file volume snapshot has the same resurrection property for deleted documents.

## Throughput

Started 2026-10-22 07:22 CEST. First push about 08:40 CEST (the same day). Rework rounds: 1 (the `target_role` workspace-role value found by the full-suite run; no CI has run on this branch: CI only runs on a PR, which the lead opens). `origin/main` was unchanged at f5cf7cb4 when this branch was pushed (merge verified: 0 commits to merge).

## Risks and limits

- The generic world test builds rows from the schema; a new table with an unusual CHECK constraint may need a small override in `tests/_erasure_world_05e.py`, which is the intended friction (the new table is then deliberately exercised).
- `AUDIT_CONTEXT_STRICT` is a test and evaluator setting; hosted environments use the drop-and-count behaviour. Setting it in a hosted environment would make a logging mistake fail the audited operation.
- The nested-window guard recomputes a report for each narrower window (up to four evaluations for `all_time`); fine at Admin scale, to be revisited if reports become large.
- SQLite does not enforce foreign keys; PostgreSQL behaviour of the sweep is reasoned (it applies the same actions the database declares) and not run.

## Decisions for the owner

1. PRIV-DSAR path: accept option A for the private beta, or choose B or C (`PRIV_DSAR_DECISION_RECORD.md`; D is not offered).
2. Whether self-service account deletion should require a fresh password step-up or a cooling-off or recovery window (the remaining D10 item). Not built; the step-up mechanism from W12.4B exists.
3. Acceptance policy: wire the `signup` source and enforce re-acceptance after a new version, or keep recording from Settings only.
4. Accept the narrowing of the 03D1 frozen-file pin (above).
5. Appoint counsel and the language qualifiers (OD-LANG-04). Counsel review is not started.

## Human, live-staging and gate evidence still missing

Legal review of the texts per language (LG-10, PG-04); hosted deletion, restore and backup behaviour; a PostgreSQL run of the sweep and of concurrent deletion; any provider's data terms; independent security review of the audit and deletion changes.
