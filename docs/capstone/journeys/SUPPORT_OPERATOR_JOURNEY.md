# Ask4Mo: Support Operator Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This document describes what the **support_operator** role can do **today**, derived from the code-defined permission preset, the frontend destination table and the route permission graph (a read-only derivation, nothing mutated). Anything not built is labelled **PLANNED W12.4**. The role index is [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md); the owner role is [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md).

## 1. Role purpose

Handle candidate support requests: read what the candidate sent to Support, reply to the candidate, keep staff-only notes, and triage by priority, status and assignee. The role can look up bounded account and workspace metadata to understand a request. Authorization is by permission string only; the role name is never checked by any route. The role is a code-defined preset and cannot be customised. It is a delegated, least-privilege operational role, not a junior Platform Admin.

## 2. Permission boundary

**7 permissions** (a strict subset of the Platform Admin's 43):
`platform.overview.read`, `platform.users.read`, `platform.workspaces.read`, `platform.support.read`, `platform.support.reply`, `platform.support.manage`, `platform.support.note`.

Of the 147 Admin API routes this role may call **13**: the Command Center, the Support queue and ticket routes (list, detail, assignees, assign, priority, status, reply, note), and read-only user and workspace metadata.

## 3. Visible navigation

**4 destinations:** Overview (`/admin`), Users (`/admin/users`), Workspaces (`/admin/workspaces`), Support (`/admin/support`). Navigation is derived from the permission list supplied by the server; the server independently enforces every route.

## 4. Typical workday / workflow

Sign in -> Overview (counts of open, unassigned, waiting and high-priority tickets) -> Support queue (filter by status, category, priority, assignee) -> open a ticket -> read the candidate's message and the safe requester metadata -> **reply** (candidate-visible) or add an **internal note** (staff-only) -> set priority, status and assignee -> if needed open the requester's account or workspace metadata (read only) -> every change is audited.

## 5. Key actions

| Action | Permission | Notes |
|---|---|---|
| Open the queue and a ticket | `support.read` | Candidate-supplied text and safe account metadata only |
| Reply to the candidate | `support.reply` | **Customer-visible**; plain text; the candidate sees it on the Support page (no email is sent) |
| Add an internal note | `support.note` | **Staff-only**; stored in a separate table; never shown to the candidate or in their export |
| Change status, priority or assignee | `support.manage` | Priority is an internal label and promises no response time |
| Look up an account or workspace | `users.read`, `workspaces.read` | Metadata only |

## 6. High-risk actions / governance

The role has **no** step-up, two-person or destructive actions. It cannot deactivate accounts, revoke sessions, change plans or roles, or touch privacy requests. Replies and notes are audited. The distinction **candidate-visible reply is not an internal note** is the main care point: the reply box says the candidate will see it; the note box says it is staff only.

## 7. What the role cannot do

Change any account, role, plan, workspace or session; see billing, plans, security, audit, privacy, legal, knowledge, jobs, integrations, configuration or reports; approve anything; attach files (attachments are not implemented); email a candidate (not implemented); set or promise an SLA (none exists).

## 8. Candidate-data boundary

| This role **can** see | This role **cannot** see |
|---|---|
| The text the candidate intentionally sent to Support (subject, messages, category, optional request reference) | The candidate's CV, documents, interview answers, Mo conversations, Story Bank, memory or reports |
| Safe account metadata (email, account id, status, tier, interface language) | Billing, privacy, security, knowledge or integration records (other roles' domains) |
| Workspace metadata (name, status, owner, member count) | Anything shared inside a workspace |

Never visible to this role (or to any Admin role, including the 43 / 43 Platform Admin): candidate CVs, raw candidate documents, interview answer text, Mo conversations, Story Bank and private evidence, private preparation memory and candidate report contents. There is no break-glass, no impersonation and no "view as user" permission.

**Support exception:** content the candidate **deliberately submitted to Support** is visible to this role. That does not widen into permission to inspect preparation content. The ticket page states that CVs, documents, interview answers and Mo chats are not available to Support.

## 9. Current operational limitations

- No attachments, no email notifications, no SLA or response-time target (the candidate is told no response time can be promised).
- The role cannot see whether a worker is running or whether any background job failed.
- UX findings from the owner walkthrough that touch this role are tracked, not fixed: F-07 (raw timestamps and long references), F-16 (small link targets).

## 10. Escalation to Platform Admin

Escalate when the request needs something outside the support permissions: a **role change** (only `platform_admin` holds `users.role.assign`), an **account deactivation** or **session revocation** (deactivation is Platform Admin; session revocation is also held by the Security / Privacy Admin), a **plan change** (Billing Admin or Platform Admin), a **billing or refund** question (Billing Admin or Platform Admin), a **privacy or deletion request** (Security / Privacy Admin or Platform Admin), a **security incident** (Security / Privacy Admin or Platform Admin) or a **provider or configuration problem** (Operations Admin or Platform Admin). There is no database hierarchy; these are simply the roles that hold the needed permission.

## 11. Planned W12.4 impact

**PLANNED W12.4, not current.** W12.4F (Admin Configuration Completeness) may review whether Support needs visibility of delivery state once email operations exist (W12.4C), because replies are currently not emailed. No change to this role's permissions is planned or made here.

## 12. Route reference

| Page | URL |
|---|---|
| Overview | `/admin` |
| Support queue | `/admin/support` |
| Ticket | `/admin/support/{ref}` |
| Users (read only) | `/admin/users`, `/admin/users/{id}` |
| Workspaces (read only) | `/admin/workspaces`, `/admin/workspaces/{id}` |
