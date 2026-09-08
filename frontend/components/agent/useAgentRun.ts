"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type {
  AgentRunRequest,
  AgentRunResponse,
  HumanDecisionRequest,
} from "@/lib/api/types";

export interface AgentError {
  message: string;
  requestId?: string | null;
  /** A bookmarked run that no longer exists / is not owned by the caller. */
  notFound?: boolean;
}

export interface UseAgentRun {
  run: AgentRunResponse | null;
  /** A request is in flight — used to lock conflicting controls (§39). */
  busy: boolean;
  /** Restoring a run from the URL on load. */
  restoring: boolean;
  error: AgentError | null;
  runId: string | null;
  start: (req: AgentRunRequest) => Promise<void>;
  send: (message: string) => Promise<void>;
  resume: (decision: HumanDecisionRequest) => Promise<void>;
  reset: () => void;
  clearError: () => void;
}

function toError(e: unknown): AgentError {
  const err = e as ApiError;
  const notFound = err?.status === 404;
  return {
    message: notFound
      ? "This preparation session can no longer be resumed."
      : err?.userMessage ?? "Something went wrong. Please try again.",
    requestId: err?.requestId ?? null,
    notFound,
  };
}

/**
 * Manages one Agent Coach run: start, multi-turn continue, HITL resume and refresh.
 * The run id lives in the URL (?run=…) so refresh/deep-link work; a single in-flight
 * request is enforced (no parallel turns on the same thread). Private content is
 * never placed in the URL or localStorage.
 */
export function useAgentRun(): UseAgentRun {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlRunId = searchParams.get("run");

  const [run, setRun] = useState<AgentRunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<AgentError | null>(null);
  const inFlight = useRef(false);

  const setRunAndUrl = useCallback(
    (next: AgentRunResponse) => {
      setRun(next);
      if (next.run_id && next.run_id !== urlRunId) {
        router.replace(`/prepare?run=${encodeURIComponent(next.run_id)}`, { scroll: false });
      }
    },
    [router, urlRunId],
  );

  // Restore a run referenced by the URL (refresh / deep link) exactly once.
  useEffect(() => {
    if (!urlRunId || run) return;
    const ctrl = new AbortController();
    setRestoring(true);
    api.agent
      .getRun(urlRunId, { signal: ctrl.signal })
      .then((r) => setRun(r))
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(toError(e));
      })
      .finally(() => setRestoring(false));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRunId]);

  const guarded = useCallback(
    async (fn: () => Promise<AgentRunResponse>) => {
      if (inFlight.current) return; // §39: one request at a time per thread
      inFlight.current = true;
      setBusy(true);
      setError(null);
      try {
        const next = await fn();
        setRunAndUrl(next);
      } catch (e) {
        setError(toError(e));
      } finally {
        inFlight.current = false;
        setBusy(false);
      }
    },
    [setRunAndUrl],
  );

  const start = useCallback(
    (req: AgentRunRequest) => guarded(() => api.agent.start(req)),
    [guarded],
  );

  const send = useCallback(
    (message: string) => {
      const id = run?.run_id;
      if (!id) return Promise.resolve();
      return guarded(() => api.agent.continue(id, { message }));
    },
    [guarded, run?.run_id],
  );

  const resume = useCallback(
    (decision: HumanDecisionRequest) => {
      const id = run?.run_id;
      if (!id) return Promise.resolve();
      return guarded(() => api.agent.resume(id, decision));
    },
    [guarded, run?.run_id],
  );

  const reset = useCallback(() => {
    setRun(null);
    setError(null);
    router.replace("/prepare", { scroll: false });
  }, [router]);

  const clearError = useCallback(() => setError(null), []);

  return {
    run,
    busy,
    restoring,
    error,
    runId: run?.run_id ?? urlRunId,
    start,
    send,
    resume,
    reset,
    clearError,
  };
}
