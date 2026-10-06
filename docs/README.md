# Documentation map

One place that says where the authoritative description of each topic lives, so documents do not
compete. Rule: **the code is the source of truth; fix documents to match it.** Older per-phase
documents are historical evidence and are labelled where they could be mistaken for current guidance.

| Topic | Canonical source |
|---|---|
| What the product is, candidate journey, current limitations | [../README.md](../README.md) |
| Current architecture (layers, agent, specialists, tools, evaluation, identity, admin, languages) | [sprint4_architecture.md](sprint4_architecture.md) - read its "Current-state overview" first |
| Registered tools (names and count) | `career_tool_registry` in `src/agent/registry.py` (do not hard-code counts elsewhere) |
| Specialists | `src/agent/specialists/registry.py` (three; there is no Evaluation specialist) |
| Product claims (what copy may say; capability matrix C1-C4) | [product/PRODUCT_CLAIMS.md](product/PRODUCT_CLAIMS.md), [capstone/p10/w9/P10B_W9_10_PRODUCT_POSITIONING.md](capstone/p10/w9/P10B_W9_10_PRODUCT_POSITIONING.md) |
| Trust wording and claim matrix | [capstone/p10/w9/P10B_W9_9_TRUST_VISUAL_POLISH.md](capstone/p10/w9/P10B_W9_9_TRUST_VISUAL_POLISH.md) |
| Privacy, data control, retention terminology and limits | [privacy.md](privacy.md), [capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md](capstone/p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md) |
| Identity, authorization, security | [capstone/p1_e1_identity_platform.md](capstone/p1_e1_identity_platform.md), [security.md](security.md) (Sprint 3 prompt-injection design, historical for auth) |
| Knowledge / RAG, sources, authority levels | [knowledge_architecture.md](knowledge_architecture.md), [knowledge_source_catalogue.md](knowledge_source_catalogue.md), [rag.md](rag.md) |
| Localization and language dimensions | [capstone/p3_5_i18n_l10n.md](capstone/p3_5_i18n_l10n.md), [capstone/p10/w9/P10B_W9_7_RUSSIAN_LOCALE.md](capstone/p10/w9/P10B_W9_7_RUSSIAN_LOCALE.md); locale constants `src/locales.py` |
| Opportunities | [capstone/p10/p10b_wave6_opportunity_model.md](capstone/p10/p10b_wave6_opportunity_model.md) |
| Workspaces, sharing, current admin foundations | [capstone/p6_5_workspaces_platform_admin.md](capstone/p6_5_workspaces_platform_admin.md) |
| Admin mock billing and payment administration (W10.5, complete) | [capstone/admin/W10_5_BILLING_PAYMENT_ADMINISTRATION.md](capstone/admin/W10_5_BILLING_PAYMENT_ADMINISTRATION.md) |
| P10B-W11 integrated candidate + Admin requalification and the integrated release acceptance matrix (W11, COMPLETE: merged PR #132; matrix 99 / 88 PASS / 11 ACCEPTED / 0 BLOCKER; RC-P10-003 not yet created) | [capstone/p10/P10B_W11_INTEGRATED_REQUALIFICATION.md](capstone/p10/P10B_W11_INTEGRATED_REQUALIFICATION.md) |
| Admin full qualification, ROLE-W10-01 closed (W10.14, complete) | [capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md](capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md) |
| Admin security, audit and incident management (W10.13, complete) | [capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md](capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md) |
| Admin reporting, analytics and AI economics (W10.12, complete) | [capstone/admin/W10_12_REPORTING_ANALYTICS_AI_ECONOMICS.md](capstone/admin/W10_12_REPORTING_ANALYTICS_AI_ECONOMICS.md) |
| Admin feature flags and safe platform configuration, durable pause (W10.11, complete) | [capstone/admin/W10_11_FEATURE_FLAGS_SAFE_PLATFORM_CONFIGURATION.md](capstone/admin/W10_11_FEATURE_FLAGS_SAFE_PLATFORM_CONFIGURATION.md) |
| Admin AI and model administration (W10.7, complete) | [capstone/admin/W10_7_AI_MODEL_ADMINISTRATION.md](capstone/admin/W10_7_AI_MODEL_ADMINISTRATION.md) |
| Admin privacy and legal administration (W10.10, complete) | [capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md](capstone/admin/W10_10_GDPR_PRIVACY_LEGAL_ADMINISTRATION.md) |
| Admin knowledge base and RAG administration (W10.8, complete) | [capstone/admin/W10_8_KNOWLEDGE_RAG_ADMINISTRATION.md](capstone/admin/W10_8_KNOWLEDGE_RAG_ADMINISTRATION.md) |
| Admin jobs, queues and operational diagnostics (W10.9, complete) | [capstone/admin/W10_9_JOBS_QUEUES_OPERATIONAL_DIAGNOSTICS.md](capstone/admin/W10_9_JOBS_QUEUES_OPERATIONAL_DIAGNOSTICS.md) |
| Admin integrations and API connections (W10.6, complete) | [capstone/admin/W10_6_INTEGRATIONS_API_CONNECTIONS.md](capstone/admin/W10_6_INTEGRATIONS_API_CONNECTIONS.md) |
| Admin plans, subscriptions and entitlements (W10.4, implemented) | [capstone/admin/W10_4_PLANS_SUBSCRIPTIONS_ENTITLEMENTS.md](capstone/admin/W10_4_PLANS_SUBSCRIPTIONS_ENTITLEMENTS.md) |
| Admin customer support and ticketing (W10.3, implemented) | [capstone/admin/W10_3_CUSTOMER_SUPPORT_TICKETING.md](capstone/admin/W10_3_CUSTOMER_SUPPORT_TICKETING.md) |
| Admin users, sessions and workspaces (W10.2, implemented) | [capstone/admin/W10_2_USERS_ACCESS_WORKSPACES.md](capstone/admin/W10_2_USERS_ACCESS_WORKSPACES.md) |
| Admin permission/audit foundation + Command Center (W10.1, implemented) | [capstone/admin/W10_1_ADMIN_FOUNDATION_COMMAND_CENTER.md](capstone/admin/W10_1_ADMIN_FOUNDATION_COMMAND_CENTER.md) |
| Planned admin / support / commercial operations (W10.2+ NOT implemented): architecture, capability matrix, decisions | [capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md](capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md), [ADMIN_CAPABILITY_MATRIX.md](capstone/admin/ADMIN_CAPABILITY_MATRIX.md), [ADMIN_ARCHITECTURE_DECISIONS.md](capstone/admin/ADMIN_ARCHITECTURE_DECISIONS.md) |
| Roadmap and status | [capstone/capstone_phase_plan.md](capstone/capstone_phase_plan.md) |
| Deployment / operations | [operations_deployment.md](operations_deployment.md), [../deploy/](../deploy/) |
| Testing and evaluators | [testing.md](testing.md); `scripts/eval_*.py` are CI/release gates (not candidate-facing evaluation) |
| Capstone evidence | [capstone/](capstone/) |

Historical (Sprint 1-4) material: `legacy_sprint3_*`, `sprint4_*`, `limitations.md`, `project_plan.md`
and similar carry a banner or describe a dated state; do not treat them as current behaviour.
