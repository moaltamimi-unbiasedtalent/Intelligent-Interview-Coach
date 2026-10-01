"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiError } from "@/lib/api/errors";

/** One independently loaded read resource: loading -> ready | error, with a safe GET retry (P10B-W9.8). */
export type Resource<T> = {
  status: "loading" | "ready" | "error";
  data: T | null;
  error: ApiError | null;
  retrying: boolean;
};

export type ResourceHandle<T> = {
  state: Resource<T>;
  reload: () => void;
  update: (fn: (d: T) => T) => void;
};

/** Read-only (covariant) view of a handle, for presentational helpers. */
export type ResourceView = { state: Resource<readonly unknown[]>; reload: () => void };

export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>): ResourceHandle<T> {
  const initial: Resource<T> = { status: "loading", data: null, error: null, retrying: false };
  const [state, setState] = useState<Resource<T>>(initial);
  const ctrl = useRef<AbortController | null>(null);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const load = useCallback((isRetry = false) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setState((s) => (isRetry ? { ...s, retrying: true } : { status: "loading", data: null, error: null, retrying: false }));
    loaderRef
      .current(c.signal)
      .then((data) => {
        if (!c.signal.aborted) setState({ status: "ready", data, error: null, retrying: false });
      })
      .catch((e) => {
        if (c.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        setState({ status: "error", data: null, error: e as ApiError, retrying: false });
      });
  }, []);

  useEffect(() => {
    load();
    return () => ctrl.current?.abort();
  }, [load]);

  const update = useCallback((fn: (d: T) => T) => {
    setState((s) => (s.data ? { ...s, data: fn(s.data) } : s));
  }, []);

  return { state, reload: () => load(true), update };
}
