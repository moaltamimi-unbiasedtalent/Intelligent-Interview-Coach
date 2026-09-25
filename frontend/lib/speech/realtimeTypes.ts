// Realtime voice — provider-neutral seam (Capstone P7.5, C1).
//
// The UI depends ONLY on these interfaces, never on a provider's event names. A concrete
// adapter (WebRTC/OpenAI-Realtime, or the deterministic fake) implements them. This mirrors
// the P7 SpeechOutputAdapter / P3 SpeechRecognitionAdapter discipline.
//
// No audio or transcript is persisted anywhere by this layer: audio streams browser↔provider,
// transcripts are held only in React state until the candidate commits them through the
// existing Practice answer contract.

export type RealtimeVoiceState =
  | "idle" // no session
  | "connecting" // fetching grant + establishing transport
  | "ready" // connected, awaiting the exchange
  | "listening" // candidate speaking (mic streaming)
  | "assistant_speaking" // Mo streaming spoken output
  | "interrupted" // candidate barged in; Mo output cancelled
  | "reconnecting" // bounded reconnect in progress
  | "ended" // session ended cleanly
  | "unavailable" // realtime not available → fall back to turn-based
  | "error"; // unrecoverable session error → fall back

export type RealtimeErrorKind =
  | "unsupported" // browser lacks WebRTC/getUserMedia
  | "unavailable" // server says realtime is off/unconfigured
  | "credential" // ephemeral session credential failed
  | "connection" // transport could not connect
  | "mic-permission" // microphone denied/blocked
  | "provider" // provider-side failure mid-session
  | "disconnect" // dropped mid-session
  | "error"; // any other failure

export type RealtimeTranscriptRole = "assistant" | "candidate";

export interface RealtimeTranscriptEvent {
  role: RealtimeTranscriptRole;
  // The evolving text for the CURRENT turn. `isFinal` marks the utterance complete.
  text: string;
  isFinal: boolean;
}

// The grant the server mints (mirror of RealtimeSessionResponse). `clientSecret` is the
// provider's EPHEMERAL token — never the long-lived key.
export interface RealtimeSessionGrant {
  provider: string;
  model: string;
  voice: string;
  locale: string;
  clientSecret: string;
  expiresAt: number;
  sessionId: string;
  baseUrl: string;
  maxSessionSeconds: number;
  idleTimeoutSeconds: number;
}

export interface RealtimeVoiceHandlers {
  onState?: (state: RealtimeVoiceState) => void;
  onTranscript?: (evt: RealtimeTranscriptEvent) => void;
  onError?: (kind: RealtimeErrorKind) => void;
  // Fired when the candidate barges in and Mo's output is cancelled/truncated.
  onInterrupted?: () => void;
  onAssistantAudioStart?: () => void;
  onAssistantAudioEnd?: () => void;
  onDisconnected?: () => void;
}

// A live realtime session. Provider-specific operations (response.cancel,
// conversation.item.truncate, SDP negotiation, ICE) stay BEHIND this interface.
export interface RealtimeVoiceSession {
  connect(): Promise<void>;
  // Barge-in: cancel + truncate Mo's current spoken output and let the candidate take the
  // turn. Synchronises provider + client so the model does NOT treat the whole response as
  // heard. Safe to call when Mo is not speaking (no-op).
  interrupt(): void;
  // Manual "Stop Mo" — cancel the current generation without ending the session.
  stopAssistant(): void;
  // End the session and release all transport/media resources. Idempotent.
  disconnect(): void;
  getState(): RealtimeVoiceState;
}

export interface RealtimeVoiceAdapter {
  // Provider/config independence: whether the runtime can do realtime at all.
  isSupported(): boolean;
  // Build a session from a server-minted grant. Never fetches the grant itself and never
  // holds a long-lived key.
  createSession(
    grant: RealtimeSessionGrant,
    handlers: RealtimeVoiceHandlers,
  ): RealtimeVoiceSession;
}
