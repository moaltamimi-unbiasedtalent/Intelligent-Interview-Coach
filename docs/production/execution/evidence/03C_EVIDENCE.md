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
