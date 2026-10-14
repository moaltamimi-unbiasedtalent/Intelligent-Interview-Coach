# Ask4Mo: Canonical Specialist Admin Journeys (index)

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This is the canonical index for the five delegated Admin roles. It describes **current** behaviour, derived read-only from the code-defined permission presets, the frontend destination table and the route permission graph. Anything not built is labelled **PLANNED W12.4** and is not current functionality. The owner / orchestrator role is documented in [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md); the candidate side is [CANDIDATE_JOURNEY.md](CANDIDATE_JOURNEY.md).

## 1. Role model
The five specialist roles are **delegated, least-privilege operational roles**. They are **not** junior Platform Admins, not partial superusers and not customisable roles. Each is a fixed, code-defined preset of permission strings, and every one is a **strict subset** of the Platform Admin's 43 / 43 permissions. The candidate role has **0** Admin permissions, and an unknown, missing or malformed role also resolves to **0**.

- **Authorization is by permission string, never by role name.** No route checks a role name. The frontend derives navigation from the permission list the server supplies (UX only); the backend independently enforces every route.
- **Specialists are not subordinate in a database hierarchy.** They simply have bounded authority; there is no "reports to" relationship, and no custom roles or role tables exist.
- **43 / 43 does not mean candidate content.** No Admin role, including the Platform Admin, can see candidate CVs, raw documents, interview answers, Mo conversations, Story Bank, private memory or report contents. There is no break-glass, impersonation or view-as.

## 2. Role journeys
| Role | Journey document |
|---|---|
| support_operator | [SUPPORT_OPERATOR_JOURNEY.md](SUPPORT_OPERATOR_JOURNEY.md) |
| billing_admin | [BILLING_ADMIN_JOURNEY.md](BILLING_ADMIN_JOURNEY.md) |
| knowledge_admin | [KNOWLEDGE_ADMIN_JOURNEY.md](KNOWLEDGE_ADMIN_JOURNEY.md) |
| security_privacy_admin | [SECURITY_PRIVACY_ADMIN_JOURNEY.md](SECURITY_PRIVACY_ADMIN_JOURNEY.md) |
| operations_admin | [OPERATIONS_ADMIN_JOURNEY.md](OPERATIONS_ADMIN_JOURNEY.md) |

## 3. Permission matrix (counts verified against the code)
| Role | Permissions | Visible destinations | Admin routes callable (of 147) | Primary domains | Explicitly excluded domains |
|---|---:|---:|---:|---|---|
| support_operator | 7 | 4 | 13 | Support queue; read-only user and workspace metadata | billing, plans, security, audit, privacy, legal, knowledge, jobs, integrations, configuration, flags, reports, AI |
| billing_admin | 10 | 5 | 28 | plans, subscriptions, mock billing, commercial reporting | support, security, audit, privacy, legal, knowledge, jobs, integrations, configuration, flags, AI |
| knowledge_admin | 6 | 5 | 41 | governed knowledge; read-only AI and jobs; diagnostics | users, support, billing, security, privacy, legal, integrations, configuration, flags, reports |
| security_privacy_admin | 11 | 6 | 33 | security, incidents, alerts, audit, privacy, legal, session revocation | roles, deactivation, support, plans, billing, knowledge, AI, jobs, integrations, configuration, flags, reports |
| operations_admin | 11 | 9 | 38 | jobs, integrations, provider status, pause, flags, operational reports, AI read | users, roles, support, plans, billing, knowledge, privacy, legal, security, audit |
| platform_admin | 43 | 19 | 147 | all control-plane domains | candidate private content (no permission exists) |
| candidate (`user`) | 0 | 0 | 0 | none | all Admin |

## 4. Navigation matrix (from `visibleDestinations()` and the presets)
| Destination | Support | Billing | Knowledge | Security / Privacy | Operations | Platform Admin |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Overview | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Users | ✓ | ✓ | — | ✓ | — | ✓ |
| Workspaces | ✓ | — | — | — | — | ✓ |
| Plans | — | ✓ | — | — | — | ✓ |
| Support | ✓ | — | — | — | — | ✓ |
| Review / Diagnostics | — | — | ✓ | — | ✓ | ✓ |
| Security | — | — | — | ✓ | — | ✓ |
| Audit | — | — | — | ✓ | — | ✓ |
| Billing | — | ✓ | — | — | — | ✓ |
| Privacy | — | — | — | ✓ | — | ✓ |
| Legal | — | — | — | ✓ | — | ✓ |
| Knowledge | — | — | ✓ | — | — | ✓ |
| Reports | — | ✓ | — | — | ✓ | ✓ |
| Configuration | — | — | — | — | ✓ | ✓ |
| Feature flags | — | — | — | — | ✓ | ✓ |
| AI and models | — | — | ✓ | — | ✓ | ✓ |
| Jobs | — | — | ✓ | — | ✓ | ✓ |
| Integrations | — | — | — | — | ✓ | ✓ |
| Provider status | — | — | — | — | ✓ | ✓ |
| **Total** | **4** | **5** | **5** | **6** | **9** | **19** |

Billing's Reports destination exposes the commercial tab only (its reports permission is the commercial one); Operations' exposes the operational, product, quality and AI-economics tabs.

## 5. Delegation and two-person model
Two-person approval means **a different active administrator who holds the required permission**; it is not tied to any role name. Current distinct-actor flows:

| Workflow | Permission(s) | Which roles can be a party | Eligible pairs |
|---|---|---|---|
| Platform role change (request and approve) | `users.role.assign` | **Platform Admin only** | Two different Platform Admin accounts (the target also cannot approve) |
| Billing price change (mock) | `plans.price.change` | Billing Admin, Platform Admin | Two different accounts among those roles |
| Billing refund (mock) | `billing.refund` | Billing Admin, Platform Admin | Two different accounts among those roles |
| AI configuration approval and activation | `ai.manage`, `ai.activate` | **Platform Admin only** (Knowledge and Operations Admins hold only `ai.read`) | Two different Platform Admin accounts; the approver is also not the author |

The Security / Privacy Admin does **not** hold `users.role.assign`, so it cannot request or approve role changes and sees no Role approvals tab. Knowledge approval, legal publication, plan activation, privacy handling, pause and flag changes and credential replacement have **no distinct-actor rule today**.

## 6. Step-up boundary
Fresh-password step-up (5 minutes, bound to the session, not MFA) is currently required **only** for requesting and approving platform role changes. The step-up endpoint itself requires `users.role.assign`, so **no specialist role can use or trigger it**. Specialist high-risk actions (refunds, price changes, privacy execution, legal publication, knowledge approval, pause, flags) rely on permissions, confirmations, reasons where stated, expected revisions, a second approver where defined, and audit. This is recorded as finding A-04 in the Platform Admin journey.

## 7. Inherited operability truth
| Domain | Current status | Notes |
|---|---|---|
| Billing | CURRENT - MOCK | MockBillingAdapter only; no live checkout, cards, tax, webhooks or revenue |
| Email | CURRENT (W12.4C): code qualified, live delivery unverified | Diagnostics, connection test and self test email for operations_admin and platform_admin; no delivery events |
| Integration secrets | CURRENT (W12.4B): Platform Admin only | Encrypted SecretStore (opt-in); operations_admin inspects but cannot rotate (no `secret.rotate`) |
| Knowledge | CURRENT - PARTIAL | W12.4A fixed two root causes in code and added readiness, inventory and a retrieval test; operator action still needed in the developer environment (activate a source, run the worker) |
| AI configuration | CURRENT - OPERATIONAL WITH LIMITATION | Deterministic evaluations only; not live-quality evidence |
| Provider status | CURRENT - STATUS / PARTIAL | Configuration only; not health, not live validated |
| Jobs | CURRENT - OPERATIONAL WITH LIMITATION | Separate worker; no dead-letter state |
| Alerts | CURRENT - IN-APP ONLY | No external paging |

A screen existing is not the same as the capability being fully operational.

## 8. Planned W12.4 impact (planning only; nothing below is implemented)
| W12.4 sub-wave | Affected roles | Expected impact |
|---|---|---|
| W12.4A Knowledge Base Accessibility & Operations (**implemented**, first sub-wave) | knowledge_admin, operations_admin, platform_admin | Root causes fixed, readiness, active inventory and a retrieval-only test added (permission `knowledge.read`); no role change |
| W12.4B Secure Provider & Secret Administration (COMPLETE) | operations_admin, platform_admin | Delivered: writable encrypted secret store; platform_admin configures, replaces and removes supported credentials (write-only, audited, step-up); operations_admin remains inspect and test only |
| W12.4C Email & Identity Operations (CODE QUALIFIED; live operator test pending) | operations_admin, platform_admin (security_privacy_admin has no integration permission) | Operationalise Brevo, sender configuration, test email, diagnostics, verification and reset email |
| W12.4D Live Billing Provider | billing_admin, operations_admin where provider health is involved, platform_admin | A real provider behind the BillingProvider abstraction; billing stays separate from entitlement |
| W12.4E Governed Speech Providers | operations_admin, platform_admin, knowledge_admin only if AI or read surfaces overlap | Whisper (STT) and Pocket TTS (TTS) behind Admin configuration; Russian stays excluded; no persistent audio |
| W12.4F Admin Configuration Completeness | potentially all specialist roles, by domain | Classify every capability and add governed controls only for normal operations; never arbitrary environment variables, commands, paths or secret values |

W12.4A came first because of the owner-reported Knowledge issue and is now implemented; W12.4B follows. No permission change is made or implied by this table.

## 9. Findings (documentation only; none fixed)
| ID | Class | Finding |
|---|---|---|
| SJA-01 | ROLE-SCOPE | AI configuration management and activation (`ai.manage`, `ai.activate`) are held only by the Platform Admin, so the required second approver must be a second Platform Admin account; no specialist can be a party. Possible future review. |
| SJA-02 | ROLE-SCOPE | Knowledge Admin holds `jobs.read` only: it cannot retry or cancel a failed parse or index job. Impact: escalation to Operations or Platform Admin. |
| SJA-03 | ROLE-SCOPE | Billing Admin (refunds) and Security / Privacy Admin (account deletion) trigger work that runs as background jobs but hold no `jobs.read`, so they cannot see queue or worker state. |
| SJA-04 | NAVIGATION | Operations Admin sees Review / Diagnostics (via `ai.read`) but lacks `knowledge.read`, so the knowledge diagnostics reads are not available to it. The destination is only partly useful for that role. |
| SJA-05 | SECURITY | Knowledge approval and activation have no distinct-actor rule and no step-up: one Knowledge Admin can upload and approve. Related to Platform Admin finding A-04. |
| SJA-06 | DOCUMENTATION | `platform.releases.read` (Operations Admin) and `platform.subscriptions.read` (Billing Admin) are held but no route requires them today. |
| SJA-07 | KNOWN LIMITATION | Support replies and notifications are in-app only: no email, no attachments, no SLA. |

W12.2 Admin UX findings F-01 to F-17 remain open and tracked.

## 10. Preserved state
No permission, preset or role was changed by this documentation. W10.14's historical 28 / 43 record and RC-P10-003 are unchanged, the Pilot 2 verdict (CONDITIONAL GO, targeted remediation required) is unchanged, P2-01 to P2-04 remain pending human revalidation, AC-24 is PARTIAL, RC-P10-004 is not created and P10C has not started.
