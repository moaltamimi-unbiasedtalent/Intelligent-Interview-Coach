"use client";

import { useEffect, useId, useRef, useState } from "react";
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
    <dl className="grid grid-cols-1 gap-y-0.5 text-sm sm:grid-cols-[max-content_1fr] sm:gap-x-4 sm:gap-y-1">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted max-sm:mt-2">{k}</dt>
          <dd className="[overflow-wrap:anywhere]">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** "created_at" -> "Created at" (display only; the data keys are unchanged). */
export function humanizeHeader(key: string): string {
  const t = key.replace(/_/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : key;
}

/** ISO date-times from the API are shown as "2026-10-13 09:00:12 UTC" (no microseconds, no "T"); every other value is shown as it is. */
export function formatCell(value: unknown): string {
  if (value === undefined || value === null || value === "") return "-";
  const text = String(value);
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]00:?00)?$/.exec(text);
  return m ? `${m[1]} ${m[2]} UTC` : text;
}

/**
 * A horizontally scrollable region that is reachable and operable from the keyboard (WCAG 2.1.1 / scrollable-region-focusable): it is focusable, labelled, and
 * positioned so that screen-reader-only text inside it cannot widen the page. Use it around any wide table instead of clipping or hiding columns.
 */
export function ScrollRegion({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div role="region" aria-label={label} tabIndex={0}
      className={"relative overflow-x-auto rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 " + className}>
      {children}
    </div>
  );
}

export function Table({ rows, cols, caption }: { rows: Row[]; cols: string[]; caption: string }) {
  if (rows.length === 0) return <p className="text-sm text-muted">Nothing to show.</p>;
  return (
    <ScrollRegion label={`${caption} (scrollable table)`}>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-xs text-muted">
            {cols.map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{humanizeHeader(c)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-default">
              {cols.map((c) => <td key={c} className="py-1 pr-4 [overflow-wrap:anywhere]">{formatCell(r[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

/** Remembers the control that opened an inline form and returns focus to it when the form is dismissed (call `restore` after the state change). */
export function useRestoreFocus() {
  const opener = useRef<HTMLElement | null>(null);
  return {
    capture: (el: Element | null) => { opener.current = el instanceof HTMLElement ? el : null; },
    restore: () => { const el = opener.current; opener.current = null; if (el) requestAnimationFrame(() => el.isConnected && el.focus()); },
  };
}

/**
 * An inline governed form that makes itself discoverable when it opens: it scrolls into view, moves keyboard focus to its first field, is a labelled region that
 * announces itself to assistive technology, and closes on Escape. The opener restores focus through `useRestoreFocus`. It never changes what the form submits.
 */
export function ActiveFormPanel({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const id = useId();
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollIntoView?.({ block: "start", behavior: "auto" });
    const first = el.querySelector<HTMLElement>("input:not([disabled]), select:not([disabled]), textarea:not([disabled])");
    (first ?? el).focus({ preventScroll: true });
  }, []);
  return (
    <section ref={ref} tabIndex={-1} role="region" aria-labelledby={id} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}
      className="scroll-mt-4 rounded-lg border-2 border-border focus:outline-none">
      <Card>
        <CardBody className="grid gap-2">
          <h2 id={id} className="text-base font-semibold">{title}</h2>
          <p role="status" className="sr-only">Form opened: {title}. Press Escape to cancel.</p>
          {children}
        </CardBody>
      </Card>
    </section>
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
