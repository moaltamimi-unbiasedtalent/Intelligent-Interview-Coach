# Admin Capability Matrix (P10B-W10) — PLANNING ONLY

Planning artefact. **No role, permission, table, route or screen described here is implemented by this
document.** Companion to `ADMIN_PLATFORM_MASTER_PLAN.md`.

Legend. **Sensitivity:** None = platform metadata; Low = account metadata; Med = aggregates/derived account
data; High = could reveal private candidate content (only via governed flow). **Priority:** Critical / Desirable /
Post. **Status:** FOUNDATION = bounded P6.5 capability exists; PARTIAL = building blocks exist; NOT STARTED.
**Mock OK:** a production-ready interface + mock adapter is acceptable (labelled as mock, never as live).
Candidate dependency = candidate-side work the capability relies on.

| Capability | Description | Candidate dependency | Admin persona | Private-data sensitivity | Authorization requirement | Audit required | Live integration required | Mock adapter acceptable | Capstone priority | Target wave | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Control-plane design | Capability inventory, IA, authz/role model, threat model, audit/secret/billing/KB designs | none | Platform owner | None | Owner approval gate | Decision record | No | n/a | Critical | W10.0 | NOT STARTED |
| Admin shell & navigation | `/admin` frame, nav, capability-aware menu | none | All admin personas | None | `admin.access` | Access logged | No | n/a | Critical | W10.1 | FOUNDATION (single page) |
| Command Center dashboard | Health, alerts, recent incidents/failed jobs, release/eval status | none | Platform admin, Ops | None | `ops.view` | No (read) | No | n/a | Critical | W10.1 | PARTIAL (`GET /admin/home`) |
| Environment/version panel | Git SHA, FE/BE version, migration version | none | Ops | None | `ops.view` | No | No | n/a | Critical | W10.1 | NOT STARTED |
| Provider health panel | Per-provider status, latency, last failure | none | Ops | None | `ops.view` | No | Yes (provider probes; sandbox ok) | Yes | Critical | W10.1/W10.6 | PARTIAL (`GET /admin/providers` metadata) |
| Admin audit-log foundation | Append-only, request-ID linked audit of privileged actions | W9.1 request IDs | Security admin | None (no secrets/content) | `audit.view` | Is the audit | No | n/a | Critical | W10.1 | PARTIAL (`GET /admin/audit`) |
| User search & safe metadata | Find users; account metadata only | none | Support admin | Low | `users.view` | Search/lookups logged | No | n/a | Critical | W10.2 | FOUNDATION (`GET /admin/users`) |
| Suspend / reactivate account | Status change with self-lockout guard | none | Platform admin | Low | `users.suspend` | Yes (before/after) | No | n/a | Critical | W10.2 | FOUNDATION |
| Role & capability assignment | Grant/revoke capability roles; no self-elevation | none | Platform owner | Low | `roles.manage` + second approver | Yes | No | n/a | Critical | W10.2 | PARTIAL (USER/PLATFORM_ADMIN only) |
| Session revocation / force logout | Invalidate a user's sessions | none | Support/Security admin | Low | `users.revoke_sessions` | Yes | No | n/a | Critical | W10.2 | NOT STARTED |
| Onboarding & consent/legal status | Onboarding state, accepted legal versions per user | W9.8 consent versions | Support/Privacy admin | Low | `users.view` | No (read) | No | n/a | Critical | W10.2 | NOT STARTED |
| Workspace administration | Workspace/membership metadata, suspension, share/revocation visibility | none | Platform admin | Low (metadata; never shared content) | `workspaces.view/manage` | Yes (changes) | No | n/a | Critical | W10.2 | FOUNDATION (`GET /admin/workspaces`) |
| Governed privileged data access (break-glass) | Reason-bound, time-boxed, audited access if ever needed | none | Designated approvers | **High** | `breakglass.request` + approver | Yes (reason, scope, window, visible to owner where policy allows) | No | n/a | Post (decide in W10.0) | W10.0 design / W10.2 only if approved | NOT STARTED |
| Candidate "Contact support" entry | In-app localized report-a-problem with request-ID | W9.1 request IDs; 8-locale copy | Candidate | Med (user-supplied text) | Authenticated candidate | Ticket created | No | n/a | Critical | W10.3 | NOT STARTED |
| Ticket queue & triage | Queue, categories, priority, assignment, SLA | none | Support agent | Med | `support.ticket.view/triage` | Yes | No | n/a | Critical | W10.3 | NOT STARTED |
| Ticket lifecycle | New -> Triaged -> In Progress -> Waiting for Customer -> Resolved -> Closed; reopen | none | Support agent | Med | `support.ticket.update` | Yes (status history) | No | n/a | Critical | W10.3 | NOT STARTED |
| Replies, internal notes, attachments | Customer-visible replies vs internal notes; safe attachments | document safety pipeline | Support agent | Med-High (attachments) | `support.ticket.reply` | Yes | Email delivery (sandbox ok) | Yes (email) | Critical | W10.3 | NOT STARTED |
| Ticket/incident linkage | Link tickets to account, request-ID, incident | W9.1 request IDs | Support lead | Low | `support.ticket.link` | Yes | No | n/a | Critical | W10.3/W10.13 | NOT STARTED |
| Subscription plan CRUD | Create/edit/archive plans; visibility public/private/internal | none | Commercial admin | None | `billing.plan.edit` (+approver for price) | Yes (before/after) | No | n/a | Critical | W10.4 | NOT STARTED (tiers hard-coded) |
| Entitlements & usage limits | Feature entitlements and limits per plan; replaces scattered `if premium` | candidate gating consumers | Commercial admin | None | `billing.entitlement.edit` | Yes | No | n/a | Critical | W10.4 | PARTIAL (`capabilities_for(tier)` in code) |
| User/workspace subscription assignment | Assign/change plan, trial, complimentary access | none | Commercial/Support admin | Low | `billing.subscription.assign` | Yes | No | n/a | Critical | W10.4 | PARTIAL (`POST /users/{id}/tier`) |
| Billing price & currency | Monthly/yearly price, currency, tax state | none | Commercial admin | None | `billing.price.edit` + second approver | Yes | Provider (sandbox ok) | Yes | Desirable | W10.4/W10.5 | NOT STARTED |
| Payment provider abstraction | Provider interface; webhooks; no raw card data | none | Platform owner | Low | `billing.provider.manage` | Yes | Yes for live; sandbox for Capstone | **Yes - labelled mock/sandbox** | Desirable | W10.5 | NOT STARTED |
| Invoices, payment state, failed payments, grace | Billing history and dunning states | none | Billing admin | Low | `billing.view` | No (read) / Yes (changes) | Provider | Yes | Desirable | W10.5 | NOT STARTED |
| Refunds, coupons, promotions | Governed financial adjustments | none | Billing admin | Low | `billing.refund` + second approver | Yes | Provider | Yes | Desirable | W10.5 | NOT STARTED |
| Integration registry | AI, email, OCR, storage, STT/TTS/realtime, Career Intelligence provider status | none | Platform admin | None | `integrations.view` | No | Yes (probes) | Yes | Critical | W10.6 | PARTIAL (`GET /admin/providers`) |
| Secret rotate/disable/test | Write-only secrets; rotate, disable, test connection; never re-displayed | none | Platform owner | None (secret never shown) | `integrations.secret.rotate` + approver | Yes (no values) | Secret store | **Yes (vault adapter)** | Critical | W10.6 | NOT STARTED |
| Model & provider catalogue | Approved providers/models/profiles; task->model & fallback mapping, timeouts, cost limits | evaluation harness | AI admin | None | `ai.model.view/edit` | Yes | Provider | Yes | Desirable | W10.7 | PARTIAL (`src/llm/policy.py` in code) |
| Model lifecycle Draft->Activate | Validate -> Evaluate -> Approve -> Activate; no bypass of evaluation | evaluation gates | AI admin + approver | None | `ai.model.activate` + second approver | Yes | Evaluation (deterministic) | Yes | Desirable | W10.7 | NOT STARTED |
| Knowledge source registry | Authority, licence, production-allowed, language, geography, classification, freshness, counts | P10C source model (later) | Knowledge admin | None | `kb.source.view` | No | No | n/a | Critical | W10.8 | PARTIAL (governance in code; `/reviewer`, diagnostics) |
| Governed manual upload | Upload -> Safety -> Parse -> Classify -> Provenance/licence -> Preview -> Approval -> Index; never straight to prod | document safety pipeline | Knowledge admin + approver | None (non-candidate sources) | `kb.source.upload`, `kb.source.approve` (distinct) | Yes | No | n/a | Critical | W10.8 | NOT STARTED |
| Indexing, re-index, refresh, enable/disable | Controlled operations with retrieval diagnostics | none | Knowledge admin | None | `kb.source.operate` | Yes | No | n/a | Critical | W10.8 | PARTIAL |
| Jobs & queue visibility | Status of document/OCR/email/ingestion/index/export/deletion/eval/webhook jobs | none | Ops | Low | `ops.jobs.view` | No | No | n/a | Desirable | W10.9 | NOT STARTED |
| Safe retry/cancel | Retry or cancel failed jobs; dead-letter handling | none | Ops | Low | `ops.jobs.operate` | Yes | Queue infra | Yes (advanced queue infra) | Desirable | W10.9 | NOT STARTED |
| Privacy request workflows | Access/export/deletion/correction requests, status, deletion execution | W9.8 Data & Privacy Center | Privacy admin | Med (metadata; no content) | `privacy.request.view/process`; `privacy.deletion.execute` + approver | Yes | No | n/a | Critical | W10.10 | PARTIAL (`GET /admin/privacy-requests`) |
| Retention & consent administration | Retention status, consent history, legal-doc versions, effective dates, re-acceptance, translation-review status | W9.8, 8-locale legal copy | Privacy/Legal admin | Low | `privacy.legal.manage` | Yes | No | n/a | Critical | W10.10 | NOT STARTED |
| Privacy incidents & sharing visibility | Record incidents; view sharing/revocation state without content | none | Privacy admin | Low | `privacy.incident.manage` | Yes | No | n/a | Critical | W10.10/W10.13 | NOT STARTED |
| Feature flags | Global/environment/account/plan flags where justified | none | Platform admin | None | `config.flag.edit` | Yes | No | n/a | Desirable | W10.11 | PARTIAL (`/admin/pause` switches) |
| Safe system settings | Limits, SLA settings, model defaults; no raw secrets | none | Platform admin | None | `config.setting.edit` | Yes | No | n/a | Desirable | W10.11 | PARTIAL (cost limits in config) |
| Product & quality reporting | Registrations, activation, usage, completion, evaluations, retrieval/abstention, feedback | none | Product/Ops | Med (aggregates only) | `reports.view` | No | No | n/a | Critical | W10.12 | PARTIAL (`/admin/home`, `/feedback`) |
| Operations & support reporting | Availability, latency, provider failures, KB health, ticket metrics | W10.3 | Ops/Support lead | None | `reports.view` | No | No | n/a | Critical | W10.12 | NOT STARTED |
| Commercial reporting | Subscriptions, up/downgrades, churn, MRR/ARR, failed payments | W10.4/W10.5 | Commercial admin | Med | `reports.commercial.view` | No | No | n/a | Desirable | W10.12 | NOT STARTED |
| AI economics | Tokens/cost per user/session/model; expensive workflows | cost accounting | AI/Finance admin | Med (aggregates) | `reports.ai_cost.view` | No | No | n/a | Desirable | W10.12 | PARTIAL (cost accounting exists) |
| Immutable admin audit trail | Append-only; sensitive-action history; export; tamper evidence | none | Security admin | None | `audit.view/export` | Is the audit | No | n/a | Critical | W10.13 | PARTIAL |
| Auth/security events | Failed logins, lockouts, privilege changes, session anomalies | none | Security admin | Low | `security.events.view` | No | No | n/a | Critical | W10.13 | NOT STARTED |
| Incident management | Affected service, assignment, root cause, resolution, linked tickets | W10.3 | Ops/Incident lead | Low | `incidents.manage` | Yes | Pager (mock ok) | Yes (pager integration) | Critical | W10.13 | NOT STARTED |
| Release & deployment controls | Release/rollback visibility and controls | none | Platform owner | None | `release.manage` | Yes | CI/CD | Yes (deployment controls) | Post | W10.1 (visibility only) | NOT STARTED |
| Admin qualification | Authorization, audit completeness, no-superuser, secret non-disclosure, owner scoping, 8-locale where defined | all W10 | QA / Owner | n/a | n/a | Evidence recorded | No (deterministic) | n/a | Critical | W10.14 | NOT STARTED |

## Notes

- Capabilities ending in `+ approver` / `+ second approver` encode proposed separation of duties; W10.0 confirms
  the list with the owner.
- "Mock OK" never relaxes honesty: any mock/sandbox adapter is visibly labelled in the admin UI, docs and reports,
  and qualification must show no mock is represented as live.
- Existing P6.5 routes noted as FOUNDATION/PARTIAL are bounded operations features, not W10 deliverables; W10
  supersedes the single-page console with a capability-gated shell.
