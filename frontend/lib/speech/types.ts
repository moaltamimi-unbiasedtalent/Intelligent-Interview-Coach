/**
 * Speech-to-text adapter contract (Capstone P3 / E-dictation).
 *
 * A thin, vendor-neutral seam over a speech-recognition engine so the UI never
 * touches browser globals directly. The browser adapter wraps the Web Speech API;
 * tests inject a deterministic fake; another provider could be substituted later
 * without changing the input components.
 *
 * DESIGN INVARIANTS:
 * - The adapter only RECOGNISES speech and emits text. It never submits anything,
 *   never persists audio, and never analyses emotion/identity/voice characteristics.
 * - Only FINAL transcript segments are meant to be committed to a text field by the
 *   caller; interim text is a transient preview and must not corrupt typed text.
 */

/** Safe, user-facing failure categories (never raw browser/vendor errors). */
export type DictationErrorKind =
  | "unsupported" // the engine is not available in this environment
  | "permission-denied" // microphone permission was refused
  | "no-microphone" // no capture device / audio capture failed
  | "no-speech" // nothing was heard
  | "network" // the recognition service could not be reached
  | "aborted" // stopped/cancelled
  | "error"; // any other failure

export interface DictationResult {
  /** The recognised text for this event. */
  transcript: string;
  /** True when the engine considers this segment final (safe to commit). */
  isFinal: boolean;
}

export interface DictationHandlers {
  onStart?: () => void;
  onResult?: (result: DictationResult) => void;
  onError?: (kind: DictationErrorKind) => void;
  /** Fires once recognition ends (whether by stop, error or natural end). */
  onEnd?: () => void;
}

export interface DictationStartOptions {
  /** BCP-47 language tag (e.g. "en-US", "de-DE"). */
  lang?: string;
}

export interface SpeechRecognitionAdapter {
  /** Whether recognition is available in this environment. */
  isSupported(): boolean;
  /** Begin recognition. No-op guidance: callers must not call while already active. */
  start(options: DictationStartOptions, handlers: DictationHandlers): void;
  /** Stop recognition gracefully (a final result may still arrive). */
  stop(): void;
  /** Abort immediately (no further results). */
  abort(): void;
}
