# P10B-W10.2 - Users, Access & Workspace Administration

**Status:** implemented on branch `feat/p10b-w10-2-users-access-workspaces`; **complete when merged to `main`**. **W10.3 is NOT STARTED.**
Migration-free (Alembic head stays `0014_opportunities`). No new dependency. 0 paid/live calls.

## 1. Starting point
Started from `main` `079ced5b637b0d4f9c4311bc61fb5954d2fe5dc0` (W10.1 complete, navigation reliability fix merged), clean tree, Alembic head `0014_opportunities`.

## 2. Branch
`feat/p10b-w10-2-users-access-workspaces`.

## 3. Authentication, session and workspace audit
| Area | Current implementation | Security consequence | W10.2 action |
|---|---|---|---|
| Account status | `users.status` (`active`, `deactivated`, `deletion_requested`), plain string | Only sign-in checked it | Enforce at request time too; deactivate/reactivate only (no invented states) |
| Sessions | `auth_sessions`: PK is the token **hash**, `user_id`, `created_at`, `expires_at`, `last_used_at`, `revoked_at`, coarse `user_agent`; cookie holds the raw token | A session row alone authenticated; deactivation left rows live (SEC-W10-01). The PK is a credential hash, so there is no safe opaque session id | Revoke in the deactivation transaction; reject inactive accounts in `SessionRepository.resolve`; revoke-all only |
| Session resolution | `get_current_user_id` (every candidate route) via `SessionRepository.resolve` | One choke point | Add the account-status check there (covers every path) |
| Role | `users.platform_role` (string, no CHECK); role re-read from the DB on every request (`get_current_principal`) | Demotion is immediate without session revocation | Pin by test; widen validation to the six presets only |
| Admin routes | W10.1 `require_permission`, atomic audit | Repository methods committed independently | New `AdminUserRepository`: state + sessions + audit in one transaction |
| Workspaces | `workspaces` (`owner_user_id`, name, status), `workspace_memberships` (unique per workspace+user; roles `workspace_owner`/`workspace_member`; status active/removed/left), invitations, share grants | Ownership is mandatory in the domain (the last owner cannot leave or be removed) | Admin list/detail, add existing user, remove, change role; keep the owner invariant; revoke removed members' shares |

## 4. SEC-W10-01 reproduction
`tests/test_sec_w10_01_repro.py` was written first and failed against the unfixed code: a session created before an admin deactivation still returned 200 from `/auth/me` afterwards. It is kept as a permanent regression (it passes now).

## 5. Root cause
Account status was checked only in `AuthService.login`. `SessionRepository.resolve` accepted any unrevoked, unexpired session and `AccountRepository.set_status` only flipped the column, so every candidate API kept working for a deactivated account until the session expired.

## 6. Request-time active-account enforcement
`SessionRepository.resolve` now also requires the owning account to be `active` (it returns no user otherwise and does not touch `last_used_at`). Because `get_current_user_id` already treats a supplied-but-unresolvable session as 401 in every environment, every session-authenticated request rejects an inactive account even if a session row survives (test SEC12 sets the status through the legacy path that does not revoke, and the live session row is still rejected; the candidate APIs `/memory` and `/opportunities` also return 401). Production stays fail-closed, the dev header and anonymous identity remain dev/test only, and email verification policy (POLICY-01) is unchanged.

## 7. Deactivation transaction
`AdminUserRepository.set_status` runs one transaction: lock and load the target, check the last-admin invariant, set the status, revoke all live sessions, add the canonical audit row (with the revoked count), commit. Any failure, including the audit insert, rolls everything back (test SEC10: after a forced audit failure the account is active, the session still works and no audit row exists).

## 8. Session revocation
Sessions are revoked by setting `revoked_at` (the existing architecture; rows are kept, never deleted). `AdminUserRepository.revoke_sessions` and the deactivation path share one helper. Expired sessions are not counted.

## 9. Reactivation semantics
Reactivation sets the status back to `active` and touches no session: pre-deactivation sessions stay revoked and the person must sign in again (SEC7-SEC9). No code path clears `revoked_at`.

## 10. Safe session metadata
The admin sees only the active-session count and, for the 10 most recent live sessions, `created_at`, `last_used_at` and `expires_at`. The token, its hash, the user agent and any IP are never selected or returned (SEC11 scans every response for the token and its SHA-256). No field was added to the schema.

## 11. Force logout
`POST /admin/users/{id}/sessions/revoke` (`platform.users.sessions.revoke`, now in the `platform_admin` preset) revokes all live sessions, audits actor, target, count, optional reason and request id, and reports a truthful zero when there are none. Revoke-all only: with the credential hash as primary key there is no safe per-session identifier to expose.

## 12. User list, search, filters, pagination
`GET /admin/users` is server-side: `q` (email substring or exact account id; `%`/`_` are literals), filters `status`, `role`, `tier`, `onboarding`, `locale`, `email_verified` (unknown values are 422), `page` and `page_size` (max 100), stable order (`created_at desc, id desc`). Workspace and session counts are correlated sub-queries in the same page query. The response keeps `users` (same page) beside `items` for the earlier shape. No query touches candidate content tables.

## 13. User detail schema
`GET /admin/users/{id}`: `account` (id, email, display name, status, role, tier, onboarding, locale, verification, timestamps, counts), `access` (role, server-resolved capability list, the code-defined assignable presets, `is_self`), `sessions` (above), `workspaces` (id, name, role, membership status), `audit` (the last 20 `admin.*` events about this account, with request id and safe context). Response models are explicit allowlists with `extra="forbid"`.

## 14. Private-content deny contract
No admin W10.2 schema, repository query or UI section carries CV/document text, answers, report text, Mo conversations, preparation chat, memories, evidence or stories. A test and `eval_admin_access.py` introspect every admin response model (109 fields) against a banned-name list (resume, document text/content, answer/report text, memory content, chat messages, private evidence, uploaded bytes, transcript, token, token hash, password, secret, user agent, storage key, IP). Workspace detail shows only an active-share count, never shared items.

## 15. Status administration
Only the real lifecycle is used: `active` and `deactivated` (`deletion_requested` is not admin-settable and is shown as stored). UI says Deactivate account / Reactivate account. A request needs `platform.users.manage`, server validation, a confirmation dialog (Cancel focused), an optional audited reason, the fail-closed audit and the request id. A no-op request is still audited.

## 16. Self-deactivation protection
Server-side: an admin deactivating their own account, or demoting their own role, gets 409 (tested through the API). The UI disables the button and says why, but the backend is the guard.

## 17. Last platform admin protection
Deactivating or demoting the last **active** `platform_admin` raises a conflict (409) inside the mutation transaction; inactive admins do not count. The active-admin rows are read `FOR UPDATE` in that transaction (real row locks on PostgreSQL; on SQLite the clause is ignored but writers are serialised, so a racing second writer fails instead of both committing). A blocked mutation leaves the database unchanged (tested). Because every actor must itself be an active `platform_admin`, the guard is reachable through the API only by races or direct repository use; both are tested at repository level.

## 18. Role administration
Role changes accept only the six code-defined presets plus `user`; unknown, custom, mis-cased or padded values are 422. There are no custom roles, no role tables and no per-user permission edits (`eval_admin_access.py` fails on a Role/Permission table). The UI's selector is fed by the server's `assignable_roles`.

## 19. Immediate role effect
The role is re-read from the database on each request, so a demotion applies to the target's existing session on its next request (tested: a demoted admin's old session gets 403 on `/admin/home`; a deactivated admin gets 401/403). No session revocation is needed for role changes.

## 20. platform_admin elevation boundary
Granting `platform_admin` needs `platform.users.role.assign`, an explicit confirmation, and writes an audit event with `before`, `after`, `elevation: true`, optional reason and request id. A second approver is not part of W10.2 and is carried to W10.13.

## 21. Tier boundary
Tier change is unchanged (`platform.subscriptions.manage`, atomic audit). It stays an account-metadata value; no purchase, plan or billing semantics are implied (W10.4).

## 22. Workspace domain audit
See section 3. Ownership is mandatory in the domain (owner membership role; "the last owner cannot leave or be removed"), memberships are unique per workspace and user, there is an invitation system (not extended) and view-only share grants.

## 23. Workspace list and detail
`GET /admin/workspaces` (search by name or id, status filter, pagination) and `GET /admin/workspaces/{id}` (metadata, owner email, members with role and status, active share count, active owner count). Never the shared items, documents, opportunities or reports.

## 24. Membership administration
`POST /admin/workspaces/{id}/members` (add an existing active account; a previously removed member's row is reactivated), `DELETE .../members/{user_id}` (status `removed`; that member's outbound shares into the workspace are revoked in the same transaction), `POST .../members/{user_id}/role`. All need `platform.workspaces.manage` (added to `platform_admin`), validate, and audit atomically with the request id. No invitation workflow was added.

## 25. Workspace invariants
A workspace keeps at least one active owner: removing or demoting the last owner is 409; duplicates are 409; an inactive account cannot be added; a deactivated workspace accepts no new member; unknown user or workspace is 404.

## 26. Audit events
New canonical names in `admin_audit.py`: `admin.sessions_revoked`, `admin.workspace_member_added`, `admin.workspace_member_removed`, `admin.workspace_member_role_changed`. Status and role changes keep `admin.account_status_change` and `admin.platform_role_change` (before/after, sessions revoked count, elevation flag); history continuity was preferred over renaming. Context is built by `build_audit` (secret/content keys rejected) and never holds a token or hash.

## 27. Permission routes
W10.2 added 6 privileged routes (user detail, force logout, workspace detail, add member, remove member, change member role) to the 27 of W10.1. **Current total: 33 privileged routes, 33 explicitly permission-covered, 0 uncovered** (dependency introspection; the guard no longer hard-codes a count). The W10.1 document keeps its historical 27 of 27.

## 28. Frontend
Extends the W10.1 shell (still English-only, permissions from `account.admin_permissions`): `/admin/users` (search, five filters, pagination, counts), `/admin/users/[id]` (account, access with role selector, sessions with force logout, workspaces, admin audit; actions appear only with their permission), `/admin/workspaces` and `/admin/workspaces/[id]` (members, add, change role, remove). Confirmations use an accessible label-agnostic dialog base (`ConfirmDialogBase`) so operator screens do not pull the locale catalogues; `ConfirmDialog` keeps the localized candidate behaviour. No role-name checks and no browser storage in admin components (test and evaluator).

## 29. Accessibility
Labelled search forms and filter controls, table captions with row/column headers, pager as a labelled `nav` with a status line, `alertdialog` confirmations with Cancel focused and focus trapped, errors inside the dialog (`role="alert"`), no colour-only state, native links and buttons.

## 30. Navigation reliability regression
All new admin links use `VerifiedLink` (`from "next/link"` is absent from admin components, enforced by the navigation guard test, which now lists the new views, and by `eval_admin_access.py`). Navigation unit tests (21) and the navigation Playwright flows pass; no retries, sleeps or timeouts were added.

## 31. Backend tests
**2630 passed, 3 skipped, 0 failed, 0 errors** (`python -m pytest`, 178 s; W10.1 baseline 2603/3). The 3 skips are unchanged: live Adzuna, a Streamlit-context render, a RAGAS adapter test. New: `tests/test_admin_access_w10_2.py` (26: SEC1-SEC12, session matrix, last-admin, roles, scoped presets, tier, list/detail, workspaces, schema guard, route coverage) and `tests/test_sec_w10_01_repro.py`. The pre-W10.2 user-list tests were updated for the additive fields. `ruff check .` is clean.

## 32. Frontend tests
565 unit tests pass in 76 files (W10.2: users list, filters, pagination, empty/forbidden, detail sections and no private-content sections, read-only role, dialog default Cancel, failed write not retried, self-view, role selector from the server, force logout, reactivation text, workspace list/detail/membership/read-only, no role-name authorisation). Typecheck, lint, production build and the hardcoded-English scanner (0 offenders) are clean. Async content is always awaited with `findBy*`/`waitFor`.

## 33. Playwright
**201 passed** (200 baseline plus the W10.2 admin journey: Users search, safe detail, governed action with confirmation, workspace membership), serial, no retries or timeout changes. Network is mocked, as established; permission, audit and session behaviour are proven in Python against a real database.

## 34. Evaluators
**29 of 29** CI evaluators pass, including the new `scripts/eval_admin_access.py` (16 checks: SEC-W10-01 tests present, request-time check, same-transaction revocation, no session revival, last-admin guard, self-lockout, code-defined roles, no role tables, no impersonation/break-glass routes, every route permissioned, W10.2 routes present, no content/secret schema fields, no token selection, no role-name UI checks, verified navigation, no migration), `eval_admin_foundation`, `eval_admin_design`. `eval_privacy_controls` now reads `ConfirmDialogBase` (behaviour moved there; same invariants).

## 35. Manual QA
Against a freshly migrated local backend (migration state `match`): the users list showed counts; the user detail showed account, access, one live session and workspaces; deactivating through the confirmation dialog reported "1 session(s) ended", the victim's earlier cookie then returned 401 and a new sign-in returned 401, and the audit table held one `admin.account_status_change` with a request id and `active to deactivated`. No secret or candidate content appeared. Test isolation: the dev-store fingerprint was unchanged and the tracked tree stayed clean.

## 36. Performance
First Load JS (`next build`): `/admin` 114 kB, `/admin/users` 114 kB, `/admin/users/[id]` 116 kB, `/admin/workspaces` 114 kB, `/admin/workspaces/[id]` 116 kB, shared 103 kB (unchanged). The detail pages are lean because `ConfirmDialogBase` avoids the locale catalogues (388 kB when the localized dialog was used). One list request per page and one detail request per detail page; sessions, audit and workspaces are loaded on detail only, never per table row; the list query is paginated (max 100).

## 37. Dependencies
None added.

## 38. Migration status
None. Existing tables and indexes are used (`auth_sessions.user_id` index, `workspace_memberships` indexes, `users` primary key). No index was proven necessary at the current scale; email search is a substring match, which would warrant an index or a different strategy at large scale (noted for W10.12 reporting/scale work, not needed now).

## 39. Alembic head
`0014_opportunities` (single head).

## 40. Security defect status
CLOSED: SEC-W10-01 (this wave, when merged), SEC-W10-02, SEC-W10-03, SEC-W10-06. OPEN: SEC-W10-04 (privacy queue, W10.10) and SEC-W10-05 (process-local pause, W10.11). No break-glass, no impersonation, no custom roles, no candidate private-content access.

## 41. W10.3 handoff
Support and ticketing can rely on: safe user lookup and detail, stable account ids and statuses, workspace metadata, force logout, request ids on every admin response and audit row, canonical permissions (`platform.support.*`) and the fail-closed audit helper. Support must keep operating without private-content access. Carried: role-assignment second approver and step-up (W10.13); per-session identifiers would need a schema decision (not needed now).

## 42. External calls
0 paid or live provider calls.
