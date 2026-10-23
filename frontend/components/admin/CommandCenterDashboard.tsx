"use client";

import { useEffect, useId, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { CcBreakdown, CcComponent, CcDefinitions, CcMetric, CcSection } from "@/lib/admin/commandCenterGuard";
import {
  COST_WORDING, EVIDENCE_LABEL, MISSING_LABEL, PERIOD_LABEL, formatBucket, formatMetricFigure, formatRatio, formatWhen, humanizeKey, suppressionText,
} from "@/lib/admin/commandCenterFormat";
import { AI_OPERATIONS_SECTION, COMMAND_CENTER_SECTIONS } from "@/lib/admin/commandCenterSections";
import type { CommandCenterSectionSpec } from "@/lib/admin/commandCenterSections";
import { PERIOD_KINDS } from "@/lib/admin/metricContract";
import type { MetricPeriodKind } from "@/lib/admin/metricContract";
import { Card, CardBody } from "@/components/ui/Card";
import { ScrollRegion } from "./ui";

// Command Center dashboard (03D2, REQ-OWN-01 C1 to C5, frontend half) over the 03D1 read model and the frozen 03K contract.
// Rules this file enforces: a figure that is suppressed, unavailable or not captured is shown AS THAT STATE and never as zero; every figure carries its period, numerator
// and denominator (when the contract provides them), coverage, evidence status and suppression state in TEXT; cost is exact integer micro-USD labelled "known cost, partial
// coverage"; every chart has a data-table equivalent and prints its values (no colour-only meaning); a response that is not the documented shape (checked at the client
// boundary) renders the explicit Admin error state; a route the account may not read is hidden or shown as "Not permitted", never an error crash.

type SectionState = { state: "loading" } | { state: "error" } | { state: "forbidden" } | { state: "ready"; data: CcSection };
const ERROR_TEXT = "That request could not be processed.";

function useSection(spec: CommandCenterSectionSpec, period: MetricPeriodKind, enabled: boolean): SectionState {
  const [value, setValue] = useState<SectionState>({ state: "loading" });
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    setValue({ state: "loading" });
    api.admin.commandCenterSection(spec.path, period)
      .then((data) => live && setValue({ state: "ready", data }))
      .catch((err) => live && setValue({ state: err instanceof ApiError && err.status === 403 ? "forbidden" : "error" }));
    return () => { live = false; };
  }, [spec.path, period, enabled]);
  return value;
}

function useDefinitions(enabled: boolean): { state: "loading" } | { state: "error" } | { state: "ready"; data: CcDefinitions } {
  const [value, setValue] = useState<{ state: "loading" } | { state: "error" } | { state: "ready"; data: CcDefinitions }>({ state: "loading" });
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    api.admin.commandCenterDefinitions().then((data) => live && setValue({ state: "ready", data })).catch(() => live && setValue({ state: "error" }));
    return () => { live = false; };
  }, [enabled]);
  return value;
}

/** Dashboard of every section the account may read (the Command Center home). */
export function CommandCenterDashboard() {
  return <Dashboard specs={COMMAND_CENTER_SECTIONS} id="cc-dashboard" title="Operations dashboard" />;
}

/** The AI operations section on its own (the AI and models destination). */
export function AiOperationsDashboard() {
  return <Dashboard specs={[AI_OPERATIONS_SECTION]} id="cc-ai-dashboard" title="AI operations" />;
}

function Dashboard({ specs, id, title }: { specs: readonly CommandCenterSectionSpec[]; id: string; title: string }) {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const ready = !!auth && auth.status !== "loading";
  const allowed = specs.filter((s) => hasAnyPermission(granted, [s.permission]));
  const hidden = specs.filter((s) => !hasAnyPermission(granted, [s.permission]));
  const [period, setPeriod] = useState<MetricPeriodKind>("30d");
  const defs = useDefinitions(ready && allowed.length > 0);
  const periods = defs.state === "ready" && defs.data.periods.length ? defs.data.periods : [...PERIOD_KINDS];
  const periodId = useId();
  if (!ready || (allowed.length === 0 && hidden.length === 0)) return null;
  const defOf = new Map(defs.state === "ready" ? defs.data.metrics.map((m) => [m.metric_id, m]) : []);
  return (
    <section aria-labelledby={`${id}-h`} className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id={`${id}-h`} className="text-lg font-semibold">{title}</h2>
        {allowed.length ? (
          <div className="grid gap-1 text-sm">
            <label htmlFor={periodId} className="text-xs text-muted">Period</label>
            <select id={periodId} value={period} onChange={(e) => setPeriod(e.target.value as MetricPeriodKind)}
              className="rounded border border-border bg-surface px-2 py-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
              {periods.map((p) => <option key={p} value={p}>{PERIOD_LABEL[p]}</option>)}
            </select>
          </div>
        ) : null}
      </div>
      <p className="text-xs text-muted">Aggregates only. Figures are never shown as zero when they are missing: a missing figure shows its state (Not captured, Unavailable or Suppressed). Times are UTC.</p>
      {defs.state === "error" ? <p role="alert" className="text-sm">Metric definitions: {ERROR_TEXT} Figures are shown without their definitions.</p> : null}
      {allowed.map((spec) => <SectionPanel key={spec.path} spec={spec} period={period} defs={defOf} />)}
      {hidden.length ? (
        <p role="status" className="text-sm text-muted">
          Not permitted for your administrator role: {hidden.map((s) => s.title).join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

function SectionPanel({ spec, period, defs }: { spec: CommandCenterSectionSpec; period: MetricPeriodKind; defs: Map<string, CcDefinitionLike> }) {
  const loaded = useSection(spec, period, true);
  const hid = useId();
  return (
    <section aria-labelledby={hid} className="grid gap-3 rounded-lg border border-border p-4">
      <div>
        <h3 id={hid} className="text-base font-semibold">{spec.title}</h3>
        <p className="text-xs text-muted">{spec.purpose}</p>
      </div>
      {loaded.state === "loading" ? <p role="status" className="text-sm text-muted">Loading...</p> : null}
      {loaded.state === "error" ? <p role="alert" className="text-sm text-muted">{ERROR_TEXT}</p> : null}
      {loaded.state === "forbidden" ? <p role="status" className="text-sm text-muted">Not permitted: your administrator role does not include {spec.title}.</p> : null}
      {loaded.state === "ready" ? <SectionBody data={loaded.data} defs={defs} /> : null}
    </section>
  );
}

type CcDefinitionLike = CcDefinitions["metrics"][number];

export function SectionBody({ data, defs }: { data: CcSection; defs: Map<string, CcDefinitionLike> }) {
  const withCharts = data.metrics.filter((m) => m.breakdowns.length > 0);
  return (
    <div className="grid gap-3">
      <p className="text-xs text-muted">
        Period: {PERIOD_LABEL[data.period]}
        {data.window_start ? `, ${formatWhen(data.window_start)} to ${formatWhen(data.window_end)}` : `, up to ${formatWhen(data.window_end)}`}. Generated {formatWhen(data.generated_at)}.
        {data.captured_since ? ` Captured since ${formatWhen(data.captured_since)}.` : ""}
      </p>
      {data.components.length ? <Components items={data.components} /> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {data.metrics.map((m) => <MetricTile key={m.metric_id} m={m} def={defs.get(m.metric_id)} />)}
      </div>
      {withCharts.map((m) => m.breakdowns.map((b) => <BreakdownChart key={`${m.metric_id}:${b.dimension_id}`} metric={m} breakdown={b} />))}
      <p className="text-xs text-muted">{data.privacy}</p>
    </div>
  );
}

export function MetricTile({ m, def }: { m: CcMetric; def?: CcDefinitionLike }) {
  const ratio = formatRatio(m);
  const missing = m.state !== "ok";
  const pct = m.state === "ok" && m.unit === "percent" && typeof m.value === "number" ? Math.max(0, Math.min(100, m.value)) : null;
  return (
    <Card>
      <CardBody className="grid gap-1.5 p-4">
        <div className="grid gap-1.5">
          <h4 className="text-sm font-medium [overflow-wrap:anywhere]">{m.label}</h4>
          <p className={"text-xl font-semibold [overflow-wrap:anywhere] " + (missing ? "text-muted" : "")} data-testid={`fig-${m.metric_id}`}>{formatMetricFigure(m)}</p>
          {pct !== null ? <div aria-hidden="true" className="h-1.5 w-full rounded bg-border"><div className="h-1.5 rounded bg-accent" style={{ width: `${pct}%` }} /></div> : null}
          <p className="text-xs">
            <span className="rounded border border-border px-1.5 py-0.5 font-medium">Evidence: {EVIDENCE_LABEL[m.evidence]}</span>
            {m.partial ? <span className="ml-1 rounded border border-border px-1.5 py-0.5 font-medium">Partial coverage</span> : null}
          </p>
          <dl className="grid gap-0.5 text-xs text-muted">
            <div><dt className="inline">Period: </dt><dd className="inline">{PERIOD_LABEL[m.period]}</dd></div>
            <div><dt className="inline">Numerator and denominator: </dt><dd className="inline">{ratio ?? (m.numerator !== null ? `${m.numerator} (no denominator)` : "none provided")}</dd></div>
            <div><dt className="inline">Coverage: </dt><dd className="inline [overflow-wrap:anywhere]">{m.coverage || "not stated"}</dd></div>
            <div><dt className="inline">Suppression: </dt><dd className="inline">{suppressionText(m)}</dd></div>
          </dl>
          {m.unit === "usd" ? <p className="text-xs">{COST_WORDING}</p> : null}
          {m.note ? <p className="text-xs text-muted [overflow-wrap:anywhere]">{m.note}</p> : null}
          {def ? (
            <details className="text-xs text-muted">
              <summary className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">Definition</summary>
              <p>{def.description}</p>
              <p>Numerator: {def.numerator.subject} ({def.numerator.aggregation}).{def.denominator ? ` Denominator: ${def.denominator.subject} (${def.denominator.aggregation}).` : " No denominator."}</p>
              <p>Source: {m.evidence_source}. Missing data shows as: {MISSING_LABEL[def.missing_behaviour]}.</p>
            </details>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}

/**
 * Horizontal bars compare buckets of ONE dimension of ONE measure (a share/comparison question). Values are printed beside each bar and a data table gives the same data,
 * so nothing relies on colour or shape. A suppressed or unavailable bucket draws NO bar and says so in text (never a zero-length bar).
 */
export function BreakdownChart({ metric, breakdown }: { metric: CcMetric; breakdown: CcBreakdown }) {
  const hid = useId();
  const max = Math.max(0, ...breakdown.buckets.map((b) => (b.state === "ok" && b.value !== null ? b.value : 0)));
  return (
    <figure aria-labelledby={hid} className="grid gap-2 rounded border border-border p-3">
      <figcaption id={hid} className="text-sm font-medium">{metric.label} by {breakdown.label.toLowerCase()} ({PERIOD_LABEL[metric.period]})</figcaption>
      {metric.unit === "usd" ? <p className="text-xs text-muted">{COST_WORDING}</p> : null}
      <ul className="grid gap-1.5 text-sm">
        {breakdown.buckets.map((b) => (
          <li key={b.key} className="grid gap-0.5">
            <div className="flex flex-wrap justify-between gap-x-3 [overflow-wrap:anywhere]">
              <span>{humanizeKey(b.label)}{b.partial ? " (partial)" : ""}</span>
              <span className={b.state === "ok" ? "font-medium" : "text-muted"}>{formatBucket(b, metric.unit)}</span>
            </div>
            {b.state === "ok" && b.value !== null ? (
              <div aria-hidden="true" className="h-2 w-full rounded bg-border">
                <div className="h-2 rounded bg-accent" style={{ width: `${max > 0 ? Math.max(2, Math.round((b.value / max) * 100)) : 2}%` }} />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      <details className="text-xs">
        <summary className="cursor-pointer text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">Data table for this chart</summary>
        <ScrollRegion label={`${metric.label} by ${breakdown.label} (scrollable table)`}>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{metric.label} by {breakdown.label}</caption>
            <thead><tr className="text-xs text-muted"><th scope="col" className="py-1 pr-4 font-medium">{breakdown.label}</th><th scope="col" className="py-1 pr-4 font-medium">Value</th><th scope="col" className="py-1 pr-4 font-medium">Coverage</th></tr></thead>
            <tbody>
              {breakdown.buckets.map((b) => (
                <tr key={b.key} className="border-t border-default">
                  <th scope="row" className="py-1 pr-4 text-left font-medium">{b.key}</th>
                  <td className="py-1 pr-4">{formatBucket(b, metric.unit)}</td>
                  <td className="py-1 pr-4">{b.state !== "ok" ? "No figure" : b.partial ? "Partial coverage" : "Complete for known units"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </details>
    </figure>
  );
}

const COMPONENT_STATUS: Record<CcComponent["status"], string> = { ok: "OK", attention: "Attention", unavailable: "Unavailable", info: "Info" };

function Components({ items }: { items: CcComponent[] }) {
  const hid = useId();
  return (
    <div>
      <h4 id={hid} className="mb-1 text-sm font-medium">Current state</h4>
      <ul aria-labelledby={hid} className="grid gap-1 text-sm sm:grid-cols-2">
        {items.map((c) => (
          <li key={c.component_id} className="rounded border border-border px-2 py-1 [overflow-wrap:anywhere]">
            <span className="font-medium">{c.label}</span>{": "}
            <span className="font-medium">{c.evidence === "unavailable" && c.status === "unavailable" ? "Unavailable" : COMPONENT_STATUS[c.status]}</span>
            {c.note ? <span className="block text-xs text-muted">{c.note}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
