# 03C completion evidence: previewed, authorised, audited bulk user actions (REQ-OWN-03, OD-BULK-ACTIONS provisional)

Branch `feat/03c-bulk-user-actions` from `origin/main` f5cf7cb. **No migration** (Alembic head unchanged, `0043_story_bank_completion`). Permission registry stays **44**.

**OD-BULK-ACTIONS is NOT approved.** This package implements the owner's *provisional recommended default* ("previewed, authorised, audited bulk user operations with appropriate transaction and partial-failure handling") for a deliberately small allow-list. The permitted set remains an owner decision; nothing here records that decision as made.

## Offered and not offered

| Action | Status | Why |
|---|---|---|
| Force sign-out (revoke live sessions) | OFFERED | Low harm, fully reversible (the person signs in again). Same permission as the single action: `platform.users.sessions.revoke` |
| Expire pending email verification links | OFFERED | Low harm, reversible (a new link can be requested). Same permission as the single action: `platform.users.manage` |
| Bulk plan assignment | Already exists (03B, `/admin/plans/assignments/bulk`) | Not duplicated |
| Bulk deactivation | NOT OFFERED | Ends access for many people at once; one wrong selection locks out candidates. Single account, revision-checked |
| Bulk deletion | NOT OFFERED | Irreversible and privacy-gated; stays the separate privacy-request pipeline |
| Bulk role change | NOT OFFERED | Authority escalation; stays the two-person step-up approval flow |
| Bulk resend verification | NOT OFFERED | Sends real email to many people; an external side effect cannot join or be rolled back with the batch transaction |
| Anything touching candidate content | NOT OFFERED | No Admin permission reads candidate content; none is added |

The same list is in code as `src/admin_users/bulk.py:NOT_OFFERED` and a test asserts none of those is a route.

## Requirement mapping

| Requirement (brief) | Covered | How | NOT covered / limits |
|---|---|---|---|
| (1) PREVIEW GET, counts and per-reason exclusion counts only, bound to a preview revision | Yes | `GET /admin/users/bulk/{force-signout,expire-verification}/preview?ids=...` returns requested, unique, eligible, excluded, `excluded_by_reason`, `max_batch`, `preview_revision`. Token = hash of action, actor id and role, active-admin count and every chosen account's `account_revision` (03C) | Ids are in the query string (as 03B preview does); responses contain no email and no id list |
| (2) EXECUTE needs revision, reason 3 to 200, same actor guards, cap 100, Idempotency-Key, per subject | Yes | `POST .../execute` body `{account_ids, preview_revision, reason}` (extra fields refused), header `Idempotency-Key` 8-64 chars mandatory. Guards: self excluded, privilege hierarchy (target permissions must be a subset of the actor's), last active `platform_admin`, acting administrator must be active (403). Each subject runs in its own SAVEPOINT | Last-admin rule is structurally redundant (a peer admin implies two active admins) but is evaluated and unit-tested at count 1 |
| Partial failure explicit, never silent success | Yes | Response: `status` (complete / partial / none_applied), applied, skipped + `skipped_by_reason`, failed + `failed_by_reason` (fixed code `apply_error`, never an exception text) | |
| Audit failure aborts the whole batch | Yes | One outer transaction; every subject row and the batch row are staged and flushed in it; any audit failure raises (503) and the transaction is never committed. Tested by failing the 3rd subject row and the batch row: nothing applied, no rows | |
| (3) One audit row per subject plus one batch row, metadata only | Yes | Applied subject: the existing event (`admin.sessions_revoked` / `admin.user_verification_expired`) with `bulk`, `batch_id`, `action`, reason. Skipped or failed subject: new `admin.user_bulk_subject` with `result` skipped/failed and `reason_code`. Batch: new `admin.user_bulk_action` with action, reason, counts, request hash, actor | Two new audit event NAMES (shared `admin_audit.py`, additive). The operator's free-text reason is stored as in every existing audit row (not a code) |
| (4) Per-batch rate limit and pause switch | Partly | New bucket `admin_bulk_user_actions` (10 executed batches per administrator per hour; replays and previews consume nothing). The durable pause store is read before the batch: unreadable platform state refuses the batch with 503 `platform_state_unavailable` | **The pause list is a fixed set of CANDIDATE capabilities; none applies to an Admin recovery action and Admin recovery is never paused by design (W10.11). So "pause switch respected" is implemented as fail-closed on an unreadable pause store, not as a pausable capability. The owner should confirm that is the intended meaning** |
| (5) Tests | Yes | See below | |
| Frontend: multi-select, explicit preview step, confirmation requiring reason, result panel | Yes | `UsersBulkPanel.tsx` + checkbox column in `UsersView.tsx` (existing Admin Users components only; `AdminShell.tsx`, `capabilities.ts`, `nav-items.ts` untouched) | Selection is client state for the current visit (up to 100) |
| Type guards at the client boundary; malformed 200 = explicit error state | Yes | `frontend/lib/admin/bulkGuard.ts` (`isBulkUserPreview`, `isBulkUserResult`, including count arithmetic). Malformed preview: error, no Apply control. Malformed execute: error in the dialog, no result panel | |
| Recorded fixture only via the generator, only new keys | Yes | `scripts/gen_w11_admin_fixture.py --merge-prefix /admin/users/bulk/` records the two preview keys and merges only those (32 lines added; every existing key untouched). The committed fixture was already stale for 24 other routes; those were deliberately NOT merged | |
| Admin UI English-only | Yes | | |

## Changes
- New: `src/admin_users/bulk.py`, `src/api/routes/admin_users_bulk.py`, `src/api/schemas/admin_users_bulk.py`, `tests/test_admin_users_bulk_03c.py`, `frontend/components/admin/UsersBulkPanel.tsx`, `frontend/lib/admin/bulkGuard.ts`, `frontend/tests/admin-users-bulk-03c.test.tsx`, `frontend/e2e/admin-users-bulk-03c.spec.ts`.
- Modified (minimal): `src/api/main.py` (register router), `src/api/rate_limit.py` (one bucket), `src/application/admin_audit.py` (two event names), `src/admin_users/actions.py` (extract `pending_verification_tokens`, reused by the single and the bulk expiry), `scripts/gen_w11_admin_fixture.py`, `frontend/components/admin/UsersView.tsx`, `frontend/lib/api/client.ts`, `frontend/lib/admin/types.ts`, `frontend/e2e/fixtures/admin-responses.json` (+2 keys).
- Not touched: `AdminShell.tsx`, `frontend/lib/admin/capabilities.ts`, `nav-items.ts`, migrations, `tests/_admin_matrix.py` (the `/admin/users` prefix already maps the new routes to the users domain), the 03C single-action routes and their behaviour.

## Design decisions worth reviewing
- **Atomicity model.** One transaction, one SAVEPOINT per subject (so one failing subject never undoes the others), all audit rows in the outer transaction (so an audit failure aborts everything). On SQLite the driver opens transactions lazily, which would make the first SAVEPOINT the outermost one and its RELEASE a COMMIT (found by the audit-failure test: sessions stayed revoked); the service therefore starts the transaction explicitly with `BEGIN IMMEDIATE` on SQLite only (also avoids a lock-upgrade failure under concurrent batches). PostgreSQL needs nothing.
- **Idempotency without a migration.** The batch audit row is the idempotency record (`target_id` = digest of actor, action and key; `request_hash` of action, ids, preview revision and reason). Same key and request returns the first result with `replayed: true`; same key and a different request is 409. `audit_events` has no unique index and no migration was added, so first-result replay is race-safe inside ONE process (a process lock serialises batches) and best-effort across processes. Even so, two overlapping batches can never change a subject twice: each subject is re-evaluated under row locks and the preview token goes stale after the first batch.
- **Stale preview.** The token covers each account's live-session count, pending-link count, status, role and update time, so any change (including the target signing in again) gives 409.
- **Throughput limit.** Batches are serialised per process (a process lock); with a cap of 100 and a 10 per hour budget this is acceptable for an operator action.

## Security and privacy impact
- Metadata only: responses and audit rows carry no email, token, link, session id or candidate content (sentinel sweep over responses and audit contexts; schemas are `extra="forbid"` with no banned field names). Preview and result never list accounts, only counts.
- Authorization: reuses the two existing permissions, so `support_operator`, `billing_admin`, `knowledge_admin` and `operations_admin` get 403; `security_privacy_admin` holds only `sessions.revoke` (force sign-out yes, expire-verification 403); `platform_admin` both. A non-owner administrator cannot touch higher-authority accounts, and nobody can include themselves.
- No Admin can read candidate content through this; no new permission.

## Tests (commands and results)
| Check | Command | Result |
|---|---|---|
| New backend suite (25 tests: registry/routes, 7-persona matrix for preview and execute, counts-only preview, strict body, cap 100, stale preview 409, idempotent replay and key clash, actor-scoped keys, self/higher-authority/last-admin/inactive-actor protection, partial failure, audit failure and batch-row failure abort, two overlapping batches, same-key overlap, rate limit, replay budget, unreadable pause store, sentinel sweep) | `.venv/bin/python -m pytest tests/test_admin_users_bulk_03c.py -p no:cacheprovider` (repo venv) and the same with `$HOME/.cache/ask4mo/ci_venv/bin/python` (canary present) | 25 passed on both; the two concurrency tests were repeated 5 times without a flake |
| Related suites | `test_admin_users_03c.py`, `test_admin_plans_03b.py`, `test_admin_qualification_w10_14.py` with the new file | pass (repo venv) and (canary: users 03C + new file) |
| Full backend suite | `$HOME/.cache/ask4mo/ci_venv/bin/python -m pytest tests -n 3 --dist loadfile -q -p no:cacheprovider` (run once, before the final push) | exit 0: 6300 passed, 43 skipped, 0 failed (counted from the progress lines) |
| Lint, shards | `ruff check .`; `python scripts/ci_test_shards.py verify --shards 4` | pass; 301 test files, each in exactly one of 4 shards |
| CI evaluators (all 51 `scripts/eval_*.py` invocations in `.github/workflows/ci.yml`, run with the canary venv) | looped once | 50 PASS first time; `eval_admin_qualification` FAILED once (its audited-in-handler heuristic did not see the audit in my execute handler); fixed by passing the audit event name from the handler, re-run PASS. 0 paid or live calls |
| Frontend | `npx tsc --noEmit`; `npm run lint`; `npx vitest run`; `npm run build` | clean; 123 files, 1305 tests passed (23 new in `admin-users-bulk-03c.test.tsx`, existing `admin-users-03c.test.tsx` 8 still pass); build OK |
| Playwright (`E2E_PORT=3138`) | `npx playwright test e2e/admin-users-bulk-03c.spec.ts e2e/admin-users-03c.spec.ts e2e/admin-ux-w12-5.spec.ts` | 14 passed (4 new, mocked network) |

Not run: PostgreSQL execution of the batch (SAVEPOINT, row locks); a real multi-process idempotency race; a live staging walk-through; CI (no PR yet).

## Risks and limits
- Cross-process idempotency is best-effort (no unique index without a migration). A PostgreSQL execution of the SAVEPOINT / row-lock path was NOT run (only SQLite); the code uses only standard SQLAlchemy `begin_nested` and `with_for_update`.
- The in-process lock means batches run one at a time per API process.
- The pause semantics question above.
- Admin copy is English-only (decision AD-01).
- A browser-visible walk-through against a live staging stack was not run.

## Owner decisions still needed
1. **OD-BULK-ACTIONS**: approve, change or reject the two-action allow-list and the "not offered" list above. Until then this is a provisional implementation.
2. Whether any further action (for example bulk resend of verification email) should ever be offered, accepting its non-reversible external side effect.
3. Confirm the intended meaning of "pause switch respected" (see mapping row 4), and whether a dedicated batch cap lower than 100 or a different per-hour budget (default 10) is wanted.
4. Whether a unique idempotency index (a future migration) is wanted for multi-process deployments.

## Remaining human, live-staging and gate evidence
- Independent security and privacy review of the bulk flow: NOT DONE (appointed later by the owner).
- Live-staging verification, a PostgreSQL run and CI: NOT AVAILABLE (CI only runs on a PR; no deployment).

## Throughput
Start 2026-10-22 14:42 CEST. First push: FIRSTPUSH. Rework rounds: SQLite savepoint commit bug and lock-upgrade race (found by tests, fixed before first push), one evaluator guard (`eval_admin_qualification` audited-in-handler heuristic) fixed before first push. SHA: SHAPLACEHOLDER.
