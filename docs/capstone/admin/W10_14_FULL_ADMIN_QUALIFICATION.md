# P10B-W10.14 - Full Admin Qualification

## 1. Status
**Implemented and qualified on branch `feat/p10b-w10-14-full-admin-qualification`; COMPLETE only after merge.** W11 is NOT STARTED. This wave is qualification and reconciliation, not a product-feature wave: no migration, no new permission, no new dependency, no product behaviour change, 0 paid/live calls.

## 2. Starting main SHA
`a077f26305776bcec76cab1c0a408ffc1fd5132f` (W10.13 integrated; Alembic head `0025_security_audit_incidents`).

## 3. W10.13 PR #128
Feature head `44f8a7397c4cadf1df9c8f3b603dbaad7410ff29`, merge `b47a10b37219cfe51c117fa1b8d99c964a18c5ff`.

## 4. W10.13 docs PR #129
Head `0e2102d2be892039b05b8f54389c06823e1eedb1`, merge/main `a077f26305776bcec76cab1c0a408ffc1fd5132f`. The W10.13 document now records it (the one known omission), plus one factual correction: `GET /auth/admin/audit` exists (own-actor view, `platform.audit.read`).

## 5. Qualification branch
`feat/p10b-w10-14-full-admin-qualification`.

## 6. Alembic head
`0025_security_audit_incidents` (single head, unchanged; W10.14 is migration-free).

## 7. Purpose
Reconcile the W10 Admin control plane as one system: roles and permissions, every route against every persona, privacy and secret boundaries, audit, entitlement/billing separation, domain requalification, and evidence from a fresh checkout. It does NOT make the product release-candidate-ready: **P10B-W11 (integrated candidate + Admin requalification) is mandatory before RC-P10-003 may be considered.**

## 8. ROLE-W10-01 final decision - CLOSED
**Least-privilege domain separation is authoritative.** The W10.0 persona wording (Platform Administrator holding every permission except break-glass) is superseded. `platform_admin` is a broad cross-domain platform operator with an explicit code-defined preset. It is not an unrestricted super-role, not billing, privacy-execution, secret-rotation, security/incident-mutation, knowledge-approval, job-operations, configuration or audit-export authority, and not a candidate-data superuser. No permission was added to satisfy the stale wording; the preset was audited from code and left unchanged. Rationale: separation of duties; it matches what W10.1-W10.13 actually built; permission strings stay authoritative; presets stay code-defined; no migration; no private candidate-data access. Recorded in the master plan (decision note), ADR-16, the capability matrix and the guards.

## 9. Final role model
Seven principal classes, exactly: `user` (candidate; no Admin permission), `platform_admin`, `support_operator`, `billing_admin`, `knowledge_admin`, `security_privacy_admin`, `operations_admin`. No custom roles, no dynamic role editor, no persisted permission grants, no break-glass or impersonation role. Preset sizes: platform_admin 28, support_operator 7, billing_admin 10, knowledge_admin 6, security_privacy_admin 11, operations_admin 11. Unknown, empty or mis-cased role values resolve to no permission (default deny); an inactive Admin has no authority.

## 10. The 43-permission matrix (generated from code)
| Permission | user | platform | support | billing | knowledge | security | operations | owners | W10.14 decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `platform.ai.activate` | - | Y | - | - | - | - | - | platform_admin | retained |
| `platform.ai.manage` | - | Y | - | - | - | - | - | platform_admin | retained |
| `platform.ai.read` | - | Y | - | - | Y | - | Y | platform_admin, knowledge_admin, operations_admin | retained |
| `platform.audit.export` | - | - | - | - | - | Y | - | security_privacy_admin | domain-owner only (absent from platform_admin) |
| `platform.audit.read` | - | Y | - | - | - | Y | - | platform_admin, security_privacy_admin | retained |
| `platform.billing.read` | - | - | - | Y | - | - | - | billing_admin | domain-owner only (absent from platform_admin) |
| `platform.billing.refund` | - | - | - | Y | - | - | - | billing_admin | domain-owner only (absent from platform_admin) |
| `platform.config.manage` | - | - | - | - | - | - | Y | operations_admin | domain-owner only (absent from platform_admin) |
| `platform.flags.manage` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.flags.read` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.incidents.manage` | - | - | - | - | - | Y | - | security_privacy_admin | domain-owner only (absent from platform_admin) |
| `platform.integrations.manage` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.integrations.read` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.integrations.secret.rotate` | - | - | - | - | - | - | - | none | unassigned by design (secret rotation stays externally managed) |
| `platform.jobs.manage` | - | - | - | - | - | - | Y | operations_admin | domain-owner only (absent from platform_admin) |
| `platform.jobs.read` | - | - | - | - | Y | - | Y | knowledge_admin, operations_admin | domain-owner only (absent from platform_admin) |
| `platform.knowledge.approve` | - | - | - | - | Y | - | - | knowledge_admin | domain-owner only (absent from platform_admin) |
| `platform.knowledge.manage` | - | - | - | - | Y | - | - | knowledge_admin | domain-owner only (absent from platform_admin) |
| `platform.knowledge.read` | - | Y | - | - | Y | - | - | platform_admin, knowledge_admin | retained |
| `platform.legal.manage` | - | - | - | - | - | Y | - | security_privacy_admin | domain-owner only (absent from platform_admin) |
| `platform.overview.read` | - | Y | Y | Y | Y | Y | Y | platform_admin, support_operator, billing_admin, knowledge_admin, security_privacy_admin, operations_admin | retained |
| `platform.plans.manage` | - | Y | - | Y | - | - | - | platform_admin, billing_admin | retained |
| `platform.plans.price.change` | - | - | - | Y | - | - | - | billing_admin | domain-owner only (absent from platform_admin) |
| `platform.plans.read` | - | Y | - | Y | - | - | - | platform_admin, billing_admin | retained |
| `platform.privacy.execute` | - | - | - | - | - | Y | - | security_privacy_admin | domain-owner only (absent from platform_admin) |
| `platform.privacy.read` | - | Y | - | - | - | Y | - | platform_admin, security_privacy_admin | retained |
| `platform.releases.read` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.reports.commercial.read` | - | - | - | Y | - | - | - | billing_admin | domain-owner only (absent from platform_admin) |
| `platform.reports.read` | - | Y | - | - | - | - | Y | platform_admin, operations_admin | retained |
| `platform.security.manage` | - | - | - | - | - | Y | - | security_privacy_admin | domain-owner only (absent from platform_admin) |
| `platform.security.read` | - | Y | - | - | - | Y | - | platform_admin, security_privacy_admin | retained |
| `platform.subscriptions.manage` | - | Y | - | Y | - | - | - | platform_admin, billing_admin | retained |
| `platform.subscriptions.read` | - | Y | - | Y | - | - | - | platform_admin, billing_admin | retained |
| `platform.support.manage` | - | Y | Y | - | - | - | - | platform_admin, support_operator | retained |
| `platform.support.note` | - | Y | Y | - | - | - | - | platform_admin, support_operator | retained |
| `platform.support.read` | - | Y | Y | - | - | - | - | platform_admin, support_operator | retained |
| `platform.support.reply` | - | Y | Y | - | - | - | - | platform_admin, support_operator | retained |
| `platform.users.manage` | - | Y | - | - | - | - | - | platform_admin | retained |
| `platform.users.read` | - | Y | Y | Y | - | Y | - | platform_admin, support_operator, billing_admin, security_privacy_admin | retained |
| `platform.users.role.assign` | - | Y | - | - | - | - | - | platform_admin | retained |
| `platform.users.sessions.revoke` | - | Y | - | - | - | Y | - | platform_admin, security_privacy_admin | retained |
| `platform.workspaces.manage` | - | Y | - | - | - | - | - | platform_admin | retained |
| `platform.workspaces.read` | - | Y | Y | - | - | - | - | platform_admin, support_operator | retained |

`platform_admin` holds 28 of 43. The 15 specialist permissions intentionally absent from it: audit.export, billing.read, billing.refund, config.manage, incidents.manage, integrations.secret.rotate, jobs.manage, jobs.read, knowledge.approve, knowledge.manage, legal.manage, plans.price.change, privacy.execute, reports.commercial.read, security.manage. `platform.integrations.secret.rotate` is held by NO role (secret rotation stays externally managed). `platform.releases.read` and `platform.subscriptions.read` are registry permissions that no current route requires (informational).

## 11. Route inventory (generated from the route dependency graph)
| Domain | Routes | GET | Mutating | Permissions required |
|---|---:|---:|---:|---|
| AI / model administration | 23 | 13 | 10 | ai.activate, ai.manage, ai.read |
| audit | 3 | 2 | 1 | audit.export, audit.read |
| billing | 15 | 9 | 6 | billing.read, billing.refund, plans.price.change |
| flags / configuration / pause | 4 | 2 | 2 | config.manage, flags.manage, flags.read |
| integrations / providers | 5 | 3 | 2 | integrations.manage, integrations.read, integrations.secret.rotate |
| jobs | 7 | 4 | 3 | jobs.manage, jobs.read |
| knowledge | 24 | 14 | 10 | ai.read, knowledge.approve, knowledge.manage, knowledge.read, privacy.read |
| overview / releases | 1 | 1 | 0 | overview.read |
| plans / subscriptions | 7 | 3 | 4 | plans.manage, plans.read, subscriptions.manage |
| privacy / legal | 13 | 5 | 8 | legal.manage, privacy.execute, privacy.read |
| reports | 7 | 7 | 0 | reports.commercial.read, reports.read |
| role approvals / step-up | 7 | 2 | 5 | users.role.assign |
| security / incidents / alerts | 12 | 5 | 7 | incidents.manage, security.manage, security.read |
| support | 8 | 3 | 5 | support.manage, support.note, support.read, support.reply |
| users | 5 | 2 | 3 | subscriptions.manage, users.manage, users.read, users.sessions.revoke |
| workspaces | 6 | 2 | 4 | subscriptions.manage, workspaces.manage, workspaces.read |
| **Total** | **147** | **77** | **70** | |

Includes the `/reviewer/*`, `/evaluation/*` and `/knowledge/diagnostics` diagnostic routes and the foundation `GET /auth/admin/audit`.

## 12. Route x persona qualification
Every privileged route x every persona (candidate + six presets) is exercised over real HTTP on a temp database by `tests/test_admin_qualification_w10_14.py::test_route_x_persona_matrix_over_http_is_exactly_the_preset_expectation`. The expected allow/deny is DERIVED from the route's `require_permission` and the code-defined preset, and the observed result must match exactly (a denial is the fixed "Administrator access required." 403; an allowed persona is never 401/403 or a 5xx). Requests carry placeholder ids and an empty body, so allowed personas fail at validation or lookup and never act: no destructive business action is executed to prove permission maths. Case count: routes x 7 (see the final report).

## 13. Candidate deny result
The candidate is denied every Admin route (HTTP matrix, domain test, manual QA 01). A deactivated Admin's session no longer authenticates.

## 14. Support separation
Support Operator has no billing, price approval, subscription management, AI activation, knowledge approval, privacy execution, security/incident mutation, audit export, job management or configuration permission (preset assertion + HTTP matrix + manual QA 04).

## 15. Billing separation
Billing Admin has no user management, knowledge, AI, privacy/legal, incident, job or secret-rotation permission and cannot read candidate private content (assertion + manual QA 06).

## 16. Knowledge separation
Knowledge Admin has no user management, subscription, billing, privacy execution, incident or role-assignment permission (manual QA 08).

## 17. Security/Privacy separation
Security / Privacy Admin has no billing, plan management, AI activation, knowledge approval, flag management, job management or role-assignment permission (manual QA 12).

## 18. Operations separation
Operations Admin has no user management, role assignment, privacy execution, billing, knowledge approval or AI activation permission (manual QA 10).

## 19. Platform Admin least-privilege result
Broad but NOT universal: the 15 absent permissions are proven absent by test, evaluator and manual QA 14 (jobs, billing, audit export, incident mutation, price change and commercial reports are all denied over HTTP).

## 20. Frontend navigation matrix (generated; permission-derived)
| Persona | Visible destinations |
|---|---|
| user | (none) |
| platform_admin | /admin, /admin/users, /admin/workspaces, /admin/plans, /admin/support, /review, /admin/security, /admin/audit, /admin/privacy, /admin/legal, /admin/knowledge, /admin/reports, /admin/configuration, /admin/flags, /admin/ai, /admin/integrations, /admin/providers |
| support_operator | /admin, /admin/users, /admin/workspaces, /admin/support |
| billing_admin | /admin, /admin/users, /admin/plans, /admin/billing, /admin/reports |
| knowledge_admin | /admin, /review, /admin/knowledge, /admin/ai, /admin/jobs |
| security_privacy_admin | /admin, /admin/users, /admin/security, /admin/audit, /admin/privacy, /admin/legal |
| operations_admin | /admin, /review, /admin/reports, /admin/configuration, /admin/flags, /admin/ai, /admin/jobs, /admin/integrations, /admin/providers |

(19 destinations in total.)

### Admin page inventory (generated)
| Admin page | Navigation permission(s) (any of) | Backend gate |
|---|---|---|
| `/admin` | overview.read | `require_permission` on every API it calls |
| `/admin/ai` | ai.read | `require_permission` on every API it calls |
| `/admin/ai/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/audit` | audit.read | `require_permission` on every API it calls |
| `/admin/billing` | billing.read | `require_permission` on every API it calls |
| `/admin/configuration` | flags.read | `require_permission` on every API it calls |
| `/admin/flags` | flags.read | `require_permission` on every API it calls |
| `/admin/integrations` | integrations.read | `require_permission` on every API it calls |
| `/admin/integrations/[code]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/jobs` | jobs.read | `require_permission` on every API it calls |
| `/admin/jobs/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/knowledge` | knowledge.read | `require_permission` on every API it calls |
| `/admin/knowledge/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/legal` | privacy.read | `require_permission` on every API it calls |
| `/admin/plans` | plans.read | `require_permission` on every API it calls |
| `/admin/plans/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/privacy` | privacy.read | `require_permission` on every API it calls |
| `/admin/privacy/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/providers` | integrations.read | `require_permission` on every API it calls |
| `/admin/reports` | reports.read, reports.commercial.read | `require_permission` on every API it calls |
| `/admin/security` | security.read, audit.read, users.role.assign | `require_permission` on every API it calls |
| `/admin/support` | support.read | `require_permission` on every API it calls |
| `/admin/support/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/users` | users.read | `require_permission` on every API it calls |
| `/admin/users/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |
| `/admin/workspaces` | workspaces.read | `require_permission` on every API it calls |
| `/admin/workspaces/[id]` | (detail/child of a listed page) | `require_permission` on every API it calls |

Every top-level Admin page is a navigation destination; every destination has a page; every API the frontend calls under `/admin/` maps to a permission-gated route. Mutations on each page use the permissions in the audit mutation inventory (section 25).

The frontend never maps roles to permissions; a vitest fixture generated from the backend presets is checked against the REAL `visibleDestinations()` for every persona. Navigation is UX only.

## 21. Candidate-private-content boundary
No Admin permission name, route, response schema or Admin UI field exposes CV, document content, file bytes, interview answers/transcripts/reports, Mo or preparation conversation, memory, evidence, prompts, raw model responses, retrieval queries or checkpoint data. Verified by name scan, schema-field scan (documented exception: `transcript_visible_to_admin`, a constant-False boundary flag), UI scan, and planted sentinels (memory, document, interview answer/evidence) across every Admin read surface for every persona.

## 22. Support-content exception
Support ticket text is candidate-authored content that a holder of `platform.support.read` MAY see on the Support surface: the Support Operator AND, by its explicit preset, the Platform Administrator (a fact this wave surfaced and now documents; no other persona). It is domain-scoped and permissioned, internal notes stay operator-only, there is no attachment capability and no unrelated CV/interview/chat data, and it is not a candidate-data browser.

## 23. Secret non-disclosure
No Admin response, audit row or UI exposes API keys, OAuth secrets, bearer/session tokens or their hashes, password hashes, reset/verification tokens or SecretStore plaintext. The runtime secret read path (`get_for_runtime`) is confined to the store and adapters (never an Admin route or schema). The environment SecretStore is read-only; `platform.integrations.secret.rotate` is unreachable.

## 24. Secret sentinel
Sentinel secrets were set as provider environment values (OpenRouter, Adzuna, Google, Brevo, Redis) and every Admin read surface was exercised for every persona (test), plus integrations/providers/AI/overview/security/jobs/reports (manual QA 20, 33): 0 leaks in responses; audit rows scanned: 0 leaks.

## 25. Audit mutation inventory (generated from the route table)
| Method | Route | Permission | Audit events named in the handler | Audited in handler |
|---|---|---|---|---|
| POST | `/admin/ai/approvals/{approval_id}/approve` | `ai.activate` | ADMIN_AI_APPROVED | yes |
| POST | `/admin/ai/approvals/{approval_id}/reject` | `ai.activate` | ADMIN_AI_REJECTED | yes |
| POST | `/admin/ai/configs` | `ai.manage` | ADMIN_AI_CONFIG_CREATED | yes |
| PATCH | `/admin/ai/configs/{public_id}` | `ai.manage` | ADMIN_AI_CONFIG_UPDATED | yes |
| POST | `/admin/ai/configs/{public_id}/activate` | `ai.activate` | ADMIN_AI_ACTIVATED | yes |
| POST | `/admin/ai/configs/{public_id}/evaluate` | `ai.manage` | ADMIN_AI_EVALUATION_REQUESTED | yes |
| POST | `/admin/ai/configs/{public_id}/request-approval` | `ai.manage` | ADMIN_AI_APPROVAL_REQUESTED | yes |
| POST | `/admin/ai/configs/{public_id}/retire` | `ai.manage` | ADMIN_AI_RETIRED | yes |
| POST | `/admin/ai/configs/{public_id}/validate` | `ai.manage` | ADMIN_AI_CONFIG_VALIDATED | yes |
| POST | `/admin/ai/rollback` | `ai.activate` | ADMIN_AI_ROLLED_BACK | yes |
| POST | `/admin/audit/export` | `audit.export` | ADMIN_AUDIT_EXPORTED | yes |
| POST | `/admin/billing/payments/{public_id}/refunds` | `billing.refund` | ADMIN_BILLING_REFUND_REQUESTED | yes |
| POST | `/admin/billing/price-changes` | `plans.price.change` | ADMIN_BILLING_PRICE_CHANGE_REQUESTED | yes |
| POST | `/admin/billing/price-changes/{approval_id}/approve` | `plans.price.change` | ADMIN_BILLING_PRICE_ACTIVATED, ADMIN_BILLING_PRICE_CHANGE_APPROVED | yes |
| POST | `/admin/billing/price-changes/{approval_id}/reject` | `plans.price.change` | ADMIN_BILLING_PRICE_CHANGE_REJECTED | yes |
| POST | `/admin/billing/refunds/{approval_id}/approve` | `billing.refund` | ADMIN_BILLING_REFUND_APPROVED | yes |
| POST | `/admin/billing/refunds/{approval_id}/reject` | `billing.refund` | ADMIN_BILLING_REFUND_REJECTED | yes |
| PUT | `/admin/flags/{key}` | `flags.manage` | ADMIN_FLAG_OVERRIDE_DISABLED, ADMIN_FLAG_OVERRIDE_ENABLED, ADMIN_FLAG_OVERRIDE_RESET | yes |
| POST | `/admin/integrations/{code}/credentials/{slot}` | `integrations.secret.rotate` | ADMIN_CREDENTIAL_REPLACEMENT_FAILED, ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED, ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED | yes |
| POST | `/admin/integrations/{code}/test` | `integrations.manage` | ADMIN_INTEGRATION_TEST_RUN | yes |
| POST | `/admin/jobs` | `jobs.manage` | ADMIN_JOB_ENQUEUED | yes |
| POST | `/admin/jobs/{public_id}/cancel` | `jobs.manage` | ADMIN_JOB_CANCELLED | yes |
| POST | `/admin/jobs/{public_id}/retry` | `jobs.manage` | ADMIN_JOB_RETRY_REQUESTED | yes |
| POST | `/admin/knowledge/sources` | `knowledge.manage` | ADMIN_KNOWLEDGE_VERSION_UPLOADED | yes |
| POST | `/admin/knowledge/sources/{source_id}/versions` | `knowledge.manage` | ADMIN_KNOWLEDGE_VERSION_UPLOADED | yes |
| DELETE | `/admin/knowledge/versions/{version_id}` | `knowledge.manage` | ADMIN_KNOWLEDGE_VERSION_DELETED | yes |
| PATCH | `/admin/knowledge/versions/{version_id}` | `knowledge.manage` | ADMIN_KNOWLEDGE_VERSION_UPDATED | yes |
| POST | `/admin/knowledge/versions/{version_id}/activate` | `knowledge.approve` | ADMIN_KNOWLEDGE_VERSION_ACTIVATED | yes |
| POST | `/admin/knowledge/versions/{version_id}/approve` | `knowledge.approve` | ADMIN_KNOWLEDGE_VERSION_APPROVED | yes |
| POST | `/admin/knowledge/versions/{version_id}/index` | `knowledge.manage` | ADMIN_KNOWLEDGE_INDEX_REQUESTED | yes |
| POST | `/admin/knowledge/versions/{version_id}/reject` | `knowledge.approve` | ADMIN_KNOWLEDGE_VERSION_REJECTED | yes |
| POST | `/admin/knowledge/versions/{version_id}/reprocess` | `knowledge.manage` | ADMIN_KNOWLEDGE_REPROCESS_REQUESTED | yes |
| POST | `/admin/knowledge/versions/{version_id}/retire` | `knowledge.manage` | ADMIN_KNOWLEDGE_VERSION_RETIRED | yes |
| PATCH | `/admin/legal/versions/{version_id}` | `legal.manage` | ADMIN_LEGAL_VERSION_UPDATED | yes |
| POST | `/admin/legal/versions/{version_id}/publish` | `legal.manage` | ADMIN_LEGAL_VERSION_PUBLISHED | yes |
| POST | `/admin/legal/{code}/versions` | `legal.manage` | ADMIN_LEGAL_VERSION_CREATED | yes |
| POST | `/admin/pause/{capability}` | `config.manage` | ADMIN_PLATFORM_PAUSED, ADMIN_PLATFORM_RESUMED | yes |
| POST | `/admin/plans/versions/{version_id}/activate` | `plans.manage` | ADMIN_PLAN_VERSION_ACTIVATED | yes |
| PATCH | `/admin/plans/versions/{version_id}/entitlements` | `plans.manage` | ADMIN_PLAN_VERSION_UPDATED | yes |
| POST | `/admin/plans/versions/{version_id}/retire` | `plans.manage` | ADMIN_PLAN_VERSION_RETIRED | yes |
| POST | `/admin/plans/{plan_code}/versions` | `plans.manage` | ADMIN_PLAN_VERSION_CREATED | yes |
| POST | `/admin/privacy/preparation/backfill` | `privacy.execute` | ADMIN_PRIVACY_BACKFILL_REQUESTED | yes |
| POST | `/admin/privacy/requests` | `privacy.execute` | ADMIN_PRIVACY_REQUEST_RECORDED | yes |
| POST | `/admin/privacy/requests/{public_id}/assign` | `privacy.execute` | ADMIN_PRIVACY_REQUEST_ASSIGNED | yes |
| POST | `/admin/privacy/requests/{public_id}/execute-deletion` | `privacy.execute` | ADMIN_PRIVACY_DELETION_INITIATED | yes |
| POST | `/admin/privacy/requests/{public_id}/status` | `privacy.execute` | ADMIN_PRIVACY_REQUEST_STATUS_CHANGED | yes |
| POST | `/admin/role-changes` | `users.role.assign` | ADMIN_ROLE_CHANGE_REQUESTED | yes |
| POST | `/admin/role-changes/{public_id}/approve` | `users.role.assign` | (built in service) | yes |
| POST | `/admin/role-changes/{public_id}/cancel` | `users.role.assign` | ADMIN_ROLE_CHANGE_CANCELLED | yes |
| POST | `/admin/role-changes/{public_id}/reject` | `users.role.assign` | ADMIN_ROLE_CHANGE_REJECTED | yes |
| POST | `/admin/security/alerts/{public_id}/acknowledge` | `security.manage` | SECURITY_ALERT_ACKNOWLEDGED | yes |
| POST | `/admin/security/alerts/{public_id}/resolve` | `security.manage` | SECURITY_ALERT_RESOLVED | yes |
| POST | `/admin/security/incidents` | `incidents.manage` | SECURITY_INCIDENT_CREATED | yes |
| POST | `/admin/security/incidents/{public_id}/status` | `incidents.manage` | SECURITY_INCIDENT_STATUS_CHANGED | yes |
| POST | `/admin/security/incidents/{public_id}/tickets/link` | `incidents.manage` | SECURITY_INCIDENT_TICKET_LINKED | yes |
| POST | `/admin/security/incidents/{public_id}/tickets/unlink` | `incidents.manage` | SECURITY_INCIDENT_TICKET_UNLINKED | yes |
| POST | `/admin/security/incidents/{public_id}/update` | `incidents.manage` | SECURITY_INCIDENT_UPDATED | yes |
| POST | `/admin/step-up` | `users.role.assign` | (built in service) | in service |
| POST | `/admin/support/tickets/{ref}/assign` | `support.manage` | ADMIN_SUPPORT_TICKET_ASSIGNED | yes |
| POST | `/admin/support/tickets/{ref}/notes` | `support.note` | ADMIN_SUPPORT_INTERNAL_NOTE_CREATED | yes |
| POST | `/admin/support/tickets/{ref}/priority` | `support.manage` | ADMIN_SUPPORT_TICKET_PRIORITY_CHANGED | yes |
| POST | `/admin/support/tickets/{ref}/reply` | `support.reply` | ADMIN_SUPPORT_REPLY_SENT | yes |
| POST | `/admin/support/tickets/{ref}/status` | `support.manage` | ADMIN_SUPPORT_TICKET_STATUS_CHANGED | yes |
| POST | `/admin/users/{user_id}/plan` | `subscriptions.manage` | ADMIN_SUBSCRIPTION_ASSIGNED | yes |
| POST | `/admin/users/{user_id}/sessions/revoke` | `users.sessions.revoke` | ADMIN_SESSIONS_REVOKED | yes |
| POST | `/admin/users/{user_id}/status` | `users.manage` | ADMIN_ACCOUNT_STATUS_CHANGE | yes |
| POST | `/admin/workspaces/{workspace_id}/members` | `workspaces.manage` | ADMIN_WORKSPACE_MEMBER_ADDED | yes |
| DELETE | `/admin/workspaces/{workspace_id}/members/{user_id}` | `workspaces.manage` | ADMIN_WORKSPACE_MEMBER_REMOVED | yes |
| POST | `/admin/workspaces/{workspace_id}/members/{user_id}/role` | `workspaces.manage` | ADMIN_WORKSPACE_MEMBER_ROLE_CHANGED | yes |
| POST | `/admin/workspaces/{workspace_id}/plan` | `subscriptions.manage` | ADMIN_SUBSCRIPTION_ASSIGNED | yes |

## 26. Audit fail-closed result
Sensitive writes stage their audit row in the SAME transaction (`_stage` / `_stage_audit`); a forced audit failure rolls the mutation back. Per family, the forced-failure rollback test: user/access (W10.1), workspace (W10.2), support (W10.3), plans/subscriptions (W10.4), billing (W10.5), integrations (W10.6), AI governance (W10.7), knowledge (W10.8), privacy/legal (W10.10), flags/config (W10.11), security/incidents/role approval (W10.13), and jobs (added in W10.14: `test_jobs_admin_enqueue_rolls_back_when_the_audit_row_cannot_be_written`). Documented exception: a failed authorization (denial) audit is best-effort because no privileged state mutation occurs. `/admin/step-up` audits inside `StepUpService` (success/failure). Where a mutation has an external side effect it runs as an idempotent W10.9 job (refunds, deletions, indexing): the request is audited and atomic and the job is replay-safe.

## 27. Audit immutability
Direct DELETE and arbitrary UPDATE on `audit_events` and `incident_events` are rejected by DB triggers (W10.13); only `actor_user_id` value-to-NULL passes (account-deletion anonymisation). Export is bounded (<=90 days, <=5,000 rows), needs `platform.audit.export` and a reason, and is itself audited. PostgreSQL trigger DDL is rendered and unit-checked only, never claimed live-executed; no DBA/superuser tamper-proofing claim.

## 28. Authorization / entitlement / billing separation
Authorization (`require_permission`), technical capability (`/capabilities`, flags), entitlement (`EntitlementService`: one authority, Basic fallback, workspace only when explicit) and billing are separate. A role cannot grant product entitlement (a candidate and a platform administrator both resolve to Basic with identical values: manual QA 18); Admin page access, flags and billing status cannot grant entitlement (static guards plus the W10.4/W10.5/W10.11 tests).

## 29. Billing non-interference
Billing code never touches subscriptions, entitlements or the tier (static guard on code with comments stripped; `test_billing_never_changes_entitlements_subscriptions_or_tier` and `test_billing_modules_never_touch_subscriptions_entitlements_or_the_tier`, re-run as manual QA 19). Failed payments, past-due invoices, refunds, provider cancellation and term changes change billing metadata only.

## 30. Mock/live truthfulness
| Capability | Current implementation | Mock/live status | Production validated? | Admin copy truthful? |
|---|---|---|---|---|
| Billing | `BillingProvider` + `MockBillingAdapter`, mirrored mock records, mock MRR/ARR | MOCK only; disabled outside dev/test | No | Yes: "MOCK BILLING - NOT LIVE" |
| SecretStore | read-only environment adapter | environment-managed; no writable store | No (no production vault) | Yes |
| OpenRouter / model provider | governed catalogue; deterministic evaluation; manual bounded probe | no live calls in qualification | Not validated live | Yes |
| Google OIDC | code present | not live validated | No | Yes |
| Redis rate limiter | adapter present | in-memory is the default; distributed NOT live | No | Yes |
| Email | provider setting; memory sender in tests | not live validated | No | Yes |
| Incident paging | none (in-app alerts only) | not built by design | n/a | Yes |
| Jobs | DB-backed queue + separate worker | SQLite claim path exercised; PostgreSQL SKIP LOCKED path present | PostgreSQL test skipped (needs a disposable `TEST_POSTGRES_URL`) | Yes |
| PostgreSQL concurrency proof | W10.9 claim test | skipped here | No | Yes |
| PostgreSQL audit-trigger proof | DDL rendered/unit-checked | not executed live | No | Yes |
| Knowledge scanning/parser | scan + parse pipeline; ClamAV adapter | bounded/manual only | Not validated live | Yes |

## 31. Integrations boundary
Code-defined registry of 9 integrations; no arbitrary URL; manual bounded tests only (the OpenRouter probe generates no model content; no polling daemon); no secret echo; Google OIDC code-present/not live; Redis distributed limiting not live; environment SecretStore read-only. 0 real probes were run.

## 32. AI governance
Catalogue code-defined (Fast/Balanced/Advanced map to luna/terra/sol); immutable versioned hash; validate/evaluate/approve/activate lifecycle; distinct second approver; production needs staging evidence; server-authoritative environment; fail-closed resolver; rollback; no browser-supplied environment or model slug; a `null` tunable inherits the true runtime default while an explicit number is an exact override; no deterministic Evaluation Specialist (scoring stays model-produced and schema-validated); 0 live model calls.

## 33. Knowledge governance
Approval-first ingestion (scan, parse, review, approve, index job, explicit activate); authority 1/2/3; provenance/licence gates; SQL active-set allowlist; deterministic replay-safe chunk ids; 7 KB languages (Russian is NOT a KB language and NOT an official ESCO language); no candidate content in the governed KB.

## 34. Jobs
DB-backed queue, separate worker, no Redis/Celery/RabbitMQ/Kafka, PostgreSQL `SKIP LOCKED` and SQLite atomic-claim paths, leases, heartbeat, crash reclaim, bounded retry with no sleep, code-defined handlers (no shell or arbitrary function), idempotent handlers. The PostgreSQL claim test stays skipped without `TEST_POSTGRES_URL`.

## 35. Privacy / legal
Durable privacy-request queue; account deletion reuses `AccountDeletionService` (no second engine); preparation-run ownership index with no checkpoint scan; legal version registry; recorded acceptances (no back-fill, no IP/device); owner-scoped candidate export; deletion complete for the documented application-controlled scope with no backup overclaim.

## 36. Flags / config
Durable DB pause (per environment, revision, fail closed, five fixed capabilities, Practice not newly pausable, Admin/privacy/legal recovery and the worker never paused). Exactly two approved restriction-only flags with durable environment overrides; an outage fails OFF; flags never grant authorization, entitlement or billing. No generic config editor.

## 37. Reporting
Aggregates only, minimum cohort 5 (an engineering control, not anonymisation), suppressed values null, no drilldown or candidate content, unknown cost is not zero, incomplete coverage explicit, AI usage not double counted, mock commercial reporting with no currency summation and no fabricated churn, read-only.

## 38. Security / incidents
Typed security events (no IP/device/user-agent/email), deterministic burst rules only (advanced anomaly detection not claimed), bounded audited export, DB audit guards, governed incidents with append-only history and identifier-only ticket links, in-app alerts for three supported categories, no external paging.

## 39. Role governance
Direct role route absent. Two-person flow: requester holds `platform.users.role.assign` and steps up; target != requester; durable request; a distinct approver who currently holds the permission and steps up; approver != requester and != target; requester/approver status and permission re-checked; target role re-read; stale request rejected; last-platform-admin guard; approval + role + audit atomic; replay idempotent; step-up is password re-authentication for 5 minutes bound to the session; OIDC-only fails closed; no MFA claim. The full W10.13 matrix is re-run unchanged by the backend suite.

## 40. No break-glass
0 break-glass permission, table, route or code.

## 41. No impersonation
0 impersonation / view-as / act-as capability.

## 42. IDOR result
Admin metadata access is explicitly permissioned; candidate endpoints remain owner-scoped; ids in the matrix probes (placeholder `0`) never bypass permission or ownership. Support, workspace, privacy, subscription, billing, incident and role-request identifiers are covered by the W10.2-W10.13 domain suites run in the full backend.

## 43. Malformed-input result
Unknown enums, malformed public ids, stale revisions, missing reasons, and arbitrary roles/integrations/models/flags/capabilities are rejected by the domain suites; no generic config-mutation endpoint exists (evaluator).

## 44. HTTP-method audit
Admin routes: 77 GET (read-only; no GET handler writes, enqueues or builds an audit row: evaluator), 63 POST, 4 PATCH, 2 DELETE, 1 PUT (all governed mutations; 70 mutating routes, each audited in its handler or service). Audit export stays a POST by design.

## 45. Partial / deferred capability matrix
The capability matrix was reconciled row by row (53 rows): COMPLETE 33; PARTIAL 13 (release/model-profile visibility, workspace deactivation not built, support attachments and live diagnostics, plan pricing, mock refunds without coupons, provider status panel, knowledge foundation/ingestion/reindex gaps, job dead-letter, DSAR admin export); UNVALIDATED LIVE 2 (integration probes, SecretStore); NOT BUILT BY DESIGN 2 (generic config editor, break-glass); POST-CAPSTONE 1 (universal operator search); OUT OF SCOPE 1 (browser deployment control); IN PROGRESS 1 (this qualification). Known not-built or not-live: support attachments (partial), workspace deactivate (not built), generic config editor (not built by design), coupons (not built), production vault (not live), external paging (not built), universal search (not built), live billing (not built), distributed Redis limiting (not live), Google OIDC (code present, not live validated), PostgreSQL W10.13 trigger execution (not performed).

## 46. Findings closure
| Finding | Status | Evidence |
|---|---|---|
| SEC-W10-01 | CLOSED | W10.2, PR #113 |
| SEC-W10-02 | CLOSED | W10.1, PR #110 |
| SEC-W10-03 | CLOSED | W10.1, PR #110 |
| SEC-W10-04 | CLOSED | W10.10, PR #122 |
| SEC-W10-05 | CLOSED | W10.11, PR #125 |
| SEC-W10-06 | CLOSED | W10.1, PR #110 |
| PRIV-W9-01 | CLOSED | W10.10, PR #122 |
| PRIV-W9-02 | CLOSED | W10.10, PR #122 |
| ROLE-W10-01 | CLOSED | W10.14 (this wave): a decision, not a permission change |

No new blocker was found. Documentation reconciliation (no behaviour change): W10.0 recorded as PR #109, W10.2 as PR #113, and the W10.13 corrections.

## 47. W10.13 dev-DB disclosure inheritance
Inherited verbatim: **disclosed contamination with stable post-incident qualification baseline** (W10.13: one bare evaluator run created empty W10.12/W10.13 schema objects in the developer DB; the original fingerprint `64d66596...` was not preserved; 141 to 224 schema objects; no restoration attempted). W10.14 starts from that post-incident baseline.

## 48. W10.14 isolation
Start baseline (post-incident): dev DB `8cd20d503943f090f890e97c6ca55709949a76d3` (224 schema objects), checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`, Chroma `6357c057606273f313b408cc7f144390453a0832`, research cache `d6708df40dab369b4368c1b4deb4dc680c14d0b1`, `evaluations/` `67259aba185daa495f8bf8958e1c905fd086b2be`. Hardening: every CI evaluator that touches the app or a database now imports `tests.conftest` first (13 existing evaluators were hardened, and the new evaluator verifies all of them): temp `DATABASE_URL`, `.env` disabled, non-temp engines fail fast. Final result: all six protected stores are UNCHANGED against the post-incident W10.14-start baseline after the complete qualification (full backend, Vitest/build, Playwright, all 40 CI evaluators, manual QA, performance runs, two determinism runs and the fresh-checkout run). This is stability of the disclosed post-incident baseline; it is NOT a claim that the pre-W10.13 developer DB is restored or equal.

## 49. Migration result
No migration added (head stays `0025`). Isolated temp-database qualification (fresh base to 0025, 0024 to 0025 upgrade, downgrade/round trip, W10.13 constraints and audit triggers) is covered by the migration tests in the full backend run; the developer DB was never migrated.

## 50. Fresh-checkout result
A detached `git worktree` of the committed tree (no `.env`, no developer DB, no checkpoint, no Chroma, no research cache; only tracked data) ran the complete backend suite and all CI evaluators: **3121 passed, 10 skipped, 0 failed** (the 4 known skips plus 6 tests that skip only because large untracked local datasets - O*NET, ESCO, OOH, BLS, CLSSI, Eurostat, DigComp - are absent from a clean checkout) and **40 of 40 evaluators passed**; the worktree stayed clean and created no developer store. Scope boundary: the frontend gates (Vitest, typecheck, lint, build, Playwright) were run in the primary working tree, not in the fresh checkout (`node_modules` is not installed there); CI installs and runs them from a fresh clone.

## 51. Two-run determinism
The integrated evaluator and the permission-matrix tests were run twice: identical evaluator output (41 checks), identical generated-matrix hash (`dfe33b8da0bbdfe7`), identical route count (147), identical permission count (43), identical 21-test result, identical protected-store fingerprints.

## 52. Backend
**3127 passed, 4 skipped, 0 failed, 0 errors** (previous W10.13: 3106; +21 new qualification tests). Skips: (1) live Adzuna integration needs explicit opt-in and credentials; (2) the PostgreSQL W10.9 claim test needs a disposable `TEST_POSTGRES_URL`; (3) the Streamlit component test needs a Streamlit context; (4) the RAGAS adapter test is a conditional skip depending on the installed/runtime condition. No new skip.

## 53. Frontend
Vitest **768 passed** in 89 files (previous 756; +12 navigation-matrix tests); typecheck, lint and production build clean; i18n scanner 0 offenders.

## 54. Playwright
**221 passed** (unchanged; no browser journey was added or changed), no retries or timeout inflation.

## 55. Evaluator
`scripts/eval_admin_qualification.py` (41 checks, in CI, imports `tests.conftest` first).

## 56. CI evaluator total
**40 of 40** CI evaluators pass (39 + the new Admin qualification evaluator; none removed). 13 existing evaluators gained the one-line test-isolation bootstrap.

## 57. Privileged-route coverage
**147** privileged routes (132 `/admin`, 9 `/reviewer`, 4 `/evaluation`, 1 `/knowledge/diagnostics`, 1 `/auth/admin/audit`): 0 new in W10.14, **147 covered, 0 uncovered**; 1,029 route x persona cases (147 x 7); 70 mutating routes, all audited in the handler or the service; 0 direct role-name authorization.

## 58. Manual QA
37 checks on a freshly Alembic-migrated temp database, no provider keys, eight real principals (candidate, platform_admin A and B, support, billing, knowledge, security/privacy, operations). The owner's 36 items map one-to-one onto checks 01-36 (check 19 delegates billing non-interference to the two deterministic billing tests, run isolated; check 18 uses the real `EntitlementService`); check 37 (audit rows free of secret and private sentinels) is an addition. 37/37 passed.

## 59. Accessibility
Deterministic static/component checks: one semantic `h1` header per Admin page, labelled controls, keyboard-operable focus-managed dialogs with Cancel first (`ConfirmDialogBase`), status as text not colour alone, captioned tables, textual form errors. No WCAG certification is claimed. The candidate `/practice` page-level h1 P3 from W9.13 is outside this wave and stays deferred.

## 60. Localization
Admin stays English-only. The hardcoded-English scanner reports 0 offenders; the candidate-facing support and privacy/legal catalogues exist for all 8 locales (manual QA 34). Interface language, Mo conversation language, dictation, document, KB and geography language separation was not changed.

## 61. Performance (single fixture, p50 of 5; not an SLA)
2,000 users and 20,000 audit rows on SQLite: Admin shell 21 ms, users list 6 ms, jobs list 4 ms, reports overview 7 ms, audit page 5 ms, security events page 14 ms.

## 62. Dependencies
No backend or frontend dependency was added or changed.

## 63. Live-call count
0 paid or live calls.

## 64. Final W10 Admin qualification verdict
**ADMIN PLATFORM QUALIFIED** (effective on merge of the W10.14 PR). Every condition of the W10.14 definition held on the exact tree: the candidate reaches no Admin route; every privileged route is permission-gated with 0 uncovered; presets are least-privilege and ROLE-W10-01 is closed without permission expansion; no private candidate-data superuser, no break-glass, no impersonation; secrets are never returned; Support content is domain-scoped; billing stays mock and never grants entitlement; entitlements are deterministic; integration truthfulness, AI governance, knowledge approval, jobs, privacy/legal, flags/config, reporting and security/audit/incident controls are intact; two-person role changes and step-up are preserved; sensitive writes fail closed on audit failure; the audit DB guard works; the migration chain is green; backend, frontend, Playwright and the evaluators are green; fresh-checkout qualification is green; the protected-store baseline is stable; 0 paid/live calls. This does NOT make the product release-candidate-ready: **W11 is required before RC-P10-003**, and the W10.13 dev-DB contamination stays permanently disclosed.

## 65. W11 handoff
Next mandatory phase: **P10B-W11 - Integrated Candidate + Admin Requalification**. RC-P10-003 may be considered only after W11 is green. Carry forward: PostgreSQL job and trigger tests unexecuted live; Google OIDC, Redis limiter, email and any live billing unvalidated/not built; no advanced anomaly detection; support attachments, workspace deactivation and universal search not built; `platform.integrations.secret.rotate` unassigned; the permanently disclosed W10.13 dev-DB contamination.
