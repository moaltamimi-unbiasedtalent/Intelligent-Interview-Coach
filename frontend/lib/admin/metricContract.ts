// Admin metric and report contract (package 03K). Hand-written mirror of src/reporting/contract.py (strict, extra=forbid).
// frontend/lib/admin/metricContract.schema.json is the committed JSON schema generated from the Python models; both
// tests/contracts/test_admin_metric_contract_03k.py and frontend/tests/admin-metric-contract-03k.test.ts keep this file in sync with it.
// Rule for every consumer: a metric that is not state "ok" has value === null and must render as that state, never as zero.

export const METRIC_STATES = ["ok", "suppressed", "unavailable", "not_captured"] as const;
export const UNITS = ["count", "percent", "ratio", "score", "seconds", "hours", "milliseconds", "tokens", "usd"] as const;
export const PERIOD_KINDS = ["7d", "30d", "90d", "all_time"] as const;
export const MISSING_BEHAVIOURS = ["unavailable", "not_captured"] as const;
export const CHART_KINDS = ["trend", "funnel", "share_of_whole", "distribution", "table"] as const;
export const COMPARISON_MODES = ["none", "previous_period"] as const;
export const SOURCE_KINDS = ["named_query", "fact_table"] as const;
export const AGGREGATIONS = ["count", "count_distinct", "sum", "mean", "p50", "p95", "ratio"] as const;
export const COVERAGE_KINDS = ["historical", "since_first_event", "lower_bound", "from_index", "current_state", "mock_state"] as const;
export const SUPPRESSION_KINDS = ["cohort", "operational"] as const;
export const DIMENSION_KINDS = ["time", "category"] as const;

export type MetricState = (typeof METRIC_STATES)[number];
export type MetricUnit = (typeof UNITS)[number];
export type MetricPeriodKind = (typeof PERIOD_KINDS)[number];
export type MissingBehaviour = (typeof MISSING_BEHAVIOURS)[number];
export type ChartKind = (typeof CHART_KINDS)[number];
export type ComparisonMode = (typeof COMPARISON_MODES)[number];

export interface SourceRef { kind: (typeof SOURCE_KINDS)[number]; name: string }
export interface Quantity { aggregation: (typeof AGGREGATIONS)[number]; subject: string }
export interface CoverageRule { kind: (typeof COVERAGE_KINDS)[number]; note: string }
export interface SuppressionPolicy { kind: (typeof SUPPRESSION_KINDS)[number]; min_cohort: number | null }
export interface DimensionDefinition { dimension_id: string; label: string; description: string; kind: (typeof DIMENSION_KINDS)[number]; max_buckets: number }
export interface MetricDefinition {
  metric_id: string; label: string; description: string; source: SourceRef; numerator: Quantity; denominator: Quantity | null; unit: MetricUnit;
  period_kinds: MetricPeriodKind[]; dimensions_allowed: string[]; coverage: CoverageRule; missing_behaviour: MissingBehaviour; suppression: SuppressionPolicy;
  permission_required: string;
}
export interface DateRangeRule { allowed_periods: MetricPeriodKind[]; default_period: MetricPeriodKind; allow_custom_range: boolean; max_custom_days: number | null }
export interface ChartSpec { chart_id: string; kind: ChartKind; metric_ids: string[]; dimension_id: string | null; title: string }
export interface ReportDefinition {
  report_id: string; title: string; description: string; metric_ids: string[]; allowed_filters: string[]; date_range: DateRangeRule;
  comparison_modes: ComparisonMode[]; charts: ChartSpec[]; permission_required: string;
}
export interface MetricResult {
  metric_id: string; period: MetricPeriodKind; state: MetricState; value: number | string | null; numerator: number | null; denominator: number | null;
  coverage: string; partial: boolean; note: string;
}

// Exhaustive key maps: adding or removing a field in an interface above without updating the map is a tsc error; the vitest compares the maps with the JSON schema.
export const CONTRACT_KEYS = {
  MetricDefinition: { metric_id: true, label: true, description: true, source: true, numerator: true, denominator: true, unit: true, period_kinds: true,
    dimensions_allowed: true, coverage: true, missing_behaviour: true, suppression: true, permission_required: true } satisfies Record<keyof MetricDefinition, true>,
  DimensionDefinition: { dimension_id: true, label: true, description: true, kind: true, max_buckets: true } satisfies Record<keyof DimensionDefinition, true>,
  ReportDefinition: { report_id: true, title: true, description: true, metric_ids: true, allowed_filters: true, date_range: true, comparison_modes: true,
    charts: true, permission_required: true } satisfies Record<keyof ReportDefinition, true>,
  MetricResult: { metric_id: true, period: true, state: true, value: true, numerator: true, denominator: true, coverage: true, partial: true,
    note: true } satisfies Record<keyof MetricResult, true>,
  SourceRef: { kind: true, name: true } satisfies Record<keyof SourceRef, true>,
  Quantity: { aggregation: true, subject: true } satisfies Record<keyof Quantity, true>,
  CoverageRule: { kind: true, note: true } satisfies Record<keyof CoverageRule, true>,
  SuppressionPolicy: { kind: true, min_cohort: true } satisfies Record<keyof SuppressionPolicy, true>,
  DateRangeRule: { allowed_periods: true, default_period: true, allow_custom_range: true, max_custom_days: true } satisfies Record<keyof DateRangeRule, true>,
  ChartSpec: { chart_id: true, kind: true, metric_ids: true, dimension_id: true, title: true } satisfies Record<keyof ChartSpec, true>,
} as const;

/** The only place a UI may turn a result into display text. A missing value is its state label, never "0". */
export function displayMetric(r: Pick<MetricResult, "state" | "value">, unit: MetricUnit | ""): string {
  if (r.state === "ok" && r.value !== null) return unit === "percent" ? `${r.value}%` : String(r.value);
  return { ok: "Unavailable", suppressed: "Suppressed: small cohort", unavailable: "Unavailable", not_captured: "Not captured" }[r.state];
}
