# P7.5 — C1 Realtime Voice + Interruption

_Capstone P7.5. Genuine realtime voice with barge-in, built provider-abstracted and
fallback-safe. Turn-based P7 voice is preserved unchanged as the fallback and is NOT
relabelled as realtime. No paid/live provider calls; no DB migration (Alembic head stays
`0011_workspaces_shares`). Companion: [`p7_5_realtime_voice_feasibility.md`](p7_5_realtime_voice_feasibility.md)._

## C1 requirement
C1 = _"Realtime voice + interruption"_ → _"Streaming conversation, visible transcript,
interrupt/stop, reconnect and recorded/text fallback"_, with the hard invariant that
_"interrupted or replayed audio cannot commit duplicate answers"_ (acceptance **EX-02**).

## Feasibility decision
The app's only configured provider (OpenRouter) is a non-streaming text proxy — it exposes
no realtime audio session and no ephemeral browser credential. Genuine realtime therefore
requires a **direct realtime-capable provider**. We selected the **OpenAI Realtime API over
WebRTC** as the architecture target and built the whole feature **behind a provider-neutral
adapter**, so a swap to Gemini Live or a backend WS proxy is a provider change, not a UI
change. Because no realtime key is authorised here, the feature ships **OFF by default** and
**live validation is NOT RUN** — everything is validated deterministically with a fake.

## Provider choice & transport
- **Provider:** OpenAI-Realtime shape (env-overridable). **Transport:** WebRTC —
  browser↔provider audio, so Ask4Mo is never in the audio path (lowest latency, cleanest
  secret boundary).
- **Model policy:** a new `ModelOperation.REALTIME_VOICE` + `ModelCapability.REALTIME` in the
  P5 policy. It resolves to **no OpenRouter chat slug** (a realtime model is a separate
  surface); the realtime registry (`src/voice/realtime.py`) picks provider/model/voice
  server-side. A client can never send a slug (the request schema has no model/provider/voice
  field).

## Session security (the secret boundary)
`POST /api/v1/voice/realtime/session` (authenticated, feature-gated, rate-limited) mints a
short-lived credential:

```
authenticated user → feature+entitlement check → rate/concurrency bound →
server-chosen model/voice → provider session-create (SERVER key) →
return ONLY the ephemeral client_secret + bounded config
```

The long-lived key is read as `SecretStr` and unwrapped **exactly once**, into the provider
`Authorization: Bearer` header. It never appears in a response, log, observability event, or
admin projection. Tests assert the response carries only an ephemeral secret.

## Realtime state machine
`idle → connecting → ready → (listening ⇄ assistant_speaking) → interrupted → … → ended`,
plus `reconnecting`, `unavailable`, `error`. Modelled in `frontend/lib/speech/realtimeTypes.ts`
and driven by `useRealtimeVoice.ts` (coordinator-aware: a realtime session **claims the
single audio channel for its whole lifetime**, so realtime and P7 STT/TTS never run together).

## Barge-in
While Mo is speaking, candidate speech-start (provider server-VAD) — or the manual
**Interrupt / Stop Mo** control — triggers, behind the adapter, `response.cancel` +
`conversation.item.truncate` and clears local playback. So the provider's conversation state
matches what the candidate actually heard; the unheard remainder is **not** treated as heard.
The hook then opens a fresh candidate turn. Proven by the unit test and the E2E.

## Practice integration & the transcript/commit model
Realtime is a **bounded Practice voice mode**. The live channel carries the spoken question,
the spoken answer, and the evolving transcript; the transcript is shown as text and, when
final, the candidate presses **Use this answer**, which commits through the **existing**
`submitAnswer` → `POST /interviews/{id}/answers` contract. The deterministic Practice state
machine remains authoritative for sequencing, scoring, completion, report and Progress.
**Commit-once** is guarded per turn (`committedTurn`/`turnId`), so a repeated click, a
re-render or a reconnect replaying the final transcript can never submit a duplicate answer.

## Fallback
Not supported / not configured / disabled / 503 / rate-limited / mic-denied / provider error /
disconnect → the live session ends cleanly, any committed answer is kept, and the candidate
continues with **turn-based P7 voice** and **typing**. The turn-based composer is always
present; realtime is an additive, explicitly-started disclosure. Never a dead end.

## Reconnect
Bounded, not infinite: a transport disconnect surfaces an error and ends the session (fall
back) rather than silently auto-replaying audio or duplicating a committed turn.

## Seven languages
Realtime language follows the candidate's conversation language across en/de/fr/es/it/pt/nl
(coerced to the nearest supported; unsupported → English). It never changes interface locale,
dictation locale, or labour-market geography. Per-language status: **configured +
deterministic** for all seven; **live/human-quality: NOT RUN** (see the matrix).

## Privacy / audio / no trait inference
Ask4Mo records/stores **no** realtime audio (WebRTC streams browser↔provider; provider-side
transient processing follows the provider's own policy — stated honestly, not "local-only").
Partial/final transcripts stay in memory until commit; nothing is written to localStorage,
URL, analytics or audit before commit; the backend never receives or logs a transcript.
**No** emotion/mood/stress/confidence/accent/personality/honesty/hiring inference; no
prosodic/acoustic scoring; no voiceprint/speaker-embedding/biometric.

## Model/agent boundary
Realtime is transport around the **bounded Practice voice mode**; it does not silently bypass
RAG provenance, HITL, private-evidence authorization, model policy, Memory approval or
Practice determinism, because durable turns still flow through the application service and no
tools are exposed to the realtime model (the request schema is a strict allow-list).

## Cost / rate bounds
Server-side: max session duration, max concurrent sessions per user, idle timeout, and a
per-user session-creation rate limit (`RealtimeSessionLimiter`). In-memory/local-only —
production needs a shared store (documented). No billing.

## Observability & admin
Session lifecycle emits **safe metadata only** (outcome, surface, coarse locale, error
category) through `safe_metadata`/`error_category` — never audio, transcript, or secret.
`/admin/providers` gains realtime booleans/labels with explicit `audio_visible_to_admin: false`
and `transcript_visible_to_admin: false` and `live_validation: NOT_RUN`. Workspaces receive
no audio/voice/transcript.

## Evaluation
- `scripts/eval_realtime_voice.py` — 28 deterministic invariants (§31), all PASS, 0 paid calls.
- `tests/test_realtime_voice.py` — 15 backend tests (secret boundary, 503 fallback, rate +
  concurrency, cross-user isolation, policy boundary, capability gate, admin privacy, units).
- `frontend/tests/realtime-voice.test.tsx` — 6 unit tests incl. the **barge-in** test (§32)
  and **commit-once** (single + reset-per-turn).
- `frontend/e2e/realtime-voice.spec.ts` — 2 Practice E2E (§33): start→barge-in→commit-once→
  advance-once; explicit End→turn-based fallback. Fake realtime session; no mic/provider.

## Live validation
| Level | Status |
|---|---|
| Architecture implemented | ✅ |
| Deterministically validated | ✅ (eval + unit + E2E, 0 paid calls) |
| Live provider validated | ❌ NOT RUN (no authorised realtime key; OpenRouter cannot serve realtime) |
| Human-quality validated | ❌ NOT RUN |

## Known limitations
Live round-trip, real VAD/barge-in timing, real reconnect, per-language live audio quality and
real cost are **unvalidated** without an authorised paid key. The WebRTC adapter targets the
documented OpenAI Realtime shape (endpoint env-overridable) but has never made a real call.
The rate limiter is single-process (production needs a shared store).

## Capstone lesson
Realtime voice's integrity lives in its **boundaries and its fallback**, not its latency: a
provider-neutral seam + a deterministic fake let a session-oriented, interruptible feature be
built and fully proven with zero paid calls, while the ephemeral-secret boundary, commit-once
Practice authority, no-audio-storage and no-trait-inference rules keep a sensitive modality
safe — and an honest "architecture delivered, live NOT RUN" beats relabelling turn-based voice
as realtime.

---

## Presentation evidence (slide-ready)

**Architecture**
```
        Candidate (browser)
            ↕ realtime audio (WebRTC)         ← Ask4Mo is NOT in the audio path
     Realtime Voice Adapter (provider-neutral seam)
            ↕ ephemeral client_secret (short-lived; minted server-side)
        Realtime provider session
            ↕ bounded transcript / events
     Ask4Mo application boundary
            ↕  submitAnswer (durable, commit-once)
     Existing Practice / Mo workflow (authoritative)
```

**Interruption (barge-in)**
```
Mo speaking → candidate starts speaking (or presses Interrupt)
           → response.cancel + conversation.item.truncate + clear local audio
           → candidate turn begins (unheard remainder NOT treated as heard)
```

**Fallback**
```
Realtime unavailable / failed  →  P7 turn-based voice  →  typing
```

**Guarantees**
```
NO long-lived provider secret in the browser   (only the ephemeral client_secret)
NO Ask4Mo audio storage                        (no recorder/blob/voiceprint)
NO human-trait inference                        (no emotion/accent/confidence/hiring)
Practice state stays authoritative              (commit-once; no duplicate answers)
```
