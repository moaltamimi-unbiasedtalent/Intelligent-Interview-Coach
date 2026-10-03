# P10B-W10.10 - GDPR, Privacy & Legal Administration

**Status:** **COMPLETE** (merged in PR #122, main `54ee591`). **W10.5 is NOT STARTED.**
One additive migration (`0020_privacy_legal_admin`). No new dependency. 0 paid/live calls.

**Legal boundary.** This is engineering support for privacy and legal workflows. It does **not** claim GDPR certification, legal compliance, completeness of any access request, or a statutory retention schedule, and it hard-codes no legal conclusion.

## 1. Starting point
`main` `35eee19a51e6aa35cb6ad669facf3d1091dacc59` (W10.8 merged, PR #121), clean tree, Alembic head `0019_knowledge_admin`.

## 2. Branch
`feat/p10b-w10-10-privacy-legal-admin`.

## 3. W9.8 privacy reuse audit
| Capability | Current implementation | Durable? | Working? | W10.10 action |
|---|---|---|---|---|
| Self-service export | `build_candidate_export` (JSON on demand, nothing stored) | no artefact, by design | yes | reused; extended with legal acceptances, privacy requests, preparation-run index; scope text states limits |
| Selective deletion (documents, memories, Opportunities, interviews) and share revocation | W9.8 owner-scoped services | yes | yes | untouched |
| Account deletion | `AccountDeletionService` (child-to-parent, anonymises audit, purges files and checkpoints) | yes | yes, but found runs only via memory references | reused as the only deletion engine; now uses the ownership index and surfaces failed purges |
| Privacy request queue | `GET /admin/privacy-requests` listing `status=deletion_requested` | no | **no** (nothing ever set that status) | replaced by a durable queue |
| Legal acceptance | none | no | n/a | new registry and records |
| Consent/preferences | `user_preferences` (response detail, locales, style) | yes | yes | untouched and kept separate from legal acceptance |
Support, plan/subscription and Opportunity cleanup, session revocation and share revocation are inherited by reusing the service.

## 4. SEC-W10-04 reproduction and root cause
The removed account-deletion request path left `status=deletion_requested` unreachable, so the Admin queue listed an always-empty set. Pre-fix behaviour is pinned by `test_pre_fix_gap_the_legacy_queue_never_saw_anything_and_the_durable_queue_does`: a candidate request is invisible to the legacy mechanism and visible in the new queue. Root cause: the queue had no durable record to read.

## 5. Privacy request domain
`PrivacyRequest` (not "DSAR"): type, status, source, a bounded candidate note (1000 characters), assignee, result category, linked job id, timestamps and a plain `subject_user_id` used only to resume a deletion after the account row is gone (cleared on completion). No IP, device, fingerprint, token or dataset snapshot.

## 6. Request lifecycle
Types (only those with a real workflow): `data_access`, `deletion`, `correction`, `consent_question`, `other_privacy`. Statuses: submitted, acknowledged, in_progress, waiting_for_user, completed, closed, rejected, with a server-side transition table and no legal meaning. `completed` requires a result category and a timestamp (database CHECK). Result categories: export_provided, deletion_performed, correction_made, information_provided, no_action_required, unable_to_verify.

## 7. Candidate request entry
Data & Privacy now has a "Privacy requests" section (type, optional note, list with safe statuses). Self-service export and deletion are unchanged and immediate. Rate limit `privacy_request_user` (5 per hour) plus at most 5 open requests per account. Operators can also record a request received another way. Copy exists in all 8 locales and promises no response time.

## 8. Admin privacy queue
`/admin/privacy`: filters (status incl. all open, type, assignee, unassigned), stable ordering, pagination, search by reference, account id or email only (never request text), preparation-index coverage, record-a-request form.

## 9. Privacy data boundary
Privacy Admin is not a content superuser. Admin schemas carry no CV, document, answer, chat, memory, evidence, export or support-note field (evaluated). The only free text shown is the bounded note the candidate wrote. No break-glass, no impersonation.

## 10. Export reuse
Export stays the candidate's own self-service download. There is **no** admin export or download of candidate data: no secure artefact store exists, and exporting to an operator would make Admin a content superuser. A data-access request is completed by recording that the candidate used the export (`export_provided`) or by providing information.

## 11. Deletion reuse
`POST /admin/privacy/requests/{id}/execute-deletion` queues a W10.9 job that calls the same `AccountDeletionService.delete_account` candidates use. The number of parallel deletion engines is 0. Admin accounts cannot be deleted this way.

## 12. Privacy jobs
`privacy_account_delete` (payload: request id), `privacy_preparation_backfill` (payload: cursor), `privacy_preparation_purge` (payload: run id). IDs only, strict schemas, not directly Admin-enqueueable.

## 13. Privacy idempotency
Deletion: the service is a no-op when the user is gone; leftover runs are tracked in the index until purged; completion is guarded and only happens after every run is purged; a replay of a finished job does nothing. Purge: delete-thread is idempotent and the index row is removed only after a successful purge. Backfill: upserts by run id. Tested, including a failed-then-healed checkpoint store.

## 14. Preparation-run index
`preparation_runs`: run id (unique), owner id (indexed with state, no FK so a failed purge can be retried after the account row is gone), state (started, ready, failed, purge_failed), source (created, backfill, lazy), coverage version. No chat content.

## 15. Creation invariant
`AgentApplicationService.run` registers the run **before** the first checkpoint exists and fails closed (the run does not start) if registration fails. SQL and the checkpoint store cannot share a transaction, so the safe order is index first; no cross-store atomicity is claimed. Failed runs are marked `failed`.

## 16. Historical backfill strategy
(1) Index new runs immediately. (2) A bounded W10.9 job reads saved-memory `source_run_id` references in batches of 500, looks up each run's own recorded owner in the checkpoint (one thread lookup), and indexes only matches. (3) Lazy indexing when a verified owner reads, resumes or deletes an old run. (4) Coverage is shown in Admin. (5) Unreachable orphans are not claimed.

## 17. No-full-scan proof
The only checkpoint read is `get_tuple` for one known run id. Evaluator and tests forbid list/scan calls (`list`, `alist`, `list_threads`, state history, raw checkpoint SQL) in privacy code, the agent service and account deletion; a test shows an unreferenced orphan is never even looked up. Full checkpoint scans performed by W10.10: 0.

## 18. Preparation export semantics
The export lists the caller's run identifiers and status (metadata). Chat content is **not** exported: safe extraction through known ids is not yet supported, and the scope text says so.

## 19. Preparation deletion semantics
Account deletion discovers runs via the index (plus legacy memory references, which are added to the index first), purges each through the saver's official delete API, and removes the index row. A failure keeps the row as `purge_failed`, is counted, and the API message does not claim full success; a purge job is queued to retry.

## 20. Orphan limitation
A historical run referenced by no memory and never opened by its owner cannot be found without scanning the whole store, which is deliberately not done. Such runs remain until the store's own cleanup. Ambiguous references (the memory owner differs from the checkpoint owner) are never assigned.

## 21. Legal document model
`legal_documents` for the three real surfaces: `terms`, `privacy`, `ai_transparency` (database CHECK).

## 22. Legal version model
`legal_document_versions`: label, state (draft, published, retired), `is_baseline`, content reference (own page path or https), optional SHA-256 content hash, effective date, publish evidence. The text stays in the product pages; no CMS or rich-text editor.

## 23. Published immutability
A published version cannot be edited (service guard) or deleted (no delete path). Exactly one version per document is published (partial unique index); publishing atomically retires the previous one. Publishing needs a content hash and an effective date (database CHECK for non-baseline versions).

## 24. Legal acceptance model
`legal_acceptances`: user, version, timestamp, source; unique per user and version. Recording the same acceptance twice is idempotent. Columns: id, user_id, version_id, accepted_at, source. No IP, device or fingerprint.

## 25. Acceptance source
Code-defined: signup, settings, reacceptance. Only `settings` is wired (a button in Data & Privacy). Registration was not changed.

## 26. Historical-user treatment
Existing users have no recorded acceptance and are shown as "no acceptance recorded". Nothing is back-filled.

## 27. No fabricated timestamps
The migration seeds only document identities and one `baseline-1` published version each, marked baseline, with no effective date and no hash. No acceptance row is inserted and no date is derived from account creation.

## 28. Reacceptance policy boundary
Not enforced. Publishing a new version leaves earlier acceptances intact and does not mark users as having accepted it. Any enforcement belongs to a later policy decision.

## 29. Consent vs acceptance
Legal acceptance acknowledges a document version. It is not consent to optional processing, is not stored with preferences, and is not required to use the product. The copy says so. No legal basis is inferred.

## 30. Retention and legal boundary
No retention period or legal conclusion is hard-coded. After account deletion a privacy request keeps only type, status, timestamps and result category (the note and account link are cleared); whether more must be kept is a counsel/policy question. Audit events keep anonymised metadata as before.

## 31. Admin Legal UI
`/admin/legal`: documents, versions with state and effective date, current version, recorded acceptance counts and the "no acceptance recorded" count, draft registration and publish (confirmation states immutability and no forced re-acceptance). No compliance score or badge.

## 32. Candidate Legal UI
Per document: current version, effective date (or "not recorded"), baseline note, the caller's recorded status, and a "Record my acceptance" button when the current version is not accepted.

## 33. Audit events
admin.privacy_request_recorded / _assigned / _status_changed, admin.privacy_deletion_initiated / _completed, admin.privacy_preparation_backfill_requested, admin.legal_version_created / _updated / _published, plus `legal.acceptance_recorded` for the candidate action. Context holds ids, states and categories only: no note, no content, no IP/device. Mutations and their audit rows share one transaction; cross-store deletion reflects partial failure in request and job state.

## 34. Permissions
Existing canonical permissions only (still 43): `platform.privacy.read` (queue, detail, coverage and legal registry reads: there is no separate legal-read permission), `platform.privacy.execute` (record, assign, status, delete, backfill), `platform.legal.manage` (draft, edit draft, publish). `security_privacy_admin` holds all three; `platform_admin` holds read only; support, billing, knowledge and operations hold none.

## 35. Migration
`0020_privacy_legal_admin` (from `0019_knowledge_admin`): five tables with CHECKs, unique constraints and indexes, and the relational legal seed. It never scans or touches the checkpoint store. Fresh, from-0019, constraint, seed and round-trip tests pass.

## 36. Backend tests
**2804 passed, 4 skipped, 0 failed, 0 errors** (baseline 2778/4). 26 new tests in `tests/test_privacy_legal_w10_10.py`. Skips: live Adzuna, Streamlit render, RAGAS and the PostgreSQL job-claim test (needs `TEST_POSTGRES_URL` and a driver).

## 37. Frontend tests
692 unit tests in 83 files (18 new for privacy/legal, 2 existing updated for the removed "not recorded" legal copy): queue, filters, pagination, detail, assign/status/delete confirmations, coverage and backfill, legal registry and publish, candidate request and legal panels, 8-locale key checks, no guarantee wording, no role-name authorisation. Typecheck, lint and build clean.

## 38. Playwright
**211 passed** (209 baseline plus the Admin privacy/legal journey and the candidate request and acceptance journey), serial, no retries or timeout changes. The journeys use stateful network stand-ins; the real lifecycle with a real worker and checkpoint store is covered by the backend tests and the manual QA.

## 39. Evaluators
**35 of 35** CI evaluators pass including the new `scripts/eval_admin_privacy_legal.py` (35 checks). Two guards (`eval_admin_design`, `eval_admin_foundation`) were updated because legal routes, the three tables and a live Command Center privacy queue now legitimately exist. Only the CI set was run; `evaluations/` is untouched.

## 40. Isolation
Tests use a temp DB, a fake checkpoint adapter, temp upload storage and in-memory vector stores. The dev-store fingerprint is unchanged across the full backend suite. Note: the first run of the CI evaluator set after adding the tables ran `create_all` against the developer SQLite file (pre-existing behaviour of some evaluators), adding the new empty tables; no rows were added and the suite itself does not touch it.

## 41. Manual QA
Fresh migrated database, API and a separate worker, real SQLite checkpoint store (temp), fake model, no network. Legal showed baseline versions with nothing pre-accepted; accepting twice stored one row; a candidate request appeared in the Admin queue, was assigned, acknowledged, moved to in progress, rejected without a result, then completed with a result and shown to the candidate; Command Center and legal counts matched; audit rows held ids and states only. Three indexed runs and one unindexed historical run were created: an Admin-recorded deletion request executed by the worker removed the account, both of its runs' checkpoints and index rows and completed with `deletion_performed` (not before the worker ran); backfill indexed the historical run (source `backfill`); a candidate's self-service deletion purged its runs through the index. No IP/device column exists. No live call.

## 42. Performance
First Load JS: `/admin/privacy` 119 kB, `/admin/privacy/[id]` 118 kB, `/admin/legal` 114 kB, `/account/data` 414 kB (candidate page, with the new panels), shared 103 kB unchanged. Indexes: queue filters (`status, created_at`; `assigned_user_id, status`; type; user), per-user run lookup (`owner_user_id, state`; unique `run_id`), current legal version (partial unique index on published), acceptance by user and version (unique constraint). Account deletion makes one indexed query for runs and never enumerates the checkpoint store.

## 43. Dependencies
None.

## 44. Alembic head
`0020_privacy_legal_admin` (single head).

## 45. SEC-W10-04 closure evidence
Durable creation (candidate and operator-recorded), queue populated, safe Admin processing, persisted state and assignment, audit, and end-to-end tests including the pre-fix reproduction. **CLOSED** (when merged).

## 46. PRIV-W9-01 closure evidence
New runs always indexed before their checkpoint; one indexed per-user lookup; account deletion uses the index; no checkpoint scan; bounded verified backfill and lazy indexing; ambiguous references not assigned; no chat content in the index; the orphan limitation is documented. **CLOSED** (when merged), with the limitation stated.

## 47. PRIV-W9-02 closure evidence
Versioned documents, identifiable current version, immutable published versions, per-user acceptance with version and timestamp, no fabricated history, no IP/device, candidate and Admin can inspect recorded truth. **CLOSED** (when merged); reacceptance is not enforced.

## 48. SEC-W10-05
Remains OPEN for W10.11. Nothing here is a platform pause.

## 49. W10.11 handoff
Feature flags and durable platform configuration can reuse the audit/permission patterns; the legal registry could later carry an enforcement flag for reacceptance; the pause switch remains process-local until W10.11.

## 50. External calls
0 paid or live provider calls.
