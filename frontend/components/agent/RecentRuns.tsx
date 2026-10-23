"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { useT } from "@/components/i18n/I18nProvider";
import { ErrorState } from "@/components/ui/States";
import Link from "@/components/ui/VerifiedLink";
import type { RecentRun, RecentRunsResponse } from "@/lib/api/types";

const STATES = new Set<RecentRun["state"]>(["started", "ready", "failed"]);
const STATE_KEY: Record<RecentRun["state"], string> = {
  started: "recentRuns.stateStarted",
  ready: "recentRuns.stateReady",
  failed: "recentRuns.stateFailed",
};

/** Validates the response shape at the client boundary: a malformed 200 is an explicit error, never a silent empty list (null = invalid). */
export function parseRecentRuns(body: unknown): RecentRun[] | null {
  const runs = (body as Partial<RecentRunsResponse> | null)?.runs;
  if (!Array.isArray(runs)) return null;
  const out: RecentRun[] = [];
  for (const r of runs) {
    const o = r as Partial<RecentRun> | null;
    if (!o || typeof o.run_id !== "string" || !o.run_id || !STATES.has(o.state as RecentRun["state"])) return null;
    out.push({ run_id: o.run_id, state: o.state as RecentRun["state"], created_at: typeof o.created_at === "string" ? o.created_at : null, updated_at: typeof o.updated_at === "string" ? o.updated_at : null });
  }
  return out;
}

/**
 * The caller's OWN recent Mo preparation runs (04D, AC-18). The server returns only the signed-in account's runs (ids, state, dates, never content); a run opens through the existing
 * owner-scoped `/prepare?run=<id>` restore. Read-only and safe to re-run, so a failure recovers in place with a Retry.
 */
export function RecentRuns() {
  const t = useT();
  const [runs, setRuns] = useState<RecentRun[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [retrying, setRetrying] = useState(false);
  const ctrl = useRef<AbortController | null>(null);

  const load = useCallback((isRetry = false) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    if (isRetry) setRetrying(true);
    else setStatus("loading");
    let request: Promise<unknown>;
    try {
      request = api.agent.listRuns(10, { signal: c.signal });
    } catch {
      setStatus("error");          // a client that cannot even issue the read is an explicit error, never a crash of the Prepare page
      setRetrying(false);
      return;
    }
    request
      .then((body) => {
        if (c.signal.aborted) return;
        const parsed = parseRecentRuns(body);
        setRuns(parsed);
        setStatus(parsed ? "ready" : "error");
        setRetrying(false);
      })
      .catch((e) => {
        if (c.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        setStatus("error");
        setRetrying(false);
      });
  }, []);

  useEffect(() => {
    load();
    return () => ctrl.current?.abort();
  }, [load]);

  return (
    <section className="mt-8" aria-labelledby="recent-runs-title" data-testid="recent-runs">
      <h2 id="recent-runs-title" className="text-sm font-semibold text-foreground">{t("recentRuns.title")}</h2>
      <p className="mt-1 text-xs text-muted">{t("recentRuns.hint")}</p>
      {status === "loading" ? <p className="mt-3 text-sm text-muted">{t("common.loading")}</p> : null}
      {status === "error" ? <div className="mt-3"><ErrorState variant="section" message={t("recentRuns.loadError")} retrying={retrying} onRetry={() => load(true)} /></div> : null}
      {status === "ready" && runs && runs.length === 0 ? <p className="mt-3 text-sm text-muted" data-testid="recent-runs-empty">{t("recentRuns.empty")}</p> : null}
      {status === "ready" && runs && runs.length > 0 ? (
        <ul className="mt-3 grid gap-2">
          {runs.map((r) => (
            <li key={r.run_id}>
              <Link href={`/prepare?run=${encodeURIComponent(r.run_id)}`} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm hover:bg-surface-2" data-testid="recent-run">
                <span className="font-medium">{t(STATE_KEY[r.state])}</span>
                <span className="text-xs text-muted">
                  {r.created_at ? t("recentRuns.started", { date: new Date(r.created_at).toLocaleDateString() }) : null}
                  {" "}
                  <span className="font-semibold text-accent">{t("recentRuns.open")}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
