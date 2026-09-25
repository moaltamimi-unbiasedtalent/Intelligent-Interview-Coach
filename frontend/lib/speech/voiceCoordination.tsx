"use client";

/**
 * Voice coordination (Capstone P7 closure).
 *
 * The smallest clean seam that guarantees Ask4Mo STT and Ask4Mo TTS are never actively
 * running at the SAME TIME on the SAME surface. A surface wraps its voice-capable subtree in
 * <VoiceCoordinationProvider>; each modality (dictation / speech output) CLAIMS the single
 * audio channel when it starts, which STOPS whatever else was active first, and RELEASES it
 * when it ends. Claiming only calls the other modality's `stop()` — it never clears the
 * candidate's typed/recognised text, never submits, and never auto-starts the opposite
 * modality. When no provider is present the hook is a no-op, so the shared STT/TTS hooks stay
 * backward-compatible everywhere else.
 */

import { createContext, useCallback, useContext, useMemo, useRef } from "react";

export interface VoiceCoordinator {
  /** Take the audio channel for `owner`, stopping any different current owner first. */
  claim: (owner: symbol, stop: () => void) => void;
  /** Give up the channel if `owner` currently holds it. */
  release: (owner: symbol) => void;
}

const VoiceCoordinationContext = createContext<VoiceCoordinator | null>(null);

export function VoiceCoordinationProvider({ children }: { children: React.ReactNode }) {
  const current = useRef<{ owner: symbol; stop: () => void } | null>(null);

  const claim = useCallback((owner: symbol, stop: () => void) => {
    const active = current.current;
    if (active && active.owner !== owner) {
      try {
        active.stop();
      } catch {
        /* best-effort: stopping the other modality must never throw into the claimer */
      }
    }
    current.current = { owner, stop };
  }, []);

  const release = useCallback((owner: symbol) => {
    if (current.current && current.current.owner === owner) current.current = null;
  }, []);

  const value = useMemo<VoiceCoordinator>(() => ({ claim, release }), [claim, release]);
  return <VoiceCoordinationContext.Provider value={value}>{children}</VoiceCoordinationContext.Provider>;
}

/** The coordinator for the current surface, or null when unwrapped (no-op). */
export function useVoiceCoordinator(): VoiceCoordinator | null {
  return useContext(VoiceCoordinationContext);
}
