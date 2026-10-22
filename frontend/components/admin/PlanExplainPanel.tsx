"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { PlanExplanation } from "@/lib/admin/types";
import { KeyValue, Panel, ScrollRegion, apiMessage, btn, field } from "./ui";

// Fixed sentences for the server's reason codes. Unknown codes are shown as they are (never hidden, never guessed).
const REASONS: Record<string, string> = {
  granted_by_plan_version: "The subject's plan version enables it.",
  disabled_by_plan_version: "The subject's plan version disables it.",
  not_listed_in_plan_version_denied_by_default: "The subject's plan version does not list it, so it is refused by default.",
  no_active_subscription_basic_fallback_grants: "No active subscription: the Basic fallback enables it.",
  no_active_subscription_basic_fallback_denies: "No active subscription: the Basic fallback does not include it.",
  code_default_basic_grants: "No plan data exists: the built-in Basic default enables it.",
  code_default_basic_denies: "No plan data exists: the built-in Basic default does not include it.",
};

const LAYER_NAMES: Record<string, string> = {
  authorization: "Authorization", capability: "Capability", entitlement: "Entitlement", billing_state: "Billing state",
};

/**
 * Why an account or workspace is allowed or refused each entitlement. The answer comes from the same resolver the product uses; it
 * is plan data only (never a candidate's content), and the four layers are kept separate: only the entitlement layer is explained here.
 */
export function PlanExplainPanel() {
  const [kind, setKind] = useState<"user" | "workspace">("user");
  const [idText, setIdText] = useState("");
  const [result, setResult] = useState<PlanExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setError(null);
    setResult(null);
    if (!/^\d+$/.test(idText.trim()) || Number(idText) < 1) return setError("Enter one whole-number id.");
    try {
      const id = Number(idText);
      setResult(await api.admin.explainPlanAccess(kind === "user" ? { user_id: id } : { workspace_id: id }));
    } catch (e) {
      setError(apiMessage(e));
    }
  };

  return (
    <Panel title="Explain effective access">
      <p className="text-xs text-muted">
        Shows why an account or workspace is allowed or refused each entitlement. It reads plan data only and never shows candidate content.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs text-muted">
          Explain access for
          <select className={field} value={kind} onChange={(e) => { setKind(e.target.value as "user" | "workspace"); setResult(null); }}>
            <option value="user">Account</option>
            <option value="workspace">Workspace</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs text-muted">
          Subject id
          <input className={`${field} w-32`} inputMode="numeric" value={idText} onChange={(e) => { setIdText(e.target.value); setResult(null); }} />
        </label>
        <button type="button" className={btn} disabled={!idText.trim()} onClick={run}>Explain access</button>
      </div>
      {error ? <p role="alert" className="text-sm">{error}</p> : null}
      {result ? (
        <div className="grid gap-2" aria-live="polite">
          <KeyValue rows={[
            ["Plan", result.plan_version === null ? `${result.plan_code} (built-in default)` : `${result.plan_code} version ${result.plan_version}${result.plan_version_status ? ` (${result.plan_version_status})` : ""}`],
            ["Resolved from", result.source === "subscription" ? "The subject's active subscription" : "The Basic fallback (no active subscription)"],
          ]} />
          <ScrollRegion label="Effective entitlements (scrollable table)">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Effective entitlements and the reason for each</caption>
              <thead>
                <tr className="text-xs text-muted">
                  {["Entitlement", "Access", "Reason"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {result.items.map((i) => (
                  <tr key={i.code} className="border-t border-default">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">{i.label}</th>
                    <td className="py-1 pr-4">{i.allowed ? (i.limit === null ? "Allowed" : `Allowed, limit ${i.limit}`) : "Refused"}</td>
                    <td className="py-1 pr-4">{REASONS[i.reason] ?? i.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <div>
            <h3 className="text-sm font-medium">Four separate layers</h3>
            <ul className="grid gap-1 text-xs text-muted">
              {result.layers.map((l) => (
                <li key={l.layer}>
                  <span className="font-medium text-foreground">{LAYER_NAMES[l.layer] ?? l.layer}</span>
                  {l.evaluated_here ? " (explained above): " : " (not evaluated here): "}
                  {l.note}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
