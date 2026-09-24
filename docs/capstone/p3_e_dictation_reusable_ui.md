# P3 + E-Dictation — Reusable UI Foundation + Safe Speech-to-Text Input

Capstone implementation story. A frontend/product-experience phase: consolidate a
duplicated input pattern and add safe, user-controlled speech-to-text dictation to two
real candidate input surfaces — without changing the agent, retrieval, grounding, HITL,
security, identity or the P2 response experience.

Base: `main` @ `2af8c89` (P2/E2 merged, PR #75). Branch:
`feature/capstone-p3-e-dictation`. No historical tag moved.

## Problem
Reviewer-adjacent usability: typing long answers/prompts is slow, and candidates who
think out loud benefit from speaking. Dictation is an **input accessibility/convenience**
capability — not voice conversation, not emotion/identity analysis, not auto-submission.

## Why this phase exists
The product had no speech input and three near-duplicate composer implementations.
Adding a microphone to each would triple the surface area and risk inconsistent, unsafe
behaviour. P3 first extracts one shared input primitive, then adds one shared, tested
dictation capability to it.

## Architecture before
- Three separate composers (agent follow-up, interview answer, first-message goal),
  each with its own textarea + submit + empty/busy logic. No speech code anywhere; a
  documented "no microphone/camera" stance in the answer composer and an e2e assertion.

## Architecture after
```
Speech → Recognition adapter (vendor-decoupled) → useDictation (state machine)
      → append FINAL text into the existing editable field (interim = preview only)
      → user reviews/edits → user explicitly clicks Send/Submit → existing Ask4Mo flow
```
- `lib/speech/types.ts` — the adapter contract + safe error kinds.
- `lib/speech/browserAdapter.ts` — Web Speech API wrapper; maps raw errors to safe
  kinds; no audio stored.
- `lib/speech/useDictation.ts` — lifecycle hook; commits only FINAL segments; exposes
  interim as a transient preview; `appendTranscript` preserves typed text.
- `lib/speech/useDictationLanguage.ts` — remembered recognition locale (per-device),
  browser-locale initialisation, bounded to the supported set.
- `components/ui/DictationControl.tsx` — accessible mic + status + bounded language
  selector; renders nothing when unsupported.
- `components/ui/Composer.tsx` — shared controlled composer hosting the dictation slot.
- Wired into `AgentComposer` (Prepare follow-up), the Prepare goal box, and
  `InterviewAnswerComposer` (Practice answer).

## Implementation decisions
- **Input-only, presentation-independent.** Dictation only writes into the editable
  field; it makes no API/model call and does not touch the P2 presentation contract.
- **Commit final, preview interim.** Only final segments enter the field; interim text
  is shown in an `aria-live` status but never written, so confirmed/typed text can't be
  corrupted.
- **Append, never replace.** `appendTranscript` preserves existing text and adds one
  separating space.

## Why dictation is input-only
Ask4Mo must only ever act on text the candidate has seen and chosen to submit. Speech
that could trigger actions would break grounding/HITL guarantees and user control.

## Why auto-submit is prohibited
Recognition is imperfect and users must review/edit before sending. There is **no code
path** from "speech recognised" to "submitted": the hook/control never call
submit/onSend/onSubmit. This invariant is tested on **both** production surfaces
(`tests/dictation-no-autosubmit.test.tsx`) and end-to-end (`e2e/dictation.spec.ts`).

## Reusable UI decisions
See `p3_ui_reuse_audit.md`. Extracted `Composer` (genuine 3-way duplication) and the
`DictationControl`/adapter layer (required abstraction). Rejected cosmetic extractions
(IconButton, an extra input wrapper) and deliberately did **not** introduce Enter-to-send.

## Accessibility
Native `<button aria-pressed aria-label>` (Start/Stop dictation), `role="status"`
`aria-live="polite"` status + interim preview, keyboard-operable stop, no colour-only
state, motion only under `motion-safe:`, bounded language `<select>` with an accessible
label, mobile-friendly layout. Unsupported → the control is absent and typing remains.

## Privacy
No audio is recorded or stored; there is no `MediaRecorder`/`getUserMedia`/Blob in the
app (the Web Speech API manages capture itself — an e2e test asserts the app never calls
`getUserMedia`). Nothing (transcript or audio) is written to localStorage, URLs,
analytics, observability or audit before submission — only the recognition **language
code** is remembered per device. Once submitted, text follows the same rules as typed
text. Help/Privacy states honestly that the browser's speech recognition may send audio
to the browser/vendor's speech service, and that **Ask4Mo does not analyse emotions,
voice characteristics, or identity.**

## Security
No new backend surface, no new secrets, no change to auth/session/authorization/
ownership. Dictation is client-side and produces ordinary field text; server-side
controls are unchanged. Cross-user isolation and production fail-closed are untouched.

## Multilingual (bounded, honest)
Seven configured recognition locales — English (en-US), German (de-DE), French (fr-FR),
Spanish (es-ES), Italian (it-IT), Portuguese (pt-PT), Dutch (nl-NL) — in a bounded,
keyboard/screen-reader-accessible selector that maps deterministically to BCP-47 tags
(no arbitrary parameters). The initial language is taken from the browser locale when it
maps to the set, else English. Support status is distinguished as CONFIGURED / TESTED /
BROWSER-ENGINE-DEPENDENT / UNSUPPORTED; we do not claim every language works in every
browser. **Whole-application UI translation is not implied by multilingual speech** —
application localisation is a separate future phase (readiness captured in the audit).

## Evaluation
`scripts/eval_dictation_experience.py` — 11 invariants (surface coverage, editability,
no-auto-submit, typed-text preservation, unsupported fallback, permission-failure
isolation, accessibility contract, no-audio-persistence, no-localStorage-candidate-
content, response-architecture-unchanged, multilingual-bounded) → all PASS, 0 paid/live
calls. Backed by 13 unit tests + 2 e2e; existing agent/response/identity gates unchanged.

## Evidence
`tests/dictation-control.test.tsx` (9), `tests/dictation-no-autosubmit.test.tsx` (4),
`e2e/dictation.spec.ts` (2), `scripts/eval_dictation_experience.py`. Regression: backend
suite, frontend unit (204), Playwright e2e, eval_agent/eval_identity_platform/
eval_response_experience all green.

## Limitations
- Browser-dependent recognition quality/availability (documented; typing is the
  guaranteed fallback).
- Live speech accuracy per language is not measured in P3 (no paid provider); only the
  UX/safety invariants are.
- Dictation on the deep-dive answer box inherits the shared composer only where
  `InterviewAnswerComposer` is used; the main answer + deep-dive both benefit.

## What was deliberately not built
Voice conversation, spoken feedback, audio recording/archive, emotion/sentiment/speaker
analysis, camera, auto-submit, whole-application translation, a paid speech provider, an
IconButton design system, Enter-to-send. (All excluded per the phase brief.)

## Next-phase recommendation (do not begin automatically)
Per the plan, **P4 + E2/E3 — documents, OCR, evidence/story bank, export/deletion** is
the next major capability. A dedicated **Internationalization & Localization** phase
(the seven app languages) is also queued; this phase's `lib/i18n/locales.ts` and the
localization-readiness audit are its inputs.
