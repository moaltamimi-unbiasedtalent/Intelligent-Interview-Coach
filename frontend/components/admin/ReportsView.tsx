"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { ReportMetric, ReportPeriod, AdminReport, ReportSection } from "@/lib/admin/types";
import { Panel, PermissionGate, ResourceState, StatusLabel, btn, field, useAdminResource } from "./ui";

// Admin reporting. Aggregates only; small candidate cohorts are suppressed by the server (value null, never a count). A missing value is
// "Not captured" or "Unavailable", never 0. Commercial figures are MOCK BILLING and live behind a separate permission.

const PERIODS: { id: ReportPeriod; label: string }[] = [
  { id: "7d", label: "Last 7 days" }, { id: "30d", label: "Last 30 days" }, { id: "90d", label: "Last 90 days" }, { id: "all_time", label: "All time" },
];
type Tab = "product" | "quality" | "operations" | "ai-economics" | "commercial";
const TABS: { id: Tab; label: string; perm: string }[] = [
  { id: "product", label: "Product", perm: P.reportsRead }, { id: "quality", label: "Quality", perm: P.reportsRead },
  { id: "operations", label: "Operations", perm: P.reportsRead }, { id: "ai-economics", label: "AI economics", perm: P.reportsRead },
  { id: "commercial", label: "Commercial", perm: P.reportsCommercial },
];
const STATE_TEXT: Record<string, string> = {
  available: "Available", partial: "Partial coverage", suppressed: "Suppressed: small cohort", unavailable: "Unavailable", not_captured: "Not captured",
};

export function ReportsView() {
  return (
    <PermissionGate anyOf={[P.reportsRead, P.reportsCommercial]}>
      <Body />
    </PermissionGate>
  );
}

function fmt(m: ReportMetric): string {
  if (m.figure === null || m.figure === undefined) return STATE_TEXT[m.state] ?? "Unavailable";
  const unit = m.unit === "percent" ? "%" : m.unit === "usd" ? " USD" : m.unit === "seconds" ? " s" : m.unit === "hours" ? " h" : m.unit === "tokens" ? " tokens" : "";
  return `${m.figure}${unit}`;
}

function Metric({ m }: { m: ReportMetric }) {
  return (
    <div className="rounded border border-default p-3">
      <p className="text-xs text-muted">{m.label}</p>
      <p className="text-lg font-semibold">{fmt(m)}</p>
      <p className="mt-1"><StatusLabel tone={m.state === "available" ? "ok" : m.state === "partial" ? "neutral" : "warn"}>{STATE_TEXT[m.state] ?? m.state}</StatusLabel></p>
      {m.coverage ? <p className="text-xs text-muted">{m.coverage}</p> : null}
      {m.note ? <p className="text-xs text-muted">{m.note}</p> : null}
    </div>
  );
}

function Section({ s }: { s: ReportSection }) {
  return (
    <section aria-labelledby={`rep-${s.section_id}`} className="grid gap-3">
      <Panel title={s.title}>
        <p id={`rep-${s.section_id}`} className="sr-only">{s.title}</p>
        <p className="text-xs text-muted">Coverage: {s.coverage}{s.captured_since ? ` Captured since ${s.captured_since}.` : ""}</p>
        {s.note ? <p className="text-sm">{s.note}</p> : null}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{s.metrics.map((m) => <Metric key={m.metric_id} m={m} />)}</div>
        {s.tables.map((t) => (
          <div key={t.table_id} className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="py-1 text-left text-sm font-medium">{t.title}</caption>
              <thead><tr className="text-xs text-muted"><th scope="col" className="py-1 pr-4 font-medium">Group</th>{t.columns.map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
              <tbody>
                {t.rows.length === 0 ? <tr><td className="py-1 text-muted" colSpan={t.columns.length + 1}>Nothing to show.</td></tr> : t.rows.map((r) => (
                  <tr key={r.label} className="border-t border-default">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">{r.label}</th>
                    {r.cells.map((c, i) => <td key={i} className="py-1 pr-4">{c.suppressed ? "Suppressed: small cohort" : c.figure === null ? "Not captured" : String(c.figure)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            {t.note ? <p className="text-xs text-muted">{t.note}</p> : null}
          </div>
        ))}
      </Panel>
    </section>
  );
}

function Body() {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const tabs = TABS.filter((t) => hasAnyPermission(granted, [t.perm]));
  const [tab, setTab] = useState<Tab>(tabs[0]?.id ?? "product");
  const [period, setPeriod] = useState<ReportPeriod>("30d");
  const report = useAdminResource<AdminReport>(() => api.admin.report(tab, period), [tab, period]);
  return (
    <div className="grid gap-4">
      <p className="text-sm">Aggregate reporting only: no candidate content, no identifiers and no per-person drilldown. Candidate groups below the engineering privacy floor are suppressed (this is not an anonymisation guarantee). Unknown values are never shown as zero.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">Period (UTC)
          <select className={field} value={period} onChange={(e) => setPeriod(e.target.value as ReportPeriod)}>
            {PERIODS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <div role="tablist" aria-label="Report sections" className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={btn} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
      </div>
      {tab === "commercial" ? (
        <p role="note" className="rounded border-2 border-border p-3 text-base font-semibold">MOCK BILLING — NOT LIVE REVENUE</p>
      ) : null}
      <ResourceState loaded={report}>
        {report.state === "ready" ? (
          <>
            <p className="text-xs text-muted">Window (UTC): {report.data.window_start ?? "all time"} to {report.data.window_end}</p>
            {report.data.sections.map((s) => <Section key={s.section_id} s={s} />)}
          </>
        ) : null}
      </ResourceState>
    </div>
  );
}
