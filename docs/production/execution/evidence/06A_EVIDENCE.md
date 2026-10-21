# 06A Evidence: locale audit, language boundaries and removal of Russian from active Candidate selection

Branch `feat/06a-locale-boundaries`, based on `origin/main` 38eabbc. ## 0. Position, stated plainly

- **Seven selectable target languages:** en, de, fr, es, it, pt, nl (`ACTIVE_CANDIDATE_LOCALES`). Russian is preserved in code and catalogue but excluded from R1.0 and from active selection.
- **ZERO production-qualified languages.** `docs/production/execution/language_readiness.json` records `production_qualified: false` for all seven; no language has passed all fourteen gates.
- **Fourteen gates (LG-01..LG-14) are required per enabled locale before real-user activation. None of that enforcement is in 06A; it is package 06H.** `ACTIVE_CANDIDATE_LOCALES` only defines the selectable set and is not a qualification or activation claim.
- **No qualified translations yet:** every non-English string (interface, Mo templates, emails, legal and trust text) is an unreviewed engineering translation. No native review (LG-11) or legal translation qualification (LG-10) has started.
- **Russian tests are excluded from passing coverage** (section 4a, `06A_RUSSIAN_TESTS_EXCLUDED.md`).

Branch `feat/06a-locale-boundaries`, based on `origin/main` 38eabbc. This package records the truth and enforces the boundaries; it qualifies nothing.

## 1. Requirements and gates

REQ-LANG-01 (audit), 07 (language never sets geography), 11 (per-language readiness), 12 (Admin English-only), 13 (no early claim), 14 (Russian out of active selection). Gates LG-01, LG-02 (inputs only), LG-07 (engineering draft), LG-13, LG-14.

## 2. Changes

Backend
- `src/locales.py`: code-defined `ACTIVE_CANDIDATE_LOCALES` (en, de, fr, es, it, pt, nl), `DEFAULT_ACTIVE_LOCALE`, `is_active_locale`, `effective_locale`. `AppLocale` (the request-schema Literal) is now the seven active locales, so every NEW-work input (account preferences, registration locale, Career chat, agent run, interview create and preparation handoff) refuses `ru` with the existing 422 validation shape. `SUPPORTED_LOCALE_CODES` (eight) is kept for the catalogue, stored values, prompts and emails. Not environment- or Admin-configurable.
- `src/auth_repository.py`: preference setters accept active locales only; account reads return `effective_locale(...)`, so a stored `ru` falls back to `en` for display. The stored row is not rewritten, geography is untouched, no migration.
- `src/api/schemas/common.py`: `GET /api/v1/capabilities` gains additive `active_candidate_locales` and `default_locale`.
- Existing interview sessions keep working: `InterviewConfiguration.conversation_language` is a plain string, so a stored `ru` session still loads (tested).

Frontend
- `frontend/lib/i18n/locales.ts`: `APP_LOCALES` and `SUPPORTED_LOCALE_CODES` keep eight (catalogue preserved); new `ACTIVE_CANDIDATE_LOCALES`, `SELECTABLE_LOCALES`, `isActiveLocale`, `toActiveLocale`.
- Selectors (`LanguageMenu`, `ConversationLanguageField`, `LanguageSettings`) render `SELECTABLE_LOCALES`. The interface provider, root layout cookie read, browser-language detection, Settings and the interview session setup use `toActiveLocale`, so a stored, cookie or browser `ru` renders English. Onboarding uses the same selectors. Header/layout/nav files were NOT edited; the 03A-owned files (`AdminShell.tsx`, `lib/admin/capabilities.ts`, `components/layout/nav-items.ts`) were not touched.
- `frontend/lib/api/types.ts`: optional capabilities fields.

Tooling and tests
- `scripts/eval_locale_inventory.py` (+ `frontend/scripts/dump-catalog-stats.mjs`): offline per-language inventory; imports `tests.conftest` first; writes to a temp dir unless `--write`; `--check` fails on a stale committed table.
- `docs/production/execution/evidence/06A_LOCALE_AUDIT.md` (generated) and `docs/production/execution/language_readiness.json` (per language, per gate LG-01..LG-14).
- `scripts/eval_i18n_l10n.py`: Russian validated as "excluded and preserved"; frontend/backend active-list parity; selectors render selectable locales only; `ru` refused for new selections. `scripts/eval_marketing_product_trust.py`: new claims-discipline check `no_language_qualification_claim` (extension; no existing check weakened).
- New tests: `tests/test_language_boundaries_06a.py`, `tests/test_language_geography_separation_06a.py`, `tests/test_language_readiness_06a.py`, `frontend/tests/active-locales-06a.test.tsx`, `frontend/e2e/language-selection-06a.spec.ts`.
- Russian tests adapted, not deleted: `tests/test_w97_russian_locale.py`, `test_wave4_language_api.py`, `test_w97a_career_language.py`, `frontend/tests/russian-locale.test.tsx` now assert Russian is excluded from new work while the catalogue, prompts and directives stay valid. The Playwright specs `russian-locale.spec.ts` and `russian-speech.spec.ts` and two Cyrillic-font tests in `experience-closure.spec.ts` are dormant (`test.skip`, reason stated, flip `RUSSIAN_ACTIVE` on re-activation) because they render Russian through the live UI, which is now deliberately impossible. Other specs that used `ru` as a "second locale" now use `fr`.

## 3. Security and privacy impact

Language never selects geography (tests across account, onboarding, Opportunity, interview creation, agent run and Career chat). The active list is code, not Admin or environment. No new data stored, no migration, no provider call. The capabilities addition exposes only locale codes. Admin stays English-only (static test: no i18n usage or Admin namespace in candidate catalogues).

## 4. Tests and commands (results)

| Command | Result |
|---|---|
| `cd frontend && npx tsc --noEmit` | clean |
| `cd frontend && npm run lint` | no warnings or errors |
| `cd frontend && npx vitest run` | 111 files, 1087 tests passed |
| `node frontend/scripts/scan-i18n.mjs --count` | 0 unexplained literals |
| `E2E_PORT=3145 npx playwright test` language-selection-06a, i18n, trust-polish, data-privacy, experience-closure, russian-locale, russian-speech | 49 passed, 14 skipped (dormant Russian) |
| `E2E_PORT=3145 npx playwright test` w11-visual-a11y, v4-experience, interview, preparation-pack-p5a, plan-ux-p3, premium-analytics-p4b | 103 passed |
| `/tmp/ci_venv/bin/python -m pytest -q tests` (fresh-install canary) | 5170 passed, 43 skipped, 0 failed |
| repo `.venv` python `-m pytest -q tests` | 5172 passed, 41 skipped, 0 failed |
| `ruff check .` | All checks passed |
| `scripts/eval_i18n_l10n.py`, `eval_marketing_product_trust.py`, `eval_doc_consistency.py`, `eval_prepare_practice_integration.py`, `eval_w11_integrated.py` | PASS |
| `scripts/eval_locale_inventory.py --check` | audit table current, 0 readiness problems |

The full Playwright suite was not run (affected specs only); the full vitest and Python suites were.

### 4a. Counts, with Russian-excluded tests reported separately

| Suite | Passed | Skipped (other) | Russian-excluded skipped | Failed |
|---|---|---|---|---|
| Playwright (affected specs, 3 batches combined, 06A follow-up rerun of 3 specs: 20 passed, 14 skipped) | 49 + 103 (earlier batches) | 0 | 14 | 0 |
| Vitest | 1087 | 0 | 0 | 0 |
| Python, `/tmp/ci_venv`, full suite (before the doc follow-up) | 5170 | 43 (pre-existing) | 0 | 0 |
| Python, repo `.venv`, full suite (before the doc follow-up) | 5172 | 41 (pre-existing) | 0 | 0 |
| Python, both venvs, affected subset after the follow-up (language, w97, wave4, openapi, doc-consistency, positioning, baseline evaluators) | 133 each | 0 | 0 | 0 |

The 14 Russian-excluded Playwright tests are named in `docs/production/execution/evidence/06A_RUSSIAN_TESTS_EXCLUDED.md`; they are skipped with the reason "Russian excluded from R1.0 (REQ-LANG-14)" and are NOT in any passed total above. The 49 Playwright passes in the first batch were obtained with those 14 skipped.

## 5. Regression evidence

Full Python and vitest suites pass under both interpreters; speech languages (7), document/OCR languages (7), KB languages (7) and geography lists are unchanged (asserted).

## 6. SHA and CI

Code SHA of the first push: f7b2e03 (on 82ef098). Follow-up commits (owner review corrections: stale-doc fixes, Russian-test visibility, this evidence) are listed in the delivery report with the final SHA. CI runs only once a pull request exists; none existed when this was written (compare URL `https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/06a-locale-boundaries`). CI result: NOT AVAILABLE.

## 7. Remaining risks: what is NOT qualified

No language has passed all gates. LG-01 and LG-14 are PASS; LG-02, LG-07, LG-12, LG-13 are ENGINEERING DRAFT; LG-03, LG-04, LG-09 NOT RUN; LG-05, LG-06, LG-08, LG-10, LG-11 NOT STARTED. All non-English text is engineering translation with no native or legal review. `ACTIVE_CANDIDATE_LOCALES` defines the selectable set only; the plan's rule that a locale is activated only when all fourteen gates pass is NOT yet enforced by code (it cannot be: no language passes), so the seven stay selectable as in the pre-06A product. Gate-driven activation (and a test that every enabled locale has all fourteen gates PASS) is package 06H. The market mapping is not approved and not implemented. The Russian live-UI Playwright coverage is dormant, not run.

## 8. Throughput record

Start 2026-10-21 18:03 UTC (`date -u`); first push 2026-10-21 18:46 UTC (wall clock as reported by the sandbox, including a pause while the shared Python interpreter was repaired). Estimate 4 to 6 engineering days versus roughly 45 minutes of wall-clock for the first push. Rework rounds (commits after first push): 2 follow-ups, both owner-review corrections (documentation, Russian-test visibility and evidence), not defects in the first push; no CI-driven fix. CI duration: not available (no PR).
