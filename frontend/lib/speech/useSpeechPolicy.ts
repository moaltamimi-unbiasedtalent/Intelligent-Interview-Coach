"use client";

/**
 * Governed browser-speech policy (W12.4E).
 *
 * The Admin-governed backend decides whether the BROWSER speech paths (dictation and speech output) may be offered, via the authenticated
 * `/speech/capabilities`. Until the answer arrives, and when it cannot be fetched (offline, signed out, a test without a backend), the existing behaviour is
 * kept (allowed): the browser path is local and was always available. An EXPLICIT `false` from the backend hides the control and leaves typing and the
 * visible text, so a disabled setting is never bypassed. No audio, language or transcript is sent here; this only reads two booleans.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { SpeechCapabilitiesResponse } from "@/lib/api/types";

export interface SpeechPolicy {
  browserSttAllowed: boolean;
  browserTtsAllowed: boolean;
  /** True once the backend answered (otherwise the safe, pre-existing defaults are in use). */
  known: boolean;
}

const DEFAULT: SpeechPolicy = { browserSttAllowed: true, browserTtsAllowed: true, known: false };

let cached: Promise<SpeechPolicy> | null = null;

function load(): Promise<SpeechPolicy> {
  if (!cached) {
    // Run the call inside a promise so ANY failure (offline, signed out, a test double without the method) falls back to the pre-existing defaults.
    cached = Promise.resolve()
      .then(() => api.speechCapabilities())
      .then((c: SpeechCapabilitiesResponse) => ({
        browserSttAllowed: c.browser_stt_allowed !== false,
        browserTtsAllowed: c.browser_tts_allowed !== false,
        known: true,
      }))
      .catch(() => DEFAULT);
  }
  return cached;
}

/** Test seam: forget the cached answer. */
export function resetSpeechPolicyCache(): void {
  cached = null;
}

export function useSpeechPolicy(): SpeechPolicy {
  const [policy, setPolicy] = useState<SpeechPolicy>(DEFAULT);
  useEffect(() => {
    let alive = true;
    load().then((p) => {
      if (alive) setPolicy(p);
    });
    return () => {
      alive = false;
    };
  }, []);
  return policy;
}
