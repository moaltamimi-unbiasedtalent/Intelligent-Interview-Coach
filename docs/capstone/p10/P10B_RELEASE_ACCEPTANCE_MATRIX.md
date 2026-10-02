# P10B Candidate-Side Release Acceptance Matrix

Canonical candidate-side release gate for P10B (W9.1 - W9.12), produced by `P10B-W9.13` from a **fresh checkout**.
Detailed per-wave design and evidence stay in `docs/capstone/p10/w9/`; this table links to them and does not duplicate them.
Qualification record and environment: [w9/P10B_W9_13_FULL_REQUALIFICATION.md](w9/P10B_W9_13_FULL_REQUALIFICATION.md).
Integrity is checked by `scripts/eval_release_matrix.py` (every evidence path exists; no BLOCKER rows).

**Status values:** PASS = deterministic evidence green in the fresh checkout; ACCEPTED = a known, documented limitation that does not block the
baseline; BLOCKER = must be fixed before the baseline passes (none). Human/legal/live validation is **not** claimed by any PASS row.

| ID | Capability | Wave | Acceptance requirement | Evidence | Result | Limitation / note |
|---|---|---|---|---|---|---|
| R-01 | Safe error envelope, CORS on errors, request ids | W9.1 | unhandled failures return a safe envelope with CORS + request id | `tests/test_service_resilience_w9_1.py`, `frontend/tests/api-errors.test.ts`, `frontend/e2e/service-resilience.spec.ts` | PASS | |
| R-02 | Non-dev CORS fail-closed | W9.1 | staging/production reject open CORS | `tests/test_service_resilience_w9_1.py`, `scripts/eval_hosting_readiness.py` | PASS | |
| R-03 | Bounded retry, writes never retried | W9.1/W9.8 | only GET/HEAD retry; POST/PATCH/DELETE never | `frontend/tests/api-retry.test.ts`, `tests/test_w98_privacy_controls.py` | PASS | |
| R-04 | Offline vs unreachable distinguished | W9.1 | "offline" only when the browser reports it | `frontend/tests/api-errors.test.ts`, `frontend/tests/error-state.test.tsx` | PASS | |
| R-05 | Independent regions, in-place retry | W9.2 | one failed region never blanks a page; History retry in place | `frontend/tests/progress-recovery.test.tsx`, `frontend/tests/history-recovery.test.tsx`, `frontend/e2e/service-recovery.spec.ts` | PASS | |
| R-06 | Admin/reviewer authorization | W9.3 | candidate denied; server is authoritative | `tests/test_review_diagnostics_authz_w9_3.py`, `frontend/tests/nav-security.test.tsx`, `frontend/e2e/review-access.spec.ts` | PASS | |
| R-07 | Agent runs owner-scoped | W9.3 | foreign run is not found | `tests/test_agent_identity.py` | PASS | |
| R-08 | Opportunity discoverability | W9.4 | clear create/view action at zero state; no blank CTA | `frontend/tests/home-opportunity.test.tsx`, `frontend/tests/opportunity-entry-states.test.tsx`, `frontend/e2e/opportunity-discoverability.spec.ts` | PASS | |
| R-09 | Onboarding, Welcome, Tutorial v2 | W9.5 | new user onboards, Welcome, tour with Opportunity; existing users not re-onboarded | `frontend/tests/tutorial.test.tsx`, `frontend/tests/wave2-onboarding.test.tsx`, `frontend/e2e/welcome-tutorial.spec.ts`, `frontend/e2e/onboarding.spec.ts` | PASS | |
| R-10 | Verified redirect ladder | W9.7B | soft, verify, retry once, hard fallback; no sleeps | `frontend/tests/redirect-verified.test.tsx`, `frontend/e2e/onboarding.spec.ts` | PASS | |
| R-11 | 8-locale localization | W9.6/6A | catalogue parity, scanner 0 offenders, Help localized | `frontend/tests/i18n.test.tsx`, `frontend/tests/no-hardcoded-english.test.ts`, `scripts/eval_i18n_l10n.py`, `frontend/e2e/localization.spec.ts` | PASS | engineering translations; native/legal review pending (ACCEPTED, R-49) |
| R-12 | Protected slogan | W9.7 | `Ask More. Be More.` never translated | `frontend/tests/brand-slogan-invariant.test.ts` | PASS | |
| R-13 | Language dimensions | W9.7/9.11 | 8 interface + 8 conversation; 7 speech/document/KB; Russian excluded from speech/ESCO/geography | `scripts/eval_doc_consistency.py`, `tests/test_w97_russian_locale.py` | PASS | |
| R-14 | Russian | W9.7 | UI + Mo conversation routing; Cyrillic renders | `frontend/tests/russian-locale.test.tsx`, `frontend/e2e/russian-locale.spec.ts`, `frontend/e2e/russian-speech.spec.ts` | PASS | not human-reviewed (ACCEPTED, R-49) |
| R-15 | Language ownership | W9.7A | interface owns chrome; conversation language owns Mo-voiced text | `tests/test_w97a_career_language.py`, `frontend/tests/career-answer-language.test.tsx` | PASS | |
| R-16 | Error tiers | W9.7A | section/page/fatal; proportionate; details collapsed | `frontend/tests/error-state.test.tsx` | PASS | |
| R-17 | Opportunity, Prepare, Practice, Progress/History journey | W9.4-9.9 | complete core flow reachable; Mo available | `frontend/e2e/journey.spec.ts`, `frontend/e2e/opportunity-practice.spec.ts`, `frontend/e2e/trust-polish.spec.ts` | PASS | deterministic mocks only |
| R-18 | Career / Mo conversation | W9.7A | conversation works; fallback; language independence | `tests/test_career_chat_schema.py`, `frontend/tests/agent-coach.test.tsx`, `frontend/e2e/agent-coach.spec.ts` | PASS | live model quality not validated (ACCEPTED, R-50) |
| R-19 | Evidence and numbered sources | W9.9 | sources only when evidence used; `[n]` markers map; insufficient-evidence note | `frontend/tests/agent-sources.test.tsx`, `frontend/tests/trust-polish.test.tsx`, `tests/test_agent_grounding.py`, `scripts/eval_faithfulness_v2.py` | PASS | not every answer is RAG-grounded |
| R-20 | Authority semantics | W9.11 | 1 official/statistical, 2 public/professional framework, 3 reputable industry | `scripts/eval_doc_consistency.py` | PASS | |
| R-21 | Tools and specialists | W9.11 | 11 tools (6/3/2); 3 specialists; no Evaluation specialist | `scripts/eval_doc_consistency.py`, `tests/test_multi_agent_specialists.py`, `scripts/eval_multi_agent.py` | PASS | |
| R-22 | Evaluation output contract | W9.12 | seven 1-10 dimensions, overall 0-100, required text; no invented formula | `tests/test_evaluation_contract.py`, `tests/test_evaluation_service.py` | PASS | POLICY-02 accepted: no score-consistency rule |
| R-23 | Practice, Deep Dive, reports | W9.8 | create, answer, complete, evaluate, report, retrieval | `tests/test_interview_api_durable.py`, `tests/test_interview_deep_dive_api.py`, `tests/test_interview_report_deepdive.py`, `frontend/e2e/interview.spec.ts` | PASS | |
| R-24 | No duplicate writes | W9.1/9.8 | idempotent create/save | `tests/test_interview_idempotency.py`, `tests/test_history_idempotency.py` | PASS | |
| R-25 | Progress, History, Memory | W9.2 | load, degrade independently, controls, removal | `frontend/tests/progress.test.tsx`, `frontend/tests/memory-manager.test.tsx`, `tests/test_memory_api.py` | PASS | |
| R-26 | Data & Privacy Center | W9.8 | overview, export, selective delete, revoke, account delete, safe dialogs | `frontend/tests/data-privacy-center.test.tsx`, `frontend/e2e/data-privacy.spec.ts`, `tests/test_w98_privacy_controls.py`, `scripts/eval_privacy_controls.py` | PASS | PRIV-W9-01, PRIV-W9-02 (ACCEPTED, R-47/R-48) |
| R-27 | Cross-user isolation | W9.8 | A cannot read/export/delete/revoke B's data; admin is not a content superuser | `tests/test_w98_privacy_controls.py`, `tests/test_workspaces_p6_5.py`, `scripts/eval_workspace_security.py`, `scripts/eval_platform_admin.py` | PASS | |
| R-28 | Account deletion | W9.8 | documented cascade, files purged, audit anonymised | `scripts/eval_account_deletion.py`, `tests/test_p8_hardening.py` | PASS | some preparation-chat working data may remain (PRIV-W9-01) |
| R-29 | Trust page and claims | W9.9 | grouped, AI-can-be-wrong, no absolute claims | `frontend/tests/trust-polish.test.tsx`, `frontend/e2e/trust-polish.spec.ts` | PASS | |
| R-30 | Product claim register | W9.10 | 28 capabilities (9/10/5/4), 20 allowed, 20 prohibited, no named competitors | `scripts/eval_product_positioning.py`, `frontend/tests/positioning-claims.test.tsx` | PASS | |
| R-31 | Documentation consistency | W9.11 | facts in README/architecture match code | `scripts/eval_doc_consistency.py`, `tests/test_doc_consistency_guard.py` | PASS | |
| R-32 | Auth fail-closed, dev identity dev-only | W9.11/9.12 | production 401 without session; dev header never in prod | `tests/test_auth_failclosed.py`, `tests/test_auth_security_matrix.py`, `scripts/eval_identity_platform.py` | PASS | OIDC backend only: off, not frontend-wired, not live-validated |
| R-33 | Email-verification behaviour pinned | W9.12 | current behaviour documented by tests | `tests/test_email_verification_policy.py` | ACCEPTED | POLICY-01: verification not required to sign in |
| R-34 | Rate limiting | W9.12 | in-memory works; optional Redis adapter (fake-tested) | `tests/test_rate_limit_adapters.py`, `scripts/eval_rate_limits.py` | PASS | **distributed limiting NOT live** (ACCEPTED, R-46) |
| R-35 | Test isolation | W9.12 | no dev DB/Chroma/cache/checkpoint writes; `.env`/secrets ignored | `tests/test_test_isolation.py`, `scripts/eval_engineering_quality.py` | PASS | |
| R-36 | Tailwind token alpha | W9.12 | no dead alpha utilities | `frontend/tests/tailwind-token-opacity.test.ts` | PASS | needs a current browser for `color-mix` |
| R-37 | Clean tree after qualification | W9.12 | tests/evaluators leave `git status --porcelain` empty | CI step "Working tree must be clean", fresh-checkout proof | PASS | |
| R-38 | Legacy Streamlit retained | W9.12 | compiles, tests, `src/auth.py` retained | CI compile step, 18 referencing test files | ACCEPTED | LEGACY-01 |
| R-39 | Schema | all | single Alembic head `0014_opportunities`; no unintended migration | `tests/test_migration_0007_identity.py`, CI Alembic step | PASS | |
| R-40 | Backend suite | all | 0 failures from a fresh checkout | full `pytest` | PASS | 10 environmental skips documented |
| R-41 | Frontend static + unit | all | typecheck, lint, build, vitest, scanner green | CI frontend job | PASS | |
| R-42 | Playwright | all | full suite green, no retries | full `playwright test` | PASS | |
| R-43 | Evaluators | all | every CI evaluator exits 0 | CI python job | PASS | |
| R-44 | Accessibility and visual QA | W9.9/9.13 | keyboard/focus/dialog semantics; light/dark/mobile/de/ru inspection | `frontend/tests/data-privacy-center.test.tsx`, QA record | PASS | no WCAG certification claimed |
| R-45 | Performance baseline | W9.13 | no material bundle regression | build output (shared first-load JS 103 kB) | PASS | optimisation pending (ACCEPTED, R-51) |
| R-46 | Distributed rate limiting | W9.12 | **not claimed as live** | `scripts/eval_hosting_readiness.py` | ACCEPTED | adapter exists, unvalidated against live Redis |
| R-47 | PRIV-W9-01 preparation chats | W9.8 | limitation stated everywhere | `docs/privacy.md`, README | ACCEPTED | no per-user run index; needs data-model work (W10.10) |
| R-48 | PRIV-W9-02 consent history | W9.8 | limitation stated; nothing fabricated | `docs/privacy.md`, README | ACCEPTED | acceptance versions not persisted (W10.10) |
| R-49 | Native/legal language review | W9.6-9.7 | not claimed complete | `docs/capstone/p10/w9/P10B_W9_7_RUSSIAN_LOCALE.md` | ACCEPTED | human review pending |
| R-50 | Live generated-language validation | W9.7 | not claimed complete | `docs/capstone/p10/w9/P10B_W9_7A_EXPERIENCE_CLOSURE.md` | ACCEPTED | needs a separately authorised live run |
| R-51 | Metadata localization and bundle optimisation | W9.6/9.7A | accepted open work | `docs/capstone/p10/w9/P10B_W9_IMPLEMENTATION_PLAN.md` | ACCEPTED | post-P10B-candidate optimisation |
| R-52 | `/practice` page-level heading | W9.9/W9.13 | every page exposes a semantic `h1` | W9.13 fresh-checkout QA (13 pages x 8 configurations) | ACCEPTED | A11Y-W9-13-01 (P3): the Practice setup page has no `h1` (its title is a card heading); all 12 other audited pages have one; not release-blocking, left for a bounded accessibility polish |

**Totals:** 52 requirements; 43 PASS, 9 ACCEPTED limitations, 0 BLOCKER. (Verified by `scripts/eval_release_matrix.py`.)
