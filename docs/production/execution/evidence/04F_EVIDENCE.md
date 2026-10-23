# 04F Evidence: browser dictation disclosure and verification (W12.4E-16, AC-13/AC-23-A; PG-04 contribution)

Branch `feat/04f-dictation-disclosure` from `origin/main` f5cf7cb. Migration: none. Browser path only; server speech untouched (gated, R1.4). Admin UI untouched.

**What this package is not:** it is not a legal review, not a native-language review, not a live browser speech-to-text check and not a measurement. Those are OPEN (below). No human review is recorded as done.

## Requirement mapping
| Item | Covered | How | NOT covered |
|---|---|---|---|
| W12.4E-16 disclosure review: audit of every place the feature, permission prompt, data flow and disclosure appear | Audit done (engineering) | `docs/production/DICTATION_DISCLOSURE_AUDIT_04F.md`: 14 places, what is true in code (7 points, test-backed), 13 questions for a legal reviewer, exact current text for all 8 locales (generated from the merged catalogues), review status table | The legal review itself: OPEN |
| Confirm from code that Ask4Mo sends no audio to its own servers on this path | Yes | Vitest source check (no fetch, XHR, WebSocket, sendBeacon, MediaRecorder, getUserMedia, AudioContext, Blob, FormData, RTCPeerConnection in the four dictation files; frontend client has no `/speech/transcriptions` or `/speech/synthesis` call, only `GET /speech/capabilities`); Playwright records requests, websockets and `getUserMedia` during a dictation interaction | What the browser vendor does with audio is not observable by Ask4Mo and not verified |
| Proposed wording as a diff-able proposal, NOT applied | Yes | `docs/production/dictation/PROPOSED_COPY_CHANGES_04F.patch` (English only; `git apply --check` passes on this branch; not applied) | Translations of the proposal (deliberately not drafted before the English wording is approved) |
| Engineering fixes (unambiguous bugs only) | 2 fixes | (1) the browser's `language-not-supported` error now has its own localised message (it was the generic "stopped unexpectedly"); (2) the disclosure paragraph is the accessible description of the mic button. Disclosure before first use and re-readable afterwards was verified already correct and is now pinned by tests | Copy defects are listed, not edited (stale Help text, `service-not-allowed` wording, no disclosure on Settings) |
| Correction-burden harness with protocol and worked example | Yes | `scripts/dictation_burden.py` (template, score, example), `evaluations/dictation_burden/prompts_v1.json` (5 synthetic prompts x 7 languages), `docs/production/dictation/CORRECTION_BURDEN_PROTOCOL_04F.md`, `tests/test_dictation_burden_04f.py` (25) | Any real run or number: OPEN. No threshold defined (owner) |
| Live browser STT check, legal review, native review | **NOT RUN** | Need the owner's appointed legal reviewer, native speakers and test participants | OPEN |

## Changes
- `frontend/lib/speech/types.ts`: new kind `language-not-supported`. `frontend/lib/speech/browserAdapter.ts`: maps the engine code to it; `mapError` exported for tests.
- `frontend/components/ui/DictationControl.tsx`: error key map entry; `aria-describedby` from the mic button to the disclosure paragraph.
- Eight catalogues: new key `dictation.languageNotSupported` (en, de, fr, es, it, pt, nl, ru `ru-parts/a.ts`). Engineering translations, NOT native-reviewed. `06A_LOCALE_AUDIT.md` regenerated with `scripts/eval_locale_inventory.py --write` (+1 key per locale).
- New: audit doc, patch, protocol doc, prompts, harness script, tests (below).
- Not touched: product copy beyond the one new key, `src/speech/*`, Admin UI, `AdminShell.tsx`, capabilities, nav items, the tracker and register.

## Security and privacy impact
No new data flow, endpoint, storage or permission. The new message is static text. The harness handles text only: no audio, pseudonymous participant codes (an email-like code is rejected), writes only to a path the operator names, makes no network call. Server speech and the PG-10 inaccessibility behaviour are unchanged (`eval_speech_providers` PASS).

## Tests and commands
| Check | Result |
|---|---|
| `frontend`: `npx vitest run tests/dictation-disclosure-04f.test.tsx` (14: disclosure before first use, accessible description, stays visible while listening / after stop / after error, unsupported note, language-not-supported message, `mapError` table, production adapter with a mocked SpeechRecognition, all 14 dictation keys in all 8 locales non-empty and (non-English) translated, disclosure names Ask4Mo, seven speech languages with no Russian, source scan for network and capture primitives, client has no transcription or synthesis call) | 14 passed |
| `npx tsc --noEmit`; `npm run lint`; `npx vitest run` (full); `npm run build` | clean; clean; 123 files, 1296 tests passed; build OK |
| Playwright `E2E_PORT=3136 npx playwright test e2e/dictation-disclosure-04f.spec.ts e2e/dictation.spec.ts e2e/voice.spec.ts e2e/help-localization.spec.ts e2e/language-selection-06a.spec.ts` (mocked `SpeechRecognition`; new spec has 4: disclosure visible before the first click and described to AT, selected tag is the only locale handed to the engine and the list is the seven, permission-denied and unsupported-language messages with typing preserved, no media capture / websocket / speech upload) | 25 passed (4 new + 21 existing) |
| `tests/test_dictation_burden_04f.py` (arithmetic of insert/delete/substitute, normalisation, burden formula, residual error, hand-checkable worked example, fail-closed validation of 10 invalid sheets, CLI writes only to the named directory, prompt set equals the product speech boundary) | 25 passed under the fresh-dependency canary `ci_venv` and under the repo `.venv` |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4` | pass (both venvs for ruff); 301 files, each in one shard |
| All 47 evaluator invocations from `.github/workflows/ci.yml` (`ci_venv`; the four with arguments run as CI does) | 47 PASS, no tracked file dirtied |
| Full backend suite `pytest tests -n 3 --dist loadfile -q -p no:cacheprovider` (`ci_venv`) | Exit code 0 (all tests passed, none failed). The per-test totals were not captured because the run's output was piped through `tail` and the summary line fell outside it; this is stated rather than guessed |

## Risks and limits
- Mocked `SpeechRecognition` proves our code path, not any browser's engine; engine behaviour, vendor routing and per-language accuracy are unverified.
- The `language-not-supported` message is shown only when the engine reports that code; some engines report other codes or fail silently for an unsupported language. Whether this is common is unknown until the live check.
- Seven translations of one new sentence are engineering translations.
- The patch depends on this branch's `languageNotSupported` line as context; re-create it if the catalogue changes before the reviewer approves.
- Word-level burden ignores punctuation effort (stated in every result file).

## Missing evidence (OPEN, nothing here marks them done)
1. Legal and privacy review of the disclosure wording and the 13 questions in section 4 of the audit (appointed legal reviewer).
2. Live browser STT check with real participants, browsers and languages, and the correction-burden run (AC-13, AC-23-A), plus the owner's acceptance threshold.
3. Native-language review of the seven translations.
4. PG-04 stays open until the reviewer's decision is applied through a small copy PR.

## Delivery
Start 08:54 (CEST, 2026-10-22). Rework rounds: 1 (a casefold expectation in my own test). SHA and first-push time: see the final report.
