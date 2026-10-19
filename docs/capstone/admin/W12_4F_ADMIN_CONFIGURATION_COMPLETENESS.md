# W12.4F: Admin Configuration Completeness

**Status: CODE QUALIFIED OFFLINE (engineering).** Not production ready, not commercially authorized, not human qualified, no live provider contacted, and **not a pass against the unchanged 95% product-coverage gate** (developer-local 386/412, clean checkout 258/412, both BELOW GATE). All 12 rollout and billing gates are False, Compensation V2 is disabled, Premium is not activated, server speech is not activated, no migration (Alembic head `0039_speech_governance`), no new permission (registry 44).

- Branch `feat/w12-4f-admin-configuration-completeness`, from `main` `360c0fb` (PR #192, W12.4E, merged; contains `2cb3902`).
- This is a completeness and correction wave over the existing Admin platform. It is not a redesign, not a commercial activation and not a speech, source or billing activation.

## 1. Starting architecture (verified from the code, not assumed)
- 20 destinations in `frontend/lib/admin/capabilities.ts` (Overview, Users, Workspaces, Plans, Support, Review/Diagnostics, Security, Audit, Billing, Privacy, Legal, Knowledge, Reports, Configuration, Feature flags, AI and models, Jobs, Integrations, Provider status) after W12.4F adds Speech. Review/Diagnostics (`/review`) sits outside the Admin shell (W12.5 finding F-01, not changed here).
- 170 permission-gated admin routes (`src/api/admin_route_invariant.py`), 44 code-defined permissions, `platform_admin` as owner/orchestrator, six least-privilege specialist presets, no custom roles, no impersonation, no break-glass, step-up for secrets, two-person approval for role changes and price/refund flows.
- Durable configuration pattern used everywhere it exists (pause, flags, AI configuration, speech): expected revision, required reason, same-transaction audit, fail-closed when the control-plane state cannot be read.
- SecretStore (W12.4B): environment adapter plus opt-in encrypted writable store; write-only; master key deployment-managed.
- Starting baselines: Alembic head `0039_speech_governance` (one head), backend 4,813 passed / 4 skipped (W12.4E), frontend 1,057 tests, 12 gates False.

## 2. Capability inventory
`ADMIN_CAPABILITY_MATRIX.md` is the row-level inventory (54 rows at the start of this wave, 56 after). Using its own vocabulary, the starting rows were: COMPLETE 34, PARTIAL 13, UNVALIDATED LIVE 2, CODE QUALIFIED (email) 1, NOT BUILT BY DESIGN 2, POST-CAPSTONE 1, OUT OF SCOPE 1. Per domain requested by the brief, with the audit result (route, service, storage, consumer, permission, step-up, audit, limits):

| Domain | Admin location | Backend and storage | Runtime consumer | Permission / step-up / audit | Status (derived vocabulary) |
|---|---|---|---|---|---|
| Platform administration, overview | `/admin` | `admin.py` `/home`, `/readiness` (new); derived | Command Center | overview.read | OPERATIONAL (code-defined) |
| Users and accounts | `/admin/users` | `admin_user_repository`; accounts | auth | users.read/manage; audit | OPERATIONAL |
| Roles and permissions | `/admin/users/[id]`, `/admin/security` | code presets; role requests | `require_permission` | role.assign, step-up, two-person; audit | OPERATIONAL (code-defined) |
| Sessions and authentication | `/admin/users/[id]` | session revoke | auth | sessions.revoke; audit | OPERATIONAL |
| Support operations | `/admin/support` | support tables | candidate Contact Support | support.*; audit | PARTIAL (attachments deferred) |
| Workspaces | `/admin/workspaces` | workspace tables | sharing | workspaces.*; audit | PARTIAL |
| Subscriptions and entitlements | `/admin/plans` | plan versions, entitlement service | gating | plans.*; audit | PARTIAL (no price here) |
| Billing | `/admin/billing` | mock provider, Stripe foundation | none live | billing.*; audit | MOCK (live billing disabled) |
| Email delivery | `/admin/integrations/email_brevo` | integration registry, bounded test | email adapter | integrations.*; audit | PARTIAL, LIVE UNVERIFIED |
| Identity configuration | `/admin/integrations/google_oidc` | registry | Google OIDC | integrations.read | PARTIAL, LIVE UNVERIFIED |
| Integrations | `/admin/integrations`, `/admin/providers` | code registry (10 integrations) + state | adapters | integrations.*; secret.rotate + step-up | PARTIAL (environment-managed runtime) |
| SecretStore | `/admin/integrations/[code]` | encrypted store + env fallback | adapters | secret.rotate + step-up; audit | OPERATIONAL (master key deployment-managed) |
| AI models and routing | `/admin/ai` | AI config versions, hash-bound evaluation | model resolver | ai.*; two-person activation; audit | PARTIAL (no live call; no arbitrary model or endpoint) |
| Knowledge base and source governance | `/admin/knowledge` | governed sources and versions | retrieval | knowledge.*; audit | PARTIAL; source qualification DEFERRED |
| Speech providers | `/admin/speech` (new page) | `speech_governance` (0039) | Dictation, Voice Playback, speech routes | flags.read / config.manage; audit | PARTIAL, OFFLINE VALIDATED, LIVE UNVERIFIED, DEFERRED |
| Feature flags | `/admin/flags` | durable overrides | flag consumers | flags.*; audit | OPERATIONAL |
| Platform pause | `/admin/configuration` | durable pause | candidate 503 | config.manage; audit | OPERATIONAL |
| Background jobs | `/admin/jobs` | job tables | worker | jobs.*; audit | PARTIAL (no dead-letter state) |
| Security and incidents | `/admin/security` | audit projection, incidents | none | security.*, incidents.manage | OPERATIONAL (in-app only) |
| Privacy and consent | `/admin/privacy`, `/admin/legal` | durable queue, legal versions | account deletion | privacy.*, legal.manage | PARTIAL (no admin export) |
| Audit logs | `/admin/audit` | append-only, DB triggers | none | audit.read/export | OPERATIONAL |
| Reporting and analytics | `/admin/reports` | aggregates | none | reports.read | PARTIAL (churn unavailable) |
| Operational diagnostics | `/admin` health, `/admin/jobs` | cheap checks | none | overview.read | PARTIAL (internal checks only; no provider polling) |
| Release readiness | `/admin` Release, migration status, `/admin/readiness` | env-injected build info, Alembic head | none | overview.read, releases.read | PARTIAL; not a production-readiness claim |

## 3. Configuration ownership matrix
| Setting | Owner | Why |
|---|---|---|
| Pause switches, feature flags (restrict only), AI configuration versions, speech selection and policy | A. Platform Admin | Operational, typed, non-secret, dynamically consumed, durable, audited |
| API keys, tokens, signing secrets | B. SecretStore (write-only, step-up) | A secret; never readable |
| Environment, provider choice, `EMAIL_PROVIDER`, sender, OIDC client, Redis, scanner, process settings | C. Deployment infrastructure | Needs deployment approval and a restart; no Admin workaround exists |
| Source authority, licence, qualification, activation | D. Source-governance workflows | Human review and licensing required |
| Provider account, eligibility, pricing, plans on the provider side | E. External provider administration | Outside the platform |
| Live billing, checkout, webhooks, reconciliation scheduler, paid entitlement policy, Premium activation, price | F. Commercial activation workflow (code constants, owner approval) | Commercial and legal decision |
| Speech authorization constants, hosting, weights, genuine validation, recording client | G. Post-submission development (owner decision 2026-10-19) | Deferred |
| The 12 rollout and billing gates | F. code constants | Deliberately no Admin control |

Items that are correctly environment-managed were left environment-managed; no Admin workaround was added.

## 4. Existing controls (verified, preserved)
Pause, flags, AI configuration lifecycle, integrations registry with bounded manual tests, SecretStore, plans and subscriptions, mock billing operations, knowledge workflow, jobs, privacy and legal, reports, security, audit. Their existing tests and evaluators were run unchanged (section 23).

## 5. Missing controls discovered
| ID | Severity | Evidence | Root cause | Expected behaviour | Acceptance test | Disposition |
|---|---|---|---|---|---|---|
| G-1 | P1 (Admin operational blocker) | `GET/PUT /admin/speech` existed (W12.4E) but no Admin page, navigation entry or client method; grep of `frontend/app/admin` and `components/admin` found none | W12.4E delivered the backend only; the Admin frontend was not in its scope | An authorized administrator can read speech governance and change policy with revision and reason, and sees that server speech is not active | `admin-speech-w12-4f.test.tsx` (8 tests), `test_speech_configuration_is_effective_at_the_runtime_consumer` | IMPLEMENTED |
| G-2 | P2 (configuration completeness) | `/admin/providers` returned `architecture: browser_web_speech` and no server-side state | Provider panel predates W12.4E | The panel also reports the governed server state (authorization, operational, genuine validation) without claiming it runs | `test_provider_panel_reports_server_speech_without_claiming_it_runs` | IMPLEMENTED (additive field) |
| G-3 | P2 | The Command Center had counts but no per-capability status vocabulary; readiness was fragmented across provider, billing, knowledge and speech endpoints | No single derived view | One derived, permission-aware view using the required vocabulary, never inferring operational from configuration | 9 backend tests, 2 frontend tests | IMPLEMENTED |
| G-4 | P3 / W12.5 | F-01 Review/Diagnostics outside the shell; F-04 Integrations mobile overflow; F-05 Billing form focus | UX | n/a | n/a | TRANSFERRED to W12.5, not closed |
| G-5 | DEFERRED | Speech activation, licensing, hosting, genuine validation | Owner decision 2026-10-19 | n/a | n/a | DEFERRED (section 7) |
| G-6 | DEFERRED | Email live delivery, Stripe sandbox, source qualification | Need owner authorization, accounts or human review | n/a | n/a | DEFERRED, unchanged |

Considered and deliberately not built: a generic system-configuration editor (W10.11 already concluded none qualifies), a second provider registry, a second feature-flag subsystem, routes for non-existent capabilities, and any control for the 12 gates.

## 6. Implemented corrections
1. `src/application/admin_readiness.py` and `GET /admin/readiness` (read-only, `platform.overview.read`): rows derived at request time from the integration registry, SecretStore state, speech runtime, billing operations, AI and knowledge statistics, pause and flag services and the gate constants. Each row has a primary `status`, independent `qualifiers`, `ownership`, `basis` (runtime or code), `evidence` and `limitations`. A row is shown only if the caller holds its domain read permission. A source that fails to read is `CONFIGURED_BUT_UNAVAILABLE` with the `UNAVAILABLE` qualifier and no error text. No persistent status enum, table or provider call was added.
2. Admin Speech page (`/admin/speech`, `SpeechView`) and navigation entry (visible with `platform.flags.read`; editing needs `platform.config.manage`).
3. `ServerSpeechStatus` in the provider panel (additive; `authorization_state` is a fixed label).
4. Command Center shows the readiness table (`CapabilityReadiness`).
5. Test and evaluator maintenance for the new route and destination (admin matrix domain map, role fixture, destination counts), each a legitimate consequence and none a weakened expectation.

## 7. Deferred functionality (owner decisions)
- **W12.4E remaining activation work (decision 2026-10-19):** 18 items recorded in `p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md` (Whisper self-hosted versus hosted, hosted data-processing review, hosting, weights and placement, sizing, genuine Whisper and Kyutai validation, Kyutai gated weights, licence, attribution, per-voice licences, Dutch TTS qualification, server-side recording client, human quality validation, authorization flag activation, production speech qualification, browser disclosure legal review, response-origin hardening, timeout and cancellation hardening). Dependencies and restrictions preserved; nothing marked complete.
- **P10C-F remaining work:** DEFERRED UNTIL AFTER CAPSTONE SUBMISSION (2026-10-18). **P10F:** DEFERRED UNTIL AFTER CAPSTONE SUBMISSION. Both unchanged here.
- Completed offline engineering is preserved. Commercial authorization remains outstanding. Live-provider testing remains outstanding. Capstone submission does not constitute production deployment approval. The decisions change scheduling, not the safety requirements.

## 8. Accurate readiness states
The vocabulary is derived, never stored. Statuses: OPERATIONAL, CONFIGURED_BUT_UNAVAILABLE, ENVIRONMENT_MANAGED, MOCK, READ_ONLY, PARTIAL, NOT_BUILT. Qualifiers: OFFLINE_VALIDATED, LIVE_UNVERIFIED, DEFERRED, UNAVAILABLE, DISABLED. Rules enforced by tests: configuration present is never OPERATIONAL; a passing mock or fixture is never live; credentials present is never ready; a provider acceptance is never delivery; the speech rows are never OPERATIONAL while the authorization constants are False; billing is MOCK while live billing is disabled; the gates row is READ_ONLY with "12 of 12 gates are False". The view carries the sentence that it is not a statement that the platform is production ready.

## 9. Runtime configuration effectiveness
`test_speech_configuration_is_effective_at_the_runtime_consumer` walks the full lifecycle against a temporary database: starting revision 0 read through Admin and seen by the candidate runtime consumer (`/speech/capabilities`, which the Dictation and Voice Playback controls read); an unauthorized specialist change refused with the revision unchanged; an authorized change returning revision 1 and read back; the candidate consumer then reports `browser_tts_allowed: false`; exactly one audit event naming only the changed setting; unrelated settings unchanged; a stale revision refused (409); invalid values refused (422) with no audit written; restart persistence proven with a brand-new service over the same database; enabling a provider recorded as a decision while readiness stays not operational and the candidate sees no server languages. Pause, flags and AI configuration already had their lifecycle proofs (W10.11, W10.7) and were re-run unchanged.

## 10. RBAC results
Registry 44, unchanged. `GET /admin/readiness` requires `platform.overview.read`; a candidate is refused (403); a support specialist sees only the rows for domains they can read (RBAC and gates, not billing, integrations, SecretStore, speech, AI or knowledge). Speech reads need `platform.flags.read` and changes `platform.config.manage` (a support specialist and a candidate were refused). The Admin route invariant and persona matrix evaluator (`eval_admin_qualification`, 45 checks) pass with the new route mapped to the overview domain. The frontend role fixture is generated from code and now lists `/admin/speech` for exactly the personas holding `platform.flags.read`.

## 11. Audit results
`admin.speech_config_changed` carries the environment, the names of the settings changed and the old and new selection values, with the actor, request id and reason; no audio, transcript, secret or path. The readiness view is read-only and writes nothing (static test: no `.add(`, `.commit(` or network call in the module). Failed attempts write no audit row.

## 12. SecretStore boundaries
Unchanged. The readiness view reports only the store state (writable, read-only, unavailable with a bounded reason). It never reads a secret value (`get_for_runtime` is not referenced; checked by the integrations evaluator) and tests assert no key-like string, path or traceback appears in the response.

## 13. AI provider configuration
Unchanged and verified read-only through `eval_admin_ai_models`. Controls: Admin-managed (governed configuration versions with hash-bound deterministic evaluation, second approver, staging before production, rollback), environment-managed (provider keys, base URLs, pricing), read-only (catalogue). Readiness shows PARTIAL with OFFLINE_VALIDATED and LIVE_UNVERIFIED. No arbitrary model name or endpoint, no pricing change, no paid routing change, no live call.

## 14. Speech governance
Verified that Admin describes: Whisper STT implemented and fixture-tested, genuine execution NOT VERIFIED, activation DISABLED; Kyutai Pocket TTS implemented and fixture-tested, genuine execution NOT VERIFIED, activation DISABLED; Dutch server TTS UNVERIFIED; Russian EXCLUDED; browser speech the governed fallback. No weights installed, no download, no live execution, no recording client, hosted Whisper not authorized, self-hosted Whisper and Kyutai not activated, cloning off, language eligibility unchanged (seven languages). The page keeps the five distinctions separate: provider capability, Admin configuration, owner authorization, runtime readiness, actual execution.

## 15. Billing governance
Verified through the existing readiness and evaluator: provider abstraction with the mock provider, Stripe Managed Payments foundation not connected, live billing, checkout, webhook, provider reads, reconciliation scheduler and paid entitlement policy all disabled by code constants, no Stripe call, no price change, no entitlement change. Admin shows MOCK, not live. The readiness row says "Simulated billing: no payment provider is contacted and no real money moves" and that commercial activation is outstanding. Nothing assumes the planned Ask4Mo UG exists or that commercial policy is approved.

## 16. Email and identity configuration
Verified: Brevo path is real code never exercised live by CI; the repository records no successful authorized live send, so live delivery stays UNVERIFIED; accepted by the provider is not delivered (no delivered or bounced state exists). Google OIDC backend support present, end-to-end sign-in not validated. Configuration is environment-managed. No email was sent, no identity provider changed, no credential exposed.

## 17. Knowledge Base governance
Verified through `eval_admin_knowledge`: governed sources and immutable versions, human approval, indexing job, explicit activation, retirement, retrieval test. P10C-G, P10D and P10D-R1 protections re-run and pass. No source acquired or qualified, no reviewer appointed, Compensation V2 disabled, no isolated US evidence promoted, no UK compensation activated.

## 18. Feature flags
Durable per-environment overrides that can only restrict, expected revision, audit, fail closed; pause switches durable and shared. Readiness shows both OPERATIONAL (offline validated). The 12 gates are code constants with no Admin control by design and all are False (tested).

## 19. Operational diagnostics
The existing Command Center (build, migration match, health ping, rate-limit mode, pause) is retained. The readiness table adds the missing per-domain status, evidence, limitation and ownership. No provider is polled; "healthy" still requires a recorded manual test. No filesystem path is shown.

## 20. Security findings
- Readiness and speech responses carry no secret, path, stack trace or candidate content (tested; the evaluator's banned-field list caught one field name, `authorization`, which was renamed `authorization_state`).
- No new write path other than the existing audited speech PUT; the readiness module has no write, network or subprocess call (static test).
- Tenant isolation, session authorization, step-up, two-person approval and audit hardening unchanged.
- Remaining known limitations (not security regressions): synthesis authorizes by text not reference and engine timeouts cannot kill a running thread (W12.4E, deferred items 17 and 18).
- No Critical or High finding was opened by this wave.

## 21. Frontend changes
New `SpeechView`, `app/admin/speech/page.tsx`, `CapabilityReadiness`; one Command Center line; one navigation entry; types and two client methods. Keyboard operable, labelled controls, a reason-required confirmation dialog (existing `ActionDialog`), stale-revision and error text shown in the dialog without losing the draft, view-only mode for roles without `platform.config.manage`, Russian never selectable, no free-form field. No visual redesign. W12.5 findings F-01, F-04, F-05 and the remaining W12.2 follow-ups are untouched.

## 22. Database changes
None. No migration; one Alembic head `0039_speech_governance`.

## 23. Regression testing
Recorded in the final engineering report with exact results (backend 4,828 tests collected, full run exit 0 (the main run had no PostgreSQL server, so the PostgreSQL-gated tests skip there; the same gated modules run separately against an isolated throwaway PostgreSQL 16 cluster: 197 passed, 1 skipped); frontend 109 files, 1,065 tests passed, typecheck clean, lint 0 errors (2 pre-existing warnings in untouched test files), build OK, Playwright 405 passed (403 existing plus 2 new admin speech specs); Ruff clean; `git diff --check` clean; all 16 admin and platform evaluators PASS including `eval_admin_qualification` 45 checks; speech evaluator PASS; `eval_release_matrix` PASS; P10C-G, P10D, P10D-R1 and product-coverage guard as recorded there). New tests: 11 backend (`tests/test_admin_completeness_w12_4f.py`), 8 frontend (`frontend/tests/admin-speech-w12-4f.test.tsx`) and 2 browser (`frontend/e2e/admin-speech.spec.ts`). A browser run caught one real defect in the first version of the readiness panel (a malformed response crashed the Command Center); the panel now renders nothing for a malformed or empty response and a test covers it.

## 24. Known limitations
- Readiness is derived from configuration and recorded evidence; it is not live health monitoring and does not poll providers.
- Several rows (RBAC, gates) have `basis: code`: they describe code constants, not runtime measurements.
- Speech: genuine Whisper and Kyutai execution NOT VERIFIED; production activation DISABLED (deferred).
- Email live delivery UNVERIFIED; Stripe not connected; source qualification deferred.
- The Provider status page and the Integrations page overlap in purpose; consolidating them is a W12.5 UX decision.

## 25. W12.5 handoff
Carry forward unchanged: F-01 (Review and Diagnostics outside the Admin shell), F-04 (Integrations mobile overflow), F-05 (Billing form focus and off-screen form behaviour), and the remaining accepted W12.2 follow-ups. None is closed by W12.4F. New notes for W12.5: the Speech page and the readiness table should be included in the responsive and keyboard walkthrough.

## 26. P10E dependencies
Unchanged: authorized paid semantic-embedder run and the model-quality contract, source-backed coverage re-measurement after real source qualification, native review of non-English routing. W12.4E speech activation work is excluded from P10E's mandatory pre-submission scope (owner decision 2026-10-19); P10E's other activities keep their authorization requirements.

## 27. Post-submission backlog
P10C-F remaining activities, P10F human validation, and the 18 W12.4E activation items (`p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md`). Roadmap sequence unchanged: W12.4F, W12.5, P10E, integrated requalification, RC-P10-004, AC-24, P11. AC-24 stays PARTIAL. RC-P10-004 not created. P11 not started.
