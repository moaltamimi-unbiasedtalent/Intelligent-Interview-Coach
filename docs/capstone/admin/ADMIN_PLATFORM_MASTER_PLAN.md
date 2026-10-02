# P10B-W10 - Platform Administration, Support & Commercial Operations: Master Plan (W10.0 architecture)

**Status: DESIGN / PLANNING. Nothing planned here is implemented.** W10.0 changes no route, model, migration, permission, dependency or UI. It is the
approved architecture and implementation plan that W10.1-W10.14 must follow. Companion files: [ADMIN_CAPABILITY_MATRIX.md](ADMIN_CAPABILITY_MATRIX.md) (every
capability, permission and wave) and [ADMIN_ARCHITECTURE_DECISIONS.md](ADMIN_ARCHITECTURE_DECISIONS.md) (decisions and open decisions AD-01..AD-08). Roadmap:
[../capstone_phase_plan.md](../capstone_phase_plan.md). Baseline: `main` f272f00 (P10B QUALIFIED AND INTEGRATED), Alembic head `0014_opportunities`.

## 1. Purpose and end state
An authorised Ask4Mo operator can run day-to-day operations (CONTROL, MONITOR, CONFIGURE, SUPPORT, REPORT, GOVERN, TROUBLESHOOT) through an Admin Portal without routinely
editing source, editing database rows, opening shells, retrieving plaintext secrets or bypassing privacy controls.
**Core rule: PLATFORM ADMIN != UNRESTRICTED PRIVATE-CANDIDATE-DATA SUPERUSER.**

## 2. Current-state inventory (verified in code at f272f00)
CURRENT (do not present planned items as current):

| Capability | Route / service | Backend authority | Candidate-visible | Production-ready? | Gap |
|---|---|---|---|---|---|
| Admin role | `users.platform_role` in {`user`,`platform_admin`}; `require_platform_admin` | `src/api/dependencies.py` | no | basic | no fine-grained roles/permissions, no MFA/step-up, only `bootstrap_admin.py` + `POST /admin/users/{id}/role` grant it |
| Account list/status/role/tier | `GET /admin/users`, `POST /admin/users/{id}/role|tier|status` | `routes/admin.py`, `auth_repository.py` | no | partial | UI read-only; **status change does not revoke sessions** (status checked only at login); email LIKE search only |
| Workspaces (metadata) | `GET /admin/workspaces`, `/admin/home` counts | `workspace_repository.py` | no | read-only | no member/share views, no deactivate route |
| Privacy requests | `GET /admin/privacy-requests` | lists `status=deletion_requested` | no | **dead queue** | nothing sets that status since W9.12 removed `/auth/account/delete-request`; admin cannot export/delete on a user's behalf |
| Feedback aggregates | `GET /admin/feedback` | aggregates only | no | read-only | no replies, no raw view (by design) |
| Pause switches | `GET /admin/pause`, `POST /admin/pause/{capability}` | `application/pause.py` | 503 to candidates when paused | partial | process-local, lost on restart, not shared across replicas |
| Provider status | `GET /admin/providers` | booleans/labels only | no | read-only | no health probes (all "UNVALIDATED"), no model/OpenRouter view, no spend |
| Audit view | `GET /admin/audit`, `GET /auth/admin/audit` (own events) | `audit_events` | no | partial | no `context`/`request_id`/actor email in the view, no filters/export, failures and document ops not audited, writes swallow errors, no DB-level immutability |
| Reviewer / knowledge diagnostics | `/reviewer/*` (GET), `GET /knowledge/diagnostics` | router-level admin gate | no | read-only | knowledge is CLI-managed; no approval, rebuild or toggle in product |
| Evaluation diagnostics | `/evaluation/*` (GET) | admin gate | no | read-only | reads stored offline runs only |
| Prompt Lab / config versions | `/reviewer/prompt-lab/*`, `/reviewer/config-versions` | admin gate | no | read-only | no model administration |
| Frontend | `/admin` (`AdminConsole`), `/review/*` | client guard + server gate | hidden from non-admins | basic | English-only, unpaginated, no write controls, no detail views |
| Health | `/health` (name + package version), `/ready`, `/capabilities` | open | yes | basic | no git SHA, build time or migration revision |

NOT YET BUILT (verified absent): comprehensive user administration, session revocation by admin, support/ticketing or any contact channel, plans/subscriptions/billing,
integration and secret administration, model administration, governed KB ingestion UI, GDPR admin workflows, incident centre, operations/commercial reporting,
background-job abstraction (all long operations are synchronous), DB-backed feature flags (env flags only), consent/legal-version persistence, preparation-run index, MFA.

**Current findings that W10 must remediate (not deferred to "later"):** SEC-W10-01 deactivated accounts keep working sessions (W10.2, first); SEC-W10-02 admin audit writes
swallow errors, i.e. a privileged change can succeed without an audit row (W10.1: sensitive writes become fail-closed); SEC-W10-03 audit events lack `request_id` on admin
paths, failed admin access is not audited and bootstrap vs API event names differ (W10.1); SEC-W10-04 dead privacy-request queue (W10.10); SEC-W10-05 pause state not durable
(W10.11); SEC-W10-06 `email.provider` is echoed raw in `/admin/providers` (W10.6).

## 3. Target architecture
```
Admin UI (Next.js /admin, capability-gated nav)  ->  /api/v1/admin/* (deny-by-default, permission dependency per route)
   -> Admin application services (one per domain; thin orchestration, no private-content access)
        -> existing domain services (account deletion, export, sharing, knowledge governance, evaluation, model policy)  [reuse, never duplicate]
        -> new domain services: Support, Plans/Entitlements, Billing(adapter), Integrations(SecretStore), Jobs, Privacy requests, Flags, Reporting, Incidents
   -> Audit service (append-only, fail-closed for sensitive writes)  ->  persistence (Alembic, grouped migrations)
   -> adapters: BillingProvider (Mock first), SecretStore (env/local first), Mailer, JobRunner (DB-backed), Alert sink (in-app only)
```
Principles: backend authoritative; deny by default; capability-based checks; admin services orchestrate and never read candidate content; every sensitive write is audited
in the same transaction; mocks are labelled; no browser-based code deployment.

## 4. Personas
| Persona | Purpose | Maps initially to |
|---|---|---|
| Platform Administrator | broad operation, role assignment, flags | `platform_admin` (all non-break-glass permissions) |
| Support Operator | tickets, account troubleshooting (metadata only) | role preset `support_operator` |
| Billing Administrator | plans, subscriptions, invoices | preset `billing_admin` |
| Knowledge Administrator | sources, ingestion, indexing, provenance | preset `knowledge_admin` |
| Security / Privacy Administrator | audit, incidents, DSAR, legal versions | preset `security_privacy_admin` |
| Operations Administrator | health, jobs, integrations, config | preset `ops_admin` |
**Decision (AD-08):** permissions are defined first; roles are named presets of permissions defined in code; the UI and routes check permissions, never role names. Runtime role
separation ships in W10.1 using the existing `users.platform_role` column (widened set of values, no schema change); a roles table is deferred until multi-role is needed.

## 5. Permission model (capability namespace, default deny)
`platform.<domain>.<action>`. Read and manage are separate; high-risk actions have their own permission and, where noted, second-approver or step-up.

| Domain | Permissions |
|---|---|
| overview | `platform.overview.read` |
| users | `platform.users.read`, `.manage` (suspend/reactivate), `.sessions.revoke`, `.role.assign` (second approver) |
| workspaces | `platform.workspaces.read`, `.manage` |
| support | `platform.support.read`, `.reply`, `.manage` (assign/close), `.note` |
| billing | `platform.plans.read`, `.manage`, `.price.change` (second approver); `platform.subscriptions.read`, `.manage`; `platform.billing.read`, `.refund` (second approver) |
| integrations | `platform.integrations.read`, `.manage`, `.secret.rotate` (step-up) |
| AI | `platform.ai.read`, `.manage`, `.activate` (second approver, evaluation-gated) |
| knowledge | `platform.knowledge.read`, `.manage`, `.approve` (distinct from upload) |
| jobs | `platform.jobs.read`, `.manage` |
| privacy | `platform.privacy.read`, `.execute` (second approver for deletion), `platform.legal.manage` |
| config | `platform.flags.read`, `.manage`, `platform.config.manage` |
| reporting | `platform.reports.read`, `platform.reports.commercial.read` |
| security | `platform.security.read`, `.manage`, `platform.incidents.manage`, `platform.audit.read`, `.export` |
| releases | `platform.releases.read` |
| RESERVED (not built) | `platform.breakglass.request`, `.approve` |
**Canonical permission list (stable identifiers; `platform.breakglass.request` / `.approve` are reserved and unimplemented):**
```
platform.ai.activate
platform.ai.manage
platform.ai.read
platform.audit.export
platform.audit.read
platform.billing.read
platform.billing.refund
platform.breakglass.request
platform.config.manage
platform.flags.manage
platform.flags.read
platform.incidents.manage
platform.integrations.manage
platform.integrations.read
platform.integrations.secret.rotate
platform.jobs.manage
platform.jobs.read
platform.knowledge.approve
platform.knowledge.manage
platform.knowledge.read
platform.legal.manage
platform.overview.read
platform.plans.manage
platform.plans.price.change
platform.plans.read
platform.privacy.execute
platform.privacy.read
platform.releases.read
platform.reports.commercial.read
platform.reports.read
platform.security.manage
platform.security.read
platform.subscriptions.manage
platform.subscriptions.read
platform.support.manage
platform.support.note
platform.support.read
platform.support.reply
platform.users.manage
platform.users.read
platform.users.role.assign
platform.users.sessions.revoke
platform.workspaces.manage
platform.workspaces.read
```

Enforcement: FastAPI dependency `require_permission("platform.x.y")` on every admin route; frontend nav built from the principal's permission list (UX only); a CI invariant fails any
`/admin` route without a permission dependency. Elevated actions: confirmation dialog with reason; high-risk: step-up (re-enter password now; MFA-ready interface) and/or second approver.

## 6. Information architecture (`/admin`)
| Section | Purpose / persona | Read | Write | Sensitive data | Permission | Audit | Wave |
|---|---|---|---|---|---|---|---|
| Overview (Command Center) | Ops/Platform | health, alerts, recent changes | none | metadata | overview.read | no | W10.1 |
| Users | Support/Platform | search, status, plan, onboarding | suspend, revoke sessions, role | email, ids | users.* | yes | W10.2 |
| Workspaces | Support | metadata, members | deactivate | member emails | workspaces.* | yes | W10.2 |
| Support | Support | queue, thread | reply, assign, close | ticket text (candidate-supplied) | support.* | yes | W10.3 |
| Plans / Subscriptions | Billing | plans, subscriptions | create/edit plans, assign | none | plans.*, subscriptions.* | yes | W10.4 |
| Billing | Billing | invoices, payments (mock) | refund (mock) | no card data | billing.* | yes | W10.5 |
| Integrations | Ops | status, health | enable, rotate, test | secret refs only | integrations.* | yes | W10.6 |
| AI & Models | Platform/Ops | profiles, policy, activations | draft, activate | none | ai.* | yes | W10.7 |
| Knowledge | Knowledge | sources, counts, health | upload, approve, index, disable | source metadata | knowledge.* | yes | W10.8 |
| Jobs | Ops | status | retry, cancel | linked ids | jobs.* | yes | W10.9 |
| Privacy & Legal | Security/Privacy | requests, consent state | execute, publish versions | request metadata | privacy.*, legal.* | yes | W10.10 |
| Flags & Settings | Platform | flags | change | none | flags.*, config.* | yes | W10.11 |
| Reports | Product/Commercial | aggregates | none | aggregates only | reports.* | no | W10.12 |
| Security / Audit / Incidents | Security | audit, events, incidents | manage incidents | metadata | security.*, audit.* | yes | W10.13 |
| Releases / System | Ops | version, SHA, migration head, model profile, knowledge snapshot | none | none | releases.read | no | W10.1 |
Admin is desktop-first, English-only internal tooling (AD-01), accessible (section 31).

## 7. Private-data boundary
**Default: admin never sees** CV/document contents, answers, preparation chats, Mo conversations, memories, evidence, reports or private files. **Admin may see** account id, email,
status, onboarding state, plan, timestamps, request ids, error metadata, ticket relationships, subscription state, consent state (when implemented), audit events.
Rules: admin services never import candidate-content repositories; reports are aggregates with a minimum cohort size; universal search targets operational identifiers only
(never full-text private content); a CI invariant fails if an admin route returns fields on a deny-list (document text, answer text, memory summary, report body).

## 8. Break-glass (decision AD-02: NOT needed for Capstone)
Support operates from metadata, request ids, structured diagnostics and **user-provided ticket attachments**. Reserved design if later required: explicit reason, linked ticket or incident,
named operator, requested scope, time-boxed grant (auto-expiry), second approver, candidate notification (consent where the use case allows), read-only, audited, no impersonation,
prohibited for export or bulk access. Permissions `platform.breakglass.*` are reserved and unimplemented.

## 9. Support domain (W10.3)
Candidate entry: "Contact support / Report a problem" (localized x8). Entities: ticket (id, user, category, priority, status, assignee, subject, body, request id, route, app version,
created/updated, SLA fields, related incident), message (customer-visible reply), internal note, attachment (safe-upload pipeline, owner = ticket). Status flow New, Triaged, In Progress,
Waiting for Customer, Resolved, Closed (reopen allowed). Categories: account/login, Opportunity, Prepare, Practice/interview, documents, AI response, billing, privacy, accessibility,
technical, data issue, other. Access: candidate sees own tickets and customer-visible replies; support sees tickets and safe diagnostics; internal notes never visible to candidates;
billing/privacy tickets visible to those personas. Safe diagnostics (section 28). Help != ticketing remains true until W10.3 ships.

## 10. Subscription / entitlement domain (W10.4)
`SubscriptionPlan -> Entitlements -> Usage Limits -> Billing Price -> User/Workspace Subscription`. Plans: create, edit, archive, visibility (public/private/internal), interval, currency,
price, trial, entitlements (voice, Career Intelligence, company research, workspace/team), limits (documents, Opportunities, practice interviews), support tier. **Entitlement resolution**: a single
`EntitlementService.resolve(user|workspace) -> ResolvedEntitlements` (deterministic: subscription state + plan + admin overrides + flags) replaces the current tier-to-capability map;
application code asks for a capability or a limit, never `if premium`. Existing `basic`/`premium` map to seeded plans so no behaviour regresses.

## 11. Billing abstraction (W10.5)
`BillingService -> BillingProvider (interface) -> MockBillingAdapter (Capstone) -> future hosted-checkout adapter`. Provider-owned: card data, tax computation, payment authorisation.
Ask4Mo stores only provider customer/subscription ids, state, invoice metadata and events. Webhook handling idempotent via the job model. The mock adapter is labelled MOCK in UI, API and
reports and can never be enabled in a production environment flagged live. Refunds: mock only.

## 12. Integration architecture (W10.6)
Registry of integrations (AI providers, email, OCR, storage, STT/TTS/realtime, research/Career Intelligence sources): configured?, enabled?, environment, provider, capability, last
success/failure, latency, health, rate-limit state, credential last-rotated. Health probes are explicit, bounded and never run on page load. Admin actions: enable/disable, set/rotate secret, test connection.

## 13. Secrets architecture
`Admin -> IntegrationService -> SecretStore (interface) -> EnvSecretStore (read from env; Capstone default) / LocalEncryptedSecretStore (dev, key from env) -> future vault adapter`.
Admin UI may **set/rotate, test, disable**; it can never read plaintext, display a full key, log a value, or put a value in audit. Stored/returned metadata: `configured`, `last_rotated_at`,
`last_tested_at`, `health`, and a secret *reference*. Configuration tables never hold secrets. Rotation requires step-up.

## 14. AI / model configuration lifecycle (W10.7)
Draft -> Validate (schema, allow-list) -> Evaluate (deterministic evaluator suite must pass) -> Approve (second approver) -> Activate (versioned, audited, instantly rollbackable).
Model profile/policy config is versioned; activation records the evaluator run id; admins cannot bypass evaluation; environment separation (staging activation before production); a raw slug
from a candidate stays impossible (existing invariant). Builds on `src/llm/models.py` and `policy.py`.

## 15. KB / RAG administration (W10.8)
Source registry fields: id, type, authority level (1 official/statistical, 2 public/professional framework, 3 reputable industry), provider, country/geography, language, classification, version,
licence, URL, publication/retrieval dates, freshness policy, production-allowed, ingestion/index status, record/chunk counts, provenance, health. Governed flow:
Upload -> file safety/malware -> parse -> classify -> provenance/licence declaration -> preview -> approve -> index -> activate (**never upload -> production**). Also refresh, reindex, disable,
rollback to prior snapshot, diagnostics, retrieval test console (admin-only, sources only). Russian or generated aliases never carry "official ESCO" provenance. Operates P10C sources later;
does not replace P10C.

## 16. Jobs / queues (W10.9; decision AD-05)
Today every long operation is synchronous and no worker exists. Design: a small DB-backed `background_job` abstraction (no external broker): states Pending, Running, Completed, Failed,
Retrying, Dead-letter; linked entity, request id, attempts, failure reason (sanitised), timestamps; a separate worker process (compose service) polls with row locking; retry/cancel are admin
actions; handlers are idempotent. First consumers: KB ingestion/indexing, DSAR export/deletion execution, webhook processing. Existing synchronous paths stay synchronous unless migrated deliberately.

## 17. Privacy / legal operations (W10.10)
Reuse W9.8 services (section 30). **PRIV-W9-01:** `preparation_run` index (AD-06) enables candidate-side list/delete and complete account deletion. **PRIV-W9-02:** `legal_document_version` and
`legal_acceptance` (AD-07) with a re-acceptance gate and translation-review status. Admin workflow: request intake (candidate-initiated or on-behalf with identity verification), status, execution
via jobs, retention state, privacy incident log. No GDPR certification claim.

## 18. Feature flags / configuration (W10.11)
DB-backed flags with scopes (global, environment, plan, account, workspace), default, fail-safe value, owner, audit; env flags remain the bootstrap default and a hard override. Pause switches move
to the same store (durable, shared). No secrets in configuration. Rollout is on/off per scope (percentage rollouts post-Capstone).

## 19. Reporting (W10.12)
Aggregates only, minimum cohort size, no content. Product (registrations, activation, onboarding, Opportunities, Prepare, Practice, completion, return), Quality (evaluator results, retrieval/abstention,
feedback, errors), Operations (availability, latency, provider failures, ingestion health, ticket metrics), Commercial (subscriptions, up/downgrades, churn, MRR/ARR), AI economics (tokens, estimated cost per
user/session/model, expensive workflows). **Instrumentation gaps (verified):** no active-user, registration-trend, error-rate, latency, provider-health, job or cross-user cost counters exist; usage is
captured per run/report only. W10.1 adds the minimal event capture needed; metrics without events are not shown.

## 20. Audit
Append-only `audit_events`, fail-closed for sensitive writes (change and audit commit together), `request_id` on every admin event, `reason` required for sensitive actions, before/after for safe fields only,
no secrets, no candidate content. Add DB-level protection (no UPDATE/DELETE grants; trigger on SQL backends where available) and an export. Coverage list: user suspended/reactivated, session revoked, admin
role changed, plan/price/subscription changed, refund, integration enabled, credential rotated, model activated, source approved/disabled, retention changed, deletion initiated, flag changed, break-glass
(reserved), failed admin access. Standardise event names (`<domain>.<action>`).

## 21. Incidents (W10.13)
Incident: title, severity, status, affected service, start/end, owner, affected-user estimate, linked tickets, root cause, remediation, audit trail. In-app alerts only (no external paging in Capstone).

## 22. Release / environment health
Read-only first: environment, version, Git SHA, build time, frontend/backend version, Alembic head, evaluator/release status, active model profile, active knowledge snapshot, flags, provider health. Build metadata is injected
at build time (new, W10.1). Observability before deployment control; no browser deployment.

## 23. Threat model
| Threat | Impact | Mitigation | Audit | Residual |
|---|---|---|---|---|
| Compromised admin account | full operational control | MFA-ready step-up, per-action permissions, second approver on high-risk, session revoke, rate limit | all admin actions | MFA not live in Capstone |
| Excessive privilege | misuse | least-privilege role presets, default deny, quarterly review report | role changes | single-owner setups |
| Cross-user access via admin API | privacy breach | admin services never touch content repos, deny-list invariant, IDOR tests | access to user records | metadata PII (email) remains visible |
| Private-content browsing | privacy breach | no content endpoints, no content search, no break-glass in Capstone | n/a | support attachments are candidate-supplied |
| Secret exposure | provider compromise | write-only secrets, references only, masked metadata, no secret in logs/audit | rotations | env adapter exposes env to ops |
| Malicious provider config | data exfiltration | allow-listed provider hosts, test-connection bounded, approval for enable | integration changes | operator error |
| Model activation bypass | unsafe model | evaluation gate + second approver, versioned rollback | activations | evaluators are deterministic only |
| Billing abuse | revenue loss | price-change second approver, plan audit | price/plan changes | mock only in Capstone |
| Refund abuse | loss | refund permission + second approver + limits | refunds | mock only |
| KB poisoning | wrong/unsafe guidance | governed ingestion, provenance, approval, preview, rollback | approve/disable | licence judgement is human |
| Malicious file upload | malware | safety scan, size/type limits, isolated storage, never served inline | uploads | scanner coverage |
| Feature-flag abuse | disable controls | flag permission, audit, fail-safe defaults | flag changes | |
| Audit tampering | evidence loss | append-only, DB protection, export | n/a | privileged DBA |
| Incident-log tampering | cover-up | append-only status history | incident edits | |
| Break-glass abuse | privacy breach | not built; if built: reason, approver, expiry | all | n/a for Capstone |
| Session hijacking | account takeover | HttpOnly cookie, revoke on deactivation (SEC-W10-01), short admin TTL, step-up | session events | cookie theft on endpoint |
| Privilege escalation | admin takeover | role assignment needs second approver; self-demotion guards; no self-grant | role changes | bootstrap script is host-trusted |

## 24. Data-model forecast and migration groups (no migration in W10.0)
| Entity | Purpose | Sensitive fields | Retention | Wave | Migration |
|---|---|---|---|---|---|
| (permissions code-defined) | roles/permissions | none | n/a | W10.1 | **none** |
| audit_events (extend) | request_id/reason/before-after | metadata | retained, anonymised on deletion | W10.1 | MG-1 (columns/indexes) |
| support_ticket, support_message, support_internal_note, support_attachment | support | candidate text | until closed + policy | W10.3 | MG-2 |
| subscription_plan, plan_entitlement, plan_price, subscription | commerce | none | life of account/legal | W10.4 | MG-3 |
| billing_event, invoice_meta, payment_attempt | billing mirror | provider ids | legal | W10.5 | MG-4 |
| integration_config, secret_reference | integrations | refs only | n/a | W10.6 | MG-5 |
| model_profile, model_activation | AI config | none | audit | W10.7 | MG-6 |
| background_job (+event) | jobs | linked ids | rolling | W10.9 | MG-7 |
| knowledge_source_admin, ingestion_job | KB governance | none | n/a | W10.8 | MG-8 |
| preparation_run | PRIV-W9-01 | user link | with account | W10.10 (earlier if needed) | MG-9 |
| legal_document_version, legal_acceptance | PRIV-W9-02 | user link, timestamps | legal | W10.10 | MG-9 |
| privacy_request | DSAR/deletion | user link | legal | W10.10 | MG-10 |
| feature_flag | flags | none | n/a | W10.11 | MG-11 |
| incident, admin_notification | ops | none | n/a | W10.13 | MG-12 |
Group by domain wave (about 12 small migrations, never one giant migration); each is additive, reversible and has its own rollback test. Candidate-owned tables use FK `ON DELETE CASCADE`
to users unless legal retention requires anonymisation (AD-07).

## 25. Capstone scope
CAPSTONE CRITICAL: admin shell and permission framework, health/release visibility, users/access incl. session revocation, support/ticketing, plan creation + entitlement model, integration/provider
administration, KB administration, privacy/GDPR operations (incl. PRIV-W9-01/02 data model), audit trail, essential reporting. CAPSTONE DESIRABLE: feature flags, incident management, AI cost reporting,
workspace administration depth, universal search, billing mock workflows, model administration UI. POST-CAPSTONE ACCEPTABLE: live refunds and payments, production vault, external paging, deployment control,
analytics warehouse, percentage rollouts, break-glass.

## 26. Mock / live boundaries
| Integration | Capstone | Never |
|---|---|---|
| Billing | mock adapter + provider interface | present mock as live |
| Secret store | interface + env/local adapter | store plaintext in DB, show secrets |
| Incident paging | in-app alerts only | claim paging |
| Rate limiter | in-memory (Redis adapter exists, not live-validated) | claim distributed limiting live |
| Email | existing adapters (console/memory/Brevo) | |
| Job runner | DB-backed in-process worker | external broker |
| AI providers | existing OpenRouter path; admin governs config | auto-activate models |

## 27. Dependency graph and critical path
```
permission framework + audit foundation (W10.1) -> every domain wave
users/sessions (W10.2) -> support (W10.3)  -> incidents/links (W10.13)
plans/entitlements (W10.4) -> billing (W10.5)
integration registry + SecretStore (W10.6) -> model admin (W10.7), KB admin (W10.8)
job model (W10.9) -> KB ingestion (W10.8), DSAR execution (W10.10), webhook handling (W10.5)
privacy models (PRIV-W9-01/02) -> W10.10
all waves -> admin qualification (W10.14) -> integrated candidate + admin requalification -> RC-P10-003
```
Critical path: W10.1 -> W10.2 -> W10.4 -> W10.6 -> W10.9 -> W10.8 -> W10.10 -> W10.14 (support W10.3 and reporting W10.12 run beside it).

## 28. Wave plan (execution order; numbering unchanged)
| Wave | Title | Cx | Priority | Order |
|---|---|---|---|---|
| W10.0 | Architecture & control-plane design (this) | M | critical | 0 |
| W10.1 | Admin shell, command center, permission framework, audit foundation, build metadata | L | critical | 1 |
| W10.2 | Users, access & workspace administration (incl. SEC-W10-01) | L | critical | 2 |
| W10.3 | Customer support & ticketing | XL | critical | 3 |
| W10.4 | Plans, subscriptions & entitlements | L | critical | 4 |
| W10.6 | Integrations & API connections (+ SecretStore) | L | critical | 5 |
| W10.9 | Jobs, queues & operational diagnostics | L | critical (needed by 8/10) | 6 |
| W10.8 | Knowledge base & RAG administration | XL | critical | 7 |
| W10.10 | GDPR, privacy & legal administration (+ PRIV-W9-01/02) | L | critical | 8 |
| W10.5 | Billing & payment administration (mock) | XL | desirable | 9 |
| W10.7 | AI & model administration | L | desirable | 10 |
| W10.11 | Feature flags & safe configuration | M | desirable | 11 |
| W10.12 | Reporting, analytics & AI economics | L | critical (essential) / desirable (economics) | 12 |
| W10.13 | Security, audit & incident management | L | critical | 13 |
| W10.14 | Full Admin qualification | L | critical | 14 |
Refinement rationale: W10.9 is moved before W10.8 and W10.10 because both need a job model; audit foundation moves from W10.13 into W10.1 because every sensitive wave needs it; billing (W10.5) follows
plans and is desirable (mock). Historical numbering is retained.

## 29. Qualification strategy
Test layers: **Backend** permission matrix (every route x every persona, default deny), IDOR/cross-user, audit emission and fail-closed, secret non-disclosure, domain behaviour. **Frontend** nav gating,
forms, destructive confirmations, state handling, accessibility. **E2E** candidate denied, support scoped, billing mock lifecycle, KB approval flow, privacy-request lifecycle. **Evaluators/guards**
admin permission invariants (every admin route has a permission), no content superuser (deny-list), no secret exposure, mock/live truthfulness, migration consistency, release matrix extension.
**"Admin Platform Qualified" (W10.14)** means: candidate cannot reach Admin; support cannot do billing/admin-only actions; billing admin cannot browse private content; knowledge admin cannot manage users; audit
events emitted (and fail-closed); secrets never returned; entitlements deterministic; billing labelled mock/live; integrations testable; KB ingestion governed; privacy workflows reuse candidate services; flags
audited; reporting privacy-safe; incident and audit workflows work; CI green from a fresh checkout with a clean tree.
**After W10.14: integrated candidate + admin requalification is still required before RC-P10-003** (candidate P10B must not regress). Sequence: W10.0 -> W10.1-14 -> integrated requalification -> RC-P10-003 -> remaining
Pilot 2 -> P10C -> P10D/E/F -> P11.

## 30. W9.8 reuse (no second privacy engine)
Admin orchestrates, existing services execute: export = `application/data_export.build_candidate_export`; account deletion = `AccountDeletionService`; selective deletes = owner services (documents, memory,
Opportunities, `delete_interview_with_source`); sharing revoke = `SharingService`; inventory = the owner-scoped list services; audit = `AuditRepository`. Admin-on-behalf actions call these with the target user id
inside an audited, permission-checked, reason-bearing admin workflow (execution as a job); they never reimplement deletion.

## 31. Cross-cutting decisions
- **Localization (AD-01):** admin is English-only internal tooling for Capstone; candidate-facing strings that W10 adds (support form, legal-version prompt, plan names/pricing) are localized x8 and scanned.
- **Accessibility:** semantic landmarks, keyboard-operable tables and filters with labels, focus-managed dialogs, non-colour status, desktop-first with usable tablet width; no WCAG certification claim.
- **Support diagnostics (safe):** account status, route, request id, error class, timestamp, app version, provider involved, latency, retry count, flag state, plan/entitlement, related ticket/incident; never raw prompts or answers.
- **Universal operator search:** user email/id, workspace, ticket, request id, subscription/invoice, Opportunity id, report id, job, provider, source; identifiers/metadata only.
- **Alerting categories:** provider outage, error rate, failed payments, stale source, indexing failure, ticket SLA breach, deletion deadline, auth anomalies, release evaluator failure, job backlog; with severity,
  de-duplication, acknowledgement, resolution and an owning persona; in-app only.
- **Observability required before dashboards:** request/error counts, latency, provider health and usage, job status, ingestion status, payment/support status, audit events. Exists today: request id, per-run usage,
  aggregate account/workspace counts. Missing: everything else (section 19).
- **Admin security baseline:** backend authoritative, default deny, capability checks, MFA-ready step-up, session revocation incl. on deactivation, elevated-action confirmation, audit, CSRF/session protections
  consistent with current auth, no plaintext secrets, rate limits on sensitive admin actions, secure uploads, input validation, anti-IDOR tests, never rely on hidden UI.

## 32. Open decisions
See ADMIN_ARCHITECTURE_DECISIONS.md: AD-01 (English-only admin), AD-02 (no break-glass), AD-03 (payment provider deferred), AD-04 (secret store interface + env/local adapter), AD-05 (DB-backed job abstraction),
AD-06 (`preparation_run` index), AD-07 (legal version/acceptance model), AD-08 (code-defined role presets). Owner confirmation requested on AD-03, AD-04, AD-05 and AD-07 before W10.4/W10.6/W10.9/W10.10 start.
