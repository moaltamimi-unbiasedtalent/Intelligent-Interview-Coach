// Deterministic fake realtime adapter/session (Capstone P7.5).
//
// Simulates the full realtime lifecycle WITHOUT a microphone or any provider — so CI, unit
// tests and Playwright can prove the state machine, barge-in, cancellation, transcript
// commit-once and fallback with ZERO paid/live calls. Tests drive it via the `__*` methods.

import type {
  RealtimeErrorKind,
  RealtimeSessionGrant,
  RealtimeVoiceAdapter,
  RealtimeVoiceHandlers,
  RealtimeVoiceSession,
  RealtimeVoiceState,
} from "./realtimeTypes";

export interface FakeRealtimeSession extends RealtimeVoiceSession {
  // Test drivers (simulate provider/mic events):
  __ready(): void;
  __assistantSpeaking(): void;
  __assistantTranscript(text: string, isFinal: boolean): void;
  __assistantAudioEnd(): void;
  __candidateSpeechStart(): void; // barge-in trigger while Mo is speaking
  __candidateTranscript(text: string, isFinal: boolean): void;
  __disconnect(): void;
  __fail(kind: RealtimeErrorKind): void;
  // Observability for assertions:
  interrupts: number;
  assistantCancels: number;
  connected: boolean;
}

export interface FakeRealtimeAdapter extends RealtimeVoiceAdapter {
  sessions: FakeRealtimeSession[];
  createSession(
    grant: RealtimeSessionGrant,
    handlers: RealtimeVoiceHandlers,
  ): FakeRealtimeSession;
}

export function createFakeRealtimeAdapter(
  opts: { supported?: boolean; connectFails?: RealtimeErrorKind | null } = {},
): FakeRealtimeAdapter {
  const supported = opts.supported ?? true;
  const connectFails = opts.connectFails ?? null;
  const sessions: FakeRealtimeSession[] = [];

  return {
    sessions,
    isSupported: () => supported,
    createSession(grant, handlers): FakeRealtimeSession {
      let state: RealtimeVoiceState = "idle";
      const set = (s: RealtimeVoiceState) => {
        state = s;
        handlers.onState?.(s);
      };

      const session: FakeRealtimeSession = {
        interrupts: 0,
        assistantCancels: 0,
        connected: false,

        async connect() {
          set("connecting");
          if (connectFails) {
            handlers.onError?.(connectFails);
            set(connectFails === "unavailable" ? "unavailable" : "error");
            return;
          }
          this.connected = true;
          set("ready");
        },

        interrupt() {
          // Barge-in: cancel + truncate Mo's output, hand the turn to the candidate.
          if (state === "assistant_speaking") {
            this.assistantCancels += 1;
            handlers.onAssistantAudioEnd?.();
          }
          this.interrupts += 1;
          handlers.onInterrupted?.();
          set("interrupted");
        },

        stopAssistant() {
          if (state === "assistant_speaking") {
            this.assistantCancels += 1;
            handlers.onAssistantAudioEnd?.();
            set("ready");
          }
        },

        disconnect() {
          if (state === "ended") return;
          this.connected = false;
          set("ended");
        },

        getState() {
          return state;
        },

        // ---- test drivers ----
        __ready() {
          this.connected = true;
          set("ready");
        },
        __assistantSpeaking() {
          handlers.onAssistantAudioStart?.();
          set("assistant_speaking");
        },
        __assistantTranscript(text, isFinal) {
          handlers.onTranscript?.({ role: "assistant", text, isFinal });
        },
        __assistantAudioEnd() {
          handlers.onAssistantAudioEnd?.();
          if (state === "assistant_speaking") set("ready");
        },
        __candidateSpeechStart() {
          // Provider server-VAD detected candidate speech. If Mo was speaking this is a
          // barge-in and Mo's output must be cancelled first.
          if (state === "assistant_speaking") {
            this.assistantCancels += 1;
            this.interrupts += 1;
            handlers.onAssistantAudioEnd?.();
            handlers.onInterrupted?.();
          }
          set("listening");
        },
        __candidateTranscript(text, isFinal) {
          handlers.onTranscript?.({ role: "candidate", text, isFinal });
        },
        __disconnect() {
          this.connected = false;
          handlers.onError?.("disconnect");
          handlers.onDisconnected?.();
          set("error");
        },
        __fail(kind) {
          handlers.onError?.(kind);
          set(kind === "unavailable" ? "unavailable" : "error");
        },
      };
      sessions.push(session);
      return session;
    },
  };
}
