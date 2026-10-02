# Admin Architecture Decisions (P10B-W10.0)

Decision record for the Admin control plane. **Accepted** architectural decisions (ADR-xx) and the **owner decisions AD-01..AD-08 (FINAL, approved)** bind W10.1-W10.14.
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

## Owner decisions AD-01..AD-08 (FINAL, approved)
| ID | Final decision |
|---|---|
| **AD-01** Admin localization | The internal `/admin` operator UI is **English-only** for the Capstone. Anything candidate-facing introduced by W10 (Contact Support forms, candidate ticket views, candidate-visible support responses/templates, privacy communications, candidate notifications, candidate billing/subscription messaging) follows the existing 8-locale candidate contract (en, de, fr, es, it, pt, nl, ru). English-only Admin is **not** permission for English-only candidate copy. |
| **AD-02** Break-glass | **No break-glass private-content access in the Capstone.** Operators work from account metadata, request ids, route/error information, subscription/entitlement state, feature/config state, operational telemetry, audit events, support-ticket information and attachments voluntarily supplied by the candidate. W10 creates **no** break-glass permission, private-content admin browser, impersonation flow, private-message search, CV/content browsing, memory browsing or interview-answer browsing without a separately approved future phase. (The earlier reserved `platform.breakglass.*` permission was removed from the namespace: 43 permissions remain.) |
| **AD-03** Payment provider | **Defer live provider selection.** Capstone uses `BillingService -> MockBillingAdapter`; the architecture stays ready for a future production adapter (Stripe or another). UI and documentation distinguish **MOCK BILLING** from **LIVE BILLING**; payments, refunds, card processing and invoices are never presented as production-live. Card/payment-instrument data stays provider-owned. |
| **AD-04** Secret store | `SecretStore` interface -> environment/local-development adapter -> future production-vault adapter. **Environment-backed secrets are externally managed:** Admin must not claim to have rotated or replaced an environment variable the runtime cannot persist. For them Admin shows only configured yes/no, provider, last test, connection health, externally managed, masked identifier where safe. Never return, log, audit or query-string plaintext; never show a full key after save. **Writable secret management is exposed only when the active adapter genuinely supports secure writes.** Mock/local behaviour is labelled. |
| **AD-05** Background jobs | **DB-backed job abstraction with a separate worker; no external broker.** Required: transactional claiming (never select-and-hope), lease/ownership with heartbeat or lease expiry, attempt count, retry policy, idempotency, failed and dead-letter states, request/correlation id, entity linkage, created/started/completed timestamps. PostgreSQL and SQLite claiming semantics are specified and tested separately. Implementation W10.9 (before W10.8 and W10.10); not in W10.0. |
| **AD-06** PRIV-W9-01 | Future (W10.10) **`preparation_run` ownership/lifecycle index; it must not duplicate chat content.** Likely: run id, user id, Opportunity id where applicable, underlying agent/checkpoint run id, run type, status, created/updated/completed timestamps, deletion state (subject to the implementation audit). Created at or before durable run creation; indexed by user, run, Opportunity and lifecycle/deletion state. Account/user deletion must enumerate all owned runs without scanning the checkpoint store. Historical pre-index runs need an explicit migration/backfill strategy; a full-store scan is not assumed acceptable. **PRIV-W9-01 stays OPEN** until implemented and deletion is verified. |
| **AD-07** PRIV-W9-02 | Separate **legal document/version** (type, version, locale, publication/effective date, content hash or immutable reference, active/superseded, re-acceptance required) from **user acceptance** (user id, legal version id, accepted_at, acceptance source, minimal metadata only if justified). **No IP, user agent or device fingerprint by default.** **Retention of acceptance records after account deletion is not an owner-defined legal policy yet:** the schema supports governed retention, anonymisation or pseudonymisation, hard-codes no period, and claims neither that records must be retained nor that they must be erased; counsel confirmation is required before production reliance. **PRIV-W9-02 stays OPEN** until versions and acceptances persist, candidate visibility and the admin/legal workflow work, and retention/deletion semantics are approved and tested. |
| **AD-08** Roles/permissions | **Code-defined role presets -> canonical permissions.** Presets: `platform_admin`, `support_operator`, `billing_admin`, `knowledge_admin`, `security_privacy_admin`, `operations_admin`. No user-configurable or custom roles in the Capstone. Backend authorization checks the **permission** via `require_permission(...)` (never `if user.role == ...` in domain code); default deny; frontend visibility follows permissions but is not the security boundary. No schema change in W10.0. |

## Approved remediation placement of the six verified defects
| ID | Defect | Target wave | Direction |
|---|---|---|---|
| SEC-W10-01 | deactivation does not revoke active sessions | **W10.2** | required security fix |
| SEC-W10-02 | privileged audit writes swallow errors | **W10.1** | sensitive privileged writes must not silently succeed without audit evidence; define transaction/failure semantics carefully |
| SEC-W10-03 | admin audit lacks request ids, failed access not audited, naming inconsistent | **W10.1** | canonical names, request/correlation id, failed authorization events, safe target/action metadata, no content or secrets |
| SEC-W10-04 | admin privacy-request queue permanently empty | **W10.10** | do not show a misleading "working" queue before the privacy-request domain exists |
| SEC-W10-05 | pause state process-local | **W10.11** | until then label as process-local or withhold; never represent as durable/shared |
| SEC-W10-06 | `/admin/providers` echoes raw email-provider setting | **W10.1** (early) | admin provider/config responses return safe metadata only; establish the contract before W10.6 expands them |

## Final W10 execution order (numbering unchanged; order differs from numeric order because of dependencies)
W10.1 -> W10.2 -> W10.3 -> W10.4 -> W10.6 -> W10.9 -> W10.8 -> W10.10 -> W10.5 -> W10.7 -> W10.11 -> W10.12 -> W10.13 -> W10.14 -> integrated candidate + admin requalification -> RC-P10-003.
W10.1 approved scope: master plan section 33 (permission framework, presets, `require_permission`, default deny, route-permission CI invariant, gated shell, fail-closed audit, canonical event names, request ids,
failed-access audit, safe provider response, Command Center, build/release metadata, health summaries, minimal event capture, no content browsing; migration-free unless proven otherwise, then STOP).

No open architecture decision blocks W10.1.
