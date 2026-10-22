# 03C Evidence: Admin Users, complete user management (REQ-OWN-03)

Branch `feat/03c-admin-users`, based on `origin/chore/migration-head-agnostic` (ec14963), a pushed prep branch that makes migration-head checks version-independent. That prep branch is NOT yet merged to main, so this branch must merge after it (or the PR must be stacked on it). Start time: 2026-10-22 01:57 CEST.

## Inventory of what existed (before any 03C code)
- `GET /admin/users` (`users.read`): q (email or id), status, role, tier, onboarding, locale, email_verified, page, page_size; fixed sort `created_at desc`. Summary allowlist (extra=forbid).
- `GET /admin/users/{id}`: account, access (role, capabilities, assignable roles, is_self), active-session metadata (no token/hash), workspaces, last 20 `admin.*` audit rows for the account, plan current + history.
- `POST /admin/users/{id}/status` (`users.manage`): deactivate/reactivate, revokes live sessions in the same transaction, self-deactivation and last-active-platform_admin guards, audit atomic; reason optional; no revision.
- `POST /admin/users/{id}/sessions/revoke` (`users.sessions.revoke`): reason optional; no revision.
- `POST /admin/users/{id}/plan` (`subscriptions.manage`): through `PlanRepository.assign` (entitlements domain, audited, atomic); no reason, no revision.
- `/admin/role-changes` (W10.13): two-person request/approve/reject/cancel, step-up, stale detection. No route changes a role directly (`set_platform_role` is repository-only).
- Workspace membership actions live on `/admin/workspaces/*`; support tickets on `/admin/support/*`; privacy requests and the deletion pipeline (`record_request`, `execute-deletion` job) on `/admin/privacy/*`.
- Frontend: `UsersView.tsx` (filters, table, pager), `UserDetailView.tsx` (account, access/role request, plan control, sessions, workspaces, audit).

## Gap list against REQ-OWN-03 (written before coding)
| # | Gap | Req |
|---|---|---|
| G1 | No sort control (fixed `created_at desc`) | U1 |
| G2 | No filter by last-activity bucket, sign-in method, open support/privacy case, workspace membership | U1 |
| G3 | List rows carry no last-activity bucket | U1 |
| G4 | Detail has no auth-method summary (password / provider kinds, no subjects or secrets) | U1/U4 |
| G5 | Detail has no support/privacy case counts, pending role-change indicator, deletion state | U6 |
| G6 | Detail has no workspace-membership summary (counts, owner-of) | U5 |
| G7 | No account `revision`; no mutation takes `expected_revision`; stale views can overwrite | all mutations |
| G8 | Reason optional on status/revoke, absent on plan | audit quality |
| G9 | No resend / expire of the email-verification link by an operator | U4 |
| G10 | No way to start account deletion from the user (only by searching the privacy domain) | U2 |
| G11 | No hierarchy guard: an actor with `sessions.revoke` can act on a more privileged account; self force-sign-out and self plan change are allowed | U8 |
| G12 | Restricted bulk actions | U7 |
| G13 | Role-change request has no stale-view (revision) guard | U3 |

## Plan for closing gaps
G1 to G6 in the list and detail read models (metadata only). G7, G8, G11 and G9, G10 through new strict action routes (`/admin/users/{id}/actions/*`, mandatory `reason` and `expected_revision`); the legacy status/sessions/plan routes stay for compatibility and accept an OPTIONAL `expected_revision` which is enforced when supplied. G13: optional `expected_revision` on the role-change request. G12: needs OD-BULK-ACTIONS, decided NOT to implement (see below).

## Requirement mapping (REQ-OWN-03, U1 to U9)
| ID | Covered | How | NOT covered |
|---|---|---|---|
| U1 search, filter, sort, paginate, safe metadata | Yes | `GET /admin/users` gains `sort` (created_at, updated_at, email, status, role, workspaces, last_active), `direction`, `last_active` bucket, `auth_method` (password/other), `open_case` (support/privacy), `has_workspace`; allowlisted enums (422 otherwise); rows gain a coarse `last_activity` bucket. Search stays email or id (no display-name or content search). | Created-date range filter (not requested by the register acceptance wording; trivial to add). |
| U2 activate, suspend, close, delete via the existing deletion engine | Yes | `actions/deactivate`, `actions/reactivate` (sessions end in the same transaction; reactivation never revives sessions). Account deletion is only a RECORDED privacy request (`actions/request-deletion`, type deletion, source `admin_recorded`, idempotent, privacy.execute); execution remains `POST /admin/privacy/requests/{id}/execute-deletion` (the same W10.9 job candidates use). The action deletes and deactivates nothing (test). | "Close" as a separate state: the account lifecycle has `active / deactivated / deletion_requested` only; no new state was invented. |
| U3 role changes only through two-person approval | Yes (unchanged flow, hardened) | No route under `/admin/users` can change a role (test scans handlers; `set_platform_role` stays repository-only). The role-change request now accepts an optional `expected_revision` (stale screen refused 409) and refuses a role with more authority than the requester/approver holds. | Step-up and two-person rules are the existing W10.13 ones, untouched. |
| U4 revoke sessions; resend permitted account communications | Yes | `actions/force-signout`; `actions/resend-verification` (existing `AuthenticationService.send_verification`, so the same template, single-newest-link rule and `EmailService`; same per-account rate limits); `actions/expire-verification` (consumes outstanding links, one transaction with audit). | Password-reset resend is NOT offered: a reset is a candidate-initiated credential flow and sending one on someone else's behalf is a phishing-shaped capability. No delivery guarantee: `mail_accepted` is provider acceptance only. |
| U5 assign plan; inspect memberships; membership actions | Partly | Plan assignment through `PlanRepository.assign` (the entitlements domain) with reason and revision; detail shows plan history and a workspace-membership summary (active/total/owner-of-active) and links; membership ACTIONS stay on `/admin/workspaces/*` (W10.2, unchanged). | Add/remove membership from the user page (existing workspace routes cover it; not duplicated). |
| U6 support status and audit history per user | Yes (counts) | Detail shows support open/total, privacy open/total, pending role change, open deletion request id/status, plus the existing last-20 `admin.*` audit rows for the account. No ticket subject, message, internal note or privacy note is returned (sentinel test). | Per-ticket listing from the user page (the support and privacy queues already filter by account). |
| U7 restricted bulk actions | NO | Needs OD-BULK-ACTIONS (open). No bulk framework was built because the approved set is unknown; building one would invent policy. Every action is single-account, revision-guarded and audited, so a future approved bulk action can wrap them. | All of U7. |
| U8 owner self-lockout and escalation prevented server-side | Yes | Self deactivate / force sign-out / plan / deletion request / verification actions are 409 on your own account. Hierarchy: an actor cannot act on an account whose permission set is not a subset of the actor's current permissions (403). The last active `platform_admin` stays protected (existing guard). Role requests/approvals cannot grant a role beyond the actor's own permissions. All checks run inside the mutation transaction against current database state. | The legacy `/status` and `/plan` routes keep their original self-semantics (see risks). |
| U9 no view of CVs, stories, interviews, conversations | Yes | Allowlist schemas (`extra=forbid`), field-name sweep, sentinel tests (ticket subject/body, privacy note, password, hashes never appear in list, detail or action responses); no new permission. | |
Also: expected-revision on every NEW mutation, mandatory reason (3 to 200 chars), audit in the same transaction, 44 permissions unchanged, English-only UI, no migration.

## Design decisions
- **Revision without a migration.** There is no `users.revision` column. `account_revision` (src/admin_users/revision.py) is a 16-hex digest of the facts Admin actions change (status, role, email-verified, `updated_at`, active subscription id, live-session count, outstanding verification-link count, open privacy-request count). It is recomputed INSIDE the mutation transaction (a `precondition` hook added to `AdminUserRepository.set_status/revoke_sessions`, `PlanRepository.assign`, `PrivacyRequestService.create`), so check-and-act is atomic. A repeat with a fresh revision is an idempotent, audited no-op (`changed:false`); a repeat with the old revision is 409.
- **Why new strict routes next to the legacy ones.** `/admin/users/{id}/status`, `/sessions/revoke`, `/plan` are pinned by many existing tests and specs with optional reason. They stay, and now ALSO accept an optional `expected_revision` (enforced when supplied; force sign-out on the legacy route is now hierarchy-protected). The UI uses only the strict `/actions/*` routes.
- **Resend verification and the transaction rule.** An email cannot join a database transaction. The audit row (authorisation, reason, revision check) is committed first, then the existing identity flow sends; a send failure is recorded by that flow as `account.email_failed` (category only). This is the one mutation whose audit precedes its side effect; the token store change itself is inside the identity flow, not ours.
- **Migration:** NOT needed, none added. Reserved revision 0045 unused. Alembic head untouched.

## Changes
- New: `src/admin_users/{__init__,revision,guards,insights,actions}.py`, `src/api/routes/admin_users.py` (7 POST routes under `/admin/users/{id}/actions/`), `src/api/schemas/admin_users.py`, `tests/test_admin_users_03c.py`, `frontend/components/admin/UsersPlanPanel.tsx`, `UsersAccountPanels.tsx`, `frontend/tests/admin-users-03c.test.tsx`, `frontend/e2e/admin-users-03c.spec.ts`.
- Modified (backend): `src/admin_repository.py` (list sort/filters, activity bucket, precondition hooks), `src/plans_repository.py`, `src/privacy/requests.py` (precondition hook only), `src/admin_security/role_changes.py`, `src/api/routes/admin.py`, `admin_security.py`, `src/api/schemas/admin.py`, `src/application/admin_audit.py` (3 new event names), `src/api/main.py` (router registration).
- Modified (frontend, Users components + their plumbing only): `UserDetailView.tsx`, `UsersView.tsx`, `lib/admin/types.ts`, `lib/api/client.ts` (one `userAction` method). NOT touched: `AdminShell.tsx`, `capabilities.ts`, `nav-items.ts`.
- Existing tests edited (disclosed, none weakened): `test_admin_access_w10_2.py` (exact response key set extended by the five new keys, still an exact-set assertion); `test_platform_admin_p6_5.py`, `test_integrated_w11.py` and `scripts/eval_platform_admin.py` (list-row allowlist gains `last_activity`); `frontend/tests/admin-users-w10-2.test.tsx` (the three tests that drove deactivate / failure / force-logout now assert the strict action call with reason and revision, because the UI contract became stricter: a reason is mandatory); `frontend/e2e/admin.spec.ts` (W10.2 and W10.4 flows fill the now-mandatory reason; mock gained the strict action route).

## Security and privacy impact
Metadata only. New response fields are counts, enums and a bucket; auth methods are `password | google | sso` (never an issuer or provider subject); activity is a bucket, not a timestamp; no ticket or privacy-note text; no email in any audit context or log line added (test); audit keys pass the forbidden-fragment guard. No new permission (registry 44; each route uses `users.manage`, `users.sessions.revoke`, `subscriptions.manage` or `privacy.execute`). 7-persona matrix test over every new route (derived from `tests/_admin_matrix.py`) plus the existing W10.14 route x persona matrix, which discovers the new routes automatically.

## Remaining human or operational evidence
OD-BULK-ACTIONS decision (U7). Owner review of whether the legacy status/sessions/plan routes should be retired. Live email delivery of the resend is unverified (memory sender in tests).

## Tests and commands (start 2026-10-22 01:57 CEST)
| Check | Result |
|---|---|
| `pytest tests/test_admin_users_03c.py` (18 tests: list sort/filter/pagination, detail completeness, sentinels, schema field sweep, 7-persona x 7-route matrix, body strictness, lifecycle + audit, plan, self/hierarchy, last admin, role-change guard, resend/expire, deletion pipeline, audit-failure rollback, legacy revision, 404s) | 18 passed, repo .venv and /tmp/ci_venv |
| Related suites (`test_admin_access_w10_2`, `test_security_w10_13`, `test_admin_qualification_w10_14`, `test_platform_admin_p6_5`, `test_plans_entitlements_w10_4`, `test_integrated_w11`) | pass under both venvs (ci_venv: 169 passed in the first batch, 18 in w11 after the allowlist fix) |
| Full `pytest tests -n 3 --dist loadfile` under /tmp/ci_venv | 2 failures, no others. (1) `test_integrated_w11::test_k1_...` : list-row allowlist lacked `last_activity`; FIXED and re-run (18 passed). (2) `test_knowledge_persistence_02a_identity::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` : it diffs against `origin/feat/02k-knowledge-contract` and flags `src/agent/*`, files this branch does not touch; it is an artefact of the base (it can only pass on a branch stacked on 02K), NOT caused by 03C. Not fixed, not weakened. |
| `ruff check .`; `ci_test_shards.py verify --shards 4` | pass; 282 files in exactly one shard |
| All 46 CI evaluators (`scripts/eval_*.py` from ci.yml, with CI's arguments) under /tmp/ci_venv | 46 PASS, 0 FAIL |
| Frontend `tsc --noEmit`, `npm run lint`, full vitest | clean; 115 files, 1143 passed (8 new, 3 existing adapted) |
| Playwright (E2E_PORT=3110): new `admin-users-03c.spec.ts` | 3 passed; `admin.spec.ts`, `admin-navigation-03a.spec.ts`, `admin-ux-w12-5.spec.ts` 31 passed |
Commands: `/tmp/ci_venv/bin/python -m pytest tests/test_admin_users_03c.py -p no:cacheprovider`; the full-suite command above; `cd frontend && E2E_PORT=3110 npx playwright test e2e/admin-users-03c.spec.ts e2e/admin.spec.ts`.
CI: not available until a PR exists. Rework rounds: 2 (test fixtures/allowlists; last-seen filter names).

## Risks and limitations
- Legacy `/admin/users/{id}/status|plan|sessions/revoke` remain with optional reason/revision (enforced when supplied) because many tests pin them; a client calling them directly bypasses the mandatory-reason rule. Recommend retiring them in a follow-up.
- The revision is a derived digest, not a stored counter; it detects any of the listed state changes but not a change that leaves all of them identical.
- Resend: audit precedes the email side effect (see design); delivery not confirmed.
- Hierarchy rule is permission-subset based; because `platform_admin` holds all 44, only it can act on another `platform_admin`.
- Base: depends on `chore/migration-head-agnostic` (unmerged). No migration; 0045 left unused.

## Delivery
Branch feat/03c-admin-users; code head e9211d2 (this note is a following docs-only commit). First push: 03:00 CEST approx. PR: owner opens https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/03c-admin-users (base on chore/migration-head-agnostic until that merges).

## Addendum 2026-10-22: integration with main (PR #231)

Merged `origin/main` (03B plans, 03D1, 03E1, 04A, 04E, 02B, 02C, 06H landed). Three conflicts: `src/api/main.py` (router list: main's list plus `admin_users` at its original position; `admin_plans_ops` stays before `admin_plans`), and two real logic conflicts around plan assignment, where both packages had added an optimistic-concurrency parameter to `PlanRepository.assign` and to `POST /admin/users/{id}/plan`:
- `PlanRepository.assign` / `assign_in_session` now accept BOTH `expected_revision` (03B: subject-plan revision token, checked with `plan_revision.require`) and `precondition` (03C: in-transaction guard run on the account row locked `FOR UPDATE`: acting administrator still active, self and hierarchy guards, account-revision check). Order: lock and load the account, run `precondition`, then check `expected_revision`, then change the subscription. Neither check was dropped and the bulk path (03B) is unchanged.
- The legacy `POST /admin/users/{id}/plan` keeps the 03B token (what the Admin plan UI `PlanControl` sends) and adds only the non-revision part of 03C's guard (acting administrator still active, row lock). The strict `/admin/users/{id}/actions/assign-plan` route keeps 03C's account-revision precondition. The two revision schemes are therefore not mixed on one route. `PlanAssignRequest.expected_revision` is `max_length=64`.
No migration is added by this package; the chain is 0040, 0041, 0042, 0043 with one head.
