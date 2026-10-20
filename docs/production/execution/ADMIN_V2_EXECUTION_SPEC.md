# Admin Platform 2.0 Execution Specification (Track C)

**Status:** PROPOSED engineering specification, 2026-10-21, from the owner's ADMIN-01 to ADMIN-06 requirements (`../OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md` section 3) and the traced rows REQ-OWN-01, 02, 03, 04, 08. It reuses the existing Admin documents (`docs/capstone/admin/W10_*`, `W12_4F_*`) and does not restate them. Nothing is implemented. Rules that never change: Admin is English-only at R1.0, owner-operated, every route has an explicit `require_permission`, Admin has no path to private candidate content, privileged changes are audited in the same transaction, configuration never creates executable behaviour.

## 1. What exists today (verified)

| Area | Existing foundation | Gap against the owner requirement |
|---|---|---|
| Navigation | 20 flat destinations in `frontend/lib/admin/capabilities.ts`, rendered by `AdminShell.tsx` with permission-aware visibility; platform-wide Review and Diagnostics at `/review`, also offered in the Candidate More menu to admin-permitted users (`INTERNAL_NAV`) | No groups, collapse, breadcrumbs or quick navigation; diagnostics sit outside the Admin shell |
| Plans | Versioned plans with draft, active and retired versions; routes `GET /admin/plans`, `/assignable`, `/{id}`, `POST /{code}/versions`, `PATCH /versions/{id}/entitlements`, activate, retire; user and workspace assignment routes; `EntitlementService` registry | No feature selection UI over registered features, comparison, access preview, clone UX or rollback tooling; limits editing is partial |
| Users | `GET /admin/users` and detail; plan, status and session-revoke actions; role changes through two-person approval; support and audit are separate pages | No sort and rich search, no membership inspection in the user view, no communications resend, no bulk actions, no per-user support and audit panel |
| Command Center | `GET /admin/home` metadata overview; readiness view (`/admin/readiness`); `src/reporting/` with suppression and telemetry tables (`ai_usage_facts`, `operational_metric_events`) | Dashboards listed by the owner (activation, interview funnel, AI failure and latency, model cost, worker and indexing failures, security indicators) are only partly sourced |
| Reports | `GET /admin/reports/definitions`, `product`, `quality`, `operations`, `ai-economics`, `commercial`; cohort suppression (`REPORTING_MIN_COHORT = 5`) | Twelve prebuilt reports not all present; no builder, saved configurations or export |
| AI operations | `src/ai_admin/` governed model configuration with evaluation and approval, provider status, integration status | No consolidated AI operations view with prompt versions (needs 01B), agent execution status or evaluation results in one place |

## 2. Package breakdown and PR boundaries

| Package | Scope | PRs | Depends on |
|---|---|---|---|
| 03A Navigation foundation | Grouped sidebar, breadcrumbs, quick navigation, relocation of Review and Diagnostics under `/admin`, Candidate nav cleanup | 1 (frontend plus redirects) | none |
| 03B Plans | Feature and limit editing on drafts, clone, compare, preview, assignment and rollback UX; backend preview and comparison | 2 (backend, frontend) | 03A |
| 03C Users | Search, sort, pagination, membership view, restricted bulk actions, communications, support and audit panels | 2 | 03A |
| 03D Command Center and AI operations | Metric catalogue, dashboards, AI operations view | 2 (metrics backend, views) | 03A (01B for prompt versions: soft) |
| 03E Reports and builder | Prebuilt reports, governed builder, saved configurations, exports | 2 | 03D (metric catalogue) |

### 03A navigation: proposed grouping (OD-ADMIN-NAV confirms)

| Group | Destinations (ids from `ADMIN_DESTINATIONS`) |
|---|---|
| Command Center | overview |
| Customers and Workspaces | users, workspaces, support, privacy |
| Products and Commercial | plans, billing |
| AI and Knowledge | ai, knowledge, speech, providers, review (moved to `/admin/review`) |
| Insights and Operations | reports, jobs, integrations |
| Governance and Settings | security, audit, legal, configuration, flags |

All 20 destinations are placed once. Route compatibility: existing `/admin/*` URLs stay; `/review` redirects to `/admin/review` for Admin users; `/review/agent` (owner-scoped run details) stays reachable for Candidates. A destination remains visible only when the caller holds its `anyOf` permission, and a group with no visible destination is hidden. Quick navigation is a filter over the visible destinations (no new data). Accessibility: disclosure pattern with `aria-expanded`, roving focus, visible focus, breadcrumb landmark, mobile drawer.

Tests: extend `frontend/tests/admin-shell-w10-1.test.tsx` (grouping, visibility per role fixture, no empty groups) and Playwright for expand/collapse, keyboard, breadcrumbs, responsive and redirects; backend 403 checks for diagnostic APIs stay as they are; `tests/_admin_matrix.py` and the role fixture are regenerated only if a route or permission changes.

### 03B plans: specification

- **Feature selection:** a draft plan edits only entitlements that exist in `EntitlementService.REGISTRY` (no free-text keys). The editor shows each registered feature with its description and the current candidate effect.
- **Limits and allowances:** typed numeric fields from the registry definition with bounds; invalid or undefined limits are rejected server-side.
- **Clone and version:** `POST /{code}/versions` already copies the active version into a draft; add an explicit clone-to-new-draft view and a comparison endpoint returning a typed diff between two versions.
- **Preview:** a read-only endpoint computes what a given account or workspace would be able to do under a draft version (using the same decision code as enforcement) so preview cannot drift from behaviour.
- **Assignment:** existing user and workspace assignment actions stay; workspace entitlements apply only through the existing authorised path.
- **Activate, retire, rollback:** activation keeps existing subscribers on their pinned version until an explicit migration decision; rollback creates a new assignment to the earlier active version (audited), never mutates history.
- **Enforcement and billing:** entitlements remain enforced in backend services only. Which entitlements are enforced during the free beta (history window, model profile) is OD-PLAN-ENFORCE; both gate constants stay False until the owner decides. No billing, checkout or payment route is touched.
- Possible migration: none expected (versions and entitlements tables exist). If a comparison cache is added, one additive migration.

### 03C users: specification

Search by email fragment and display name with filters (status, role, plan, workspace count, created range), sort and pagination on the existing list route; safe metadata only. Membership inspection reuses `AdminWorkspaceDetail`. Bulk actions are limited to a code-defined allow-list chosen by the owner (OD-BULK-ACTIONS): the proposed candidate set is session revoke and deactivate with a required reason, capped batch size, per-item audit, dry-run preview and no role changes or deletions. Account closure keeps the existing deletion engine. Communications resend uses `EmailService` for verification and recovery only, to the account's own address, rate limited. Per-user support status and audit history are read-only joins over existing tables. Self-lockout and privilege escalation guards stay server-side; role changes remain two-person with step-up. No view of CVs, stories, interviews or conversations (sentinel tests).

### 03D Command Center and AI operations: specification

A metric catalogue assigns each tile a source query, numerator, denominator, period, coverage rule and missing-data behaviour. Proposed tiles and sources:

| Tile | Source | Notes |
|---|---|---|
| Active users and registration trend | accounts and session tables | Needs a defined "active" window |
| Candidate activation | first Opportunity, Prepare run or Practice session (existing definition) | Cohort suppression applies |
| Interview start and completion rate | interview sessions | Denominator: started sessions |
| AI failure rate and latency | `ai_usage_facts`, `operational_metric_events` | Unknown stays null, never zero |
| Model usage and cost | `ai_usage_facts` | Known cost with explicit partial coverage |
| Retrieval and source health | knowledge readiness and index records | Uses 02A identity diagnostics |
| Worker and indexing failures | `jobs`, `job_workers` | Heartbeat staleness |
| Support ticket trends | support tables | |
| Security and incident indicators | security events and incidents | Metadata only |
| Deployment and provider readiness | `/admin/readiness` | Derived, never persisted |

Charts: chart type by meaning (trends as lines with the period axis, funnels as ordered bars, shares only where parts sum to a whole), always showing period, numerator, denominator, coverage and a missing-data state; an unavailable metric renders as unavailable. AI operations view assembles existing sources (model configuration and evaluation from `src/ai_admin`, prompt versions from 01B, provider status, agent execution status from owner-aggregated run facts, evaluation results) with no editing of system instructions or tool permissions.

### 03E reports and builder: specification

Prebuilt reports (acquisition and onboarding; engagement; interview practice and completion; AI feedback quality; Story Bank adoption and reuse; Workspace invitations and sharing; model performance and economics; agent and tool outcomes; knowledge and RAG quality; support; security and privacy; commercial only after real billing qualifies) are built from a registry of approved metrics and dimensions. The builder composes only registered metric and dimension ids with date range and comparison; it never accepts SQL or arbitrary column names. Saved configurations are stored as validated id lists (one additive migration), exports are limited to formats chosen by the owner (OD-REPORT-EXPORT; proposed CSV and JSON of already-suppressed aggregates). Suppression and permission checks run server-side on every request; a missing metric is returned as missing. Scheduled distribution and advanced automation are R1.2.

## 3. Permissions and migrations

Reuse existing permissions (`platform.plans.*`, `platform.users.*`, `platform.reports.read`, `platform.overview.read`, `platform.ai.read`) wherever possible. If the builder needs its own write permission, adding a 45th permission requires updating `src/application/admin_permissions.py`, the role presets, `tests/_admin_matrix.py`, the regenerated role fixture and `eval_admin_foundation`; that decision is flagged inside 03E rather than assumed. New tables (saved report configurations, optional invitation tables elsewhere) each get one Alembic revision after head `0039_speech_governance`, applied sequentially to keep a single head.

## 4. Test plan and exit gate (PG-08, PG-14)

Unit and API tests per package (above); the admin Playwright suites (`admin.spec.ts`, `admin-ux-w12-5.spec.ts`, `admin-secrets.spec.ts`, `admin-speech.spec.ts`) stay green; permission matrix and route invariant unchanged except as declared; privacy sentinels prove no candidate content reaches any new response; metric-source tests prove each tile is traceable. Exit: REQ-OWN-01, 02, 03, 04, 08 acceptance criteria pass in the browser with real or clearly labelled synthetic data.
