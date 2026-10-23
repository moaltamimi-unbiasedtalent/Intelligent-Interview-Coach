// Command Center client boundary (package 03D2). Hand-written mirror of src/api/schemas/command_center.py, built over the frozen 03K contract
// (metricContract.ts, conform only), plus runtime type guards: a successful HTTP response that does not have the documented shape (a proxy answering `{}`, a contract
// drift) must surface as the explicit Admin error state, never as a crash and never as a silently empty dashboard.
import { COVERAGE_KINDS, METRIC_STATES, PERIOD_KINDS, SUPPRESSION_KINDS, UNITS } from "./metricContract";
import type { DimensionDefinition, MetricDefinition, MetricPeriodKind, MetricState, MetricUnit } from "./metricContract";

export const EVIDENCE_STATUSES = ["captured", "partial", "current_state", "not_captured", "unavailable", "suppressed"] as const;
export const COMPONENT_STATUSES = ["ok", "attention", "unavailable", "info"] as const;
export const BUCKET_STATES = ["ok", "suppressed", "unavailable"] as const;
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];
export type ComponentStatus = (typeof COMPONENT_STATUSES)[number];
export type BucketState = (typeof BUCKET_STATES)[number];

export interface CcBucket { key: string; label: string; state: BucketState; value: number | null; partial: boolean }
export interface CcBreakdown { dimension_id: string; label: string; buckets: CcBucket[] }
export interface CcMetric {
  metric_id: string; label: string; unit: MetricUnit; period: MetricPeriodKind; state: MetricState; value: number | string | null;
  numerator: number | null; denominator: number | null; coverage: string; partial: boolean; note: string; evidence: EvidenceStatus; evidence_source: string;
  suppression: "cohort" | "operational"; dimensions: string[]; cost_micro_usd: number | null; breakdowns: CcBreakdown[];
}
export interface CcComponent { component_id: string; label: string; status: ComponentStatus; evidence: "current_state" | "unavailable"; note: string }
export interface CcSection {
  section_id: string; title: string; period: MetricPeriodKind; window_start: string | null; window_end: string; generated_at: string; utc: boolean; privacy: string;
  captured_since: string | null; metrics: CcMetric[]; components: CcComponent[];
}
export interface CcDefinitions { periods: MetricPeriodKind[]; default_period: MetricPeriodKind; metrics: MetricDefinition[]; dimensions: DimensionDefinition[] }

/** Thrown when a 200 response is not the documented shape. Callers show the explicit Admin error state. */
export class MalformedCommandCenterResponse extends Error {
  constructor(what: string) {
    super(`malformed command center response: ${what}`);
    this.name = "MalformedCommandCenterResponse";
  }
}

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const numOrNull = (v: unknown) => v === null || isNum(v);
const strOrNull = (v: unknown) => v === null || isStr(v);
const oneOf = (list: readonly string[], v: unknown) => isStr(v) && list.includes(v);

export function isCcBucket(v: unknown): v is CcBucket {
  if (!isObj(v)) return false;
  if (!isStr(v.key) || !isStr(v.label) || !oneOf(BUCKET_STATES, v.state) || !numOrNull(v.value) || typeof v.partial !== "boolean") return false;
  // 03K rule: only a state "ok" bucket carries a value, and it carries one. A suppressed or unavailable bucket must never be a number (never zero).
  return v.state === "ok" ? v.value !== null : v.value === null;
}

function isBreakdown(v: unknown): v is CcBreakdown {
  return isObj(v) && isStr(v.dimension_id) && isStr(v.label) && Array.isArray(v.buckets) && v.buckets.every(isCcBucket);
}

export function isCcMetric(v: unknown): v is CcMetric {
  if (!isObj(v)) return false;
  if (!isStr(v.metric_id) || !isStr(v.label) || !oneOf(UNITS, v.unit) || !oneOf(PERIOD_KINDS, v.period) || !oneOf(METRIC_STATES, v.state)) return false;
  if (!(v.value === null || isNum(v.value) || isStr(v.value))) return false;
  if (!numOrNull(v.numerator) || !numOrNull(v.denominator) || !isStr(v.coverage) || typeof v.partial !== "boolean" || !isStr(v.note)) return false;
  if (!oneOf(EVIDENCE_STATUSES, v.evidence) || !isStr(v.evidence_source) || !oneOf(SUPPRESSION_KINDS, v.suppression)) return false;
  if (!Array.isArray(v.dimensions) || !v.dimensions.every(isStr)) return false;
  if (!(v.cost_micro_usd === null || (isNum(v.cost_micro_usd) && Number.isInteger(v.cost_micro_usd) && v.cost_micro_usd >= 0))) return false;
  if (!Array.isArray(v.breakdowns) || !v.breakdowns.every(isBreakdown)) return false;
  // 03K rule: a metric that is not state "ok" has value null and must render as its state. A number under a missing state is a contract break.
  return v.state === "ok" ? v.value !== null : v.value === null;
}

function isComponent(v: unknown): v is CcComponent {
  return isObj(v) && isStr(v.component_id) && isStr(v.label) && oneOf(COMPONENT_STATUSES, v.status) && oneOf(["current_state", "unavailable"], v.evidence) && isStr(v.note);
}

export function isCcSection(v: unknown): v is CcSection {
  if (!isObj(v)) return false;
  if (!isStr(v.section_id) || !isStr(v.title) || !oneOf(PERIOD_KINDS, v.period) || !strOrNull(v.window_start) || !isStr(v.window_end) || !isStr(v.generated_at)) return false;
  if (typeof v.utc !== "boolean" || !isStr(v.privacy) || !strOrNull(v.captured_since)) return false;
  return Array.isArray(v.metrics) && v.metrics.every(isCcMetric) && Array.isArray(v.components) && v.components.every(isComponent);
}

function isNamed(v: unknown, keys: string[]): boolean {
  return isObj(v) && keys.every((k) => isStr(v[k]));
}

function isMetricDefinition(v: unknown): v is MetricDefinition {
  if (!isObj(v) || !isNamed(v, ["metric_id", "label", "description", "permission_required"]) || !oneOf(UNITS, v.unit)) return false;
  const qty = (q: unknown) => isObj(q) && isStr(q.aggregation) && isStr(q.subject);
  if (!qty(v.numerator) || !(v.denominator === null || qty(v.denominator))) return false;
  if (!Array.isArray(v.period_kinds) || !v.period_kinds.every((p) => oneOf(PERIOD_KINDS, p))) return false;
  if (!Array.isArray(v.dimensions_allowed) || !v.dimensions_allowed.every(isStr)) return false;
  if (!isObj(v.coverage) || !oneOf(COVERAGE_KINDS, v.coverage.kind) || !isStr(v.coverage.note)) return false;
  if (!isObj(v.suppression) || !oneOf(SUPPRESSION_KINDS, v.suppression.kind)) return false;
  return isObj(v.source) && isStr(v.source.name) && oneOf(["unavailable", "not_captured"], v.missing_behaviour);
}

export function isCcDefinitions(v: unknown): v is CcDefinitions {
  if (!isObj(v)) return false;
  if (!Array.isArray(v.periods) || !v.periods.every((p) => oneOf(PERIOD_KINDS, p)) || !oneOf(PERIOD_KINDS, v.default_period)) return false;
  return Array.isArray(v.metrics) && v.metrics.every(isMetricDefinition) && Array.isArray(v.dimensions) && v.dimensions.every((d) => isNamed(d, ["dimension_id", "label"]));
}

export function assertCcSection(v: unknown): CcSection {
  if (!isCcSection(v)) throw new MalformedCommandCenterResponse("section");
  return v;
}

export function assertCcDefinitions(v: unknown): CcDefinitions {
  if (!isCcDefinitions(v)) throw new MalformedCommandCenterResponse("definitions");
  return v;
}
