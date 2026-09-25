/**
 * Text-to-speech (speech OUTPUT) adapter contract (Capstone P7 / E5).
 *
 * A thin, vendor-neutral seam over a speech-synthesis engine so candidate components
 * never touch browser globals directly. The browser adapter wraps the Web Speech
 * SpeechSynthesis API; tests inject a deterministic fake; a different provider could be
 * substituted later without changing the UI.
 *
 * DESIGN INVARIANTS:
 * - The adapter only SPEAKS candidate-visible text. It never records, never persists
 *   audio, never listens, and NEVER derives/returns any human-trait signal (emotion,
 *   personality, accent, confidence, honesty, intelligence, hiring suitability, …).
 * - Playback is always user-initiated and always interruptible (stop()).
 * - No microphone is touched by this layer (that is the separate P3 STT adapter).
 */

/** Safe, user-facing speech-output failure categories (never a raw vendor error). */
export type SpeechOutputErrorKind =
  | "unsupported" // speech synthesis is not available in this environment
  | "no-voice" // no voice is available for the requested language
  | "synthesis-error" // the engine failed while speaking
  | "error"; // any other failure

/** The deterministic speech-output state machine (§21). */
export type SpeechOutputStatus =
  | "idle"
  | "speaking"
  | "paused"
  | "stopped"
  | "unsupported"
  | "error";

export interface SpeechOutputHandlers {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (kind: SpeechOutputErrorKind) => void;
  onPause?: () => void;
  onResume?: () => void;
}

export interface SpeechOutputOptions {
  /** BCP-47 speech-synthesis language tag (e.g. "en-US", "de-DE"). */
  lang?: string;
  /** An optional safe device voice identifier (never a human-trait label). */
  voiceURI?: string;
}

export interface SpeechOutputAdapter {
  /** Whether speech synthesis is available in this environment. */
  isSupported(): boolean;
  /** Whether at least one voice matching `lang` is available (best-effort). */
  hasVoiceFor(lang: string): boolean;
  /** Speak `text`. Any current utterance is cancelled first. Never persists audio. */
  speak(text: string, options: SpeechOutputOptions, handlers: SpeechOutputHandlers): void;
  /** Stop playback immediately. */
  stop(): void;
  /** Optional pause/resume — only exposed where reliably supported. */
  pause?(): void;
  resume?(): void;
}
