# P7 + E5 — Multilingual Turn-Based Voice Experience

_Capstone P7 (E5). A bounded voice modality: hear Mo/questions (TTS) and answer by speaking
(reused P3 STT), with editable transcripts and explicit submission preserved. NO realtime
streaming, NO audio storage, and NO human-trait inference of any kind. No paid/live provider
calls; no DB migration (Alembic head stays `0011_workspaces_shares`)._

## Why voice / why turn-based / why not realtime
Voice improves accessibility and reduces cognitive load for candidates who prefer to listen
and speak. **Turn-based** (Listen → Speak → edit → Submit) keeps Ask4Mo's deterministic
Practice lifecycle, explicit-submission and text-based evaluation intact, and avoids the
privacy/complexity of always-listening realtime streaming (WebRTC C1/EX-02 stays DEFERRED).

## Architecture
Mirrors the P3 STT seam. All under `frontend/lib/speech/`:
- `ttsTypes.ts` — `SpeechOutputAdapter` (isSupported/hasVoiceFor/speak/stop/pause/resume) +
  the state machine types.
- `speechSynthesisAdapter.ts` — `browserSpeechSynthesisAdapter` over `window.speechSynthesis`
  (auto-selects a voice matching the language; all access guarded).
- `useSpeechOutput.ts` — the hook: IDLE→SPEAKING→(PAUSED)→STOPPED, UNSUPPORTED/ERROR;
  cancels playback on unmount (no zombie speech after navigation, §22).
- `ttsLocales.ts` — 7-language product→speech locale mapping + honest per-language status.
- `speechText.ts` — `toSpeechText`: deterministic markdown/link/URL/citation sanitiser (no
  LLM); citations → "Sources are available on screen."; never drops caveats.
- `fakeSpeechOutputAdapter.ts` — deterministic fake for tests.
- `components/ui/VoicePlaybackControl.tsx` — reusable Listen/Stop button; renders null when
  unsupported; a11y mirrors `DictationControl`.

## STT reuse
The "Speak answer / dictate" path is the **unchanged P3** `DictationControl` (adapter/hook/
control). P7 adds no second microphone implementation. Explicit-submit and editable-
transcript invariants are inherited.

## TTS + language model
Speech-OUTPUT language follows the **Mo conversation language** (§11), resolved via
`toSpeechLocale(account.conversation_language)` — independent of interface language and
dictation locale, and it never changes career/salary/credential geography (§12). A candidate
can run UI German + Mo English + dictation English + English playback.

## Practice flow
Question renders → optional **Listen to the question** (`VoicePlaybackControl` on `q.question`)
→ candidate **Speak answer** (existing dictation) → **editable transcript** → **explicit
Submit** → existing text-only evaluation → report/progress. The raw audio is never evaluated;
scoring operates on the submitted text exactly as before.

## Prepare flow
Each Mo assistant turn shows a **Listen** control that speaks the PRIMARY visible answer
(`presentation.answer`, brief-first §6) or `m.content`. Dictation + explicit Send are
unchanged. Agent, RAG, specialists, HITL, Brief/Detailed, sources and current-market routing
are untouched — voice is only the interaction layer.

## Explicit submission & safety
- **Speech never auto-submits** (P3 invariant, extended to all voice surfaces).
- **TTS never auto-opens the microphone**; there is no speak→auto-mic→auto-submit loop.
- Starting playback cancels any prior utterance. Route change/unmount cancels playback.

## Voice concurrency — STT/TTS mutual exclusion (pre-merge closure)
On a given surface, Ask4Mo STT and Ask4Mo TTS are **never actively running at the same time**.
A small shared **voice coordinator** (`lib/speech/voiceCoordination.tsx`,
`VoiceCoordinationProvider` + `useVoiceCoordinator`) owns a single audio channel per surface.
Both shared hooks opt in: `useSpeechOutput` and `useDictation` **claim** the channel when they
start (which **stops** whatever else was active first) and **release** it when they end. So:
- starting **Listen** stops any active dictation, then speaks;
- starting **Speak** stops any active playback, then listens;
- neither action submits; stopping a modality **never clears** typed/recognised text;
- the coordinator **only stops** the other modality — it never auto-starts STT or TTS (no
  feedback loop);
- when a surface is not wrapped in the provider the hooks are a **no-op** (backward
  compatible). The two candidate voice surfaces (`/prepare`, `/practice`) wrap their voice
  subtree in the provider. Route change/unmount still cancels cleanly.
Chosen as the smallest architecture that works for both surfaces without threading callbacks
through the Composer/DictationControl nesting, without a global audio daemon, second
adapter, polling or DOM hacks. Proven by `voice-concurrency.test.tsx` (unit),
`voice.spec.ts` (E2E) and the eval invariants `stt_tts_mutual_exclusion`,
`tts_stops_active_stt`, `stt_stops_active_tts`, `no_feedback_loop`.

## Privacy
Ask4Mo hands **candidate-visible text** to the browser/OS speech engine and stores **no
synthesised audio**. STT audio is processed by the browser/vendor (honestly stated — we do
not claim "audio never leaves the device"). No `MediaRecorder`/`getUserMedia`/Blob; no
voiceprint/biometric/acoustic embedding. Voice preference (on/off, device voice) is
device-local (localStorage), never candidate content. Admin sees only speech **architecture**
metadata; workspaces never auto-share audio/voice.

## Human-trait prohibition (§16/§33)
P7 derives, stores or transmits **no** assessment of emotion, mood, stress, confidence,
accent, native-speaker status, personality, intelligence, honesty, deception, mental/physical
state, professionalism or hiring/employability from voice. No prosodic/acoustic/pitch/
speech-rate score. No recruiter-facing voice rating. Enforced by `eval_voice_experience.py`
(`no_voice_trait_analysis`, `no_biometric_storage`, scanned as code identifiers) +
`tests/test_voice_experience_p7.py`.

## i18n
New candidate-facing strings live under the `voice` namespace in all 7 catalogues (key-parity
enforced) — the voice controls AND the **Voice Help section**, which is rendered from the
catalogues via `useT()` (P3.5 coding standard), so it shows in the selected interface language
(EN/DE/FR/ES/IT/PT/NL). Translations are ENGINEERING DRAFT; no human review claimed. Older
pre-P7 Help article bodies remain English on the documented localization-completion backlog —
the whole Help Center is **not** claimed as fully localized. The admin console stays English.

## Evaluation
`scripts/eval_voice_experience.py` — 26 deterministic invariants (adapter boundary, 7-language
config, user-initiated TTS/STT, no-auto-submit, no-auto-mic, editable transcript, text-only
Practice eval, no audio persistence, no trait analysis, no biometric storage, stop control,
unsupported/permission fallback, language/geography separation, Brief/Detailed preserved,
source visibility, admin boundary, workspace no-auto-share, navigation cleanup, PLUS the
closure's STT/TTS mutual-exclusion set: `stt_tts_mutual_exclusion`, `tts_stops_active_stt`,
`stt_stops_active_tts`, `surfaces_scope_coordinator`, `no_feedback_loop`). Unit:
`tests/voice-output.test.tsx` (8), `tests/voice-concurrency.test.tsx` (3),
`tests/voice-help-i18n.test.tsx` (4). Playwright: `e2e/voice.spec.ts` (Practice Listen+Speak+
Submit; Practice mutual-exclusion; Prepare Listen + no-auto-mic) with fake speech engines.

## Live validation matrix (§37) — honest status

| Lang | STT configured | STT browser-tested | STT human quality | TTS configured | TTS browser-tested | TTS human quality |
|---|---|---|---|---|---|---|
| EN | ✅ | deterministic (fake) | ❌ not reviewed | ✅ | deterministic (fake) | ❌ not reviewed |
| DE | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |
| FR | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |
| ES | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |
| IT | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |
| PT | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |
| NL | ✅ | deterministic (fake) | ❌ | ✅ | deterministic (fake) | ❌ |

"Configured" + "deterministic" = owned mapping + offline tests. Real voice availability is
**browser/OS-dependent**; **live human voice quality is UNVALIDATED** (no paid provider, no
human review claimed). No "all languages work" claim.

## Browser limitations
TTS/STT depend on the browser/OS Web Speech implementation (best in Chromium). Where speech
synthesis or a language voice is absent, the Listen button is not shown and text is read
normally; where recognition is absent, the mic is not shown and typing works.

## Trade-offs / Capstone lesson
Reusing the vendor-neutral adapter seam let voice ship as a thin, testable layer with fakes
and zero paid calls, while the strict turn-based + no-audio-storage + no-trait-inference
boundaries kept a sensitive modality safe and honest. The lesson: a voice feature's integrity
lives in its BOUNDARIES (explicit submission, no persistence, no human-trait inference) far
more than in its synthesis quality.

## Known limitations / deferred
Realtime/streaming voice (C1/EX-02); live human voice-quality review; a device voice picker;
cross-device voice preference (would need a `UserPreference` column + migration). See the
carried quality register.
