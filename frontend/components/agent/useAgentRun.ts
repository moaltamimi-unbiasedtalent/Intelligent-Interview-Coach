"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useT } from "@/components/i18n/I18nProvider";
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
  /** An operator pause (stable code platform_paused): the UI shows localized copy, never this message. */
  paused?: boolean;
  /** An accurate, localizable cause (04D): the i18n key to show INSTEAD of `message`, set for "AI not configured" and "AI service unavailable" (stable codes, never English matching). */
  stateKey?: string;
}

export interface UseAgentRun {
  run: AgentRunResponse | null;
  /** A request is in flight — used to lock conflicting controls (§39). */
  busy: boolean;
  progress: string | null;
  stopping: boolean;
  cancel: () => Promise<void>;
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

function toError(e: unknown, t: (key: string) => string): AgentError {
  const err = e as ApiError;
  const notFound = err?.status === 404;
  return {
    paused: err?.kind === "paused",
    stateKey: err?.kind === "aiNotConfigured" ? "states.aiNotConfigured" : err?.kind === "aiUnavailable" ? "states.aiProviderUnavailable" : err?.kind === "unavailable" ? "states.serviceUnavailable" : undefined,
    message: notFound
      ? t("prepare.sessionGone")
      : err?.userMessage ?? t("states.genericError"),
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
export function useAgentRun(streamEnabled = false): UseAgentRun {
  const t = useT();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlRunId = searchParams.get("run");

  const [run, setRun] = useState<AgentRunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<AgentError | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [streamId, setStreamId] = useState<string | null>(null);
  const currentStreamId = useRef<string | null>(null);
  const transport = useRef<AbortController | null>(null);
  useEffect(() => () => transport.current?.abort(), []);
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
    if (!urlRunId || run || inFlight.current) return;
    const ctrl = new AbortController();
    setRestoring(true);
    api.agent
      .getRun(urlRunId, { signal: ctrl.signal })
      .then(async (r) => {
        setRun(r);
        if (streamEnabled && r.status === "running") {
          // Read-only reconnect: keep the same durable run; never replay POST /run.
          inFlight.current = true;
          setBusy(true);
          setProgress("run_started");
          currentStreamId.current = urlRunId;
          setStreamId(urlRunId);
          const restored = await api.agent.reconnect(urlRunId, { onProgress: setProgress }, { signal: ctrl.signal });
          setRun(restored);
        }
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(toError(e, t));
      })
      .finally(() => {
        setRestoring(false);
        if (currentStreamId.current === urlRunId) {
          inFlight.current = false;
          setBusy(false);
          setProgress(null);
          setStopping(false);
          currentStreamId.current = null;
          setStreamId(null);
        }
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRunId, streamEnabled]);

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
        if (!(e instanceof DOMException && e.name === "AbortError")) setError(toError(e, t));
      } finally {
        inFlight.current = false;
        setBusy(false);
        setProgress(null);
        setStopping(false);
        currentStreamId.current = null;
        setStreamId(null);
      }
    },
    [setRunAndUrl, t],
  );

  const start = useCallback(
    (req: AgentRunRequest) => guarded(() => {
      if (!streamEnabled) return api.agent.start(req);
      const ctrl = new AbortController();
      transport.current = ctrl;
      setProgress("run_started");
      return api.agent.startStream(req, {
        onRun: (id) => {
          currentStreamId.current = id;
          setStreamId(id);
          router.replace(`/prepare?run=${encodeURIComponent(id)}`, { scroll: false });
        },
        onProgress: (kind) => setProgress(kind),
      }, { signal: ctrl.signal });
    }),
    [guarded, router, streamEnabled],
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

  const cancel = useCallback(async () => {
    const id = currentStreamId.current;
    if (!id || stopping) return;
    setStopping(true);
    try {
      await api.agent.cancel(id);
      setProgress("stopping");
    } catch (e) {
      setError(toError(e, t));
      setStopping(false);
    }
  }, [stopping, t]);

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
    runId: run?.run_id ?? streamId ?? urlRunId,
    progress, stopping, cancel,
    start,
    send,
    resume,
    reset,
    clearError,
  };
}
