# W12.4E: Governed Speech Providers (offline engineering implementation and qualification)

**Status: CODE QUALIFIED OFFLINE (engineering).** Server-side speech is **implemented, governed and NOT ACTIVE**. It is not production speech, not live-validated, not commercially authorised and not a statement of speech quality. Genuine execution of Whisper and Kyutai Pocket TTS on real audio is **NOT VERIFIED** (no weights, no authorization, no hardware decision): the adapters are proven with deterministic fixture engines, and a fixture engine is not a speech model. All 12 rollout and billing gates are False, Compensation V2 is disabled, no paid call was made, no model was downloaded, no candidate audio was stored, no protected store was written.

- Predecessors: P10D (PR #190) and P10D-R1 (PR #191, merged `bf72f1e10cb90d61dd8569d10d8ac578a2256591`). Branch `feat/w12-4e-governed-speech-providers`.
- Selected providers (owner, recorded; unchanged): speech-to-text **OpenAI Whisper**, text-to-speech **Kyutai Pocket TTS**.
- New Alembic migration `0039_speech_governance` (additive, one table; head was `0038_compensation_concepts`).

## 1. Existing architecture (verified, reused, not rebuilt)
| Capability | What exists | Status |
|---|---|---|
| Browser dictation (STT) | `frontend/lib/speech/browserAdapter.ts` (Web Speech API), `useDictation`, `DictationControl`; the Next.js product's speech input | IMPLEMENTED; recognition may be done by the browser vendor |
| Browser speech output (TTS) | `speechSynthesisAdapter.ts`, `useSpeechOutput`, `VoicePlaybackControl`, `toSpeechText` | IMPLEMENTED |
| Server-side STT | `src/speech_service.py`: provider-agnostic `SpeechTranscriptionService`, Google Chirp 3 provider, used ONLY by the legacy Streamlit interview | IMPLEMENTED (legacy; not exposed by the FastAPI product) |
| Server-side TTS | none | NOT IMPLEMENTED before this wave |
| Realtime voice | `src/voice/realtime.py`, `/voice/realtime/*` (P7.5) | separate capability, untouched, LIVE NOT RUN |
| Admin visibility | `GET /admin/providers` reports `speech.architecture = browser_web_speech` | IMPLEMENTED (unchanged) |
| Language policy | seven speech languages (frontend `ttsLocales`, `DICTATION_LANGUAGES`); interface set is eight with Russian; `SUPPORTED_REALTIME_LOCALES` | IMPLEMENTED |
| Secrets, RBAC, audit, flags, pause | `SecretStore`, 44 permissions, `admin_audit`, durable flags and pause (W10 and W12.4B) | reused; no new permission |

## 2. Implementation architecture (`src/speech/`, one new package; nothing parallel)
| Module | Responsibility |
|---|---|
| `policy.py` | the seven-language product boundary (Russian excluded), the code authorization constants (all False), verified provider capability facts, `effective_languages` = product AND provider AND admin |
| `audio.py` | `TransientAudio` (zeroed on discard), `secure_tempfile` (0700 dir, 0600 file, overwritten and removed in `finally`, observable counter), container sniffing, `validate_and_sniff` (the existing size, MIME and duration checks plus a content check) |
| `engines.py` | `BoundedRunner` (hard timeout, at most 2 in flight, over-bound requests refused as `busy`), controlled exceptions; engine failures become categories, never raw text |
| `stt_whisper.py` | `WhisperTranscriptionService` (implements the EXISTING interface) over a `WhisperEngine`: fixture, `LocalWhisperEngine` (self-hosted open weights, never downloads), `OpenAIWhisperApiEngine` (hosted `whisper-1`, third-party transfer, needs its own authorization) |
| `tts_kyutai.py` | new provider-agnostic `TextToSpeechService`, `KyutaiPocketTtsService` over fixture and `LocalPocketTtsEngine`; server-chosen built-in voice per language; no cloning, no client voice or model parameter |
| `text.py` | `sanitize_transcript` (the SAME validation and injection scan as typed text) and `prepare_speech_text` (what may be spoken) |
| `governance.py` | `SpeechGovernanceService`: validated, durable, revision-protected, audited configuration; unreadable store fails closed |
| `runtime.py` | `SpeechRuntime`: gating, readiness (separate states), the candidate capability view, the per-language matrix |
| `src/api/routes/admin_speech.py`, `speech.py` | Admin governance and the candidate routes |

## 3. Whisper adapter
Verified facts (`policy.WHISPER_CAPABILITY`): Whisper's official `tokenizer.py` language table has 100 languages including en, de, fr, es, it, pt, nl (and ru, ar, which the product excludes); code and weights are MIT; open-weight models tiny 39M to large 1550M (about 1 to 10 GB VRAM); `ffmpeg` is required; the hosted `whisper-1` endpoint accepts mp3, mp4, mpeg, mpga, m4a, wav, webm up to 25 MB (secondary sources). Two deployment models sit behind one contract: **self-hosted** (audio never leaves our infrastructure; default) and **hosted API** (audio goes to a third party; needs `WHISPER_API_TRANSPORT_AUTHORIZED` and a SecretStore credential; a mock client proves its request contract: constant URL, `whisper-1`, explicit language). The language must be an explicit eligible code ("auto" is refused), checked BEFORE any audio is touched. Status: adapter and contract IMPLEMENTED and fixture-validated; genuine execution **NOT VERIFIED**.

## 4. Kyutai Pocket TTS adapter
Verified from the official pages: about 100M parameters, CPU capable, code MIT, weights cc-by-4.0 and **gated** (access requires sharing contact information, so they can never be downloaded automatically), package `pocket-tts` (Python 3.10 to 3.14, PyTorch 2.5+), cloning without explicit lawful consent prohibited. Languages: the README lists english, french, german, portuguese, italian, spanish and **dutch**; the Hugging Face model card lists six **without Dutch**. The two official sources disagree, so **Dutch is UNVERIFIED and not eligible** (Dutch speech output stays with the governed browser path). Built-in voices used (one per language, chosen by the server): en alba, fr estelle, de juergen, it giovanni, pt rafael, es lola; **per-voice licences were not verified** (listed on a separate page): an owner licence review is required before any real use. The local engine binding was deliberately NOT written against a guessed library API: it reports `ModelUnavailable`, and execution is `MODEL_EXECUTION_NOT_VERIFIED`.

## 5. Admin configuration (existing Platform Admin controls)
`GET /admin/speech` (permission `platform.flags.read`) returns the configuration, separate readiness for STT and TTS, the language matrix, the verified provider facts and the authorization constants. `PUT /admin/speech` (permission `platform.config.manage`, expected revision, required reason, audit event `admin.speech_config_changed` in the same transaction) changes ONLY: selected providers (from a code-defined list of one each), enabled flags, eligible languages (a subset of the seven; Russian is refused), the two browser-fallback permissions, and timeouts (STT 5 to 120 s, TTS 5 to 60 s). There is no route and no field for a secret, path, command, endpoint, environment variable or model-loading instruction, and no route contacts a provider. The request model forbids extra fields. Defaults (no row): providers selected, **everything disabled**, all seven languages eligible, browser fallback allowed (the existing behaviour). Enabling a provider records a decision only.

## 6. Supported-language matrix
| Language | Product speech | Whisper STT | Kyutai TTS | Effective STT | Effective TTS |
|---|---|---|---|---|---|
| en, de, fr, es, it, pt | yes | verified | verified | yes | yes |
| nl | yes | verified | **unverified (sources disagree)** | yes | **no** (browser path) |
| ru | **no (excluded)** | supported by Whisper, ignored | no | **no** | **no** |
| ar and others | no | not offered | no | no | no |
Provider capability and product authorization are separate: effective eligibility is their intersection further narrowed by the administrator. "Effective" means eligible in principle; nothing is executable while the authorization constants are False.

## 7. Privacy model and audio lifecycle
Candidate audio is transient: read with a bounded buffer, validated (size, MIME, duration, container signature), held in a `TransientAudio` for one request, handed to the engine and zeroed in a `finally`; a private temporary file is created only if an engine needs a path and is overwritten and removed even when the engine crashes (`live_temp_file_count()` is observable and tested to be 0). Nothing is logged except categories and coarse labels (a test proves no audio bytes or transcript appear in logs), nothing is written to object storage, analytics or audit payloads, no route can return stored audio (none is stored), and responses carry `Cache-Control: no-store`. Generated audio is likewise transient. No real candidate recording is used in any test.

## 8. Fallback policy
The Next.js product's speech paths remain the browser's. `GET /speech/capabilities` (authenticated) tells the frontend which server languages are executable (none by default) and the two browser permissions. The frontend (`useSpeechPolicy`) keeps today's behaviour when the answer is unavailable and **hides** browser dictation or speech output when an administrator disabled them (typing and the visible text remain), and `DictationControl` now shows a point-of-use disclosure in all eight locales: the browser may send the voice to its provider and Ask4Mo does not store audio. A server failure answers with a stable error code and the endpoint implies the fallback (browser dictation or typing; browser speech or reading on screen). There is no silent fallback to an unapproved third-party service.

## 9. Provider readiness (separate states, existing vocabulary)
`configured`, `dependency_available`, `model_available`, `ready_for_offline_execution`, `validated_with_fixture`, `validated_with_genuine_model` (NOT_VERIFIED / MODEL_EXECUTION_NOT_VERIFIED), `live_authorized`, `operational`, plus an explicit blocker list. Measured now: both adapters validated with fixtures, nothing else true; `operational` is False for both. A configured provider is not operational and a fixture-passing adapter is not live-qualified (tested, including that a fixture engine is never reported operational even with authorization and enablement).

## 10. Candidate integration
A transcript is untrusted candidate input: the route returns it for the candidate to review and submit through the normal answer path (explicit submission preserved), after the same normalisation, length bound and injection scan as typed text; a transcript that trips the guard is refused as typed text would be (English, German, French and Spanish attacks tested). Synthesis speaks only text the client presents as the visible response, after server-side sanitisation (no markdown, links, citation markers, secrets, system-prompt markers or error traces). No interview-state, question, feedback, history or accessibility code changed. Authorization is by-text, not by-reference: the server cannot prove a client-supplied string is the approved response (limitation, below).

## 11. Security and offline test results
`tests/test_speech_w12_4e.py` (65 tests) and `scripts/eval_speech_providers.py` (a CI step, 25 checks), frontend `speech-policy-w12-4e.test.tsx` (4 tests). Covered: unauthorized configuration (candidate and specialist roles refused, only `platform.config.manage` may change), unauthorized activation (constants), cross-session isolation and no retrievable audio, audio retention, secret leakage, malicious spoken instructions, malformed, empty, oversized, over-length and mislabelled audio, unsupported and excluded languages, provider timeout, crash, model unavailable, empty transcription and synthesis, repeated and concurrent requests (bounded, released after a timeout), unsafe diagnostics, revoked browser permission, invalid configuration (free-form fields rejected), unreadable store (fail closed). Exact totals are in the delivery report.

## 12. Performance (measured, fixture mode only)
ADAPTER OVERHEAD on deterministic fixture engines (200 runs each): audio validation and sniffing p50 0.003 ms; Whisper adapter p50 0.39 ms; Kyutai adapter p50 0.26 ms; speech-text preparation p50 0.003 ms; transcript sanitisation p50 0.017 ms; secure temp-file create and remove p50 0.36 ms (p95 0.53 ms); 0 temporary files left. **These are not Whisper or Kyutai inference latencies** (no model ran); real latency is not measured and no benchmark is invented.

## 13. Operational restrictions
Production speech is NOT activated: the code constants `SERVER_SPEECH_PROVIDERS_AUTHORIZED`, `WHISPER_API_TRANSPORT_AUTHORIZED`, `MODEL_DOWNLOADS_AUTHORIZED` and `VOICE_CLONING_ENABLED` are False, no setting or Admin action can change them, weights are never downloaded, and voice cloning is never offered. Realtime voice is separate and unchanged.

## 14. Remaining owner decisions
1. Whisper deployment model: self-hosted open weights (audio stays on our infrastructure) or the hosted API (third-party transfer; needs a data-processing review and the second constant).
2. Hosting and resources: weights placement, model size, CPU or GPU sizing for both providers (an explicit resource decision; nothing is downloaded automatically).
3. Kyutai: confirm Dutch (the two official pages disagree), review the per-voice licences, and accept the gated cc-by-4.0 weights terms.
4. Authorization to flip the code constants, after genuine validation on real (consented, non-candidate) audio and a human quality review.
5. A server-side recording client in the frontend (MediaRecorder to `/speech/transcriptions`) was not built: no provider is operational, so it would be untestable; it follows decisions 1 to 4.
6. Legal review of the browser disclosure wording (engineering translation in eight locales).

## 15. Known limitations
Genuine model execution NOT VERIFIED for both providers; the local Whisper engine supports the faster-whisper loader only and the local Kyutai binding is intentionally not implemented; the timeout cannot kill a running engine thread (the slot is released when the thread ends; concurrency is bounded per process, not across replicas); synthesis authorizes by text not by reference; the Streamlit Google provider path is unchanged; the migration adds one table (`speech_governance`, fail-closed downgrade) and updated the schema-head pins in tests and evaluators.

## 16. P10D risk register carried forward (not fixed here)
| Id | Candidate-facing impact | Severity | Required remediation | Owner decision | Target |
|---|---|---|---|---|---|
| L-ANSWER-GUARD | Career Chat and Mo's agent now share one grounding decision | resolved | none | accepted (P10D-R1) | closed in P10D-R1 |
| F-COV-1 | the legacy evaluator counted source families, not origin or country | addressed | source-backed coverage (V2) added as a separate measurement; legacy unchanged | accepted (P10D-R1) | review before integrated requalification |
| L-REL-1 | no calibrated relevance floor: out-of-scope questions still receive nearest chunks (deterministic part addressed in R1) | medium | semantic embedder calibration | defer to P10E (authorised paid run) | P10E |
| L-ROUTE-1 | non-English questions skip the structured lanes | medium | multilingual routing | native review | before integrated requalification |
| L-XLANG-1 | no cross-language retrieval offline | medium | semantic embeddings | P10E | P10E |
| L-STALE-1 | no staleness handling in the narrative lane | low | publication-date policy | owner | after P10E |
| L-CODE-1 | occupation codes do not resolve | low | resolver extension | owner | after P10E |
Before the integrated Candidate/Admin/Operations requalification, the candidate grounding path and the provenance-aware coverage evaluation must be reviewed for remediation. The 95% coverage gate is unchanged and BELOW GATE (developer-local 386/412, clean checkout 258/412).

## 17. W12.4F entry readiness
Ready: governance patterns (durable config, expected revision, audit, RBAC) are reusable; no blocker from W12.4E. W12.4F was not started.


## 18. Owner decision of 2026-10-19: remaining activation work deferred (recorded by W12.4F)
W12.4E is accepted as CODE QUALIFIED OFFLINE and merged (PR #192). Every item in sections 14 and 15 that concerns deployment, licensing, genuine model validation or activation is DEFERRED UNTIL AFTER CAPSTONE SUBMISSION and recorded as 18 items in `docs/capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md`. Nothing above is marked complete by this deferral; the engineering recorded in this document is preserved unchanged; production speech stays NOT ACTIVATED; genuine Whisper and Kyutai execution stays NOT VERIFIED; a deferral is not production authorization. W12.4F added an Admin Speech page and derived readiness reporting over this implementation without changing any speech behaviour or authorization.
