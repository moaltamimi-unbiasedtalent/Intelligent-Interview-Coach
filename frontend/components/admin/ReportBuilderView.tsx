"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type {
  BuilderDefinition, ExportFormat, Problem, PreviewResult, ReportFamily, ReportRegistry, RegistryReportType, SavedReport, ValidateResult,
} from "@/lib/admin/reportBuilder";
import { commonDimensions, metricsFor, offeredFilterLabels, problemsFromMessage } from "@/lib/admin/reportBuilder";
import { Panel, ResourceState, StatusLabel, btn, field, useAdminResource } from "./ui";
import { ReportResult } from "./ReportResult";
import { SavedReports, reportErrorText } from "./ReportSaved";

// Governed report builder (03E2). Every choice below comes from the registry the API returned: the report type, the metrics, the window, the grouping
// dimension, the chart kind and the comparison are <select>s and checkboxes over registered ids. There is no field that can carry an unregistered metric,
// an unregistered dimension or a free-text filter (filter values are only the bucket labels a previous grouped preview offered). Validation messages are
// the API's own stable problem codes. The server re-validates and re-authorises everything.

type Draft = BuilderDefinition;

function initialDraft(registry: ReportRegistry, type: RegistryReportType): Draft {
  const first = type.metrics[0];
  const window = (type.windows.includes("30d") ? "30d" : type.windows[0] ?? "30d") as Draft["window"];
  return normalise(registry, { report_id: type.report_id, metric_ids: first ? [first.metric_id] : [], window, group_by: null, filters: [], chart: null, comparison: "none" });
}

/** Keeps a draft consistent with the registry: only registered, compatible choices survive. Never invents a metric. */
function normalise(registry: ReportRegistry, d: Draft): Draft {
  const type = registry.report_types.find((t) => t.report_id === d.report_id);
  if (!type) return d;
  const known = new Set(type.metrics.map((m) => m.metric_id));
  const metric_ids = d.metric_ids.filter((m) => known.has(m)).slice(0, registry.limits.max_metrics);
  let group_by = d.group_by;
  const dims = commonDimensions(registry, d.report_id, metric_ids).map((x) => x.dimension_id);
  const must = type.metrics.filter((m) => metric_ids.includes(m.metric_id) && m.must_group_by).map((m) => m.must_group_by as string);
  if (must.length > 0) group_by = must[0];
  if (group_by !== null && !dims.includes(group_by)) group_by = null;
  const filters = group_by === null ? [] : d.filters.filter((f) => f.dimension_id === group_by && f.values.length > 0);
  const comparable = type.metrics.filter((m) => metric_ids.includes(m.metric_id)).every((m) => m.comparable);
  return { ...d, metric_ids, group_by, filters, comparison: comparable ? d.comparison : "none" };
}

type Check = { status: "idle" } | { status: "checking" } | { status: "error"; message: string } | { status: "done"; result: ValidateResult };

function problemList(problems: Problem[]) {
  return (
    <ul className="grid gap-1 text-sm">
      {problems.map((p, i) => (
        <li key={`${p.code}-${i}`}><code className="text-xs">[{p.code}]</code> {p.message}</li>
      ))}
    </ul>
  );
}

function BuilderBody({ family, registry }: { family: ReportFamily; registry: ReportRegistry }) {
  const client = api.admin.reportBuilder[family];
  const [draft, setDraft] = useState<Draft | null>(() => (registry.report_types[0] ? initialDraft(registry, registry.report_types[0]) : null));
  const [check, setCheck] = useState<Check>({ status: "idle" });
  const [preview, setPreview] = useState<{ result: PreviewResult; key: string } | null>(null);
  const [previewState, setPreviewState] = useState<"idle" | "loading">("idle");
  const [previewError, setPreviewError] = useState<{ message: string; problems: Problem[] } | null>(null);
  const [loadedSaved, setLoadedSaved] = useState<SavedReport | null>(null);
  const [exportBusy, setExportBusy] = useState<ExportFormat | null>(null);
  const [exportNote, setExportNote] = useState<{ ok: boolean; text: string } | null>(null);
  const saved = useAdminResource(() => client.saved(), [family]);
  const pendingSelect = useRef<number | null | undefined>(undefined);

  const type = draft ? registry.report_types.find((t) => t.report_id === draft.report_id) : undefined;
  const key = draft ? JSON.stringify(draft) : "";
  const update = (patch: Partial<Draft>) => setDraft((d) => (d ? normalise(registry, { ...d, ...patch }) : d));

  // Validation by the API (stable problem codes) whenever the definition changes. The result is the only gate for save and export.
  useEffect(() => {
    if (!draft || draft.metric_ids.length === 0) { setCheck({ status: "idle" }); return; }
    let live = true;
    setCheck({ status: "checking" });
    const t = setTimeout(() => {
      client.validate(draft).then(
        (result) => live && setCheck({ status: "done", result }),
        (err) => live && setCheck({ status: "error", message: reportErrorText(err) }),
      );
    }, 200);
    return () => { live = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, family]);

  // After a saved list reload, re-select the saved report the last write concerned (its revision changed).
  useEffect(() => {
    if (saved.state !== "ready" || pendingSelect.current === undefined) return;
    const id = pendingSelect.current;
    pendingSelect.current = undefined;
    setLoadedSaved(id === null ? null : saved.data.items.find((i) => i.id === id) ?? null);
  }, [saved]);

  if (!draft || !type) return <p className="text-sm text-muted" role="status">No report types are available to your role.</p>;

  const valid = check.status === "done" && check.result.valid;
  const validated: BuilderDefinition | null = valid ? draft : null;
  const dims = commonDimensions(registry, draft.report_id, draft.metric_ids);
  const chosen = metricsFor(registry, draft.report_id).filter((m) => draft.metric_ids.includes(m.metric_id));
  const mustGroup = chosen.find((m) => m.must_group_by);
  const comparable = chosen.every((m) => m.comparable);
  const labels = draft.group_by ? offeredFilterLabels(preview?.result ?? null) : [];
  const selectedLabels = draft.filters[0]?.values ?? [];

  const toggleMetric = (id: string) => {
    const has = draft.metric_ids.includes(id);
    if (!has && draft.metric_ids.length >= registry.limits.max_metrics) return;
    update({ metric_ids: has ? draft.metric_ids.filter((m) => m !== id) : [...draft.metric_ids, id] });
  };
  const toggleLabel = (label: string) => {
    if (!draft.group_by) return;
    const has = selectedLabels.includes(label);
    if (!has && selectedLabels.length >= registry.limits.max_filter_values) return;
    const values = has ? selectedLabels.filter((v) => v !== label) : [...selectedLabels, label];
    update({ filters: values.length ? [{ dimension_id: draft.group_by, values }] : [] });
  };
  const chooseType = (id: string) => {
    const t = registry.report_types.find((x) => x.report_id === id);
    if (!t) return;
    setDraft(initialDraft(registry, t));
    setLoadedSaved(null);
    setPreview(null);
    setPreviewError(null);
  };

  const runPreview = async () => {
    if (!validated) return;
    setPreviewState("loading");
    setPreviewError(null);
    try {
      const result = await client.preview(validated);
      setPreview({ result, key: JSON.stringify(validated) });
    } catch (err) {
      setPreview(null);
      setPreviewError({ message: reportErrorText(err), problems: err instanceof ApiError && err.status === 422 ? problemsFromMessage(err.message) : [] });
    } finally {
      setPreviewState("idle");
    }
  };

  const doExport = async (format: ExportFormat) => {
    if (!validated) return;
    setExportBusy(format);
    setExportNote(null);
    try {
      const file = await client.exportReport(format, validated);
      const name = file.filename ?? `ask4mo-${validated.report_id}-${validated.window}.${format}`;
      if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
        const url = URL.createObjectURL(file.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 0);
      }
      setExportNote({ ok: true, text: `Downloaded ${name}${file.rows !== null ? ` (${file.rows} rows)` : ""}. The export was recorded in the audit log before it was sent.` });
    } catch (err) {
      const refused = err instanceof ApiError && err.status === 503 ? err.message
        : err instanceof ApiError && err.status === 403 ? "The export was refused: you may not export this report."
        : err instanceof ApiError && err.status === 422 ? (problemsFromMessage(err.message).map((p) => p.message).join(" ") || "The export was refused.")
        : "The export failed.";
      setExportNote({ ok: false, text: `${refused} No file was downloaded.` });
    } finally {
      setExportBusy(null);
    }
  };

  const loadSaved = (s: SavedReport) => {
    if (!s.definition || !registry.report_types.some((t) => t.report_id === s.definition?.report_id)) return;
    setDraft(normalise(registry, { ...s.definition, window: s.definition.window === "all_time" ? "30d" : s.definition.window }));
    setLoadedSaved(s);
    setPreview(null);
    setPreviewError(null);
  };

  return (
    <div className="grid gap-4">
      <Panel title="Report catalogue">
        <p className="text-xs text-muted">Report types the API lists for your role. Choose one to start a definition.</p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {registry.report_types.map((t) => (
            <li key={t.report_id} className="grid gap-1 rounded border border-default p-3">
              <h3 className="text-sm font-semibold">{t.title}</h3>
              <p className="text-xs text-muted">{t.description}</p>
              <p className="text-xs">{t.metrics.length} metrics. Windows: {t.windows.join(", ")}.</p>
              <button type="button" className={btn} aria-pressed={draft.report_id === t.report_id} onClick={() => chooseType(t.report_id)} aria-label={`Use ${t.title} in the builder`}>
                {draft.report_id === t.report_id ? "In the builder" : "Use in the builder"}
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Builder">
        {family === "commercial" ? <p className="text-sm font-semibold">MOCK BILLING: NOT LIVE REVENUE. Commercial figures come from configured mock terms.</p> : null}
        <fieldset className="grid gap-1">
          <legend className="text-sm font-medium">Metrics (up to {registry.limits.max_metrics})</legend>
          <div className="grid gap-1 sm:grid-cols-2">
            {type.metrics.map((m) => (
              <label key={m.metric_id} className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={draft.metric_ids.includes(m.metric_id)} onChange={() => toggleMetric(m.metric_id)} />
                <span><span className="font-medium">{m.label}</span>{m.must_group_by ? <span className="text-xs text-muted"> (per {m.must_group_by}, always grouped)</span> : null}
                  <span className="block text-xs text-muted">{m.description}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">Window (UTC)
            <select className={field} value={draft.window} onChange={(e) => update({ window: e.target.value as Draft["window"] })}>
              {type.windows.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-sm">Group by
            <select className={field} value={draft.group_by ?? ""} disabled={!!mustGroup} onChange={(e) => update({ group_by: e.target.value || null, filters: [] })}>
              {!mustGroup ? <option value="">No grouping</option> : null}
              {dims.map((d) => <option key={d.dimension_id} value={d.dimension_id}>{d.label}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-sm">Chart
            <select className={field} value={draft.chart ?? ""} onChange={(e) => update({ chart: e.target.value || null })}>
              <option value="">No chart</option>
              {registry.chart_kinds.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-sm">Comparison
            <select className={field} value={draft.comparison} disabled={!comparable} onChange={(e) => update({ comparison: e.target.value as Draft["comparison"] })}>
              {registry.comparisons.map((c) => <option key={c} value={c}>{c === "none" ? "None" : "Previous period"}</option>)}
            </select>
          </label>
        </div>
        {!comparable ? <p className="text-xs text-muted">A selected metric is a current-state figure, so a previous period would be the same number.</p> : null}
        {draft.group_by ? (
          <fieldset className="grid gap-1">
            <legend className="text-sm font-medium">Filter groups (optional)</legend>
            {labels.length === 0 ? <p className="text-xs text-muted">Run a preview to see the groups you can select. Filters only choose among the groups the server returned.</p> : (
              <div className="flex flex-wrap gap-3">
                {labels.map((l) => (
                  <label key={l} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selectedLabels.includes(l)} onChange={() => toggleLabel(l)} /> {l}</label>
                ))}
              </div>
            )}
          </fieldset>
        ) : null}

        <div aria-live="polite" className="grid gap-1" data-testid="report-validation">
          {check.status === "checking" ? <p className="text-sm text-muted">Checking the definition...</p> : null}
          {check.status === "error" ? <p role="alert" className="text-sm">{check.message}</p> : null}
          {draft.metric_ids.length === 0 ? <p className="text-sm text-muted">Select at least one metric.</p> : null}
          {check.status === "done" && check.result.valid ? <StatusLabel tone="ok">Definition is valid</StatusLabel> : null}
          {check.status === "done" && !check.result.valid ? (
            <div role="alert" className="rounded border border-border p-2"><p className="text-sm font-medium">This definition cannot be run:</p>{problemList(check.result.problems)}</div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className={btn} disabled={!valid || previewState === "loading"} onClick={runPreview}>{previewState === "loading" ? "Running..." : "Run preview"}</button>
          <span className="text-sm text-muted">Export:</span>
          {(["csv", "json", "pdf"] as ExportFormat[]).map((f) => (
            <button key={f} type="button" className={btn} disabled={!valid || exportBusy !== null} onClick={() => doExport(f)} aria-label={`Export ${f.toUpperCase()}`}>
              {exportBusy === f ? "Exporting..." : f.toUpperCase()}
            </button>
          ))}
        </div>
        {exportNote ? <p role={exportNote.ok ? "status" : "alert"} className="rounded border border-border p-2 text-sm">{exportNote.text}</p> : null}
        <p className="text-xs text-muted">Exports (CSV, JSON and PDF) contain the already-suppressed aggregates only, at most {registry.limits.max_export_rows} rows (a PDF holds fewer; the server says so if it is too large). Every export is audited before it is sent; if the audit cannot be written nothing is exported.</p>
        {previewError ? (
          <div role="alert" className="rounded border border-border p-2 text-sm">
            <p>{previewError.message}</p>
            {previewError.problems.length ? problemList(previewError.problems) : null}
          </div>
        ) : null}
      </Panel>

      {preview ? <ReportResult preview={preview.result} stale={preview.key !== key} /> : null}

      <ResourceState loaded={saved}>
        {saved.state === "ready" ? (
          <SavedReports family={family} list={saved.data} definition={validated} loaded={loadedSaved} onLoad={loadSaved}
            onChanged={(id) => { pendingSelect.current = id === undefined ? loadedSaved?.id ?? null : id; saved.reload(); }} />
        ) : null}
      </ResourceState>

      <Panel title="Rules">
        <ul className="list-disc pl-5 text-xs text-muted">{registry.rules.map((r, i) => <li key={i}>{r}</li>)}</ul>
        <p className="text-xs text-muted">Candidate groups below {registry.min_cohort} are suppressed.</p>
      </Panel>
    </div>
  );
}

function FamilyBody({ family }: { family: ReportFamily }) {
  const registry = useAdminResource(() => api.admin.reportBuilder[family].registry(), [family]);
  return (
    <ResourceState loaded={registry}>
      {registry.state === "ready" ? <BuilderBody family={family} registry={registry.data} /> : null}
    </ResourceState>
  );
}

/** The catalogue and governed builder inside the Reports destination. The commercial family is offered only to accounts holding the commercial permission. */
export function ReportBuilderView() {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const families = useMemo(() => {
    const f: { id: ReportFamily; label: string }[] = [];
    if (hasAnyPermission(granted, [P.reportsRead])) f.push({ id: "standard", label: "Product, quality and AI economics" });
    if (hasAnyPermission(granted, [P.reportsCommercial])) f.push({ id: "commercial", label: "Commercial (mock billing)" });
    return f;
  }, [granted]);
  const [family, setFamily] = useState<ReportFamily | null>(null);
  const active = family ?? families[0]?.id ?? null;
  if (!active) return <p className="text-sm text-muted" role="status">Your administrator role does not include report access.</p>;
  return (
    <div className="grid gap-4">
      {families.length > 1 ? (
        <div role="group" aria-label="Report family" className="flex flex-wrap gap-2">
          {families.map((f) => <button key={f.id} type="button" className={btn} aria-pressed={active === f.id} onClick={() => setFamily(f.id)}>{f.label}</button>)}
        </div>
      ) : null}
      <FamilyBody key={active} family={active} />
    </div>
  );
}
