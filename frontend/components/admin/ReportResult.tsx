"use client";

import type { Bucket, MetricStateB, PreviewMetric, PreviewResult } from "@/lib/admin/reportBuilder";
import { STATE_WORDS, figureText } from "@/lib/admin/reportBuilder";
import { Panel, ScrollRegion, StatusLabel } from "./ui";

// Preview rendering for the governed builder (03E2). A suppressed bucket, an unavailable metric or a not-captured one is shown as exactly that, never as 0;
// a bar exists only for an "ok" figure. Every chart is followed by its data-table equivalent (a table is always present, so the chart is never the only carrier).

interface Row { label: string; state: MetricStateB | Bucket["state"]; value: number | string | null; series: "current" | "previous" }

function rowsFor(m: PreviewMetric, compare: boolean): Row[] {
  const rows: Row[] = [];
  if (m.buckets !== null) {
    for (const b of m.buckets) rows.push({ label: b.label, state: b.state, value: b.value, series: "current" });
    if (compare && m.previous?.buckets) for (const b of m.previous.buckets) rows.push({ label: b.label, state: b.state, value: b.value, series: "previous" });
  } else {
    rows.push({ label: "Current period", state: m.state, value: m.value, series: "current" });
    if (compare && m.previous) rows.push({ label: "Previous period", state: m.previous.state, value: m.previous.value, series: "previous" });
  }
  return rows;
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function Bars({ metric, rows, kind }: { metric: PreviewMetric; rows: Row[]; kind: string }) {
  const bars = rows.filter((r) => r.state === "ok" && isNum(r.value));
  const max = Math.max(0, ...bars.map((r) => r.value as number));
  const total = kind === "share_of_whole" ? bars.filter((r) => r.series === "current").reduce((a, r) => a + (r.value as number), 0) : 0;
  const rowH = 26;
  const labelW = 150;
  const barW = 320;
  const height = rows.length * rowH + 4;
  const summary = `${metric.label}: ${rows.map((r) => `${r.label}${r.series === "previous" ? " (previous)" : ""} ${figureText(r.state, r.value, metric.unit)}`).join("; ")}`;
  return (
    <figure className="grid gap-1">
      <svg role="img" aria-label={summary} viewBox={`0 0 ${labelW + barW + 120} ${height}`} className="h-auto w-full max-w-2xl text-foreground">
        {rows.map((r, i) => {
          const y = i * rowH + 2;
          const ok = r.state === "ok" && isNum(r.value);
          const w = ok && max > 0 ? Math.max(0, ((r.value as number) / max) * barW) : 0;
          const share = ok && kind === "share_of_whole" && total > 0 ? ` (${Math.round(((r.value as number) / total) * 100)}% of shown)` : "";
          return (
            <g key={`${r.series}-${r.label}-${i}`}>
              <text x={0} y={y + 16} fontSize="12" fill="currentColor">{r.label.length > 24 ? `${r.label.slice(0, 23)}...` : r.label}{r.series === "previous" ? " (prev.)" : ""}</text>
              {ok ? (
                <>
                  <rect x={labelW} y={y + 3} width={w} height={rowH - 8} className={r.series === "previous" ? "fill-muted" : "fill-accent"} />
                  <text x={labelW + w + 6} y={y + 16} fontSize="12" fill="currentColor">{figureText(r.state, r.value, metric.unit)}{share}</text>
                </>
              ) : (
                <text x={labelW} y={y + 16} fontSize="12" fill="currentColor" fontStyle="italic">{STATE_WORDS[r.state] ?? "Unavailable"}</text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="text-xs text-muted">
        Chart kind: {kind.replace(/_/g, " ")}.
        {kind === "share_of_whole" ? " Shares are of the visible buckets only; suppressed buckets are excluded." : ""}
        {kind === "trend" ? " Registered metrics have no time breakdown, so this compares the groups or periods shown." : ""}
      </figcaption>
    </figure>
  );
}

function MetricBlock({ m, preview }: { m: PreviewMetric; preview: PreviewResult }) {
  const compare = preview.comparison === "previous_period";
  const rows = rowsFor(m, compare);
  const chartable = preview.chart !== null && preview.chart !== "table" && rows.some((r) => r.state === "ok" && isNum(r.value));
  const grouped = m.buckets !== null;
  return (
    <section aria-labelledby={`rb-${m.metric_id}`} className="grid gap-2 rounded border border-default p-3">
      <h3 id={`rb-${m.metric_id}`} className="text-sm font-semibold">{m.label}</h3>
      {!grouped ? <p className="text-lg font-semibold">{figureText(m.state, m.value, m.unit)}</p> : null}
      <p className="flex flex-wrap gap-2">
        <StatusLabel tone={m.state === "ok" ? "ok" : "warn"}>{STATE_WORDS[m.state] ?? m.state}</StatusLabel>
        {m.partial ? <StatusLabel tone="neutral">Partial coverage</StatusLabel> : null}
      </p>
      {m.coverage ? <p className="text-xs text-muted">Coverage: {m.coverage}</p> : null}
      {m.note ? <p className="text-xs text-muted">{m.note}</p> : null}
      {chartable ? <Bars metric={m} rows={rows} kind={preview.chart as string} /> : null}
      <ScrollRegion label={`${m.label} data table (scrollable)`}>
        <table className="w-full text-left text-sm">
          <caption className="py-1 text-left text-xs text-muted">{chartable ? "Data table equivalent of the chart" : "Data table"}</caption>
          <thead>
            <tr className="text-xs text-muted">
              <th scope="col" className="py-1 pr-4 font-medium">{grouped ? m.group_dimension ?? "Group" : "Period"}</th>
              {compare ? <th scope="col" className="py-1 pr-4 font-medium">Series</th> : null}
              <th scope="col" className="py-1 pr-4 font-medium">Value</th>
              <th scope="col" className="py-1 pr-4 font-medium">State</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? <tr><td className="py-1 text-muted" colSpan={compare ? 4 : 3}>No groups to show.</td></tr> : rows.map((r, i) => (
              <tr key={`${r.series}-${r.label}-${i}`} className="border-t border-default">
                <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">{r.label}</th>
                {compare ? <td className="py-1 pr-4">{r.series === "current" ? "Current" : "Previous"}</td> : null}
                <td className="py-1 pr-4">{r.state === "ok" ? figureText(r.state, r.value, m.unit) : "-"}</td>
                <td className="py-1 pr-4">{STATE_WORDS[r.state] ?? r.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

export function ReportResult({ preview, stale }: { preview: PreviewResult; stale: boolean }) {
  return (
    <Panel title={`Preview: ${preview.title}`}>
      {stale ? <p role="status" className="rounded border border-border p-2 text-sm">The definition changed after this preview. Run the preview again to refresh it.</p> : null}
      <p className="text-xs text-muted">
        Window (UTC): {preview.window_start ?? "all time"} to {preview.window_end}
        {preview.comparison === "previous_period" && preview.previous_window_start ? `. Previous period: ${preview.previous_window_start} to ${preview.previous_window_end}.` : ""}
      </p>
      <div className="grid gap-3">{preview.metrics.map((m) => <MetricBlock key={m.metric_id} m={m} preview={preview} />)}</div>
      <p className="text-xs text-muted">{preview.privacy}</p>
    </Panel>
  );
}
