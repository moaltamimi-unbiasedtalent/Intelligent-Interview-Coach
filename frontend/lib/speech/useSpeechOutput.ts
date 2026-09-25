"use client";

/**
 * Speech-output (TTS) state hook (Capstone P7 / E5).
 *
 * Owns the playback lifecycle over an injectable SpeechOutputAdapter (browser by default,
 * a fake in tests) with the deterministic state machine IDLE → SPEAKING → (PAUSED) →
 * STOPPED, plus UNSUPPORTED/ERROR. Playback is always user-initiated by the caller; the
 * hook records no audio, listens to nothing, and derives no human-trait signal. It cancels
 * any active playback on unmount so speech never outlives the component (§22).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { browserSpeechSynthesisAdapter } from "./speechSynthesisAdapter";
import type {
  SpeechOutputAdapter,
  SpeechOutputErrorKind,
  SpeechOutputStatus,
} from "./ttsTypes";

export interface UseSpeechOutputOptions {
  adapter?: SpeechOutputAdapter;
  /** BCP-47 speech locale (from toSpeechLocale(conversationLanguage)). */
  lang?: string;
  voiceURI?: string;
}

export interface UseSpeechOutput {
  supported: boolean;
  status: SpeechOutputStatus;
  speaking: boolean;
  error: SpeechOutputErrorKind | null;
  /** Speak the given already-visible text. A no-op fallback sets UNSUPPORTED. */
  speak: (text: string) => void;
  stop: () => void;
}

export function useSpeechOutput({ adapter, lang, voiceURI }: UseSpeechOutputOptions = {}): UseSpeechOutput {
  const engine = adapter ?? browserSpeechSynthesisAdapter;
  const supported = engine.isSupported();
  const [status, setStatus] = useState<SpeechOutputStatus>(supported ? "idle" : "unsupported");
  const [error, setError] = useState<SpeechOutputErrorKind | null>(null);

  const speak = useCallback(
    (text: string) => {
      if (!supported) {
        setStatus("unsupported");
        setError("unsupported");
        return;
      }
      setError(null);
      engine.speak(
        text,
        { lang, voiceURI },
        {
          onStart: () => setStatus("speaking"),
          onEnd: () => setStatus("idle"),
          onError: (kind) => {
            setError(kind);
            setStatus("error");
          },
          onPause: () => setStatus("paused"),
          onResume: () => setStatus("speaking"),
        },
      );
    },
    [engine, lang, voiceURI, supported],
  );

  const stop = useCallback(() => {
    engine.stop();
    setStatus((s) => (s === "unsupported" ? s : "stopped"));
  }, [engine]);

  // Stop any active playback on unmount / adapter change — no zombie speech after
  // navigation (§22).
  useEffect(() => {
    return () => engine.stop();
  }, [engine]);

  return { supported, status, speaking: status === "speaking", error, speak, stop };
}
