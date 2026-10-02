"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";

/** Admin surface UI primitives (English-only by decision AD-01; operators, not candidates). */

type Row = Record<string, unknown>;

/** UX gate for one admin view. The server re-authorises every request; this only avoids a dead end. */
export function PermissionGate({ anyOf, children }: { anyOf: readonly string[]; children: ReactNode }) {
  const auth = useAuthOptional();
  if (!auth || auth.status === "loading") return <p className="text-sm text-muted">Loading...</p>;
  if (!hasAnyPermission(adminPermissions(auth.account), anyOf)) {
    return (
      <p role="status" className="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-muted">
        Your administrator role does not include access to this area.
      </p>
    );
  }
  return <>{children}</>;
}

export type Loaded<T> =
  | { state: "loading" }
  | { state: "error" }
  | { state: "ready"; data: T };

/** One bounded fetch on mount and whenever `deps` change; `reload()` refetches after a write. Nothing is retried automatically. */
export function useAdminResource<T>(load: () => Promise<T>, deps: readonly unknown[] = []): Loaded<T> & { reload: () => void } {
  const [value, setValue] = useState<Loaded<T>>({ state: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    load()
      .then((data) => live && setValue({ state: "ready", data }))
      .catch(() => live && setValue({ state: "error" }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...value, reload: () => setTick((n) => n + 1) };
}

export function ResourceState({ loaded, children }: { loaded: Loaded<unknown>; children: ReactNode }) {
  if (loaded.state === "loading") return <p className="text-sm text-muted" role="status">Loading...</p>;
  if (loaded.state === "error") return <p className="text-sm text-muted" role="alert">That request could not be processed.</p>;
  return <>{children}</>;
}

export function Stat({ label, value }: { label: string; value: unknown }) {
  return (
    <Card>
      <CardBody>
        <p className="text-xs text-muted">{label}</p>
        <p className="text-xl font-semibold">{value === undefined || value === null ? "Not available" : String(value)}</p>
      </CardBody>
    </Card>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardBody className="grid gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {children}
      </CardBody>
    </Card>
  );
}

/** Status is conveyed by a text label first; the marker is decoration only (never colour-only). */
export function StatusLabel({ tone, children }: { tone: "ok" | "warn" | "neutral"; children: ReactNode }) {
  const mark = tone === "ok" ? "OK" : tone === "warn" ? "Attention" : "Info";
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-border px-2 py-0.5 text-xs font-medium text-foreground">
      <span aria-hidden="true">{tone === "warn" ? "!" : tone === "ok" ? "+" : "-"}</span>
      <span className="sr-only">{mark}: </span>
      {children}
    </span>
  );
}

export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="[overflow-wrap:anywhere]">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Table({ rows, cols, caption }: { rows: Row[]; cols: string[]; caption: string }) {
  if (rows.length === 0) return <p className="text-sm text-muted">Nothing to show.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-xs text-muted">
            {cols.map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-default">
              {cols.map((c) => <td key={c} className="py-1 pr-4 [overflow-wrap:anywhere]">{String(r[c] ?? "-")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Pager for server-side pagination (page numbers are 1-based). */
export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 text-sm">
      <span role="status">{total === 0 ? "No results" : `Page ${page} of ${pages} (${total} total)`}</span>
      <span className="flex gap-2">
        <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)} className={btn}>Previous</button>
        <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)} className={btn}>Next</button>
      </span>
    </nav>
  );
}

export const btn =
  "min-h-[40px] rounded border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:opacity-50";
export const field =
  "min-h-[40px] rounded border border-border bg-surface px-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";

export function apiMessage(err: unknown): string {
  const m = err instanceof Error ? err.message : "";
  return m && m.length < 200 ? m : "That request could not be processed.";
}
