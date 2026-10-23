// Admin report builder (package 03E2): types, runtime guards and pure helpers over the merged 03E1 API (src/api/schemas/report_builder.py).
// The contract files metricContract.* (03K) are frozen and are only imported here, never edited.
//
// Rule for every consumer: a bucket or metric that is not state "ok" has value === null and renders as that state, never as zero. Every response is
// validated at the client boundary by the guards below (the lesson of PR #228): a malformed 200 must surface as the explicit Admin error state.

import { CHART_KINDS, COMPARISON_MODES } from "./metricContract";
import type { AdminReport, ReportCell, ReportMetric, ReportRow, ReportTable } from "./types";

export type BuilderWindow = "7d" | "30d" | "90d";
export type MetricStateB = "ok" | "suppressed" | "unavailable" | "not_captured";
export type BucketState = "ok" | "suppressed" | "unavailable";
export type ExportFormat = "csv" | "json" | "pdf";
export type ReportFamily = "standard" | "commercial";

export interface RegistryMetric {
  metric_id: string; label: string; description: string; unit: string; coverage: string; suppression: "cohort" | "operational";
  dimensions: string[]; must_group_by: string | null; comparable: boolean;
}
export interface RegistryReportType {
  report_id: string; title: string; description: string; permission_required: string; windows: string[]; metrics: RegistryMetric[];
}
export interface RegistryDimension { dimension_id: string; label: string; description: string; kind: "time" | "category"; max_buckets: number }
export interface RegistryLimits { max_metrics: number; max_filters: number; max_filter_values: number; max_export_rows: number; max_definition_bytes: number }
export interface ReportRegistry {
  report_types: RegistryReportType[]; dimensions: RegistryDimension[]; windows: string[]; chart_kinds: string[]; comparisons: string[];
  limits: RegistryLimits; min_cohort: number; rules: string[];
}

export interface FilterSpec { dimension_id: string; values: string[] }
/** What an Admin may express. Every id is chosen from the registry the API returned; there is no free-text field. */
export interface BuilderDefinition {
  report_id: string; metric_ids: string[]; window: BuilderWindow | "all_time"; group_by: string | null; filters: FilterSpec[]; chart: string | null; comparison: "none" | "previous_period";
}
export interface Problem { code: string; field: string; message: string }
export interface ValidateResult { valid: boolean; problems: Problem[] }
export interface Bucket { label: string; state: BucketState; value: number | string | null }
export interface PreviousMetric { state: MetricStateB; value: number | string | null; partial: boolean; note: string; buckets: Bucket[] | null }
export interface PreviewMetric {
  metric_id: string; label: string; unit: string; period: string; coverage: string; suppression: "cohort" | "operational"; state: MetricStateB;
  value: number | string | null; partial: boolean; note: string; group_dimension: string | null; buckets: Bucket[] | null; previous: PreviousMetric | null;
}
export interface PreviewResult {
  report_id: string; title: string; window: string; window_start: string | null; window_end: string; generated_at: string; utc: boolean; group_by: string | null;
  filters: FilterSpec[]; chart: string | null; comparison: "none" | "previous_period"; previous_window_start: string | null; previous_window_end: string | null;
  metrics: PreviewMetric[]; privacy: string;
}
export interface SavedReport {
  id: number; name: string; report_id: string; definition: BuilderDefinition | null; valid: boolean; shared: boolean; revision: number; editable: boolean;
  created_at: string | null; updated_at: string | null;
}
export interface SavedList { items: SavedReport[]; max_saved: number }

// ------------------------------------------------------------------------------------------------------------------------------ guards
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isBool = (v: unknown): v is boolean => typeof v === "boolean";
const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const isNumOrStrOrNull = (v: unknown) => v === null || isStr(v) || (typeof v === "number" && Number.isFinite(v));
const strArr = (v: unknown): v is string[] => Array.isArray(v) && v.every(isStr);
const arrOf = <T,>(v: unknown, f: (x: unknown) => x is T): v is T[] => Array.isArray(v) && v.every(f);
const METRIC_STATES = ["ok", "suppressed", "unavailable", "not_captured"];
const BUCKET_STATES = ["ok", "suppressed", "unavailable"];

function isRegistryMetric(v: unknown): v is RegistryMetric {
  return isObj(v) && isStr(v.metric_id) && isStr(v.label) && isStr(v.description) && isStr(v.unit) && isStr(v.coverage) && (v.suppression === "cohort" || v.suppression === "operational")
    && strArr(v.dimensions) && (v.must_group_by === null || isStr(v.must_group_by)) && isBool(v.comparable);
}
function isRegistryType(v: unknown): v is RegistryReportType {
  return isObj(v) && isStr(v.report_id) && isStr(v.title) && isStr(v.description) && isStr(v.permission_required) && strArr(v.windows) && arrOf(v.metrics, isRegistryMetric);
}
function isRegistryDimension(v: unknown): v is RegistryDimension {
  return isObj(v) && isStr(v.dimension_id) && isStr(v.label) && isStr(v.description) && (v.kind === "time" || v.kind === "category") && isInt(v.max_buckets);
}

/** The registry the API returned. Cross-checked: a metric may only name dimensions the registry lists, and a must-group dimension must be one of its own. */
export function isReportRegistry(v: unknown): v is ReportRegistry {
  if (!isObj(v) || !arrOf(v.report_types, isRegistryType) || !arrOf(v.dimensions, isRegistryDimension)) return false;
  if (!strArr(v.windows) || !strArr(v.chart_kinds) || !strArr(v.comparisons) || !strArr(v.rules) || !isInt(v.min_cohort)) return false;
  const lim = v.limits;
  if (!isObj(lim) || !["max_metrics", "max_filters", "max_filter_values", "max_export_rows", "max_definition_bytes"].every((k) => isInt(lim[k]))) return false;
  const dims = new Set((v.dimensions as RegistryDimension[]).map((d) => d.dimension_id));
  for (const t of v.report_types as RegistryReportType[]) {
    const ids = new Set<string>();
    for (const m of t.metrics) {
      if (ids.has(m.metric_id)) return false;
      ids.add(m.metric_id);
      if (!m.dimensions.every((d) => dims.has(d))) return false;
      if (m.must_group_by !== null && !m.dimensions.includes(m.must_group_by)) return false;
    }
  }
  return true;
}

export function isBuilderDefinition(v: unknown): v is BuilderDefinition {
  return isObj(v) && isStr(v.report_id) && strArr(v.metric_ids) && v.metric_ids.length > 0 && (v.window === "7d" || v.window === "30d" || v.window === "90d" || v.window === "all_time")
    && (v.group_by === null || isStr(v.group_by)) && arrOf(v.filters, (f): f is FilterSpec => isObj(f) && isStr(f.dimension_id) && strArr(f.values))
    && (v.chart === null || isStr(v.chart)) && (v.comparison === "none" || v.comparison === "previous_period");
}

export function isValidateResult(v: unknown): v is ValidateResult {
  return isObj(v) && isBool(v.valid) && arrOf(v.problems, (p): p is Problem => isObj(p) && isStr(p.code) && isStr(p.field) && isStr(p.message))
    && (v.valid ? v.problems.length === 0 : v.problems.length > 0);
}

function isBucket(v: unknown): v is Bucket {
  if (!isObj(v) || !isStr(v.label) || !isStr(v.state) || !BUCKET_STATES.includes(v.state) || !isNumOrStrOrNull(v.value)) return false;
  return v.state === "ok" || v.value === null;                      // a suppressed or unavailable bucket never carries a figure
}
function isPrevious(v: unknown): v is PreviousMetric {
  if (!isObj(v) || !isStr(v.state) || !METRIC_STATES.includes(v.state) || !isNumOrStrOrNull(v.value) || !isBool(v.partial) || !isStr(v.note)) return false;
  if (v.state !== "ok" && v.value !== null) return false;
  return v.buckets === null || arrOf(v.buckets, isBucket);
}
function isPreviewMetric(v: unknown): v is PreviewMetric {
  if (!isObj(v) || !isStr(v.metric_id) || !isStr(v.label) || !isStr(v.unit) || !isStr(v.period) || !isStr(v.coverage) || !isBool(v.partial) || !isStr(v.note)) return false;
  if (!(v.suppression === "cohort" || v.suppression === "operational") || !isStr(v.state) || !METRIC_STATES.includes(v.state) || !isNumOrStrOrNull(v.value)) return false;
  if (!(v.group_dimension === null || isStr(v.group_dimension))) return false;
  if (v.state !== "ok" && v.value !== null) return false;           // never a number for a suppressed, unavailable or not-captured metric
  if (v.buckets !== null && !arrOf(v.buckets, isBucket)) return false;
  if (v.buckets === null && v.state === "ok" && v.value === null) return false;
  return v.previous === null || v.previous === undefined || isPrevious(v.previous);
}
export function isPreviewResult(v: unknown): v is PreviewResult {
  if (!isObj(v) || !isStr(v.report_id) || !isStr(v.title) || !isStr(v.window) || !(v.window_start === null || isStr(v.window_start)) || !isStr(v.window_end)
    || !isStr(v.generated_at) || !isBool(v.utc) || !(v.group_by === null || isStr(v.group_by)) || !(v.chart === null || isStr(v.chart)) || !isStr(v.privacy)) return false;
  if (!(v.comparison === "none" || v.comparison === "previous_period")) return false;
  if (!(v.previous_window_start === null || isStr(v.previous_window_start)) || !(v.previous_window_end === null || isStr(v.previous_window_end))) return false;
  if (!arrOf(v.filters, (f): f is FilterSpec => isObj(f) && isStr(f.dimension_id) && strArr(f.values))) return false;
  return arrOf(v.metrics, isPreviewMetric);
}

export function isSavedReport(v: unknown): v is SavedReport {
  if (!isObj(v) || !isInt(v.id) || !isStr(v.name) || !isStr(v.report_id) || !isBool(v.valid) || !isBool(v.shared) || !isInt(v.revision) || !isBool(v.editable)) return false;
  if (!(v.created_at === null || isStr(v.created_at)) || !(v.updated_at === null || isStr(v.updated_at))) return false;
  return v.valid ? isBuilderDefinition(v.definition) : v.definition === null;
}
export function isSavedList(v: unknown): v is SavedList {
  return isObj(v) && isInt(v.max_saved) && arrOf(v.items, isSavedReport);
}

// ------------------------------------------------------------------------------------------------------------------------------ helpers
/** Query parameters of GET validate and preview. Filters are `dimension:value` pairs; every value comes from the registry or a bucket label the API returned. */
export function definitionQuery(d: BuilderDefinition): string {
  const sp = new URLSearchParams();
  sp.set("report_id", d.report_id);
  for (const m of d.metric_ids) sp.append("metric_ids", m);
  sp.set("window", d.window);
  if (d.group_by) sp.set("group_by", d.group_by);
  for (const f of d.filters) for (const val of f.values) sp.append("filter", `${f.dimension_id}:${val}`);
  if (d.chart) sp.set("chart", d.chart);
  sp.set("comparison", d.comparison);
  return `?${sp.toString()}`;
}

/** Problems from a failed request, from the API's stable `[code] message` text of a 422. Falls back to one generic problem; never invents a code. */
export function problemsFromMessage(message: string): Problem[] {
  const out: Problem[] = [];
  for (const part of message.split(";")) {
    const m = /^\s*\[([a-z_]+)\]\s*(.+?)\s*$/.exec(part);
    if (m) out.push({ code: m[1], field: "", message: m[2] });
  }
  return out;
}

/** The label filter values the API's grouped result offered; a filter can only select these (the server accepts short labels only). */
const LABEL = /^[A-Za-z0-9][A-Za-z0-9 _./:-]{0,63}$/;
export function offeredFilterLabels(preview: PreviewResult | null): string[] {
  if (!preview) return [];
  const seen = new Set<string>();
  for (const m of preview.metrics) for (const b of m.buckets ?? []) if (LABEL.test(b.label)) seen.add(b.label);
  return Array.from(seen).sort();
}

export function metricsFor(registry: ReportRegistry, reportId: string): RegistryMetric[] {
  return registry.report_types.find((t) => t.report_id === reportId)?.metrics ?? [];
}

/** Dimensions every selected metric can be grouped by (intersection), ordered as the registry lists them. */
export function commonDimensions(registry: ReportRegistry, reportId: string, metricIds: string[]): RegistryDimension[] {
  const ms = metricsFor(registry, reportId).filter((m) => metricIds.includes(m.metric_id));
  if (ms.length === 0) return [];
  return registry.dimensions.filter((d) => d.kind === "category" && ms.every((m) => m.dimensions.includes(d.dimension_id)));
}

/** A cell for a figure. Only an "ok" state with a real value is a figure; everything else is the state itself, never 0. */
export function figureText(state: MetricStateB | BucketState, value: number | string | null, unit: string): string {
  if (state !== "ok") return STATE_WORDS[state] ?? "Unavailable";
  if (value === null || value === undefined) return "Unavailable";
  const suffix = unit === "percent" ? "%" : unit === "usd" ? " USD" : unit === "seconds" ? " s" : unit === "hours" ? " h" : unit === "milliseconds" ? " ms" : unit === "tokens" ? " tokens" : "";
  return `${value}${suffix}`;
}
export const STATE_WORDS: Record<string, string> = { ok: "Available", suppressed: "Suppressed: small cohort", unavailable: "Unavailable", not_captured: "Not captured" };

export const KNOWN_CHARTS: readonly string[] = CHART_KINDS;
export const KNOWN_COMPARISONS: readonly string[] = COMPARISON_MODES;

// ------------------------------------------------------------------------------------------------------------------------------ fixed /admin/reports/* (W10.12)
// The existing standard reports view had no shape check: a malformed 200 crashed the page. Same rule as the builder: validate, or show the Admin error state.
const isFigure = (v: unknown) => v === null || isStr(v) || (typeof v === "number" && Number.isFinite(v));
/** Runtime check of GET /admin/reports/{kind}. A metric or cell that is not available never carries a figure interpretation here: the view shows its state. */
export function isAdminReport(v: unknown): v is AdminReport {
  if (!isObj(v) || !isStr(v.period) || !(v.window_start === null || isStr(v.window_start)) || !isStr(v.window_end) || !isStr(v.generated_at) || !isBool(v.utc) || !isStr(v.privacy)) return false;
  if (!Array.isArray(v.sections)) return false;
  return v.sections.every((s) => isObj(s) && isStr(s.section_id) && isStr(s.title) && isStr(s.coverage) && (s.captured_since === null || isStr(s.captured_since)) && isStr(s.note)
    && arrOf(s.metrics, (m): m is ReportMetric => isObj(m) && isStr(m.metric_id) && isStr(m.label) && isFigure(m.figure) && isStr(m.unit) && isStr(m.state) && isStr(m.coverage) && isStr(m.note))
    && arrOf(s.tables, (t): t is ReportTable => isObj(t) && isStr(t.table_id) && isStr(t.title) && strArr(t.columns) && isStr(t.note)
      && arrOf(t.rows, (r): r is ReportRow => isObj(r) && isStr(r.label) && arrOf(r.cells, (c): c is ReportCell => isObj(c) && isFigure(c.figure) && isBool(c.suppressed)))));
}
