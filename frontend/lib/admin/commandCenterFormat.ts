// Display rules of the Command Center (package 03D2). Pure functions, so the "a missing figure is never zero" rule is unit-tested in one place.
import type { MetricPeriodKind } from "./metricContract";
import type { CcBucket, CcMetric, EvidenceStatus } from "./commandCenterGuard";

export const PERIOD_LABEL: Record<MetricPeriodKind, string> = { "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days", all_time: "All time" };

/** Evidence status in TEXT first (never colour only). */
export const EVIDENCE_LABEL: Record<EvidenceStatus, string> = {
  captured: "Captured", partial: "Partial coverage", current_state: "Current state", not_captured: "Not captured", unavailable: "Unavailable", suppressed: "Suppressed",
};

/** What the figure position shows when there is no figure. NEVER "0". */
export const MISSING_LABEL = { suppressed: "Suppressed: small cohort", unavailable: "Unavailable", not_captured: "Not captured" } as const;

const GROUP = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

/**
 * Integer micro-USD to a display amount without floating point: 1_234_500 -> "USD 1.2345". At least two decimals, at most six; never rounded.
 * Currencies are never combined: the only currency here is USD and it is always printed.
 */
export function formatMicroUsd(micro: number): string {
  const whole = Math.trunc(micro / 1_000_000);
  const frac = String(micro - whole * 1_000_000).padStart(6, "0").replace(/0+$/, "").padEnd(2, "0");
  return `USD ${GROUP.format(whole)}.${frac}`;
}

function unitSuffix(unit: CcMetric["unit"]): string {
  return { count: "", percent: "%", ratio: "", score: "", seconds: " s", hours: " h", milliseconds: " ms", tokens: " tokens", usd: "" }[unit];
}

function formatNumber(n: number, unit: CcMetric["unit"]): string {
  return `${GROUP.format(n)}${unitSuffix(unit)}`;
}

/** The figure text of a metric. A metric that is not state "ok" shows its state label, never a number. */
export function formatMetricFigure(m: Pick<CcMetric, "state" | "value" | "unit" | "cost_micro_usd">): string {
  if (m.state !== "ok" || m.value === null) return MISSING_LABEL[m.state === "ok" ? "unavailable" : m.state];
  if (m.unit === "usd") return m.cost_micro_usd !== null ? formatMicroUsd(m.cost_micro_usd) : `USD ${String(m.value)}`;
  return typeof m.value === "number" ? formatNumber(m.value, m.unit) : m.value;
}

/** Wording that must accompany any cost figure. */
export const COST_WORDING = "Known cost, partial coverage: units without a known cost are excluded, never counted as zero. Currencies are never combined.";

export function formatBucket(b: CcBucket, unit: CcMetric["unit"]): string {
  if (b.state === "ok" && b.value !== null) return formatNumber(b.value, unit);
  return b.state === "suppressed" ? MISSING_LABEL.suppressed : MISSING_LABEL.unavailable;
}

/** Bucket keys are bounded code-defined vocabularies ("career_ai"); they are shown humanised, the key stays in the data table. */
export function humanizeKey(key: string): string {
  const t = key.replace(/[_-]+/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : key;
}

/** "numerator of denominator" only when the contract provides both. */
export function formatRatio(m: Pick<CcMetric, "numerator" | "denominator">): string | null {
  if (m.numerator === null || m.denominator === null) return null;
  return `${GROUP.format(m.numerator)} of ${GROUP.format(m.denominator)}`;
}

export function suppressionText(m: Pick<CcMetric, "state" | "suppression">): string {
  if (m.state === "suppressed") return "Suppressed: below the privacy floor for small cohorts";
  return m.suppression === "cohort" ? "Not suppressed (small-cohort floor applies to this figure)" : "Not suppressed (operational figure, no candidate cohort)";
}

/** "2026-10-22T05:23:53.719023+00:00" -> "2026-10-22 05:23 UTC". Anything unparseable is shown as it is, not guessed. */
export function formatWhen(iso: string | null): string {
  if (!iso) return "-";
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? `${m[1]} ${m[2]} UTC` : iso;
}
