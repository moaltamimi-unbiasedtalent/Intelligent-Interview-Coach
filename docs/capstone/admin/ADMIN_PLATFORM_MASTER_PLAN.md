# P10B-W10 — Platform Administration, Support & Commercial Operations: Master Plan

**Status: PLANNING ONLY. Nothing in this document is implemented.** No roles, tables, routes or screens are
created by it. It is the approved scope and design brief for the phase; W10.0 (design) must be approved
before any broad implementation. Companion: `ADMIN_CAPABILITY_MATRIX.md`. Programme position:
`../capstone_phase_plan.md` (master roadmap).

## 1. Purpose and end state

Build the Ask4Mo **operational control plane** so authorized platform operators can run, configure,
monitor, support and govern the product **without routinely** editing source code, manually editing database
rows, opening server shells, retrieving plaintext secrets, or bypassing privacy controls.

The Admin Portal supports seven verbs: **CONTROL · MONITOR · CONFIGURE · SUPPORT · REPORT · GOVERN ·
TROUBLESHOOT.**

### The core principle (non-negotiable)

> **PLATFORM ADMIN != UNRESTRICTED PRIVATE-CANDIDATE-DATA SUPERUSER.**

Every admin function respects authorization, data minimization, audit, owner scoping, privacy and *explicit,
governed* access. This extends the existing P6.5 rule (admin is an operations surface: metadata only, no "view
as user", no private-data search, owner-scoped repositories stay owner-scoped, privileged changes audited).

## 2. Current baseline (verified in code at `main` d6c3493)

What exists today is a **bounded P6.5 operations console**, not this phase:
- One page, `frontend/app/admin/page.tsx` -> `AdminConsole`, English-only ops UI; excluded from candidate
  localization by design.
- 12 routes under `src/api/routes/admin.py`, router-level `require_platform_admin`: `GET /home`, `/users`,
  `POST /users/{id}/role|tier|status` (audited, self-lockout guards), `GET /workspaces` (metadata), `GET
  /privacy-requests`, `GET /feedback`, `GET/POST /pause`, `GET /providers` (metadata), `GET /audit`.
- Admin-gated: reviewer/KB diagnostics (`/reviewer/*`, `/knowledge/diagnostics`), `/evaluation/*`, Prompt Lab.
- Platform roles `USER`/`PLATFORM_ADMIN` on `users.platform_role` (admin bootstrapped by an audited script, no
  self-promotion); tiers are the hard-coded constants `basic`/`premium` with a code-defined capability set
  (`capabilities_for(tier)`), no billing (`BILLING_ENABLED=false`).
- Audit log exists (bounded, no secrets); pause switches and per-user/global cost limits exist.
It lacks: a shell/navigation, health/version dashboard, support tooling, data-driven plans/entitlements,
billing, integration/secret administration, model lifecycle, KB administration UI, job visibility, GDPR
operations UI, feature flags, reporting, incident management and break-glass.

## 3. Architectural boundaries (apply to every W10 wave)

1. **Private-data boundary.** Admins never automatically see CVs, private answers, Prepare/Mo chats, memory
   content, private documents, or interview reports. Aggregates and metadata only. If privileged support access
   is ever needed it is a **separate governed break-glass flow**: explicit reason, time-boxed, scope-limited,
   second-approver where appropriate, fully audited, visible to the data owner where policy allows. Not built in
   W10 unless W10.0 designs and the owner approves it.
2. **Authorization = capabilities, not a single "admin" bit.** Define fine-grained capabilities (e.g.
   `support.ticket.reply`, `billing.plan.edit`, `kb.source.approve`, `ai.model.activate`, `privacy.deletion.execute`)
   granted to roles; server-side enforcement on every route; candidate-denied tests; no frontend-only hiding.
3. **Separation of duties** for sensitive changes (price change, model activation, source production-enable,
   deletion execution, role elevation, break-glass): initiator != approver where the owner decides it is required.
4. **Audit everything privileged**: immutable (append-only), who/what/when/before/after (never secrets or
   private content), request-ID linked, exportable. Audit completeness is a qualification gate.
5. **Secrets.** Plaintext is never shown after save; rotate/disable/test-connection only; stored behind a
   secret-management boundary (interface + adapter); generic config never stores raw secrets; secrets never
   appear in logs, audit, reports or exports.
6. **Evaluation controls cannot be bypassed.** A model/prompt/profile moves Draft -> Validate -> Evaluate ->
   Approve -> Activate; an admin cannot activate an unevaluated model; no autonomous self-modification (existing
   invariant).
7. **Knowledge governance cannot be bypassed.** Manual source flow is Upload -> Safety validation -> Parse ->
   Classification -> Provenance/licence review -> Preview -> Approval -> Index. **Never upload -> immediate
   production RAG.** Official sources keep authority levels; Russian/other generated aliases never carry
   "official ESCO/taxonomy" provenance.
8. **Mocks are honest.** Where a live integration is disproportionate (payments, refunds, secret vault, pager,
   queue infra, deployment controls) a production-ready *interface + mock adapter* is acceptable, and the UI/docs
   must label it as a mock/sandbox, never as live.
9. **Owner scoping preserved.** Admin features read through governed services; owner-scoped repositories are not
   widened; workspace sharing stays VIEW-only grants.
10. **Locale.** Admin remains an English operations surface unless W10.0 decides otherwise; any *candidate-facing*
    string W10 adds (e.g. "Contact support", plan names on pricing, legal-version prompts) is localized in all 8
    locales and passes the hardcoded-English guard. The slogan `Ask More. Be More.` stays untranslated.

## 4. Information architecture (target `/admin`, subject to W10.0)

Command Center · Users & Access · Workspaces · Support (tickets) · Plans & Entitlements · Billing ·
Integrations · AI & Models · Knowledge & RAG · Jobs & Queues · Privacy & Legal (GDPR) · Feature Flags &
Settings · Reporting · Security, Audit & Incidents · Release & Environment.

## 5. Waves

Complexity: S/M/L/XL (relative; no hour estimates). Priority: **Critical** = Capstone-critical, **Desirable** =
Capstone-desirable, **Post** = post-Capstone acceptable. Dependencies are within W10 unless stated.

| Wave | Title | Key deliverables | Depends on | Cx | Priority |
|---|---|---|---|---|---|
| **W10.0** | Admin architecture & control-plane design | capability inventory; target IA; bounded contexts; authorization/capability model; support/admin role model; private-data boundaries; audit-event design; operational threat model; secret boundary; billing + provider abstractions; KB-admin architecture; support/ticket domain model; implementation sequence; acceptance gates. **Design gate: no broad implementation before approval.** | W9.13 | M | Critical |
| **W10.1** | Admin shell & Command Center | `/admin` shell + navigation; dashboard; platform health; alerts; environment/version (Git SHA, frontend/backend version, DB migration version); provider health; recent incidents and failed jobs; release/evaluator status; audit-log foundation | W10.0 | L | Critical |
| **W10.2** | Users, access & workspaces | search/filter users; safe metadata; suspend/reactivate; revoke sessions / force logout; onboarding status; plan; workspace membership; governed access; consent/legal-version status; ticket history. **No** CV/answers/chats/memory/documents/reports exposure | W10.1 | L | Critical |
| **W10.3** | Support & ticketing | candidate "Contact support / Report a problem" (localized); admin queue, categories, priority, assignment, SLA, request-ID + account linkage, attachments, internal notes, customer-visible replies, status history, incident linkage, reopen/resolve/close. Statuses: New -> Triaged -> In Progress -> Waiting for Customer -> Resolved -> Closed. Categories: account/login, interview, Opportunity, document upload, AI response, billing, privacy, accessibility, technical, data, other | W10.1, W10.2 | XL | Critical |
| **W10.4** | Plans, subscriptions & entitlements | create/edit/archive plans; public/private/internal visibility; monthly/yearly; currency/price; trial; feature entitlements; usage limits (interviews, documents, Opportunities, voice, Career Intelligence, workspace/team); support tier; retention policy where appropriate. Target: `SubscriptionPlan -> Entitlements -> Usage Limits -> Billing Price -> User/Workspace Subscription`; **no scattered `if premium`** | W10.1, W10.2 | L | Critical |
| **W10.5** | Billing & payment administration | subscriptions, invoices, payment state, failed payments, cancellations, grace periods, refunds (where supported), complimentary/internal access, coupons/promotions, VAT/tax state, billing history; **payment-provider abstraction**; no raw card data; production-ready interface + mock adapter acceptable, labelled as mock | W10.4 | XL | Desirable (mock-adapter acceptable) |
| **W10.6** | Integrations & API connections | AI providers, email, OCR, storage, STT/TTS/realtime, Career Intelligence providers, external APIs: configured/enabled, environment, last success/failure, health, latency, capability, rate-limit status, credential last-rotated; secrets rotate/disable/test via the secret boundary | W10.1 | L | Critical |
| **W10.7** | AI & model administration | approved providers/models/profiles; task->model mapping; fallback mapping; availability; timeouts; token policy; cost limits; routing. Lifecycle Draft -> Validate -> Evaluate -> Approve -> Activate; cannot bypass evaluation | W10.6, existing `src/llm/policy.py` | L | Desirable |
| **W10.8** | Knowledge base & RAG administration | source registry, authority, licence, production-allowed, language, geography, classification, structured/vector status, counts, freshness, ingestion, indexing, provenance, retrieval diagnostics, re-index, governed refresh, governed manual upload (see §3.7), enable/disable. **Operational UI for later P10C sources; does not replace P10C architecture** | W10.6; existing knowledge governance | XL | Critical |
| **W10.9** | Jobs, queues & operational diagnostics | document processing, OCR, email, ingestion, indexing, exports, deletion jobs, evaluations, billing webhooks, source refresh; statuses pending/running/completed/failed/retrying/dead-letter; **safe retry/cancel only**; advanced queue infrastructure may be mocked | W10.1 | L | Desirable |
| **W10.10** | GDPR, privacy & legal administration | access/export/deletion requests, correction workflows where supported, retention status, consent history, Terms/Privacy/AI-Transparency versions, effective dates, re-acceptance, translation-review status, deletion execution status, privacy incidents, sharing/revocation visibility; never silently grants private-content access | W9.8, W10.1, W10.2 | L | Critical |
| **W10.11** | Feature flags & safe system configuration | global/environment/account/plan flags where justified; safe settings; usage limits; support SLA settings; approved model defaults; availability. No raw secrets in generic config | W10.1 | M | Desirable |
| **W10.12** | Reporting, analytics & AI economics | Product (registrations, activation, onboarding, Opportunities, Prepare/Practice usage, completion, returning); Quality (evaluations, retrieval success, abstention, failures, feedback); Operations (availability, latency, provider failures, KB health, ticket metrics); Commercial (subscriptions, up/downgrades, churn, MRR/ARR, failed payments); AI economics (tokens, cost per user/session/model, expensive workflows). Aggregates only | W10.1 (+W10.4/5 for commercial) | L | Critical (essential reporting); economics Desirable |
| **W10.13** | Security, audit & incident management | immutable admin audit trail; sensitive-action history; auth/security events; incident management (affected service, assignment, root cause, resolution, linked tickets). Audit examples: account suspended, role changed, plan/price changed, source enabled, credential rotated, retention changed, deletion initiated, flag changed | W10.1 (foundation), all | L | Critical |
| **W10.14** | Admin qualification | unauthorized candidate denied; capability boundaries; admin not a private-data superuser; audit completeness; ticketing; plans/subscriptions; provider configuration; KB administration; GDPR workflows; billing state; system health; reporting; incident handling; secret non-disclosure; owner scoping preserved; 8-locale coverage where defined | W10.1-W10.13 | L | Critical |

## 6. Capstone must-have vs mock/adapter-acceptable

**CAPSTONE MUST-HAVE (full implementation):** admin shell; health dashboard; users/access; session revocation;
workspace administration; support/ticketing; subscription-plan creation/editing; entitlement management;
integration/provider administration; knowledge/RAG administration; GDPR operational workflows; audit trail;
essential reporting; platform health; incident visibility.

**PRODUCTION-READY MOCK/ADAPTER ACCEPTABLE (never represented as live):** payment provider; refunds; secret
vault; pager/incident integration; advanced queue infrastructure; deployment controls.

## 7. Critical path and parallelism

`W9.13 -> W10.0 -> W10.1 -> {W10.2 -> W10.4} -> {W10.3, W10.6 -> W10.8, W10.10, W10.12, W10.13} -> W10.14 -> W11`.
W10.1 delivers the audit foundation everything else depends on. After W10.1/W10.2, W10.6, W10.9 and W10.11 are
largely independent. W10.5 (billing) follows W10.4 and may ship with the mock adapter. W10.7 follows W10.6.
W10.10 depends on the candidate-side W9.8 Data & Privacy Center. Largest items: W10.3 (support) and W10.8 (KB
admin), both XL.

## 8. Explicitly out of scope for W10

Enterprise SSO/SCIM/HRIS; plugin marketplace; autonomous prompt/code/model changes; "view as user"/user
impersonation; storing or displaying raw card data; unrestricted crawling or job-board scraping; replacing the
P10C occupation/compensation architecture; changing candidate-facing product behaviour except the support entry
point and legal-version prompts.

## 9. Relationship to other phases

- **W9.8** builds the *candidate* Data & Privacy Center; **W10.10** is the *operator* side of the same workflows.
- **P10C** (Global Career Intelligence & Compensation Overhaul) stays separate; W10.8 later provides the UI to
  operate P10C sources. W10 does not replace P10C.
- **RC-P10-003** is created only after W11 (integrated candidate + admin requalification); **Pilot 2** resumes
  only against that RC (see the master roadmap).

## 10. Open owner decisions (needed at or before W10.0)

Payment provider (or sandbox-only); secret store (managed vault vs encrypted-at-rest adapter); support intake
channels (in-app only vs email ingestion); SLA values and business hours; whether any break-glass flow is built;
separation-of-duties list; which reports are Capstone-mandatory; admin locale policy; hosting/environment for
the control plane.
