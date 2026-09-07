"use client";

import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { CapabilitiesResponse } from "./api/types";

/** Safe defaults: everything experimental is OFF until the backend says otherwise. */
const SAFE_DEFAULT: CapabilitiesResponse = {
  career_intelligence: true,
  interview_practice: true,
  knowledge_base: true,
  evaluation: true,
  live_interview_enabled: false,
  agentic_rag: false,
  agent_memory: false,
  human_in_the_loop: false,
};

export interface CapabilitiesState {
  capabilities: CapabilitiesResponse;
  loading: boolean;
  /** True when the backend couldn't be reached (safe defaults are in use). */
  offline: boolean;
}

/**
 * Fetches /capabilities on mount (client-side only, never at build/SSR) and falls
 * back to safe defaults if the backend is unavailable — so Live is never shown as
 * production functionality unless the backend explicitly enables it.
 */
export function useCapabilities(): CapabilitiesState {
  const [state, setState] = useState<CapabilitiesState>({
    capabilities: SAFE_DEFAULT,
    loading: true,
    offline: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    api
      .capabilities({ signal: controller.signal })
      .then((capabilities) =>
        setState({ capabilities, loading: false, offline: false }),
      )
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ capabilities: SAFE_DEFAULT, loading: false, offline: true });
        }
      });
    return () => controller.abort();
  }, []);

  return state;
}
