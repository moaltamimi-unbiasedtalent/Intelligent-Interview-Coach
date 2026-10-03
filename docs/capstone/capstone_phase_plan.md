# Ask4Mo Capstone — Phase Plan (P0–P11 / E0–E8)

Refines the reference plan against verified repository dependencies. Each phase: objective, scope,
dependencies, expected changes, gates, STOP/must-not-start. Dates are targets (24 Sep → 20 Oct), not
effort guarantees; feasibility checkpoints 4 Oct / 8 Oct / 13 Oct freeze. Do not relabel incomplete
work as deferred to manufacture a verdict.

## Status and revised sequence (reconciled at `main` d6c3493, after W9.7B)

This section is the **single canonical forward-looking roadmap**. The P0-P11 text below it is preserved as the
original plan; where they differ, this section wins. Do not create competing master plans; per-wave documents
(`docs/capstone/p10/w9/*`, `docs/capstone/admin/*`) are detail under this roadmap.

**Naming convention (history is not rewritten).** The original "P10 - Capstone evaluation + live golden" and
"P11 - Submission packaging" keep their numbers. P10 was executed as P10A (stabilisation), P10 Waves 1-8 (PRs
#86-#98) and the **P10B-W9 pilot-remediation series**. "P10B-Wn" = a wave inside P10B. The later stages are named
P10C-P10F (below) and P11 is unchanged. W9.12/W9.13 were renumbered on this date (old W9.12 requalification
became W9.13; new W9.12 is Engineering Quality & Technical Debt Closure).

### Completed (merged on GitHub `main`, PR #101 chain, Alembic head `0014_opportunities`)
| Wave | Outcome |
|---|---|
| W9.1 | Resilience: bounded states, request IDs, safe errors |
| W9.2 | Recovery paths |
| W9.3 | Security and menu hygiene |
| W9.4 | Opportunity discoverability |
| W9.5 | Welcome and Tutorial v2 |
| W9.6 / W9.6A | Full localization of the candidate app; Help content localization; scanner closure |
| W9.7 | Russian as the 8th locale |
| W9.7A | Language ownership (interface vs Mo conversation), error tiers, Cyrillic font, dev-DB reconciliation |
| W9.7B | CI onboarding-gate fix (verified redirects) |

Locale facts: 8 product locales (en/de/fr/es/it/pt/nl/ru). Russian is supported for the interface and for Mo
conversation only. Russian **speech** (dictation/TTS/realtime) is NOT supported. Russian does **not** imply a
Russian labour market/geography and is **not** an official ESCO language. `Ask More. Be More.` is a protected,
never-translated slogan. Local `main` == `origin/main`; GitHub integration is part of the Definition of Done.

### Remaining work (nothing below has started; RC-P10-003 does not exist)

| Step | Scope | Cx | Priority |
|---|---|---|---|
| **W9.8** Privacy & Candidate Data Controls (**DELIVERED** - `p10/w9/P10B_W9_8_PRIVACY_DATA_CONTROLS.md`; deferred: preparation-chat run index, consent/legal-version history (need migration/owner decision), bulk memory clear) | Data & Privacy Center: what is stored; export; selective deletion (documents, memory, Opportunities, interviews, reports); agent-run/checkpoint implications; workspace/shared-data visibility and revocation; account deletion; retention; consent/legal versions; request status; 8 locales; audit/legal records preserved | L | Capstone critical |
| **W9.9** Trust & Visual Product Polish (**DELIVERED** - `p10/w9/P10B_W9_9_TRUST_VISUAL_POLISH.md`) | Visual/trust consistency pass over candidate surfaces | M | Desirable |
| **W9.10** Product Positioning / Comparison Foundation (**DELIVERED** - `p10/w9/P10B_W9_10_PRODUCT_POSITIONING.md`, `docs/product/PRODUCT_CLAIMS.md`) | Factual positioning; no unsupported superiority claims; external competitor research separately authorized | S | Desirable |
| **W9.11** Architecture & Documentation Consistency (**DELIVERED** - `p10/w9/P10B_W9_11_ARCHITECTURE_DOCUMENTATION_CONSISTENCY.md`) | Specialist reconciliation (no false Evaluation Specialist claim), authority-level comment, stale tool counts, docs aligned to code | M | Capstone critical |
| **W9.12** Engineering Quality & Technical Debt Closure (**DELIVERED** - `p10/w9/P10B_W9_12_ENGINEERING_QUALITY.md`) | **TD-W9-01** Tailwind `token/NN` opacity classes (~15: inventory, supported token strategy, light/dark/mobile visual regression); **TD-W9-02** backend test isolation leak (isolated test DB, prove no dev/prod DB writes, defensive guards); metadata localization architecture if deferred; 8-locale bundle/performance review; optional locale-aware font subset only if profiling justifies (TD-W9-03) | M-L | Capstone critical |
| **W9.13** Full P10B Requalification (**QUALIFIED** - `p10/w9/P10B_W9_13_FULL_REQUALIFICATION.md`, `p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md`; engineering decision only, no RC) | Full-suite requalification of the candidate product. No RC before it is green | L | Capstone critical |
| **P10B-W10** Platform Administration, Support & Commercial Operations | W10.0-W10.14, see `admin/ADMIN_PLATFORM_MASTER_PLAN.md` and `admin/ADMIN_CAPABILITY_MATRIX.md` | see below | see below |
| **P10B-W11** Integrated Candidate + Admin Requalification | Joint qualification of candidate product and admin plane | L | Capstone critical |
| **RC-P10-003** | Release candidate created only after W11 is green | M | Capstone critical |
| **Pilot 2** (remaining) | Resumes only per the rules below | L | Capstone critical |
| **P10C** Global Career Intelligence & Compensation Overhaul | Occupation graph, classification versioning, crosswalks, multilingual aliases, ESCO/ISCO/O*NET/NOC/SINCO/CBO/KldB, Europe/North/South America, Compensation V2, data-driven source precedence, licensing/provenance/freshness, global multilingual evaluation. **Separate from W10** | XL | Capstone desirable / post-Capstone acceptable by scope |
| **P10D** Global KB / multilingual requalification | Requalify the P10C KB and multilingual behaviour | L | follows P10C |
| **P10E** Live capability validation | Live (paid/provider) validation, separately authorized | L | follows P10D |
| **P10F** Final targeted human validation | Targeted human review | M | follows P10E |
| **P11** Final Capstone packaging/release | Submission packaging | M | Capstone critical |

**P10B-W10 sub-waves** (detail, deliverables and dependencies in `admin/ADMIN_PLATFORM_MASTER_PLAN.md`):

| Wave | Title | Cx | Priority |
|---|---|---|---|
| W10.0 | Admin architecture and control-plane design (**owner-approved design, AD-01..AD-08 FINAL; complete when merged**; design only - `admin/ADMIN_PLATFORM_MASTER_PLAN.md`, `admin/ADMIN_CAPABILITY_MATRIX.md`, `admin/ADMIN_ARCHITECTURE_DECISIONS.md`) | M | Capstone critical |
| W10.1 | Admin Shell, Permission & Audit Foundation, Command Center (**COMPLETE, merged in PR #110 at 301173d**; closes SEC-W10-02/03/06; migration-free; see `admin/W10_1_ADMIN_FOUNDATION_COMMAND_CENTER.md`) | L | Capstone critical |
| W10.2 | Users, access and workspaces (**COMPLETE: merged in PR #118, main `e47ba76`**; closes SEC-W10-01; migration-free; see `admin/W10_2_USERS_ACCESS_WORKSPACES.md`) | L | Capstone critical |
| W10.3 | Support and ticketing (**COMPLETE, merged in PR #114 at b80635d**; migration `0015_support_ticketing`; see `admin/W10_3_CUSTOMER_SUPPORT_TICKETING.md`) | XL | Capstone critical |
| W10.4 | Plans, subscriptions and entitlements (**COMPLETE, merged in PR #116 at 787178d**; migration `0016_plans_entitlements`; no billing or price; see `admin/W10_4_PLANS_SUBSCRIPTIONS_ENTITLEMENTS.md`) | L | Capstone critical |
| W10.5 | Billing and payment administration (mock adapter acceptable) | XL | Capstone desirable |
| W10.6 | Integrations and API connections (**COMPLETE: merged in PR #118, main `e47ba76`**; migration `0017_integrations`; see `admin/W10_6_INTEGRATIONS_API_CONNECTIONS.md`) | L | Capstone critical |
| W10.7 | AI and model administration | L | Capstone desirable |
| W10.8 | Knowledge base and RAG administration | XL | Capstone critical |
| W10.9 | Jobs, queues and operational diagnostics | L | Capstone desirable |
| W10.10 | GDPR, privacy and legal administration | L | Capstone critical |
| W10.11 | Feature flags and safe system configuration | M | Capstone desirable |
| W10.12 | Reporting, analytics and AI economics (essential reporting critical; AI economics desirable) | L | Capstone critical / desirable |
| W10.13 | Security, audit and incident management | L | Capstone critical |
| W10.14 | Admin qualification | L | Capstone critical |

Complexity is relative (S/M/L/XL); no hour estimates are asserted.

**W10 execution order (refined in W10.0; numbering unchanged):** W10.1 (shell, permission framework, audit foundation, build metadata) -> W10.2 (users, sessions, SEC-W10-01) -> W10.3 (support) -> W10.4 (plans/entitlements) -> W10.6 (integrations + SecretStore) -> W10.9 (jobs) -> W10.8 (knowledge administration) -> W10.10 (privacy/legal incl. PRIV-W9-01/02) -> W10.5 (billing, mock) -> W10.7 (model administration) -> W10.11 (flags) -> W10.12 (reporting) -> W10.13 (security/incidents) -> W10.14 (qualification), then integrated candidate + admin requalification -> RC-P10-003.

**Critical path:** W9.8 -> W9.11 / W9.12 -> W9.13 -> W10.0 -> W10.1 -> W10.2 / W10.13 -> W10.4 -> {W10.3, W10.6 -> W10.8,
W10.10, W10.12} -> W10.14 -> W11 -> RC-P10-003 -> Pilot 2 -> P10C -> P10D -> P10E -> P10F -> P11. W9.9 and W9.10 are off
the critical path (can slip without blocking W10). W10.5, W10.7, W10.9, W10.11 are desirable and may ship reduced
(mock/adapter) without blocking qualification.

**Admin principle.** PLATFORM ADMIN != UNRESTRICTED PRIVATE-CANDIDATE-DATA SUPERUSER. Admin scope is classified as
Capstone must-have vs production-ready mock/adapter-acceptable in the Admin master plan section 6; a mock is never
represented as live.

**Pilot 2 stays PAUSED.** It resumes only when: (1) candidate remediation (W9.8-W9.13) is complete; (2) admin changes
that affect support/privacy are stable; (3) the full integrated qualification (W11) passes against RC-P10-003.
Future Pilot 2 coverage: Opportunity, Welcome/Tutorial, non-English incl. Russian, error recovery, Privacy/Data
Center, Trust, support/ticketing where implemented, and Voice separately where supported. RC-P10-002 evidence is
immutable.

**P10C stays separate.** W10 provides the Admin UI (notably W10.8) that later operates P10C sources; it neither
implements nor replaces the P10C architecture.

**Permanent GitHub Definition of Done** (see also `capstone_definition_of_done.md` and `CLAUDE.md`): 1 gates pass;
2 deterministic tests/evaluators run; 3 commit; 4 push the branch; 5 open a PR into `main`; 6 required CI green;
7 merge; 8 fast-forward local `main`; 9 verify local `main` == `origin/main` and a clean tree; 10 a local-only
wave is not integrated. Never force-push `main`.

## Critical path
Identity/authorization (P1) is the spine — documents, evidence, teams, entitlements, admin, hosting
all depend on it. Knowledge expansion (K1–K4) and marketing IA can proceed partly in parallel.

## Phases
**P0+E0 — Baseline & feasibility (this phase).** Objective: establish current state, reconcile
requirements, target architecture, data/security/privacy/product/provider/evaluation plans, risks,
DoD, presentation standard. Gate: evidence-backed feasibility verdict + P1 entry criteria. STOP: no
feature implementation.

**P1+E1 — Identity & platform foundation.** Real accounts (register/verify/recover/login/logout/
expiry), ownership on all paths, authorization dependency (ownership+role+entitlement+flag), platform
roles, workspace-role + entitlement + audit foundations, public/authenticated route boundary. Deps: P0.
Changes: `src/auth.py`, new migrations, `src/api` middleware, `frontend (marketing)/(app)` groups.
Gate: two-user negative tests, logout/expiry, migration/backup proof, no cross-user leak. STOP: no
docs/OCR/teams/speech/admin-console/marketing yet.

**P2 — Return journey on accounts.** Preserve History/Progress/Sources; add A2 active-session
discovery; distinguish live KB readiness from snapshots. Deps: P1. Gate: AC-04/05/06/07.

**P3+E-dictation — Reusable UI + dictation control.** Two real natural-language dictation surfaces,
editable transcript, no auto-submit, race/cancel handling. Deps: P1. Gate: AC-11/12.

**P4+E2+E3 — Documents, OCR, story bank, export/deletion.** Private PDF/DOCX/TXT upload + native
extraction, OCR for scanned, evidence/story bank, A9 export/delete. Deps: P1. Gate: AC-08/09/10,
EX-01/03/08. STOP: realtime voice/teams not required here.

**P5+E4 — Bounded multi-agent + per-op model policy.** Mo + Research/Candidate/Preparation/Evaluation
specialists (only if justified), typed hand-offs, budgets, single-agent baseline comparison; C8 server
model policy. Deps: P1, P4. Gate: AC-15/16/22, EX-05/09. Freeze comparison tasks before eval.

**P6+E6+E7 — Platform ops & collaboration.** Teams/workspaces + sharing/revocation, retention/cleanup,
privacy operations, **Admin Console**, user/tier controls, K1–K4 knowledge expansion, Prompt Lab,
owned run discovery (A6), truthful A7/A8 artifact visibility. Deps: P1, P4, P5. Gate: EX-06/10/11/13–16,
admin neg tests.

**P7+E5 — Speech / recorded Practice.** Recorded answers → STT → existing evaluation first; spoken
questions (TTS); EN/DE; then realtime (C1) if feasible; audio/transcript lifecycle. Deps: P1, P4.
Gate: AC-13/14/23, EX-02/04.

**P8+E8 — Productisation.** Marketing website, pricing/trust/privacy public surfaces, hosting (private
staging → authorized public), production auth hardening, rate limits, SEO/accessibility, entitlement
enforcement at prod. Deps: all prior. Gate: EX-12, AC-19/25.

**P9 — Integrated quality/UX hardening.** Security/retrieval/session/document/speech integration +
controlled agent evaluation tied to exact code. Gate: AC-21/22.

**P10 — Capstone evaluation + live golden.** Real pilot + priority repairs; one authorized live golden.
Gate: AC-24 + acceptance evidence.

**P11 — Submission packaging.** Presentations, implementation stories, requirements matrix, architecture,
evidence, demo script, reviewer guide, final readiness, release/tag. Gate: AC-25.

## Per-phase Definition of Done
See `capstone_definition_of_done.md` (applies to every implementation phase P1+).
