# P7 — Voice Architecture Audit

_Written before implementation. P7 is a bounded, TURN-BASED voice modality (browser TTS +
reuse of the P3 browser STT). NOT realtime/streaming, NOT always-listening, NOT any
human-trait inference._

## Current state (pre-P7)

| Area | Current | Ref |
|---|---|---|
| **Current STT** | Browser Web Speech recognition behind a vendor-neutral seam: `SpeechRecognitionAdapter` (`frontend/lib/speech/types.ts`), `BrowserSpeechAdapter` (`browserAdapter.ts`), `useDictation` hook (`useDictation.ts`), `DictationControl` (`components/ui/DictationControl.tsx`). Fake adapter injected in unit tests; `window.SpeechRecognition` stubbed in Playwright. | P3 |
| **Input flow** | Speech → `useDictation` commits FINAL segments only → `appendTranscript` into the editable field → explicit Send/Submit. No auto-submit. | P3 |
| **Practice question flow** | `PracticeClient.tsx` renders `state.current_question.question` in an `<h1>`; answer typed/dictated via `InterviewAnswerComposer` → `Composer` → `DictationControl`; explicit "Submit answer"; evaluation is TEXT-only on the submitted answer. | P3/Practice |
| **Mo response flow** | `AgentConversation.tsx` renders assistant turns; `AgentAnswer.tsx` renders the P2 presentation contract (`presentation.answer` primary; `details` behind a Disclosure in Brief). | P2/P5 |
| **Language settings** | Interface locale, Mo conversation language, dictation locale — three INDEPENDENT settings (P3.5). STT locales: en-US/de-DE/fr-FR/es-ES/it-IT/pt-PT/nl-NL. | P3.5 |
| **Audio storage** | None. No `MediaRecorder`/`getUserMedia`/Blob in the app; only a language code persisted (localStorage). | P3 |
| **Browser support** | STT gated on `window.SpeechRecognition`/`webkitSpeechRecognition`; control renders null when unsupported. | P3 |
| **Privacy** | STT audio processed by browser/vendor; Ask4Mo stores no audio; no emotion/identity analysis. | P3 |
| **Accessibility** | Inline `role="status" aria-live="polite"`, `aria-pressed`, `motion-safe:` reduced-motion. | P3 |
| **Missing voice capabilities** | No TTS anywhere (grep confirmed zero `speechSynthesis`); no "Listen"; no speech-output locale mapping; no speech-output state machine. | — |

## Classification of proposed P7 functionality

| Capability | Verdict | Note |
|---|---|---|
| STT adapter / hook / control | **REUSE** as-is | `lib/speech/*`, `DictationControl` — the "Speak answer / dictate" path. |
| TTS adapter (`SpeechOutputAdapter` + browser impl + fake) | **NEW** | Mirrors the STT seam; browser `speechSynthesis`; deterministic fake for tests. |
| `useSpeechOutput` hook + state machine | **NEW** | IDLE/SPEAKING/PAUSED/STOPPED/UNSUPPORTED/ERROR; unmount cleanup. |
| 7-language TTS locale mapping + honest status | **NEW** | `ttsLocales.ts`; separate from STT locales. |
| Speech-text sanitiser (`toSpeechText`) | **NEW** | Deterministic; strips markdown, links/URLs, citations→"sources on screen"; no LLM. |
| `VoicePlaybackControl` (Listen/Stop) | **NEW** | Reusable; a11y mirrors `DictationControl`; renders null when unsupported. |
| Mo response "Listen" | **NEW, wired into** `AgentConversation` | Speaks `presentation.answer` (brief-first) or `m.content`. |
| Practice question "Listen" | **NEW, wired into** `PracticeClient` | Speaks the visible `q.question`. |
| Practice answer "Speak" | **REUSE** (existing dictation) | Already present via the answer composer. |
| Speech-output language | **NEW dimension** | Follows Mo conversation language; independent from UI/dictation locale. |
| Voice preference persistence | **DEFER / device-local** | Follows the `useDictationLanguage` precedent (localStorage); no backend migration. |
| Voice selection (device voice picker) | **DEFER** | Auto-select a matching voice by language; no giant catalogue, no gender/name trait. |
| Realtime/streaming voice (C1, EX-02) | **DEFER / OUT OF SCOPE** | Explicitly not P7 (turn-based only). |
| Any human-trait inference (emotion/accent/confidence/hiring…) | **NEVER** | Prohibited (§16/§33). |
| Admin provider-status voice architecture | **EXTEND** | `/admin/providers` speech entry gains input/output architecture + `audio_persisted=false`. |

No implementation began before this audit.
