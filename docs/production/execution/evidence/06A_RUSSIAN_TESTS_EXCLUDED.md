# 06A Russian tests excluded from passing coverage

Russian is excluded from R1.0 and from active Candidate selection (REQ-LANG-14). The Russian catalogue, prompts, directives, emails and code are preserved. The tests below exercise Russian through the LIVE UI, which is now deliberately impossible (a stored, cookie or browser `ru` falls back to English), so they are skipped with the reason "Russian excluded from R1.0 (REQ-LANG-14)". They are NOT counted as passing. Reported totals separate passed, skipped, and Russian-excluded skipped.

Hand-maintained list (14 Playwright tests; 0 Python tests; 0 Vitest tests are skipped):

| # | File | Test | Why excluded |
|---|---|---|---|
| 1 | `frontend/e2e/experience-closure.spec.ts:179` | Russian text renders in the existing Inter family (webfont), with the Cyrillic file preloaded | needs a Russian-rendered page |
| 2 | `frontend/e2e/experience-closure.spec.ts:309` | Russian surfaces (desktop): Inter webfont, no overflow, controls not clipped | needs a Russian-rendered page |
| 3 | `frontend/e2e/experience-closure.spec.ts:309` | Russian surfaces (390px): same | needs a Russian-rendered page |
| 4 | `frontend/e2e/russian-locale.spec.ts:120` | AB: Russian interface across the core journey | Russian UI not selectable |
| 5 | `frontend/e2e/russian-locale.spec.ts:142` | AG: role, company and source names verbatim; chrome Russian | Russian UI not selectable |
| 6 | `frontend/e2e/russian-locale.spec.ts:156` | AC: first-run in Russian (onboarding, Welcome, Tutorial) | Russian UI not selectable |
| 7 | `frontend/e2e/russian-locale.spec.ts:187` | AD1: Russian UI + English conversation | stored `ru` now falls back to English |
| 8 | `frontend/e2e/russian-locale.spec.ts:202` | AD2: English UI + Russian conversation | `ru` conversation not selectable (API 422) |
| 9 | `frontend/e2e/russian-locale.spec.ts:220` | AE: Russian error chrome | Russian UI not selectable |
| 10 | `frontend/e2e/russian-locale.spec.ts:244` | AF: Help in Russian | Russian UI not selectable |
| 11 | `frontend/e2e/russian-locale.spec.ts:262` | Public /trust renders Russian copy | a `ru` cookie falls back to English |
| 12 | `frontend/e2e/russian-speech.spec.ts:90` | Russian conversation: no Listen, no live voice | `ru` conversation not selectable |
| 13 | `frontend/e2e/russian-speech.spec.ts:109` | en conversation under a Russian interface | Russian UI not selectable |
| 14 | `frontend/e2e/russian-speech.spec.ts:109` | de conversation under a Russian interface | Russian UI not selectable |

Still active and passing (Russian preserved, not excluded): catalogue parity and completeness (`frontend/tests/russian-locale.test.tsx`, `tests/test_w97_russian_locale.py`: prompts, directives, speech/OCR/KB/geography boundaries), plus the new tests asserting `ru` is excluded from selection and falls back safely.

Re-activation: flip `RUSSIAN_ACTIVE` in the two Russian spec files, remove the `test.skip(true, ...)` lines in `experience-closure.spec.ts`, and return `ru` to `ACTIVE_CANDIDATE_LOCALES` only by an owner decision with gate evidence.
