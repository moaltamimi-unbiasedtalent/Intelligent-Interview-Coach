import type {
  DictationErrorKind,
  DictationHandlers,
  SpeechRecognitionAdapter,
} from "@/lib/speech/types";

/**
 * Deterministic speech adapter for tests. Nothing here touches the browser, a
 * microphone or any network — recognition events are emitted on demand.
 */
export class FakeSpeechAdapter implements SpeechRecognitionAdapter {
  supported: boolean;
  handlers: DictationHandlers | null = null;
  started = false;
  stopCalls = 0;
  abortCalls = 0;

  constructor(opts?: { supported?: boolean }) {
    this.supported = opts?.supported ?? true;
  }

  isSupported() {
    return this.supported;
  }

  start(_opts: unknown, handlers: DictationHandlers) {
    this.handlers = handlers;
    this.started = true;
    handlers.onStart?.();
  }

  stop() {
    this.stopCalls++;
    this.handlers?.onEnd?.();
  }

  abort() {
    this.abortCalls++;
  }

  // --- test helpers ---
  emitInterim(transcript: string) {
    this.handlers?.onResult?.({ transcript, isFinal: false });
  }
  emitFinal(transcript: string) {
    this.handlers?.onResult?.({ transcript, isFinal: true });
  }
  emitError(kind: DictationErrorKind) {
    this.handlers?.onError?.(kind);
    this.handlers?.onEnd?.();
  }
}
