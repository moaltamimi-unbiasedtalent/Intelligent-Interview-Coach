/**
 * Browser Web Speech API adapter (Capstone P3 / E-dictation).
 *
 * Wraps `window.SpeechRecognition` / `window.webkitSpeechRecognition`. Recognition
 * may be performed by a browser/vendor speech service (NOT necessarily on-device) —
 * the Help/Privacy copy states this honestly. We map raw error codes to safe kinds
 * and never expose vendor errors to the UI. No audio is stored anywhere.
 */

import type {
  DictationErrorKind,
  DictationHandlers,
  DictationStartOptions,
  SpeechRecognitionAdapter,
} from "./types";

// Minimal structural types for the Web Speech API (avoids a lib dependency).
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
  onend: (() => void) | null;
  onresult: ((e: SpeechResultEventLike) => void) | null;
}
interface SpeechResultEventLike {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
}

function getCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function mapError(code: string | undefined): DictationErrorKind {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "permission-denied";
    case "audio-capture":
      return "no-microphone";
    case "no-speech":
      return "no-speech";
    case "network":
      return "network";
    case "aborted":
      return "aborted";
    default:
      return "error";
  }
}

export class BrowserSpeechAdapter implements SpeechRecognitionAdapter {
  private recognition: SpeechRecognitionLike | null = null;

  isSupported(): boolean {
    return getCtor() !== null;
  }

  start(options: DictationStartOptions, handlers: DictationHandlers): void {
    const Ctor = getCtor();
    if (!Ctor) {
      handlers.onError?.("unsupported");
      handlers.onEnd?.();
      return;
    }
    let recognition: SpeechRecognitionLike;
    try {
      recognition = new Ctor();
    } catch {
      handlers.onError?.("error");
      handlers.onEnd?.();
      return;
    }
    this.recognition = recognition;
    recognition.lang = options.lang || "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => handlers.onStart?.();
    recognition.onerror = (e) => handlers.onError?.(mapError(e?.error));
    recognition.onend = () => {
      this.recognition = null;
      handlers.onEnd?.();
    };
    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const transcript = res[0]?.transcript ?? "";
        handlers.onResult?.({ transcript, isFinal: Boolean(res.isFinal) });
      }
    };

    try {
      recognition.start();
    } catch {
      // e.g. start() called twice; surface a safe error and end.
      this.recognition = null;
      handlers.onError?.("error");
      handlers.onEnd?.();
    }
  }

  stop(): void {
    try {
      this.recognition?.stop();
    } catch {
      /* ignore */
    }
  }

  abort(): void {
    try {
      this.recognition?.abort();
    } catch {
      /* ignore */
    }
    this.recognition = null;
  }
}

/** Default singleton adapter (browser). Tests inject a fake instead. */
export const browserSpeechAdapter = new BrowserSpeechAdapter();
