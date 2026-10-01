"use client";

import type { AgentProfile, AgentRunResponse, AgentUsage } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

/**
 * Fast / Balanced / Advanced Agent Coach controls + safe usage display (P1).
 *
 * The candidate picks a speed/quality tier — never a raw provider model name. Usage
 * is shown honestly: unknown usage is never rendered as $0.00, and a partial-coverage
 * run says so rather than showing false precision. Copy is localized (W9.6).
 */

export const PROFILE_OPTIONS: { value: AgentProfile; labelKey: string; descKey: string }[] = [
  { value: "fast", labelKey: "prepare.profileFast", descKey: "prepare.profileFastDesc" },
  { value: "balanced", labelKey: "prepare.profileBalanced", descKey: "prepare.profileBalancedDesc" },
  { value: "advanced", labelKey: "prepare.profileAdvanced", descKey: "prepare.profileAdvancedDesc" },
];

export const DEFAULT_PROFILE: AgentProfile = "balanced";

export function profileLabel(profile: string | null | undefined, t: Translate): string {
  const found = PROFILE_OPTIONS.find((o) => o.value === profile);
  return t(found ? found.labelKey : "prepare.profileBalanced");
}

/** A compact, accessible speed selector. No technical model names in candidate UI (§20). */
export function AgentProfileSelector({
  value,
  onChange,
  disabled,
}: {
  value: AgentProfile;
  onChange: (p: AgentProfile) => void;
  disabled?: boolean;
}) {
  const t = useT();
  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-sm font-medium">{t("prepare.speed")}</legend>
      <div role="radiogroup" aria-label={t("prepare.coachSpeedAria")} className="flex flex-wrap gap-2">
        {PROFILE_OPTIONS.map((opt) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={disabled}
              onClick={() => onChange(opt.value)}
              title={t(opt.descKey)}
              className={
                active
                  ? "min-h-[40px] rounded-lg bg-accent px-3.5 text-sm font-semibold text-accent-foreground"
                  : "min-h-[40px] rounded-lg border border-border px-3.5 text-sm font-medium"
              }
            >
              <span>{t(opt.labelKey)}</span>
              {opt.value === "balanced" ? <span className="ml-1 text-xs opacity-80">· {t("prepare.recommended")}</span> : null}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted" aria-live="polite">
        {t(PROFILE_OPTIONS.find((o) => o.value === value)?.descKey ?? "prepare.profileBalancedDesc")}
      </p>
    </fieldset>
  );
}

/**
 * A subtle one-line runtime summary shown to the candidate after a completed turn,
 * e.g. "Fast · 3 AI calls · 4.1s" (§37). Cost is shown only when known; a run with
 * partial usage says "usage partial" instead of a misleadingly precise figure (§38).
 */
export function usageSummaryLine(run: AgentRunResponse, t: Translate): string | null {
  const usage = run.usage;
  if (!usage) return null;
  const parts: string[] = [profileLabel(run.profile, t)];
  parts.push(t(usage.model_calls === 1 ? "prepare.aiCalls_one" : "prepare.aiCalls_other", { count: usage.model_calls }));
  if (typeof run.latency_ms === "number") parts.push(`${(run.latency_ms / 1000).toFixed(1)}s`);
  parts.push(costLabel(usage, t));
  return parts.filter(Boolean).join(" · ");
}

function costLabel(usage: AgentUsage, t: Translate): string {
  if (typeof usage.estimated_cost_usd === "number") {
    const money = `~$${usage.estimated_cost_usd.toFixed(2)}`;
    return usage.usage_complete ? money : t("prepare.capturedPartial", { money });
  }
  return usage.usage_complete ? "" : t("prepare.usagePartial");
}

/** The full, safe usage breakdown for the Agent Inspector (§14). Never prompts/cost fiction. */
export function UsageDetails({ run }: { run: AgentRunResponse }) {
  const t = useT();
  const usage = run.usage;
  const Row = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
  if (!usage) {
    return <Row label={t("prepare.usageCost")} value={<span className="text-muted">{t("prepare.notCaptured")}</span>} />;
  }
  const fmt = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString() : "—");
  const cost = typeof usage.estimated_cost_usd === "number" ? `~$${usage.estimated_cost_usd.toFixed(4)}` : "—";
  return (
    <div className="space-y-1.5">
      <Row label={t("prepare.profile")} value={profileLabel(run.profile, t)} />
      <Row label={t("prepare.modelCalls")} value={`${usage.model_calls} (${usage.agent_model_calls} / ${usage.tool_model_calls})`} />
      <Row label={t("prepare.inputTokens")} value={fmt(usage.input_tokens)} />
      <Row label={t("prepare.outputTokens")} value={fmt(usage.output_tokens)} />
      <Row label={t("prepare.totalTokens")} value={fmt(usage.total_tokens)} />
      <Row label={t("prepare.estimatedCost")} value={cost} />
      <Row
        label={t("prepare.usageCoverage")}
        value={usage.usage_complete ? t("prepare.coverageComplete") : t("prepare.coveragePartial")}
      />
      {!usage.usage_complete ? (
        <p className="text-xs text-muted">{t("prepare.toolUsageUnavailable")}</p>
      ) : null}
      {typeof run.latency_ms === "number" ? <Row label={t("prepare.latency")} value={`${(run.latency_ms / 1000).toFixed(1)}s`} /> : null}
      <Row label={t("prepare.retrievalCache")} value={`${run.cache_hits ?? 0} / ${run.cache_misses ?? 0}`} />
    </div>
  );
}
