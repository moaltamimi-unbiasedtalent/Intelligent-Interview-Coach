# P3 — Reusable UI Audit

Bounded audit of duplicated interaction patterns in the Next.js app, done before adding
dictation. The goal was **not** a design-system project — only to extract primitives
where there is demonstrated duplication or where dictation needs a shared input
abstraction. Cosmetic-only refactors were rejected.

## Findings

### Extracted: `Composer` (shared controlled input)
| | |
|---|---|
| **Existing duplication** | Three separate "textarea + right-aligned submit + `trim().length>0` empty check + busy-driven disabled/label" implementations: `components/agent/AgentComposer.tsx`, `components/interview/InterviewAnswerComposer.tsx`, and the goal box in `AgentPrepareWorkspace.tsx` (`FirstMessageForm`). |
| **Reusable primitive** | `components/ui/Composer.tsx` — controlled (`value`/`onChange`/`onSubmit`), `busy`/`disabled`, caller-supplied `label`/`submitLabel`/`busyLabel`/`placeholder`, and a trailing dictation slot. |
| **Affected surfaces** | `AgentComposer` (Prepare follow-up) and `InterviewAnswerComposer` (Practice answer) now render `Composer`. |
| **Behaviour preserved** | Submit stays **click-only** (no Enter-to-send introduced — none existed); exact accessible labels kept ("Message Mo", "Your answer", "Send", "Submit answer", "Reviewing your answer…"); parent still owns clear-on-success / preserve-on-failure. Verified by existing `agent-coach`/`practice` tests (unchanged). |
| **Accessibility** | `sr-only` label bound to the textarea `id`; `aria-busy` on submit; disabled semantics preserved. |
| **Why worthwhile** | Removes a genuine 3-way duplication AND gives dictation a single home, so the mic is implemented once, not per surface. |

### Extracted: `DictationControl` + speech adapter layer (new capability)
| | |
|---|---|
| **Existing duplication** | None — there was no speech/microphone code. The abstraction is required so two surfaces don't each hand-roll the Web Speech API. |
| **Reusable primitive** | `components/ui/DictationControl.tsx` over `lib/speech/{types,browserAdapter,useDictation,useDictationLanguage}.ts`. Vendor-decoupled (adapter interface), testable (inject a fake), substitutable later. |
| **Affected surfaces** | Prepare (goal box + follow-up composer) and Practice (answer). |
| **Behaviour preserved** | Input only — appends recognised text to the existing editable field; never submits; typing always works. |
| **Accessibility** | Native `<button aria-pressed aria-label>`, `role="status"` `aria-live` region, keyboard-operable stop, no colour-only state, motion only via `motion-safe:`. |
| **Why worthwhile** | The core of the phase; a single, tested capability instead of two microphone implementations. |

### Considered but NOT extracted (avoiding cosmetic refactoring)
- **`IconButton`** — ad-hoc icon buttons exist (`＋` shortcuts, disclosure `▲/▾`) but are low-volume and heterogeneous; extraction has marginal value. Deferred.
- **A full `NaturalLanguageInput` wrapper beyond `Composer`** — unnecessary; `Composer` already carries the textarea + submit + dictation slot.
- **Enter-to-send hook** — deliberately NOT introduced. No composer uses Enter-to-send today; tests assert click submission. Adding it would be a behavioural change, not a refactor.
- **Dead scaffold `components/coach/CoachComposer.tsx`** — imported nowhere; left untouched (removing it is unrelated cleanup, flagged for a separate task).

## Localization readiness (input to the future Internationalization & Localization phase)

P3 does **not** implement whole-application translation. This section records the
current localization debt and the design choices that keep a later i18n phase tractable.

**Explicit scope statement (preserved):** *Whole-application UI translation is not
implied by multilingual speech.* Multilingual **dictation** only sets the
speech-recognition locale; it never translates the user's words and never changes the
application's language.

**Four concepts kept deliberately separate (do not conflate):**
1. **Application locale** (UI language) — declared, typed, but NOT yet applied:
   `lib/i18n/locales.ts` (`APP_LOCALES` = English, German, French, Spanish, Italian,
   Portuguese, Dutch; `DEFAULT_APP_LOCALE = "en"`).
2. **Dictation recognition locale** (BCP-47) — `DICTATION_LANGUAGES` in
   `components/ui/DictationControl.tsx` (en-US, de-DE, fr-FR, es-ES, it-IT, pt-PT, nl-NL).
3. **Model/capability profile** — Fast/Balanced/Advanced (`AgentProfile`).
4. **Response-detail preference** — Brief/Detailed (`ResponseDetail`).

The application locale is **never** inferred from the dictation locale (or vice versa);
each is chosen explicitly. No personal characteristic (ethnicity, nationality,
identity) is inferred from a language choice. Recognised speech is never auto-translated.

**Dictation language support status (honest):**
- **CONFIGURED** (offered in the selector, mapped to a BCP-47 tag): all seven above.
- **TESTED** (deterministically, via a fake adapter and an injected browser engine):
  the selector, mapping, browser-locale initialisation, and the end-to-end mic→field
  flow (English text used in tests).
- **BROWSER/ENGINE-DEPENDENT**: whether a given browser actually transcribes a given
  language. We do **not** claim every language works in every browser; the Help Center
  says so.
- **UNSUPPORTED**: any browser without the Web Speech API — the control renders nothing
  and typing remains.

**Current localization debt (hard-coded user-facing strings introduced/touched in P3):**
- `components/ui/DictationControl.tsx` — button labels ("Start/Stop dictation"), status
  ("Listening… speak, then review before sending.", "Heard: …"), the `ERROR_COPY` map,
  and language display names.
- `components/ui/Composer.tsx` — default `submitLabel`/`busyLabel` ("Send"/"Sending…").
- `components/help/HelpCenter.tsx` — the new "Using dictation" section text.
- `components/agent/AgentComposer.tsx`, `components/interview/InterviewAnswerComposer.tsx`
  — caller-supplied labels remain English literals at the call sites.

All are English literals; there is no message-catalog / i18n framework yet. **Debt:**
these strings must be externalised into a keyed catalog in the i18n phase. Choosing
caller-supplied labels for `Composer` (rather than hard-coding inside it) already makes
that extraction easier — labels live at call sites, not buried in the primitive.

**Unicode:** all transcript handling is plain JS string manipulation
(`appendTranscript`), which is Unicode-safe end to end; recognised non-ASCII text is
appended and submitted unchanged.

**Recommendation for the i18n phase:** introduce a typed message catalog keyed by
`AppLocale`, replace the literals above, add a user-facing application-locale selector
(separate from the dictation-locale selector), and keep the four-concept separation.
