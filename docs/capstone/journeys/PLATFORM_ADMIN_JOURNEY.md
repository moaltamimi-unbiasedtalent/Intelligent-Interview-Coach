# Ask4Mo: Canonical Platform Admin Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `396bf173b11982fbb2e98af01c388840ee2b11ca` (2026-10-13). **Knowledge section updated for W12.4A** (see [../knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md](../knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md)).

This document describes what the Platform Admin experience does **today**. It was written from the current code (routes, services, frontend destinations and deterministic tests). Historical W10.x documents remain historical evidence and were not used as authority where the code differs. Anything that is not built yet is labelled **PLANNED W12.4** (or **PLANNED W12.5**) and must not be read as current functionality. Status labels used throughout: **CURRENT**, **CURRENT - LIMITED**, **CURRENT - MOCK**, **CURRENT - ENVIRONMENT MANAGED**, **CURRENT - UNVALIDATED LIVE**, **PLANNED W12.4**.

For the candidate side of the product see [CANDIDATE_JOURNEY.md](CANDIDATE_JOURNEY.md). Specialist Admin journeys are not part of this document (section 29).

## 1. Who the Platform Admin is
The Platform Admin is the Ask4Mo **platform owner / orchestrator**. It holds **all 43 canonical control-plane permissions** (AD-W12-01, implemented in W12.1; W10.14 historically qualified the role at 28 of 43, and that record is unchanged). It is one code-defined role preset, resolved on the server from the account's stored role. It is not a custom role, and no browser state decides authority.

## 2. Owner / orchestrator responsibility
The Platform Admin operates the platform: it manages users and access, reviews platform and provider state, administers plans and (mock) commercial controls, governs AI model configuration, governs platform knowledge, runs privacy and legal workflows, watches security and audit state, sets the durable pause and restriction-only flags, and can orchestrate work across every domain that specialist roles also cover.

**It is not a candidate-content superuser.** This distinction is central and is repeated in section 28.

## 3. Admin architecture and safety boundaries
- **Permission-gated routes only.** Every Admin route declares an explicit `require_permission(...)`; there is no role-name check anywhere and a CI invariant fails on an ungated Admin route. The permission strings are the authority; the role is only a preset.
- **43 permissions, none for candidate content.** No permission reads a CV, document, answer, Mo conversation, memory, evidence or report content. There is **no break-glass**, **no impersonation** and **no "view as user"**.
- **Default deny.** An unknown or missing role, and the candidate role, resolve to no permissions.
- **Governance is not bypassed by holding every permission:** step-up where required, a different approver where required, expected-revision (concurrency) checks, and mandatory same-transaction audit all still apply to the owner.
- **Authorization is not capability, entitlement or billing.** A permission means the Admin may attempt an action; whether the platform can technically perform it is a separate question (section 24).
- **Responses are allowlist schemas** with no candidate content, no secrets and no raw exception text.
- The Admin interface is English-only by design.

## 4. High-level journey map
```
Sign in -> Command Center -> inspect platform state
   -> go to an operational domain -> review state
   -> perform a permitted action
        -> step-up where required (today: role changes)
        -> a different approver where required (role change, price change, refund, AI activation)
   -> audit trail written -> monitor the result

Supporting flows: Security | Audit | Provider status | Jobs | Reports | Configuration | Review / Diagnostics
```
Not every action needs a second person. Only the flows in section 23 do, and most actions need neither step-up nor a second approver.

## 5. Sign-in and step-up
- **Sign-in:** an ordinary authenticated session (server-side session cookie). `GET /auth/me` returns the platform role and the resolved `admin_permissions`; the frontend only reflects them to show or hide navigation. Every API call is authorised again by the server.
- **Step-up (password re-authentication):** `POST /admin/step-up` re-verifies the Admin's password and elevates the **current server-side session** for **5 minutes**. It is bound to that session, is not multi-factor authentication, is rate limited (5 attempts per 5 minutes) and fails closed for accounts with no password credential (for example an OIDC-only account).
- **Where step-up is currently required:** **only** on **requesting a platform role change** and **approving a platform role change**. Other high-risk actions (price changes, refunds, AI activation, knowledge approval, legal publication, deactivation, credential replacement) do **not** currently require a fresh password. They are protected by permissions, confirmations, audit and, for some, a second approver. See finding A-04.
- **The owner is not exempt:** holding all 43 permissions does not skip step-up where it is required.

## 6. Command Center / Overview (`/admin`)
- **Purpose:** orientation and operational state.
- **Shows (CURRENT):** release (version, git revision, build time, environment; "unknown" when build details were not injected), database migration state (repository head versus database revision), runtime (database reachable, provider health, rate-limit mode, platform running or paused, durable pause state and feature-flag overrides), account and workspace counts, and one counts-only panel per domain the Admin may see: integrations, AI and models, billing (labelled mock), knowledge base, jobs and workers, plans, support, privacy requests and security. Diagnostics links lead to Review / Diagnostics.
- **Read only.** It carries the boundary line "Operational metadata only. No candidate-private content is accessible here."
- **Configured is not healthy, and healthy is not live-validated:** the panels say "Health is shown only after a manual test; nothing is assumed healthy", counts carry no revenue figure, and queue size never implies a worker is running.

## 7. Users and access (`/admin/users`, `/admin/users/{id}`)
- **CURRENT.** Search and filter accounts; open an account to see **metadata only**: email, id, status, legacy tier (display only), onboarding state, interface language, verification, created and updated times, platform role and its assignable presets, plan and plan history, active sessions, workspace memberships and Admin actions on the account.
- **Actions:** deactivate or reactivate (confirmation, optional reason, audited); force logout by revoking all sessions (confirmation, audited); change a user's plan; **request a platform role change** (reason required, password step-up, a **different** Admin must approve, section 23).
- **Protections:** deactivation revokes live sessions in the same transaction and a non-active account is rejected at request time; self-deactivation and removing the last active `platform_admin` are refused; roles are the code-defined presets only; there is no direct role-edit route.
- **Not accessible:** CV, raw documents, interview answers, Mo conversations, Story Bank or private evidence, private preparation content. The Admin sees that an account exists and how it is configured, not what the candidate wrote.

## 8. Workspaces (`/admin/workspaces`, `/admin/workspaces/{id}`)
- **CURRENT.** Workspace metadata: name, status, owner, members and roles, and share counts; management actions for members and the workspace plan.
- **Boundary:** this is control-plane metadata. Workspace membership, including the Admin's own, does not give permission to browse any candidate's preparation content; shared content is never shown here. A Workspace is a collaboration construct and is separate from a candidate's private Opportunity.

## 9. Support (`/admin/support`, `/admin/support/{ref}`)
- **CURRENT.** A ticket queue with filters (status, category, priority, assignee), ticket detail, and actions: **assign**, **change status**, **change priority**, **reply to the candidate** (customer-visible) and add an **internal note** (Admin-only).
- **Boundary:** the Support domain exposes the text the candidate **intentionally sent to Support**, with safe account metadata. It does not grant access to unrelated candidate-private content: the ticket page states that CVs, documents, interview answers and Mo chats are not available. **Internal notes are never shown to the candidate**, are stored in a separate Admin-only table and are excluded from the candidate's data export.
- **Limitations:** attachments are not implemented; replies are not emailed (the candidate sees them on the Support page); there is no SLA or response-time target.

## 10. Plans and subscriptions (`/admin/plans`, `/admin/plans/{id}`)
- **CURRENT.** Plan versions and their entitlements; create the next draft of a plan, edit a draft's entitlements, activate (an active version is immutable and assignable) or retire (subscribers keep it); assign a plan to an account or workspace from its detail page.
- **Invariants:** entitlement is not billing. A plan decides product access only; a subscription assignment does not prove payment, and the Plans page states there are no prices, payments or invoices. Only existing real plans exist (Basic, and Premium as a preview); there is no invented price or quota. Access is decided only by the entitlement service, never by comparing a tier.
- **Governance:** plan activation has no distinct-approver rule today (it needs the plan-management permission and is audited).

## 11. Billing (`/admin/billing`)
**CURRENT - MOCK. MOCK BILLING, NOT LIVE BILLING.**
- **What exists:** a `BillingProvider` abstraction with **one** adapter, `MockBillingAdapter`, enabled only in development or test environments. The page shows a MOCK banner, mock invoices, mock payments, mock customers and subscriptions (informational), **commercial terms** per plan version (versioned and immutable; "not configured" is not "free"), **price-change** requests and **refund** requests with approvals.
- **Governance:** a price change needs `platform.plans.price.change` and a refund needs `platform.billing.refund`; **a different active administrator must decide** (requester is not approver, no override, even for the owner). Refunds and event processing run as idempotent background jobs.
- **Boundary:** billing state never changes entitlement or access (price changes, failed payments, refunds and provider cancellation never alter a plan). Money is integer minor units with a currency; currencies are never combined. No price is seeded.
- **Not built (do not read as implemented):** real checkout, a live payment provider, real card processing, live invoices, live refunds, tax handling, live webhooks, production billing reconciliation, coupons and revenue or MRR reporting. Card and payment-method data is never handled by Ask4Mo. **PLANNED W12.4D.**

## 12. Integrations and provider status (`/admin/integrations`, `/admin/integrations/{code}`, `/admin/providers`)
- **CURRENT - ENVIRONMENT MANAGED.** The integration set is **code-defined** (nine integrations: OpenRouter, OpenAI embeddings (optional), realtime voice, Adzuna, Google sign-in, Brevo email, Redis rate limiting, Langfuse observability and ClamAV malware scanning); there is no custom integration and no admin-entered URL.
- **Five separate questions** are never collapsed: **supported** versus **configured** versus **enabled / runtime active** versus **health tested** versus **live validated**. The list shows configuration, runtime and health as separate columns; only an explicit manual **Test connection** (available for OpenRouter and ClamAV, bounded, one call, no polling) can show a successful health result, and everything else reads "Not tested".
- **Provider status** (`/admin/providers`) is a subset: booleans and fixed labels for email, Google sign-in, OpenRouter, Adzuna and Langfuse plus document OCR, speech and realtime state. It contacts no provider and says "configured does not mean healthy".
- **SecretStore:** the active store is the **environment adapter, which is read-only**. Credentials are managed outside Ask4Mo (in the deployment environment) and are never returned, displayed, masked or logged. The Admin therefore **can inspect** integration state but **cannot change a provider credential from the UI**. The credential-replacement route exists and the owner holds the rotation permission, but a write returns a read-only conflict because no writable secure adapter exists; the interface offers no rotation control. **PLANNED W12.4B.**

## 13. Email (current truth)
- **Architecture exists:** an `EmailSender` abstraction with a console adapter (development default), an in-memory adapter (tests) and a **Brevo transactional adapter**. It is selected by environment settings (`EMAIL_PROVIDER`, `BREVO_API_KEY`, `EMAIL_SENDER`); with Brevo selected but credentials missing it falls back to console and logs a warning.
- **Used today for:** email verification, password reset and workspace invitations, when Brevo is configured. Support replies are never emailed.
- **Admin visibility:** the Integrations page lists "Brevo (transactional email)" and Provider status shows whether email is configured. There is **no test-email action and no health probe**, no sender-domain configuration and no email diagnostics in Admin.
- **Status: CURRENT - ENVIRONMENT MANAGED / UNVALIDATED LIVE.** The adapter is implemented; live delivery has **not** been validated, and the operational configuration and validation are incomplete. Email is not unimplemented. The closure is **PLANNED W12.4C**.

## 14. AI and models (`/admin/ai`, `/admin/ai/{id}`)
- **CURRENT - LIMITED.** A governed lifecycle over a code-defined approved model catalogue: **draft, validate, evaluate, request approval, a distinct approver approves, activate, roll back or revert to code defaults**. A configuration can only choose which approved catalogue entry serves the Fast, Balanced and Advanced profiles and set bounded numbers; capability, minimum tier, fallbacks, prompts and secrets stay in code. With nothing active, behaviour is identical to the code defaults (shown as "Code defaults").
- **Governance:** a configuration is **never active without a passed, hash-bound evaluation and a different approver** (not the requester and not the author); the activation environment is the server's own and production needs a prior staging activation of the same configuration; the owner does not bypass this.
- **Honest limits:** evaluations are **deterministic contract checks** run as background jobs and make no provider call; **a passing deterministic evaluation is not proof of live model quality**. Evaluation needs a worker. Live model quality is not measured here.

## 15. Knowledge (`/admin/knowledge`, `/admin/knowledge/{id}`)
**CURRENT - LIMITED (PARTIAL). W12.4A added readiness, an active-knowledge inventory and a retrieval-only test, and fixed two root causes (below).**
- **Governed lifecycle:** register a source (title, publisher, https reference that is never fetched, language, authority level, licence class, provenance note), upload a file (PDF, TXT or Markdown), **scan**, **parse** (bounded preview), **human review**, **approve**, **index**, **activate**, and later retire or add a new version. Parse, index and removal are **background jobs** (payload is only the version id). Versions are immutable; one active version per source.
- **Authority levels:** 1 = official / statistical; 2 = public / professional framework; 3 = reputable industry. Knowledge languages are the seven knowledge-base languages; Russian is not a knowledge-base language and is not an official ESCO language. A licence class of "unclear" or "restricted", missing provenance or a failed or missing malware scan blocks approval.
- **Invariant:** unapproved knowledge never reaches candidate retrieval. Parsed is not approved, approved is not indexed, indexed is not active; retrieval trusts only the SQL active set and writes go only to the separate `governed_knowledge` collection, never the legacy corpus.
- **Readiness (W12.4A, CURRENT):** the Knowledge page opens with a **Knowledge readiness** section: an overall state (Ready, No active sources, Indexing worker unavailable, Indexing in progress, Index build failed, Retrieval store unavailable, Governed collection missing, Embedding provider unavailable, Configuration problem, Degraded), whether candidate retrieval is ready, active and indexed counts, pending and failed indexing jobs, the worker state (from heartbeats only), embedder and collection state, and the last failure category. Ready is shown only when an active, indexed source is physically present in the store candidate retrieval reads; configuration, a source or a queued job alone is never shown as healthy. An **Active knowledge** inventory lists what is active (metadata only) and a **Test retrieval** panel runs a retrieval-only query through the production boundary (no model, no answer, no overrides). A source waiting on a job says plainly when no worker can progress it.
- **Limits that still exist:** no complete snapshot or rollback model; parse and index depend on a separate worker process; parts of the Knowledge capability remain PARTIAL in the Admin capability matrix; the retrieval test shows what retrieval returns and is not a relevance judgement (the pipeline has no relevance cutoff for unfiltered queries).
- **Owner-reported issue (W12.4A):** the Knowledge Base was reported inaccessible or not working in the normal environment. Two root causes were found and fixed in code: (1) every default store path was relative to the process working directory, so an app or worker launched from any other folder saw an empty knowledge base (now anchored to the repository data root, overridable with `COPILOT_DATA_DIR`); (2) Mo's agent was not wired to Admin-governed knowledge. **Operator verification (W12.4A-OPS):** in the developer environment the curated knowledge base (14,087 chunks) works from any launch directory, the developer database was brought to the current schema, the worker was run, and a synthetic governed source went through the whole lifecycle (index, activate, retrieve, retire). The governed corpus legitimately has **no active operator-managed sources** until real sources are onboarded, and a real malware scanner must be configured for governed uploads. One residual defect (R-1) remains: readiness can read Degraded after a recovered failed job. Knowledge is still not described as fully production-operational.

## 16. Jobs and operational diagnostics (`/admin/jobs`, `/admin/jobs/{id}`)
- **CURRENT - LIMITED.** The queue shows counts (queued, running, failed, stale leases, waiting to retry), oldest ready job, workers seen recently and last worker report; a filterable job list; job detail with a safe summary and bounded failure category (never an exception dump or payload); actions: **queue a no-op diagnostic job**, **retry** a failed job and **cancel** a queued job. Running jobs are not cancellable.
- **Job types are code-defined:** knowledge parse, index and index removal; privacy account deletion and preparation-run indexing; billing event processing and mock refund; AI configuration evaluation. There is no arbitrary or shell job.
- **A worker is a separate process** (`python -m src.jobs.worker`); the API never executes jobs. **Queuing a job does not mean a worker is running**: the page says a job only moves when a worker has reported recently, and shows "Never" when none has. There is no dead-letter state.

## 17. Privacy (`/admin/privacy`, `/admin/privacy/{ref}`)
- **CURRENT.** A durable privacy-request queue (submitted by candidates, or recorded from another channel), assignee and status workflow (submitted, acknowledged, in progress, waiting for the candidate, completed, closed, not accepted) with a result category, and **account deletion orchestration**: an Admin-triggered deletion runs the **same** account-deletion service as the candidate's own deletion as a background job (there is no second deletion engine and no Admin export of candidate data). A preparation-run index with a bounded backfill job supports completing deletions.
- **Terminology:** *delete* removes data; *archive* hides but keeps; *revoke* ends a share; *unlink* separates records without deleting them; *anonymise* removes identity from records that must be kept (for example security records). The page states it is not a statement of legal compliance and that it never shows a candidate's documents, answers, chats or memories.

## 18. Legal (`/admin/legal`)
- **CURRENT.** Versions of the Terms, Privacy notice and AI transparency page: register a draft version (label, page reference, optional SHA-256 content hash, effective date), **publish** a version (it becomes current, the previous one retires, a published version can never be edited), and see recorded-acceptance counts.
- **Boundaries:** a published version is immutable; exactly one is current; acceptance records carry a user, a version, a time and a source, and **no IP or device**; **acceptance is not consent** (it is separate from privacy choices) and re-acceptance is not enforced; acceptance is never back-filled for earlier accounts. The page says it is not a compliance measure. No statutory retention period and no GDPR compliance or certification is claimed.

## 19. Reports (`/admin/reports`)
- **CURRENT.** Aggregate **product, quality, operations, AI economics** and **mock commercial** reporting over a chosen period. **Read-only.**
- **Invariants:** aggregates only, with no candidate content, identifiers, per-user drilldown or raw events; candidate groups below the engineering floor of five are **suppressed** (this is not anonymisation, and rates also need a non-small numerator and complement); **unknown is never shown as zero**; unknown tokens or cost are shown as unknown (cost is "known cost, partial coverage"), never as $0; **mock billing is not live revenue**; currencies are never combined; no revenue, MRR or churn is invented. Commercial reporting needs its own permission.

## 20. Security and incidents (`/admin/security`)
- **CURRENT.** Five tabs: **Security events** (a typed projection of audit events with category, severity and period), **Audit** (history with filters and a bounded CSV export that needs a reason and period), **Incidents** (create, update, change status, link support tickets), **Alerts** (in-app only, code-defined categories, acknowledge and resolve, no external paging) and **Role approvals** (section 23). Incident and alert free text is never copied into audit context.
- **Not present:** break-glass, impersonation, view-as, private-candidate-content inspection, email, IP or session-token display.

## 21. Audit (`/admin/audit`)
- **CURRENT - LIMITED.** A read-only list of privileged actions and denied access with request ids. Audit is **mandatory for privileged mutations** (written in the same transaction as the change; an audit failure rolls the change back), and the audit log is **append-only at the database** (triggers reject deletion and updates, other than the actor being anonymised after account deletion). The PostgreSQL trigger statements are unit-checked but not executed against a live PostgreSQL.
- **UX note:** the top-level Audit page is a plain list; filtering and export are in the Security page's Audit tab (W12.2 finding F-06, unresolved).

## 22. Configuration and feature flags (`/admin/configuration`, `/admin/flags`)
- **CURRENT - LIMITED, intentionally bounded.**
- **Configuration is the durable platform pause:** five capabilities can be paused (realtime voice, external market research, document OCR, Mo agent runs, open registration). Pausing refuses **new** candidate activity of that kind with a fixed message; saved data, privacy and account controls, legal pages, Admin recovery and the job worker are not paused. Each change needs a reason, an expected revision and a confirmation and is audited; the environment is the server's own.
- **Feature flags** are **code-defined** (two today: external research and company website research), environment-aware, with durable override states (inherit, enabled, disabled). A flag can only **restrict** availability: it never grants permission, entitlement, billing or AI changes.
- **There is no generic environment-variable, secret, database or JSON editor, and none is planned.** Deployment settings such as the coach switch, live interview, realtime voice, Google sign-in, billing provider and authentication settings are listed as "not configurable here".
- The owner has asked that genuinely operational provider and configuration controls become manageable through Admin before project closure. That is a **PLANNED W12.4** requirement (W12.4F), subject to the same exclusions: no arbitrary environment variables, commands, filesystem paths, secret values or unrestricted platform internals.

## 23. High-risk approval workflows
| Workflow | Step-up (fresh password) | Distinct approver | Notes |
|---|---|---|---|
| Platform role change | Yes, to request and to approve | Yes: requester, approver and target must be three different parties for the approval (neither the requester nor the target may approve); the target role must not be stale; the last active `platform_admin` is protected; request, approval, role update and audit are one transaction | There is no direct role-edit route |
| Billing price change (mock) | No | Yes: a different administrator must decide; no override | Terms are immutable versions |
| Billing refund (mock) | No | Yes: a different administrator must decide; no override | Executes as a background job; no real money moves |
| AI configuration activation | No | Yes: approver is not the requester and not the author; evaluation must have passed; production needs prior staging | Rollback or revert needs no new approval |
| Knowledge approval, legal publication, plan activation, privacy handling, pause and flag changes, credential replacement | No | **No distinct-actor rule today** | Protected by permission, confirmation, reason where stated, expected revision and audit |

The owner holds every permission above and is still bound by these rules: one `platform_admin` account can request but never approve its own request, so two distinct administrators are needed.

## 24. Technical capability versus authorization
Authorization (a permission), technical capability (can the platform do it), entitlement and billing are separate.
- Secret rotation: authorised for the owner; technically unavailable (read-only store).
- Refund and commercial reporting: authorised; they operate on **mock** billing and never move money or report live revenue.
- Knowledge management: authorised; unapproved knowledge still cannot be indexed or activated, and indexing needs a worker.
- Configuration management: authorised for the pause only; there is no generic settings editor.
- Privacy execution: authorised; it uses the existing deletion service and shows no content.
- Job management: authorised for code-defined job types only.

## 25. Current platform-operability matrix
| Domain | Current status | Admin can inspect? | Admin can manage? | Production provider / config ready? | Known gap | Planned closure |
|---|---|---|---|---|---|---|
| Users and access | OPERATIONAL | Yes (metadata) | Yes (status, sessions, plan, governed role change) | n/a | UX items F-07, F-12, F-16 | W12.5 |
| Workspaces | OPERATIONAL | Yes (metadata) | Yes | n/a | none recorded | n/a |
| Support | OPERATIONAL WITH LIMITATION | Yes | Yes | No email notifications | No attachments, email or SLA | later, not scheduled |
| Plans and subscriptions | OPERATIONAL | Yes | Yes | n/a | No distinct approver on activation | review in W12.4F |
| Billing | MOCK | Yes (mock) | Yes (mock) | No live provider | No checkout, live payments, webhooks, tax or reconciliation; page forms off screen (F-05) | W12.4D; W12.5 |
| Email | ENVIRONMENT-MANAGED / UNVALIDATED LIVE | Status only | No | Adapter exists; live delivery not validated | No test email, health check or sender configuration in Admin | W12.4C |
| Integrations and secrets | ENVIRONMENT-MANAGED | Yes | Test connection only (OpenRouter, ClamAV) | Read-only SecretStore | No writable secure adapter; narrow-width overflow (F-04) | W12.4B; W12.5 |
| Provider status | STATUS / PARTIAL | Configuration only | No | Health not tested | Overlaps Integrations (F-17) | W12.4F |
| AI and models | OPERATIONAL WITH LIMITATION | Yes | Yes (governed) | Deterministic checks only | No live-quality evidence | P10E |
| Knowledge | PARTIAL (readiness, inventory and retrieval test added in W12.4A) | Yes (governance state, readiness, active corpus) | Yes (lifecycle) | Needs a running worker; operator action pending in the developer environment | No snapshots or rollback; retrieval test is not a relevance judgement | W12.4A done; later reviews in W12.4F |
| Jobs | OPERATIONAL WITH LIMITATION | Yes | Retry, cancel, diagnostic | Worker is a separate process | No dead-letter state; worker presence not guaranteed | W12.4A, W12.4F |
| Privacy | OPERATIONAL WITH LIMITATION | Yes (workflow only) | Yes | n/a | Not a compliance statement; backups not erased instantly | later |
| Legal | OPERATIONAL | Yes | Yes | n/a | Acceptance is not consent; no re-acceptance enforcement | later |
| Reports | OPERATIONAL | Yes (aggregate) | n/a (read only) | n/a | Small-environment suppression noise (F-09) | W12.5 |
| Security and incidents | OPERATIONAL WITH LIMITATION | Yes | Yes | In-app alerts only | No external paging; step-up only on role changes (A-04) | review before RC |
| Audit | OPERATIONAL WITH LIMITATION | Yes | Export | Append-only triggers not run on live PostgreSQL | Two audit surfaces (F-06) | W12.5 |
| Configuration and flags | OPERATIONAL WITH LIMITATION | Yes | Pause and two flags | Environment decides deployment settings | Bounded by design; owner wants operational controls | W12.4F |
| Review / Diagnostics | OPERATIONAL WITH LIMITATION | Yes | n/a (read only) | n/a | Outside the Admin shell (F-01) | W12.5 |
| Speech providers | ENVIRONMENT-MANAGED / UNVALIDATED LIVE | Status only | No | Browser speech by default; realtime not validated | Provider-backed speech not built | W12.4E |

## 26. Known limitations and accepted follow-ups
- Billing is mock only; email, Google sign-in, realtime voice, Redis distributed rate limiting and provider health are not live-validated; the SecretStore is read-only; Knowledge is partial with an undiagnosed owner-reported issue; no external paging; step-up is password re-authentication, not MFA; PostgreSQL audit-trigger execution is not run live; Support has no attachments, email or SLA; Russian remains an interface and Mo-conversation language only.
- The W12.2 Admin UX findings F-01 to F-17 (0 blocker, 0 high, 5 medium, 12 low) remain open and tracked; the owner accepted the experience with follow-ups, and this document does not resolve any of them. F-01 (Review / Diagnostics renders outside the Admin shell) remains unresolved.

### Operability findings recorded by this documentation wave (none fixed here)
| ID | Class | Finding |
|---|---|---|
| A-01 | OPERABILITY | Owner-reported Knowledge Base accessibility problem. **W12.4A: root causes found and fixed in code** (working-directory-relative store paths; agent not wired to governed knowledge). Residual operator action: register and activate a governed source and run the worker |
| A-02 | ADMIN-CONTROL | No writable secure SecretStore adapter; provider credentials cannot be configured or rotated from Admin (W12.4B) |
| A-03 | INTEGRATION | Brevo email adapter exists but live delivery is unvalidated and Admin has no sender configuration, test email or diagnostics (W12.4C) |
| A-04 | SECURITY | Step-up is required only for platform role changes; refunds, price changes, AI activation and other high-risk actions rely on permission, a second approver (where defined) and audit, with no fresh password |
| A-05 | ADMIN-CONTROL | **Addressed in W12.4A:** readiness, an active inventory, a retrieval-only test and a worker hint now exist on the Knowledge pages |
| A-06 | INTEGRATION | No live billing provider (W12.4D) |
| A-07 | INTEGRATION | Provider-backed speech is not built; speech is browser-based and realtime is unvalidated (W12.4E) |
| A-08 | ADMIN-CONTROL | Normal platform-operations settings beyond the pause and two flags are environment-only (W12.4F) |
| A-09 | KNOWN LIMITATION | Jobs have no dead-letter state |
| A-10 | DOCUMENTATION | The Admin capability matrix has no row for email |

## 27. Planned production-operability closure (PLANNED W12.4; not implemented)
W12.4 is **owner-approved** and is **not started**. Nothing below is current behaviour.
- **W12.4A, Knowledge Base Accessibility & Operations (implemented; see section 15):** reproduce the owner's Knowledge problem, diagnose the real root cause, verify the whole path (source, scan and parse, approve, index, worker, retrieval store, activation, candidate retrieval), restore an accessible candidate Knowledge path, add Admin readiness and retrieval-test capability, make failures visible, and make the active knowledge base understandable from Admin.
- **W12.4B, Secure Provider & Secret Administration:** move from the read-only environment SecretStore to a production-suitable writable secure adapter; Admin configures and rotates supported provider credentials; values stay write-only with no raw retrieval; audit and step-up; **no generic environment editor**.
- **W12.4C, Email & Identity Operations:** operationalise Brevo transactional email; an approved, Admin-configurable email provider architecture; sender identity and domain configuration; secure credentials; verification and password-reset email; a bounded test email and health check; diagnostics; production readiness; Google sign-in administration and live validation only where separately approved.
- **W12.4D, Live Billing Provider:** a real billing provider behind the `BillingProvider` abstraction (checkout, customer and subscription mapping, webhooks, invoices, payments, refunds, reconciliation, Admin configuration and status); billing stays separate from entitlement; card and payment data stays with the provider. The provider is not chosen here.
- **W12.4E, Governed Speech Providers:** owner-selected future providers: OpenAI Whisper (https://github.com/openai/whisper) as primary server-side speech-to-text and Kyutai Pocket TTS (https://github.com/kyutai-labs/pocket-tts) as primary server-side text-to-speech; Admin configuration; the seven-language speech boundary preserved and Russian excluded from speech; governed browser fallback; realtime voice remains separate; transient audio processing with no persistent candidate audio.
- **W12.4F, Admin Configuration Completeness:** audit every Admin destination and supported integration and classify each capability (operational, configured but unavailable, environment-managed, mock, read-only, partial, not built); provide governed Admin control for everything that genuinely belongs to normal platform operations, **without** exposing arbitrary environment variables, commands, filesystem paths, secret values or unrestricted internals. The goal is for Admin to function as a real operator control plane, not a set of status pages.
- **W12.5, Preferred Admin UX Corrections (after W12.4):** preferred findings F-01 (Review / Diagnostics outside the Admin shell), F-04 (Integrations narrow-width overflow) and F-05 (Billing form focus and off-screen forms); reassess F-03, F-06 and all low findings after W12.4 changes.

## 28. Platform Admin data-access boundary
| The Platform Admin **can** see | The Platform Admin **cannot** see, even with 43 / 43 |
|---|---|
| Account metadata (email, status, role, plan, sessions) | Candidate CVs |
| Workspace metadata and member roles | Raw candidate documents |
| Support ticket content the candidate intentionally sent to Support | Interview answer text |
| Provider and configuration status (never secret values) | Mo conversations |
| Audit metadata (actor, action, target, result, request id) | Story Bank and private evidence |
| Aggregate reporting (small cohorts suppressed) | Private candidate preparation memory |
| Knowledge governance metadata and platform knowledge text | Candidate report contents |
| Privacy-request workflow state | Anything through impersonation, view-as or break-glass (none exists) |

43 / 43 means all 43 **control-plane** permissions. It does not mean all candidate data.

## 29. Delegation to specialist Admin roles
Five code-defined, least-privilege roles are delegated operational roles and gained nothing from W12.1: **support_operator** (support queue), **billing_admin** (plans, subscriptions, billing, commercial reporting), **knowledge_admin** (governed knowledge, AI read, jobs read), **security_privacy_admin** (privacy, legal, security, incidents, audit) and **operations_admin** (jobs, integrations, configuration and flags, releases, reports, AI read). The Platform Admin can orchestrate across all of these domains; the specialist roles each see only their own. Their full journeys are documented separately: see the index [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md) and [SUPPORT_OPERATOR_JOURNEY.md](SUPPORT_OPERATOR_JOURNEY.md), [BILLING_ADMIN_JOURNEY.md](BILLING_ADMIN_JOURNEY.md), [KNOWLEDGE_ADMIN_JOURNEY.md](KNOWLEDGE_ADMIN_JOURNEY.md), [SECURITY_PRIVACY_ADMIN_JOURNEY.md](SECURITY_PRIVACY_ADMIN_JOURNEY.md) and [OPERATIONS_ADMIN_JOURNEY.md](OPERATIONS_ADMIN_JOURNEY.md).

## 30. Canonical route reference
### Top-level destinations (19)
| Destination | URL | Permission to see it (any of) |
|---|---|---|
| Overview | `/admin` | `platform.overview.read` |
| Users | `/admin/users` | `platform.users.read` |
| Workspaces | `/admin/workspaces` | `platform.workspaces.read` |
| Plans | `/admin/plans` | `platform.plans.read` |
| Support | `/admin/support` | `platform.support.read` |
| Review / Diagnostics | `/review` | `platform.ai.read`, `platform.knowledge.read` |
| Security | `/admin/security` | `platform.security.read`, `platform.audit.read`, `platform.users.role.assign` |
| Audit | `/admin/audit` | `platform.audit.read` |
| Billing | `/admin/billing` | `platform.billing.read` |
| Privacy | `/admin/privacy` | `platform.privacy.read` |
| Legal | `/admin/legal` | `platform.privacy.read` |
| Knowledge | `/admin/knowledge` | `platform.knowledge.read` |
| Reports | `/admin/reports` | `platform.reports.read`, `platform.reports.commercial.read` |
| Configuration | `/admin/configuration` | `platform.flags.read` |
| Feature flags | `/admin/flags` | `platform.flags.read` |
| AI and models | `/admin/ai` | `platform.ai.read` |
| Jobs | `/admin/jobs` | `platform.jobs.read` |
| Integrations | `/admin/integrations` | `platform.integrations.read` |
| Provider status | `/admin/providers` | `platform.integrations.read` |

### Child and detail routes
`/admin/users/{id}`, `/admin/workspaces/{id}`, `/admin/support/{ref}`, `/admin/plans/{id}`, `/admin/privacy/{ref}`, `/admin/knowledge/{id}`, `/admin/ai/{id}`, `/admin/jobs/{id}`, `/admin/integrations/{code}`, and the Review / Diagnostics pages `/review/agent`, `/review/rag` and `/review/evaluation`. The Security page's tabs (Security events, Audit, Incidents, Alerts, Role approvals) are views of `/admin/security`. Review / Diagnostics is part of the Admin navigation but renders outside the Admin shell (F-01).

## 31. Next steps
1. W12.3C Specialist Admin journeys: **complete** (separate documents, linked in section 29).
2. W12.4 (A to F): Admin Operability & Production Configuration Closure, **next**, beginning with W12.4A (Knowledge Base Accessibility & Operations).
3. W12.5: Preferred Admin UX corrections.
4. Integrated Candidate + Admin + Operations requalification, then RC-P10-004, then AC-24 closure where its criterion is met (AC-24 remains PARTIAL), then P10C.

None of these has started. The Pilot 2 historical verdict (CONDITIONAL GO, targeted remediation required) and the P2-01 to P2-04 states (pending human revalidation) are unchanged, and RC-P10-003 and the W10.14 28 of 43 record remain historical evidence.
