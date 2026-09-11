"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { InterviewStateResponse } from "@/lib/api/types";

/** Which action is in flight (drives disabled state + observable labels). */
export type Busy =
  | null
  | "loading"
  | "submit"
  | "next"
  | "complete"
  | "recover"
  | "report"
  | "deep_dive"
  | "deep_dive_answer"
  | "deep_dive_next"
  | "deep_dive_return";

export interface InterviewController {
  state: InterviewStateResponse | null;
  busy: Busy;
  loadError: { message: string; requestId?: string | null } | null;
  actionError: string | null;
  conflict: boolean;
  reload: () => Promise<void>;
  submitAnswer: (answer: string) => Promise<boolean>;
  nextQuestion: () => Promise<void>;
  complete: () => Promise<void>;
  recover: () => Promise<void>;
  startDeepDive: (mode: string) => Promise<void>;
  deepDiveAnswer: (answer: string) => Promise<boolean>;
  deepDiveNext: () => Promise<void>;
  deepDiveReturn: () => Promise<void>;
  generateReport: () => Promise<void>;
}

/**
 * Owns the full interview lifecycle against the durable backend. Every mutation
 * disables input while in flight (no duplicate provider calls); a 409 conflict
 * reloads the authoritative state (never overwrites another tab). The backend is the
 * only authority for transitions/scoring — this hook never invents state.
 */
export function useInterview(sessionId?: string): InterviewController {
  const [state, setState] = useState<InterviewStateResponse | null>(null);
  const [busy, setBusy] = useState<Busy>(sessionId ? "loading" : null);
  const [loadError, setLoadError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const mounted = useRef(true);

  // Set true on every (re)mount, not only at initial ref creation. React StrictMode
  // runs effects mount → cleanup → mount again in development; without restoring the
  // flag here the cleanup's `mounted.current = false` would persist into the second
  // mount, and successful fetch results would be silently discarded by the
  // `if (!mounted.current) return` guards below (the interview stayed on its loading
  // skeleton until a manual reload). The cleanup still guards against applying a
  // response after a genuine unmount.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const reload = useCallback(async () => {
    if (!sessionId) return;
    setBusy("loading");
    try {
      const s = await api.interviews.get(sessionId);
      if (!mounted.current) return;
      setState(s);
      setLoadError(null);
    } catch (e) {
      if (!mounted.current) return;
      const err = e as ApiError;
      setLoadError({ message: err.userMessage ?? "Couldn't load the interview.", requestId: err.requestId });
    } finally {
      if (mounted.current) setBusy(null);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) void reload();
  }, [sessionId, reload]);

  // Run a mutation: set busy, apply the returned state, translate a 409 into a
  // conflict reload. Returns true on success (so composers can clear only then).
  const run = useCallback(
    async (label: Busy, fn: () => Promise<InterviewStateResponse>): Promise<boolean> => {
      if (!sessionId) return false;
      setBusy(label);
      setActionError(null);
      setConflict(false);
      try {
        const s = await fn();
        if (!mounted.current) return false;
        setState(s);
        return true;
      } catch (e) {
        if (!mounted.current) return false;
        const err = e as ApiError;
        if (err.status === 409) {
          setConflict(true);
          await reload();
          return false;
        }
        setActionError(err.userMessage ?? "That action could not be completed.");
        return false;
      } finally {
        if (mounted.current) setBusy((b) => (b === label ? null : b));
      }
    },
    [sessionId, reload],
  );

  return {
    state,
    busy,
    loadError,
    actionError,
    conflict,
    reload,
    submitAnswer: (answer) => run("submit", () => api.interviews.submitAnswer(sessionId!, answer)),
    nextQuestion: () => run("next", () => api.interviews.nextQuestion(sessionId!)).then(() => undefined),
    complete: () => run("complete", () => api.interviews.complete(sessionId!)).then(() => undefined),
    recover: () => run("recover", () => api.interviews.recover(sessionId!)).then(() => undefined),
    startDeepDive: (mode) => run("deep_dive", () => api.interviews.deepDive.start(sessionId!, mode)).then(() => undefined),
    deepDiveAnswer: (answer) => run("deep_dive_answer", () => api.interviews.deepDive.answer(sessionId!, answer)),
    deepDiveNext: () => run("deep_dive_next", () => api.interviews.deepDive.next(sessionId!)).then(() => undefined),
    deepDiveReturn: () => run("deep_dive_return", () => api.interviews.deepDive.return(sessionId!)).then(() => undefined),
    generateReport: async () => {
      if (!sessionId) return;
      setBusy("report");
      setActionError(null);
      setConflict(false);
      try {
        // Generate + persist the report (idempotent server-side), then reload the
        // canonical interview state (now report_available).
        await api.interviews.generateReport(sessionId);
        await reload();
      } catch (e) {
        if (!mounted.current) return;
        const err = e as ApiError;
        if (err.status === 409) {
          setConflict(true);
          await reload();
        } else {
          setActionError(err.userMessage ?? "The performance review could not be created.");
        }
      } finally {
        if (mounted.current) setBusy((b) => (b === "report" ? null : b));
      }
    },
  };
}
