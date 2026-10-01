# P10B-W9 — Current State (Baseline)

Audit phase. **No runtime code changed.** This file records the exact repository
baseline P10B-W9 is planned against, so every later wave can be diffed from a
known point.

Date captured: 2026-09-30. Author: Claude Opus 4.8 (assisted). Read-only audit.

> **Update (W9.1 delivered):** the error/resilience foundation has since been implemented on branch
> `fix/p10b-w9-1-service-resilience` (from this audit branch). Unhandled 500s now carry CORS +
> `X-Request-Id` (new `CatchAllErrorMiddleware`, CORS installed outermost), the frontend error
> taxonomy is truthful (offline vs unreachable vs server, no "check your connection" for server
> faults), a bounded GET-only retry honours `Retry-After`, and staging joins production in
> failing closed on missing CORS config. See `P10B_W9_1_SERVICE_RESILIENCE.md`. The test/eval
> baseline in §4 is otherwise unchanged (the `.env` model-override artifact persists and is out of
> W9.1 scope; new W9.1 tests are hermetic).
>
> **Update (W9.2 delivered):** candidate read surfaces now recover gracefully after an outage
> (branch `fix/p10b-w9-2-recovery-ux`). Progress renders two independent, coherently-degrading
> regions (one page-level error when both fail; per-region section errors otherwise); History + 5
> other read surfaces gained race-safe in-place Retry (retry-capable `ErrorState` 3→10); recovery
> needs no reload or re-login. Frontend-only: vitest **320** (56 files), full Playwright **125**,
> typecheck/lint/build green; no backend/schema/migration change. See `P10B_W9_2_RECOVERY_UX.md`.
>
> **Update (W9.3 delivered):** internal Review & Diagnostics is now **platform-admin-only** (branch
> `fix/p10b-w9-3-security-menu`), closing the Pilot "security lapse on menu items". Nav item moved to
> an admin-only `INTERNAL_NAV`; `/review` + `/review/rag` + `/review/evaluation` guarded by
> `RequirePlatformAdmin`; `GET /knowledge/diagnostics` + all `/evaluation/*` now require
> `require_platform_admin` server-side (`knowledge/sources`+`/snapshot` stay candidate-facing;
> `/review/agent` stays owner-scoped). No migration, no new role. Frontend vitest **326**, full
> Playwright 126/127 (1 pre-existing unrelated `nextjs.spec` flake, passes in isolation), backend 13
> env-artifact only; security/admin/workspace/identity/multi-agent/RC/i18n evals PASS. See
> `P10B_W9_3_SECURITY_MENU.md`.
>
> **Update (W9.4 delivered):** Opportunity discoverability (Pilot PF-10) on branch
> `fix/p10b-w9-4-opportunity-discoverability`. New Home `OpportunityEntry` (job-centric concept +
> adaptive Create/View, before the Prepare composer, `data-tour="opportunity-entry"`); `?create=1`
> deep-links into the existing inline create flow; ReturnJourney "Your opportunities" chip; desktop +
> mobile nav salience + full mobile accessible name. New copy across 7 locales. Frontend-only: vitest
> **336** (59 files), full Playwright **129/0-fail**, typecheck/lint/build green; no
> backend/schema/migration; opportunity/security/identity/i18n/RC/marketing evals PASS. See
> `P10B_W9_4_OPPORTUNITY_DISCOVERABILITY.md`.
>
> **Update (W9.5 delivered):** Post-onboarding Welcome + Tutorial v2 (PF-11/PF-12) on branch
> `fix/p10b-w9-5-welcome-tutorial-v2`. Onboarding completion renders an intentional Welcome (Create
> opportunity / Take tour / Go to workspace, none mandatory); Tutorial v2 is a 9-step
> Opportunity-centred journey with 0 dead targets, localized chrome+steps across 7 locales, and
> account-scoped state (`ask4mo.tutorial:<user_id>`) closing the shared-browser leak. **No migration**
> (typed-column prefs; account-scoped localStorage used). Frontend-only: vitest **342** (59 files),
> full Playwright **132 (131 pass; 1 unrelated batch flake, isolated-green)**, typecheck/lint/build green; onboarding/opportunity/identity/security/
> i18n/RC evals PASS. See `P10B_W9_5_WELCOME_TUTORIAL_V2.md`.
>
> **Update (W9.6 delivered):** Full-app localization completion (PF-13) on branch
> `fix/p10b-w9-6-full-localization`. Every Ask4Mo-owned candidate-facing string across Prepare/Mo,
> Practice/Interview, Opportunities/Documents/Company/Workspaces, Progress/Memory, the public
> legal/trust/marketing/help pages and shared chrome now renders via `useT()`/`translate()` — **527 new
> keys × 7 locales (3,689 strings)** as five fragments merged in `catalog.ts`. A deterministic scanner
> (`frontend/scripts/scan-i18n.mjs`) + vitest guard + `eval_i18n_l10n` invariant keep candidate-facing
> hardcoded English at **0** (one allowlist entry: reviewer-only `AgentInspector`). Backend locale
> allowlists consolidated to `src/locales.py` (W9.7 insertion point); a shared `I18nProvider`
> fallback-stability fix removes an effect-reload bug surfaced by the change. **No migration, no API
> change, no RC.** vitest **343** (60 files), new `e2e/localization.spec.ts` **11/0** (+50 regression
> specs green), typecheck/lint(0 warnings)/build green; i18n/RC(27)/security/identity(1.0)/opportunity/
> onboarding/dictation/voice evals PASS; backend ruff + locale tests green; 0 paid/live. Human/legal
> review of legal-copy drafts PENDING; page `metadata` titles + Help article bodies deferred; W9.7
> (Russian) NOT started. See `P10B_W9_6_FULL_LOCALIZATION.md`.
>
> **Update (W9.6A — Help + guard closure):** a W9.6 gate inconsistency was found and closed on branch
> `fix/p10b-w9-6a-help-localization-closure`. The Help Center article bodies (a TS object literal) were
> still English and had escaped the JSX-only scanner (false "0 offenders"). Now the Help Center (12
> sections / 66 articles = **144 strings**) is localized across 7 locales (a sixth `help` fragment; 671
> total new keys/locale); the scanner gained a bounded object-literal content pass + a regression test
> proving the blind spot is closed; a Prepare tab label and the dictation language option labels (now
> native-name endonyms from the canonical locale registry) were localized. **Corrected scanner result:
> 0 unexplained candidate-facing offenders** (allowlist = reviewer-only `AgentInspector`). vitest
> **350** (61 files), new `e2e/help-localization.spec.ts` **11/0**, typecheck/lint(0)/build green;
> `eval_dictation` read-path updated → PASS; i18n/voice/realtime-voice/RC(27)/identity(1.0) evals PASS;
> 0 paid/live; no migration, no API/backend-locale change, no RC. With W9.6A, **W9.6 is fully
> DELIVERED**. See `P10B_W9_6A_LOCALIZATION_CLOSURE.md`.

---

## 1. Exact repository baseline

| Fact | Value |
|---|---|
| Audit branch | `docs/p10b-w9-audit` (created for the W9 planning docs only) |
| Base | `main` @ `80354f3` |
| Working tree | clean at capture |
| `origin/main` tip | `80354f3` — *Merge pull request #100* (`fix/pilot2-mo-practice-handoff`) |
| PR #100 fix commit | `9a063bd` — `fix(career): SourceOut.authority_level is int (was str)` — **merged** (ancestor of `origin/main`) |
| Alembic head | `0014_opportunities` (single head; migrations `0007`..`0014` present) |
| RC in effect | **RC-P10-002** (historical, immutable) — product SHA `ab9ff73`; artifact `artifacts/capstone/p10/RC-P10-002/{manifest.json,gate_results.md}` |
| Next RC | **not created** (W9 must qualify a replacement RC *after* remediation; not in this task) |

Recent merged history (newest first):
`80354f3` (#100 authority_level fix) → `ca0e0e2` (#99 Stage B RC-P10-002 + Pilot 2 kit)
→ `72a6269` (RC-P10-002 doc/eval) → `ab9ff73` (#98 Visual System v2) → `d255d34` (#97 Wave 8 requalification)
→ `477d8c5` (#96 Wave 7 marketing) → `934b006` (#95 Wave 6 Opportunities, mig 0014).

## 2. Post-RC-P10-002 changes (what differs from the RC baseline)

Since RC-P10-002 (`ab9ff73`) the product code changed via:
- `#99` (`ca0e0e2`) — Stage B: RC-P10-002 artifact declaration + Pilot 2 readiness kit (`docs/capstone/p10/pilot2/`). Doc/eval only.
- `#100` (`9a063bd`) — the Career Chat 500 defect fix: `SourceOut.authority_level` changed
  `str | None → int | None` in `src/api/schemas/career.py`; frontend type aligned in
  `frontend/lib/api/types.ts`; regression `tests/test_career_chat_schema.py` (3 tests) added.

**Consequence for RC discipline:** the running product is no longer byte-identical to RC-P10-002.
A replacement RC must be qualified before any resumed Pilot 2 evidence is attributed to a single SHA
(never run Pilot 2 across two SHAs). RC-P10-002 stays immutable and historical.

## 3. Relevant implementation inventory (surfaces touched by W9 findings)

| Area | Key paths |
|---|---|
| API error taxonomy (frontend) | `frontend/lib/api/errors.ts`, `frontend/lib/api/client.ts` |
| Shared error/empty/loading UI | `frontend/components/ui/States.tsx` |
| Backend middleware + handlers | `src/api/main.py`, `src/api/middleware.py`, `src/api/exception_handlers.py` |
| Progress / History | `frontend/components/progress/{ProgressClient,PracticeProgress}.tsx`, `frontend/components/interview/HistoryClient.tsx` |
| i18n core | `frontend/lib/i18n/{locales.ts,catalog.ts,messages/*.ts}`, `frontend/components/i18n/I18nProvider.tsx` |
| Backend locale allowlists | `src/persistence.py`, `src/api/schemas/{auth,interview,documents,agent}.py`, `src/agent/policies.py`, `src/prompts.py`, `src/voice/realtime.py`, `src/documents/ocr.py`, `src/copilot/knowledge/governance.py` |
| Navigation | `frontend/components/layout/{nav-items.ts,PrimaryNavigation,MobileNavigation,MoreMenu,AccountMenu}.tsx` |
| Auth boundary | `src/api/dependencies.py`; routers under `src/api/routes/*` |
| Onboarding / Tutorial | `frontend/components/onboarding/OnboardingClient.tsx`, `frontend/components/tutorial/*`, `frontend/lib/tutorial/*` |
| Opportunity | `frontend/app/opportunities/*`, `frontend/components/opportunities/*`, `src/api/routes/opportunity.py` |
| Trust / marketing | `frontend/components/marketing/TrustContent.tsx`, `frontend/lib/pricing.ts` |
| Specialists | `src/agent/specialists/*`, `src/agent/specialist_tools.py` |
| Career authority model | `src/copilot/models.py` (`KnowledgeEvidence.authority_level`), `src/api/schemas/career.py` |
| Knowledge / compensation | `src/copilot/knowledge/*`, `data/knowledge/*` |

## 4. Deterministic test / eval baseline (measured this session, 0 paid/live calls)

**Backend (`pytest -q`, from project cwd — loads the gitignored `.env`):**
- **2461 tests collected.**
- **As-is: 13 FAILED, 3 skipped, 2445 passed.** The 13 failures are confined to 5 files:
  `tests/test_config.py`, `tests/test_model_registry.py`, `tests/test_evaluation_service.py`,
  `tests/test_interview_service.py`, `tests/test_report_service.py`.
- **Isolated (model-override env vars unset, run outside the project cwd): 0 FAILED** (exit 0).
- **Root cause of the 13:** the gitignored `.env` sets `OPENROUTER_MODEL_FAST/BALANCED/ADVANCED`
  (the owner's live model mapping). `load_dotenv` auto-loads these, so tests asserting the
  *default* documented model slugs / profile tiers see the overridden slugs and fail. These are a
  **local-environment artifact, not product defects** — proven by the isolated run passing 0-fail.
  The 3 skips are the RAGAS installed/absent guards.
- **Discrepancy note (2455 vs 2445):** historical docs cite `2455 passed` because those runs pre-date
  both the added `.env` model overrides and later test additions. The reconciliation is exact:
  `2461 collected = 2445 passed + 3 skipped + 13 env-artifact failures` with overrides present;
  `= 2458 passed + 3 skipped` with overrides absent. W9.1/W9.12 will make this isolation intrinsic
  (a test fixture that neutralises the model-override env for the default-slug assertions) so the
  suite is 0-fail regardless of local `.env`, without weakening any assertion.
- `ruff check .` — **clean.**

**Frontend (`cd frontend`):**
- `npm run lint` — **clean** (no ESLint warnings/errors).
- `npm run typecheck` (`tsc --noEmit`) — **clean.**
- `npm test` (vitest) — **282 passed, 53 files.**
- `npm run build` — **success**, 37 static pages generated.
- `npm run e2e` (Playwright) — **not run in this audit** (heavy; requires both servers). To be run in
  W9.12 requalification alongside new resilience/localization/security E2E.

**Deterministic evaluators run (all PASS, 0 paid/live):**
`eval_release_candidate` (27/27), `eval_restart_recovery`, `eval_i18n_l10n`,
`eval_security` (prompt-injection detection), `eval_marketing_product_trust` (32),
`eval_opportunity_journey`, `eval_platform_admin`, `eval_workspace_security`, `eval_multi_agent`.

**Interpretation:** the deterministic/offline baseline is green. The pilot findings are
*experience/resilience/coverage* gaps that the existing suites do not yet assert — which is itself a
coverage finding (e.g. `eval_i18n_l10n` passes while ~190 candidate-facing strings remain hardcoded,
because it only checks specific known keys; `eval_restart_recovery` passes at the DB layer while the
*frontend* cannot recover without a reload). W9 must add the missing assertions.

## 5. Constraints carried into W9 (unchanged)

- RC-P10-002 immutable/historical; do not edit its artifact or the detached runtime worktree.
- 0 paid/live provider calls unless explicitly authorised; never print/log/commit the OpenRouter key.
- Do not weaken tests, security boundaries, provenance, HITL, scoring semantics, ownership, or
  existing architecture.
- Do not create RC-P10-003 in the audit task; do not resume Pilot 2; do not modify Pilot evidence.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
