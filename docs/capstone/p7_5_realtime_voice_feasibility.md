# P7.5 — C1 Realtime Voice Feasibility Audit

_Capstone P7.5. This audit is written **before** implementation, as the phase mandates. Its
job is to answer honestly whether genuine realtime voice + interruption can be built safely
and credibly within Ask4Mo's provider/runtime constraints — and to refuse to relabel P7
turn-based voice as realtime. No paid/live provider calls were made to produce this audit._

Baseline: `main` @ `77690b7` (P7 merged, PR #82); Alembic head `0011_workspaces_shares`;
branch `feature/capstone-p7-5-c1-realtime-voice`.

---

## A. What exactly does C1 require?

Canonical wording (verbatim from the requirements package):

- **C1** (`docs/capstone/capstone_requirements_matrix.md`, Group H): _"Realtime voice +
  interruption"_ — Current `DEFERRED (out of P7 scope) — turn-based voice delivered instead;
  realtime streaming not built`; Target `Streaming + interrupt + fallback`; Phase `P7+`;
  Acceptance `EX-02`.
- **C1 scope** (`reference/00_Expanded_Project_Plan.md`): _"Streaming conversation, visible
  transcript, interrupt/stop, reconnect and recorded/text fallback"_ with the dependency
  _"Stable recorded Practice first; interrupted or replayed audio cannot commit duplicate
  answers."_
- **EX-02** (`reference/02_Expanded_Acceptance_Checklist.md`): _"C1 realtime speech"_ —
  Status `Not run`; evidence required: _"Actual streaming round trip, interruption, silence,
  timeout, reconnect and recorded/text fallback; no duplicate/stale answer commit or
  post-logout capture."_

So C1 = a **session-oriented, low-latency, streaming** voice conversation with **barge-in
interruption**, a **visible transcript**, **reconnect**, and a **safe fallback**, and the
hard invariant that **interrupted/replayed audio must never commit a duplicate or stale
answer**, and **no capture after logout**.

## B. What counts as genuine realtime in this product?

Explicitly **more than** browser STT + browser TTS in sequence (which is exactly what P7
delivered). Genuine realtime, for Ask4Mo, requires: an explicit realtime-session start;
streaming microphone input; streaming/low-latency spoken model output; session
event/state handling; partial/final transcripts; user interruption (barge-in); output
cancellation/truncation; explicit session end; safe reconnect; and fallback to P7. We do
**not** call sequential STT/TTS "realtime". P7's mutual-exclusion coordinator (one modality
at a time) is the *opposite* of the full-duplex, interruptible channel C1 needs — so realtime
cannot be an incremental tweak to P7; it is a distinct mode.

## C. Which existing P7 components can be reused?

- **The vendor-neutral adapter pattern** (`SpeechOutputAdapter` / `SpeechRecognitionAdapter`)
  is the template for a new `RealtimeVoiceAdapter` seam — same "UI depends on an interface,
  not a provider" discipline, same deterministic-fake-for-CI approach.
- **`toSpeechLocale(conversation_language)`** and the 7-language locale mapping (`ttsLocales`)
  are reused directly for realtime language selection.
- **`toSpeechText`** sanitiser is reusable for anything we render/speak deterministically.
- **The voice coordinator** (`voiceCoordination.tsx`) is reused so a realtime session
  **claims the single audio channel for its whole lifetime** (stopping P7 STT/TTS while
  live), then releases it on end — preventing P7 and realtime from both touching the mic.
- **The i18n `voice` namespace**, `VoicePlaybackControl` a11y patterns, and the Playwright
  fake-injection harness are reused/extended.
- **Backend**: the P5 model-policy pattern, `require_capability`/`get_current_principal`
  auth, the `/capabilities` deployment-flag precedent (`agent_coach_enabled`), the
  `/admin/providers` "booleans only" contract, the `safe_metadata`/`error_category`
  observability choke points, and `read_secret` (SecretStr) secret handling.
- **The Practice application service** (`POST /interviews/{id}/answers`, OCC + idempotency)
  remains the sole authority for durable turns — realtime only *feeds text* into it.

What **cannot** be reused: there is **no backend realtime transport at all** (no WebSocket,
no WebRTC, OpenRouter is non-streaming `"stream": False`), and no realtime provider client.
These are net-new.

## D. Which realtime transports/providers are technically viable?

| Option | Transport | Browser credential | Barge-in | Verdict |
|---|---|---|---|---|
| **OpenAI Realtime API** | **WebRTC** (browser↔provider) or WebSocket | **Ephemeral `client_secret`** minted server-side | Yes: server VAD + `response.cancel` + `conversation.item.truncate` + `input_audio_buffer` events | **Selected** (architecture target) |
| Google Gemini Live | WebSocket | Ephemeral token minted server-side | Yes (provider VAD/interruption) | Viable alternative; there is a *legacy experimental* Gemini-Live browser component behind `INTERVIEW_LIVE_ENABLED` |
| **OpenRouter** (current provider) | chat/completions only | n/a | **No** | **Not viable** — OpenRouter is a non-streaming text proxy; it exposes no realtime audio session and no ephemeral client credential |
| Backend WS proxy (browser↔our server↔provider) | our FastAPI WebSocket | none (key stays server-side) | provider-dependent | Viable but audio flows through our server (cost/latency/statefulness); rejected in favour of WebRTC per §4 "prefer WebRTC" |

**Decision: WebRTC to a direct realtime provider (OpenAI Realtime shape), with the long-lived
key staying server-side and the browser receiving only a short-lived ephemeral session
credential.** This is the lowest-latency browser path, keeps audio off Ask4Mo's servers, and
gives the cleanest, most testable secret boundary. The provider is chosen **behind an
adapter** so a swap to Gemini Live (or a backend WS proxy) is a provider change, not a UI
change. Crucially: **the app's only configured provider today is OpenRouter, which cannot do
this** — so realtime requires introducing a *new* provider surface, which is why this phase
is feasibility-first and live validation is gated on explicit owner authorization + a real
realtime key.

## E. Can credentials remain server-side?

Yes. The long-lived realtime provider key is read via `read_secret` as `SecretStr`
(mirroring `OPENROUTER_API_KEY` / `GEMINI_API_KEY`) and is used **only** on the backend to
mint a short-lived session credential. It is never serialised into any response, log,
observability event, or admin projection. This is the same pattern the codebase already
documents for the Gemini Live key ("used only on the backend to mint short-lived ephemeral
tokens; never sent to the browser").

## F. Can browser clients receive short-lived/session-scoped credentials?

Yes. The OpenAI Realtime session-creation endpoint returns an **ephemeral `client_secret`**
with a short TTL (≈1 minute to establish the connection). The Ask4Mo endpoint
`POST /api/v1/voice/realtime/session` authenticates the user, checks the feature flag +
entitlement, rate-limits, resolves the **server-chosen** model/voice from a bounded
allow-list (never a client slug), mints the ephemeral secret, and returns **only** that
short-lived secret + bounded config + expiry. The browser uses only the ephemeral secret to
open the WebRTC connection.

## G. Can the provider support interruption/barge-in?

Yes — this is the core C1 capability and the reason the OpenAI Realtime shape was chosen.
Server-side VAD detects candidate speech-start while the model is speaking; the client
issues `response.cancel` and (for the already-played prefix) `conversation.item.truncate`,
and clears its local audio buffer, so the provider's conversation state and the candidate's
heard audio stay synchronised — the model does **not** believe the whole answer was heard.
A manual **"Interrupt / Stop Mo"** control performs the same cancellation. All of this lives
**behind the adapter**; the UI emits an abstract `interrupt()` and observes abstract state.

## H. Can sessions fall back safely to P7?

Yes, and this is mandatory and preserved. When realtime is not configured, unsupported
(no `RTCPeerConnection`/`getUserMedia`), disabled by flag, or fails at any point
(connection/credential/provider/mic-denied/disconnect), the session ends cleanly, any
already-committed transcript remains, and the candidate is offered **P7 turn-based voice**
and **typing** — never a dead-end. The Practice state machine is untouched by realtime, so
falling back is just "don't use the live panel". Default configuration ships realtime
**OFF**, so the product's normal state *is* the fallback.

## I. What does realtime cost/latency imply?

Realtime audio models are materially more expensive per minute than turn-based text+browser
speech (which is ~free, browser-side). This phase therefore adds **server-side bounds**:
max session duration, max concurrent sessions per user, idle timeout, and rate-limiting on
the session-creation route (local in-memory limiter; production needs a shared store —
documented). No billing is implemented. Latency is minimised by WebRTC (browser↔provider,
Ask4Mo not in the audio path). Because live calls are unauthorised here, **measured**
cost/latency is not collected; the bounds are enforced regardless.

## J. What remains unvalidated without live authorization?

Everything that requires a real paid realtime session:
- actual streaming round-trip audio quality and latency;
- real provider VAD/barge-in timing and truncation behaviour;
- reconnect against real network failures;
- per-language live audio quality (all 7 languages);
- real cost/usage figures.

These are marked **LIVE PROVIDER VALIDATION: NOT RUN** and **HUMAN QUALITY: not reviewed**.
Everything that can be validated **deterministically** — the provider-neutral adapter, the
session state machine, barge-in event flow, response cancellation, server/client state sync,
manual stop, session end, no-audio-persistence, no-trait-inference, transcript privacy,
Practice-state authority, commit-once/duplicate-turn prevention, cross-user isolation,
language/geography separation, fallback, disconnect recovery, rate bounds, model-policy
boundary, admin/workspace privacy, and the ephemeral-secret boundary — **is** validated with
a deterministic fake adapter/session and an offline invariant eval, with **zero** paid calls.

---

## Feasibility verdict

**Genuine realtime voice + interruption is architecturally feasible** and is implemented in
P7.5 as a **provider-abstracted, fallback-safe** capability: a `RealtimeVoiceAdapter` seam,
a concrete WebRTC adapter targeting the OpenAI Realtime shape, a server-side ephemeral-
session endpoint that never leaks the long-lived key, full barge-in/cancel/state-sync, and a
mandatory fallback to P7 turn-based voice.

**It is scoped as a bounded Practice voice mode** (§19 option A + guardrails): the realtime
channel carries the spoken question, the spoken candidate answer, and the evolving
transcript, but **durable Practice transitions still pass through the existing application
service** — realtime never owns question sequencing, scoring, completion, the report
lifecycle, or Progress persistence, and it never auto-saves Memory. This preserves
determinism, provenance and privacy while delivering the realtime interaction.

**Honest status:** C1 architecture is **DELIVERED + DETERMINISTICALLY VALIDATED**;
**LIVE PROVIDER VALIDATION is NOT RUN** (the only configured provider, OpenRouter, cannot
serve realtime, and no realtime key is authorised/available). Turn-based P7 remains a
separate, delivered capability and the safe fallback. EX-02 remains **Not run** for the live
round-trip; its deterministic sub-checks pass.
