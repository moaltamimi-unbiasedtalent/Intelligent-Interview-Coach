# Admin Architecture Decisions (P10B-W10.0)

Decision record for the Admin control plane. **Accepted** decisions bind W10.1-W10.14; **recommended** decisions (AD-01..AD-08) are proposals awaiting owner confirmation where marked.
Context and detail: [ADMIN_PLATFORM_MASTER_PLAN.md](ADMIN_PLATFORM_MASTER_PLAN.md). Nothing here is implemented.

## Accepted architectural decisions
| ID | Decision | Rationale |
|---|---|---|
| ADR-01 | Platform admin is **not** a candidate-content superuser | privacy by design; consistent with P6.5 and W9.3; no content routes, no content search, deny-list invariant |
| ADR-02 | Authorization is **capability-based** (`platform.<domain>.<action>`), default deny, enforced on the backend | avoids role-name logic in code; UI visibility is UX only |
| ADR-03 | Secrets are **write-only** from the Admin perspective (set, rotate, test, disable); only masked metadata is returned; never in audit or logs | prevents credential exfiltration through the portal |
| ADR-04 | A model/prompt configuration **cannot be activated without a passing evaluation** and a second approver; activation is versioned and reversible | no ungoverned model change; preserves the no-autonomous-self-modification invariant |
| ADR-05 | **Knowledge uploads never reach production retrieval without approval**; flow is upload, safety, parse, classify, provenance, preview, approve, index, activate | KB poisoning and licence risk |
| ADR-06 | **Payment data stays with the provider**; Ask4Mo stores only provider ids, state and invoice metadata | PCI scope avoidance |
| ADR-07 | **No arbitrary browser-based code deployment**; observability before deployment control | risk and Capstone scope |
| ADR-08 | **Mocks and adapters are labelled** (UI, API, reports) and never presented as live | honesty; matches the claim register |
| ADR-09 | Every **sensitive admin write is audited in the same transaction** (fail-closed), with `request_id` and a reason where required; no secrets, no candidate content | closes SEC-W10-02/03 |
| ADR-10 | External integrations go through **adapters/interfaces** (BillingProvider, SecretStore, JobRunner, Mailer) | testability, replaceability |
| ADR-11 | **Candidate private content is not searchable by Admin**; operator search targets identifiers and metadata | privacy boundary |
| ADR-12 | Admin **orchestrates** privacy workflows by calling the existing W9.8 services; it does not create a second privacy engine | one source of truth for deletion/export |
| ADR-13 | Migrations are **grouped per domain wave** (about 12 small, additive, reversible), never one giant migration | rollback and review |
| ADR-14 | **Integrated candidate + admin requalification is required after W10.14 and before RC-P10-003** | candidate P10B must not regress |
| ADR-15 | Sequence and numbering of W10.x are retained; execution order is refined (W10.9 before W10.8/W10.10; audit foundation in W10.1) | dependency-driven, history preserved |

## Open decisions with recommendations
| ID | Question | Options | Recommendation | Needs owner |
|---|---|---|---|---|
| **AD-01** | Admin localization | A English-only internal tooling; B localized admin shell | **A.** Admin is internal; maintenance cost of 8 locales is not Capstone value. Candidate-facing strings introduced by W10 (support form, legal prompts, plan names) ARE localized x8. Admin must still be accessible. | confirm |
| **AD-02** | Break-glass support access | needed for Capstone, or metadata-only support | **Not needed.** Support uses metadata, request ids, safe diagnostics and candidate-supplied attachments. Reserve `platform.breakglass.*` and the design (reason, ticket link, named operator, scope, time-box, approver, candidate notice, read-only, audit). | confirm |
| **AD-03** | Payment provider | defer selection; or nominate an adapter target | **Defer selection.** Ship `BillingProvider` + `MockBillingAdapter`; shape the interface for hosted-checkout + webhook providers so a Stripe-style adapter drops in. No live billing in Capstone. | **yes** |
| **AD-04** | Production secret manager | interface only; or name a provider | **Interface + env/local adapter** now (`SecretStore`: `EnvSecretStore` read-only, `LocalEncryptedSecretStore` for dev with a key from the environment); name no provider yet (managed vault later). | **yes** |
| **AD-05** | Background job execution | stay synchronous; or a job abstraction | **DB-backed `background_job` abstraction with a small separate worker process; no external broker.** First consumers: KB ingestion, DSAR execution, webhook handling. Existing synchronous paths unchanged. | **yes** |
| **AD-06** | PRIV-W9-01 preparation-run index | index table; scan checkpoints; ignore | **`preparation_run(run_id PK = thread id, user_id FK CASCADE, opportunity_id nullable, status, created_at, last_active_at)` written at run start by the agent service.** Enables list and delete of preparation chats and complete account deletion via the index. Historical runs: a one-time bounded job may back-fill ownership from checkpoints (a full-store scan inside a request is rejected: it took minutes on a 35 MB store in W9.8). Migration group MG-9. | **yes** (schema) |
| **AD-07** | PRIV-W9-02 legal/consent model | version tables; or document only | **`legal_document_version(doc_type, version, locale, effective_at, content_hash, review_status)` and `legal_acceptance(user_id, doc_type, version, accepted_at, locale)`;** registration records acceptance; a re-acceptance gate when a version is published; acceptance rows retained as an anonymised legal record on account deletion (counsel to confirm). No source IP or device unless justified. | **yes** (retention) |
| **AD-08** | Roles vs capabilities | single `platform_admin`; or multiple runtime personas | **Capabilities first; roles are code-defined presets** (`platform_admin`, `support_operator`, `billing_admin`, `knowledge_admin`, `security_privacy_admin`, `ops_admin`) stored in the existing `users.platform_role` column (widened values, no schema change). A roles table is deferred until multi-role is required. | confirm |

## Pre-W10.1 findings promoted to requirements
SEC-W10-01 session revocation on deactivation (W10.2 first task); SEC-W10-02 fail-closed audit for sensitive writes (W10.1); SEC-W10-03 request ids, failed-access events and standard event names (W10.1);
SEC-W10-04 dead privacy-request queue (W10.10); SEC-W10-05 durable pause state (W10.11); SEC-W10-06 raw `email.provider` echo (W10.6).
