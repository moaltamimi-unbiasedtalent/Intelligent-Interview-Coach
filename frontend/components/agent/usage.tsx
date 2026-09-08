"use client";

import type { AgentProfile, AgentRunResponse, AgentUsage } from "@/lib/api/types";

/**
 * Fast / Balanced / Advanced Agent Coach controls + safe usage display (P1).
 *
 * The candidate picks a speed/quality tier — never a raw provider model name. Usage
 * is shown honestly: unknown usage is never rendered as $0.00, and a partial-coverage
 * run says so rather than showing false precision.
 */

export const PROFILE_OPTIONS: { value: AgentProfile; label: string; description: string }[] = [
  { value: "fast", label: "Fast", description: "Quicker and lower-cost preparation" },
  { value: "balanced", label: "Balanced", description: "Recommended" },
  { value: "advanced", label: "Advanced", description: "More capable for complex preparation" },
];

export const DEFAULT_PROFILE: AgentProfile = "balanced";

export function profileLabel(profile: string | null | undefined): string {
  const found = PROFILE_OPTIONS.find((o) => o.value === profile);
  return found ? found.label : "Balanced";
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
  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-sm font-medium">Speed</legend>
      <div role="radiogroup" aria-label="Coach speed" className="flex flex-wrap gap-2">
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
              title={opt.description}
              className={
                active
                  ? "min-h-[40px] rounded-lg bg-accent px-3.5 text-sm font-semibold text-accent-foreground"
                  : "min-h-[40px] rounded-lg border border-border px-3.5 text-sm font-medium"
              }
            >
              <span>{opt.label}</span>
              {opt.value === "balanced" ? <span className="ml-1 text-xs opacity-80">· recommended</span> : null}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted" aria-live="polite">
        {PROFILE_OPTIONS.find((o) => o.value === value)?.description}
      </p>
    </fieldset>
  );
}

/**
 * A subtle one-line runtime summary shown to the candidate after a completed turn,
 * e.g. "Fast · 3 AI calls · 4.1s" (§37). Cost is shown only when known; a run with
 * partial usage says "usage partial" instead of a misleadingly precise figure (§38).
 */
export function usageSummaryLine(run: AgentRunResponse): string | null {
  const usage = run.usage;
  if (!usage) return null;
  const parts: string[] = [profileLabel(run.profile)];
  parts.push(`${usage.model_calls} AI call${usage.model_calls === 1 ? "" : "s"}`);
  if (typeof run.latency_ms === "number") parts.push(`${(run.latency_ms / 1000).toFixed(1)}s`);
  parts.push(costLabel(usage));
  return parts.filter(Boolean).join(" · ");
}

function costLabel(usage: AgentUsage): string {
  if (typeof usage.estimated_cost_usd === "number") {
    const money = `~$${usage.estimated_cost_usd.toFixed(2)}`;
    return usage.usage_complete ? money : `${money} captured · partial`;
  }
  return usage.usage_complete ? "" : "usage partial";
}

/** The full, safe usage breakdown for the Agent Inspector (§14). Never prompts/cost fiction. */
export function UsageDetails({ run }: { run: AgentRunResponse }) {
  const usage = run.usage;
  const Row = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
  if (!usage) {
    return <Row label="Usage / cost" value={<span className="text-muted">Not captured for this run</span>} />;
  }
  const fmt = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString() : "—");
  const cost = typeof usage.estimated_cost_usd === "number" ? `~$${usage.estimated_cost_usd.toFixed(4)}` : "—";
  return (
    <div className="space-y-1.5">
      <Row label="Profile" value={profileLabel(run.profile)} />
      <Row label="Model calls (agent / tool)" value={`${usage.model_calls} (${usage.agent_model_calls} / ${usage.tool_model_calls})`} />
      <Row label="Input tokens" value={fmt(usage.input_tokens)} />
      <Row label="Output tokens" value={fmt(usage.output_tokens)} />
      <Row label="Total tokens" value={fmt(usage.total_tokens)} />
      <Row label="Estimated cost" value={cost} />
      <Row
        label="Usage coverage"
        value={usage.usage_complete ? "Complete" : "Partial"}
      />
      {!usage.usage_complete ? (
        <p className="text-xs text-muted">Some tool-internal provider usage was unavailable.</p>
      ) : null}
      {typeof run.latency_ms === "number" ? <Row label="Latency" value={`${(run.latency_ms / 1000).toFixed(1)}s`} /> : null}
      <Row label="Retrieval cache (hits / misses)" value={`${run.cache_hits ?? 0} / ${run.cache_misses ?? 0}`} />
    </div>
  );
}
