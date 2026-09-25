"use client";

/**
 * Dictation state hook (Capstone P3 / E-dictation).
 *
 * Owns the recognition lifecycle over an injectable adapter (browser by default,
 * a fake in tests). It commits ONLY final transcript segments to the caller; interim
 * text is exposed as a transient preview and is never written into the field, so
 * confirmed/typed text can never be corrupted. The hook submits nothing, stores no
 * audio, and writes nothing to storage.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  DictationErrorKind,
  SpeechRecognitionAdapter,
} from "./types";
import { browserSpeechAdapter } from "./browserAdapter";
import { useVoiceCoordinator } from "./voiceCoordination";

export type DictationStatus = "idle" | "listening";

export interface UseDictationOptions {
  adapter?: SpeechRecognitionAdapter;
  lang?: string;
  /** Called with each FINAL segment — safe to append to the text field. */
  onCommitFinal: (text: string) => void;
}

export interface UseDictation {
  supported: boolean;
  status: DictationStatus;
  interim: string;
  error: DictationErrorKind | null;
  start: () => void;
  stop: () => void;
}

export function useDictation({ adapter, lang, onCommitFinal }: UseDictationOptions): UseDictation {
  const engine = adapter ?? browserSpeechAdapter;
  const [status, setStatus] = useState<DictationStatus>("idle");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<DictationErrorKind | null>(null);

  // Keep the latest commit callback without re-subscribing the adapter.
  const commitRef = useRef(onCommitFinal);
  commitRef.current = onCommitFinal;

  const supported = engine.isSupported();

  // Voice coordination (P7 closure): claim the surface's single audio channel when we start
  // listening (stops any active TTS first) and release it when recognition ends. No-op when
  // the surface is not wrapped in a VoiceCoordinationProvider. Stopping the other modality
  // never clears typed/recognised text and never submits.
  const coordinator = useVoiceCoordinator();
  const ownerId = useRef<symbol>(Symbol("stt"));

  const start = useCallback(() => {
    if (!supported) {
      setError("unsupported");
      return;
    }
    setError(null);
    setInterim("");
    // Claim BEFORE listening so active playback is stopped first (mutual exclusion).
    coordinator?.claim(ownerId.current, () => engine.stop());
    engine.start(
      { lang },
      {
        onStart: () => setStatus("listening"),
        onResult: ({ transcript, isFinal }) => {
          if (isFinal) {
            setInterim("");
            const text = transcript.trim();
            if (text) commitRef.current(text);
          } else {
            setInterim(transcript);
          }
        },
        onError: (kind) => {
          coordinator?.release(ownerId.current);
          setError(kind);
          setStatus("idle");
          setInterim("");
        },
        onEnd: () => {
          coordinator?.release(ownerId.current);
          setStatus("idle");
          setInterim("");
        },
      },
    );
  }, [engine, lang, supported, coordinator]);

  const stop = useCallback(() => {
    engine.stop();
    coordinator?.release(ownerId.current);
  }, [engine, coordinator]);

  // Abort on unmount so a background recognition never outlives the component.
  useEffect(() => {
    return () => engine.abort();
  }, [engine]);

  return { supported, status, interim, error, start, stop };
}

/**
 * Append a recognised segment to existing field text, preserving what the user has
 * already typed. Adds a single separating space when needed; never replaces content.
 */
export function appendTranscript(existing: string, chunk: string): string {
  const addition = chunk.trim();
  if (!addition) return existing;
  if (!existing) return addition;
  const needsSpace = !/\s$/.test(existing);
  return existing + (needsSpace ? " " : "") + addition;
}
