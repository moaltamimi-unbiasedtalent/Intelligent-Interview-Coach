# Ask4Mo: Security / Privacy Admin Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This document describes what the **security_privacy_admin** role can do **today**, derived from the code-defined permission preset, the frontend destination table and the route permission graph (a read-only derivation, nothing mutated). Anything not built is labelled **PLANNED W12.4**. The role index is [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md); the owner role is [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md).

## 1. Role purpose

Watch security events, manage in-app alerts and incidents, review and export bounded audit data, run the privacy-request workflow including the existing account-deletion orchestration, administer legal-document versions and revoke sessions. Authorization is by permission string only; the role name is never checked by any route. The role is a code-defined preset and cannot be customised. It is a delegated, least-privilege operational role, not a junior Platform Admin.

## 2. Permission boundary

**11 permissions:** `platform.overview.read`, `platform.users.read`, `platform.users.sessions.revoke`, `platform.privacy.read`, `platform.privacy.execute`, `platform.legal.manage`, `platform.security.read`, `platform.security.manage`, `platform.incidents.manage`, `platform.audit.read`, `platform.audit.export`.

Of the 147 Admin API routes this role may call **33**. It does **not** hold `platform.users.role.assign`, so it cannot request or approve platform role changes and has no Role approvals tab.

## 3. Visible navigation

**6 destinations:** Overview (`/admin`), Users (`/admin/users`, read only plus session revocation), Security (`/admin/security`), Audit (`/admin/audit`), Privacy (`/admin/privacy`), Legal (`/admin/legal`). Inside Security the tabs available are Security events, Audit, Incidents and Alerts.

## 4. Typical workday / workflow

Sign in -> Overview (open incidents, alerts, privacy requests) -> Security events -> **alerts**: acknowledge or resolve (in-app only) -> **incidents**: open, update, change status, link support tickets -> **Audit**: filter and, with a reason and period, export a bounded CSV -> **Privacy**: assign, change status, and where a deletion is requested **execute the existing deletion workflow** -> **Legal**: register a draft version and publish it -> **Users**: revoke a person's sessions where needed.

## 5. Key actions

| Action | Permission | Notes |
|---|---|---|
| View security events, alerts, incidents and the summary | `security.read` | Typed projection of audit events; no email, IP or token |
| Acknowledge or resolve an alert | `security.manage` | Alerts are in-app only; no external paging |
| Create, update, change status of and link tickets to an incident | `incidents.manage` | Free text is never copied into audit context |
| View and export audit data | `audit.read`, `audit.export` | Export needs a reason and a period; bounded |
| View the privacy queue; assign, change status, record a request, backfill the run index, execute deletion | `privacy.read`, `privacy.execute` | **`privacy.execute` is not a second deletion engine**: Admin-triggered deletion runs the same account-deletion service as a candidate's own deletion, as a background job |
| Register and publish legal versions | `legal.manage` | A published version is immutable; one is current |
| Revoke all of an account's sessions | `users.sessions.revoke` | Confirmation and optional reason; audited |

## 6. High-risk actions / governance

- Privacy execution, legal publication and session revocation each need a confirmation and are audited; **none requires step-up or a second approver today**. Step-up applies only to platform role changes, and this role cannot reach them (`/admin/step-up` itself requires the role-assignment permission).
- **Legal acceptance is not consent**: acceptance records (user, version, time, source) are kept without IP or device and are never back-filled; re-acceptance is not enforced. The pages state they are not a compliance measure. No GDPR compliance or certification claim and no statutory retention period is made.
- Terminology is exact: *delete* removes data; *archive* hides it; *revoke* ends a share or session; *unlink* separates records; *anonymise* removes identity from records that must be kept.

## 7. What the role cannot do

Change roles or deactivate accounts (no `users.manage`); read support, plans, billing, knowledge, AI configuration, jobs, integrations, configuration, flags or reports; approve role changes; **see or export candidate content**; impersonate, view as a user or use break-glass (none exists); and see Admin export of candidate data (none exists).

## 8. Candidate-data boundary

| This role **can** see | This role **cannot** see |
|---|---|
| Account metadata, privacy-request workflow state and result category, audit and security metadata, legal-version metadata and acceptance counts | CV, documents, interview answers, Mo conversations, Story Bank, memory, reports |
| The short note a candidate typed into a privacy request (the field asks for no private content) | The content of what is deleted |
| Retention inventory (classification only) | Backup contents |

Never visible to this role (or to any Admin role, including the 43 / 43 Platform Admin): candidate CVs, raw candidate documents, interview answer text, Mo conversations, Story Bank and private evidence, private preparation memory and candidate report contents. There is no break-glass, no impersonation and no "view as user" permission.

## 9. Current operational limitations

- Alerts are in-app only; there is no external paging, no advanced anomaly detection and no email.
- **PostgreSQL append-only audit triggers are unit-checked but not executed against a live PostgreSQL.**
- The role holds no `jobs.read`, so it cannot see the queue or worker state that account deletion depends on (finding SJA-03).
- Two audit surfaces exist (`/admin/audit` is a bare list; filters and export are under Security, Audit), owner-walkthrough finding F-06, tracked not fixed.
- Backups are not erased instantly and some preparation-chat working data may remain until cleanup; the Admin pages say so.

## 10. Escalation to Platform Admin

Escalate for: a **role change** (only the Platform Admin holds `users.role.assign`), **account deactivation** (`users.manage`, Platform Admin), a stuck deletion job or worker problem (Operations Admin or Platform Admin hold `jobs.manage`), billing, integrations, knowledge or AI matters (their roles or the Platform Admin), and any configuration or secret issue (Operations Admin or Platform Admin).

## 11. Planned W12.4 impact

**PLANNED W12.4, not current.** W12.4C (Email & Identity Operations) will matter here where verification, password-reset and identity diagnostics become Admin-visible, and W12.4B (secret administration) will add security-relevant audit and step-up requirements. W12.4F may review whether this role needs job visibility. No permission change is made or promised here.

## 12. Route reference

| Page | URL |
|---|---|
| Overview | `/admin` |
| Security (events, audit, incidents, alerts) | `/admin/security` |
| Audit | `/admin/audit` |
| Privacy | `/admin/privacy`, `/admin/privacy/{ref}` |
| Legal | `/admin/legal` |
| Users (read only, session revoke) | `/admin/users`, `/admin/users/{id}` |
