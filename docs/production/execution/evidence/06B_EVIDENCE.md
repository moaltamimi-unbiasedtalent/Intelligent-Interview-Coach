# 06B Evidence: per-language Candidate journeys, Story Bank and Workspaces

Branch `feat/06b-language-journeys` from `origin/main` f5cf7cb. Migration: none. No live provider call.

## 0. Position, stated plainly

- Seven selectable languages (en, de, fr, es, it, pt, nl). Russian is excluded; its dormant specs stay skipped (`06A_RUSSIAN_TESTS_EXCLUDED.md`).
- **Every non-English string in this package is an ENGINEERING translation, not native-reviewed.** The one new catalogue key (`prepare.sessionGone`) is such a translation.
- **LG-03, LG-09 and LG-10/11 are NOT approved and NOT marked passed.** A green journey run is automated, mocked-network and single-browser (Chromium) evidence. 06H requires a named human approver, an evidence reference, an approval date and a release SHA; none exists. `language_readiness.json` is untouched.

## 1. Requirement mapping

| Item | Covered | NOT covered |
|---|---|---|
| LG-03 per-language Candidate journey (onboarding, Opportunity, Company, Prepare/Mo, Practice, History, Progress, Documents, Settings, privacy controls) | One shared journey definition run for all seven languages: chrome localised, no English leak, slogan untranslated, Mo-vs-chrome ownership, geography independence, dates/numbers, no overflow at 768 and 1280, named controls, keyboard, localised error states | Native-speaker review, real-device and multi-browser runs, screen-reader testing, live staging, real model output per language |
| LG-09 Story Bank and Workspaces per language | Browser journeys (mocked network) and real-backend journeys in all seven languages incl. owner isolation, consent, revocation, deletion, restart survival, invitation e-mail in the invitee's language | PostgreSQL race/row-lock behaviour (still NOT RUN, see 04B), native review of the 116 + Workspaces strings |
| PG-13 contribution | Per-language evidence recorded | Gate decision (lead/owner) |

## 2. Changes (smallest fixes) and defects with before/after

| # | Defect found | Before | After |
|---|---|---|---|
| D1 | Dates in History list and detail, Progress recent sessions, Data and Privacy (requests, legal versions), Support list and ticket, Documents inventory used the browser/OS locale (`toLocaleDateString()`); Company report showed ISO `2026-01-15` | German interface in an en-US browser showed `9/1/2026` | `Intl` with the interface language via `useI18n().formatDate` (`1.9.2026`) |
| D2 | Progress tiles printed raw numbers (`1234`, `72.5/100`); Coach usage line printed `4.1s` and `~$0.12` with a point | `1234`, `72.5/100` in German | `formatNumber` / `Intl.NumberFormat(locale)`: `1.234`, `72,5/100` (English unchanged) |
| D3 | `ApiError.userMessage` was English-only, so load errors showed English chrome in a non-English interface (Story Bank load error in de; Documents load error in de, es, pt, a race with the account language arriving after first paint) | "Ask4Mo hit a problem while processing that request..." in a German page | `userMessage` reads `<html lang>` and returns the `states.*` catalogue text for non-English (English byte-identical); Story Bank and Documents keep the error and build the message at render |
| D4 | Prepare showed hard-coded English "This preparation session can no longer be resumed." | English in every language | catalogue key `prepare.sessionGone` in all eight catalogues (fragment `lang06b`, parity enforced) |
| D5 | Onboarding review step showed raw codes (`de`, `en`) for interface and conversation language | `de` | the language's own name (`Deutsch`); the existing e2e assertion `"en"` in `onboarding.spec.ts` was updated to `"English"` with a comment (same intent, same strength) |
| D6 | Documents upload showed the browser's own file control text ("Choose File / No file chosen", browser language) | English text on an nl page (seen in the review screenshot) | native input visually hidden but labelled and focusable inside a button-styled label carrying the catalogue text |
| D7 | Story Bank filter row was a 5-column grid inside the reading column; Dutch/German option text was clipped ("Actieve verha") | clipped | 3 columns at lg |

Files: `frontend/components/{progress/PracticeProgress,interview/HistoryClient,interview/HistoryDetailClient,account/PrivacyLegalPanels,support/SupportHome,support/SupportTicketView,documents/DocumentsClient,documents/DocumentUpload,company/CompanyReport,agent/usage,agent/AgentPrepareWorkspace,agent/useAgentRun,onboarding/OnboardingClient,stories/StoryBank}.tsx|ts`, `frontend/lib/api/errors.ts`, `frontend/lib/i18n/messages/lang06b/*` (+ one line in `w96/index.ts`), `docs/production/execution/evidence/06A_LOCALE_AUDIT.md` (regenerated with `scripts/eval_locale_inventory.py --write`: +1 key per language, key and placeholder parity in all eight catalogues).

Verified OK (no defect): lang attribute, protected slogan on Home and `common.tagline` in every language; Mo-voiced text follows the conversation language while chrome follows the interface language (chat body carries only `conversation_language`); language choices never send `career_geography`; no horizontal overflow at 768 and 1280 on 12 surfaces plus Story Bank list, editor, workspace detail and dialogs; every visible control has an accessible name; skip link, language menu and Settings selects are keyboard operable; confirmation dialogs focus Cancel, trap focus and close on Escape.

## 3. Security and privacy impact

No new data, route, permission or migration. Language never changes authorization, consent or isolation (real-backend tests). The invitation e-mail follows the invitee's own interface language and carries the protected slogan once. Screenshots are review artefacts only, written to the git-ignored `frontend/playwright-report/06b-screens/` (84 PNGs: 12 surfaces by 7 languages); none are committed.

## 4. Tests (exact commands and results)

| Command | Result |
|---|---|
| `cd frontend && E2E_PORT=3131 npx playwright test e2e/language-journeys-06b.spec.ts` | 161 passed (7 languages x 23 tests; one shared journey definition) |
| `E2E_PORT=3131 npx playwright test` language-selection-06a, i18n, language-activation-06h, localization, story-bank, workspaces, workspaces-journey-04b, experience-closure, data-privacy, progress, onboarding, documents, company, support, interview, premium-analytics-p4b, settings-memory, help-localization, agent-coach, journey, russian-locale, russian-speech | 142 passed, 14 skipped (dormant Russian), 1 failed before D5 was reconciled; onboarding re-run 12 passed |
| `npx playwright test e2e/language-journeys-06b.spec.ts e2e/documents.spec.ts e2e/story-bank.spec.ts` (after D6/D7) | 166 passed |
| `npx tsc --noEmit`, `npm run lint` | clean |
| `npx vitest run` | 123 files, 1290 tests passed (new `tests/language-journeys-06b.test.ts`, 8 tests) |
| `node frontend/scripts/scan-i18n.mjs --count` | 0 |
| `.venv/bin/python -m pytest -p no:cacheprovider -q tests/test_language_journeys_06b.py` | 23 passed (real backend: Story Bank and Workspaces per language, isolation, consent, e-mail language, geography) |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4` | passed; 301 files each in one shard |
| all `scripts/eval_*.py` that CI runs (45, incl. the four with `--json` paths) and `eval_locale_inventory.py --check` | all PASS; audit table current |
| Full backend suite, fresh-dependency canary (`~/.cache/ask4mo/ci_venv`, `-n 3 --dist loadfile`) | about 6,304 passed (dot count), 0 failed, about 45 skipped |
| Full backend suite, repo venv | all passed except `tests/test_test_isolation.py::test_identity_evaluator_never_touches_the_developer_database_or_a_caller_supplied_one`: its evaluator subprocess aborts with a libc++ `recursive_mutex lock failed` in the repo venv (fails alone too); the same test passes in the canary. No file it exercises is touched by 06B; not verified against origin/main in the repo venv |

The detector for English leaks was checked to catch a deliberate leak (an English page asserted as German fails). The date/number test fails on the pre-fix code (verified by reverting HistoryClient and PracticeProgress).

## 5. Risks and limits

- Some components store an already translated error string at catch time (for example Memory, Interview report, Sources); if the interface language only becomes known after the failure they can show the earlier language. Documents and Story Bank were fixed and tested; the rest was not observed failing and is not changed.
- `AgentPrepareWorkspace` start-practice errors still prefer the server-provided `err.message` (backend English text by design).
- Mocked-network journeys prove the UI drives the rules, not the deployed stack; Chromium only.
- Automated accessible-name checks are not an accessibility audit.

## 6. Evidence still missing

Native-speaker review of every new and existing string (LG-11), legal translation review (LG-10), a named approver, evidence reference, approval date and release SHA for 06H, staging runs, PostgreSQL concurrency for invitations, multi-browser and assistive-technology testing.

## 7. SHA and throughput

Start 2026-10-22 08:15. Rework rounds: 2 (error-message approach reworked after 25 mocked-module unit tests showed components must keep reading `userMessage`; onboarding assertion reconciliation). SHA and full-suite results are in the final report.
