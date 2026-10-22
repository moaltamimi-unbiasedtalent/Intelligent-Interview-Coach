"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { PlanAssignmentPreview } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Panel, ScrollRegion, apiMessage, btn, field, useAdminResource } from "./ui";

const MAX = 100;

/** "1, 2 3" -> [1, 2, 3]; null when anything is not a positive whole number or the list is empty or too long. */
export function parseIds(text: string): number[] | null {
  const parts = text.split(/[\s,]+/).filter(Boolean);
  if (parts.length === 0 || parts.length > MAX) return null;
  const ids = parts.map((p) => (/^\d+$/.test(p) ? Number(p) : NaN));
  return ids.some((n) => !Number.isSafeInteger(n) || n < 1) ? null : Array.from(new Set(ids));
}

/**
 * Assign several accounts or workspaces to the active version of a plan. The preview shows COUNTS only (never who), and the
 * assignment needs the preview's revision, so a plan or subscription that changed meanwhile is refused instead of applied.
 * An assignment is an access decision: nothing here charges, prices or invoices anyone.
 */
export function PlanAssignPanel() {
  const canManage = hasAnyPermission(adminPermissions(useAuthOptional()?.account), [P.subscriptionsManage]);
  const options = useAdminResource(() => (canManage ? api.admin.assignablePlans() : Promise.resolve([])), [canManage]);
  const [plan, setPlan] = useState("");
  const [kind, setKind] = useState<"user" | "workspace">("user");
  const [idsText, setIdsText] = useState("");
  const [preview, setPreview] = useState<PlanAssignmentPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  if (!canManage) return null;

  const reset = () => {
    setPreview(null);
    setNotice(null);
    setError(null);
  };
  const runPreview = async () => {
    reset();
    const ids = parseIds(idsText);
    if (!ids) return setError(`Enter between 1 and ${MAX} whole-number ids, separated by commas or spaces.`);
    try {
      setPreview(await api.admin.previewPlanAssignment(plan, kind, ids));
    } catch (e) {
      setError(apiMessage(e));
    }
  };

  return (
    <Panel title="Assign plans">
      <p className="text-xs text-muted">
        Moves the chosen accounts or workspaces to the active version of a plan. This is an access decision: nothing here charges, prices or
        invoices anyone. The preview shows counts only.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs text-muted">
          Plan to assign
          <select className={field} value={plan} onChange={(e) => { setPlan(e.target.value); reset(); }}>
            <option value="">Choose a plan</option>
            {(options.state === "ready" ? options.data : []).map((o) => (
              <option key={o.plan_code} value={o.plan_code}>{`${o.display_name} (version ${o.version})`}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-muted">
          Subject type
          <select className={field} value={kind} onChange={(e) => { setKind(e.target.value as "user" | "workspace"); reset(); }}>
            <option value="user">Accounts</option>
            <option value="workspace">Workspaces</option>
          </select>
        </label>
        <label className="grid min-w-[16rem] gap-1 text-xs text-muted">
          Ids (comma or space separated, at most 100)
          <input className={field} inputMode="numeric" value={idsText} onChange={(e) => { setIdsText(e.target.value); reset(); }} />
        </label>
        <button type="button" className={btn} disabled={!plan || !idsText.trim()} onClick={runPreview}>Preview effect</button>
      </div>
      {error ? <p role="alert" className="text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      {preview ? (
        <div className="grid gap-2" aria-live="polite">
          <p className="text-sm" role="status">
            {`Requested ${preview.requested}, found ${preview.found}, not found ${preview.missing}. ${preview.would_change} would change, ${preview.unchanged} already on this version.`}
          </p>
          <p className="text-xs text-muted">
            {`Current plans of the found subjects: Basic ${preview.by_current_plan.basic}, Premium ${preview.by_current_plan.premium}, no active subscription ${preview.by_current_plan.none}.`}
          </p>
          <ScrollRegion label="Effect on entitlements (scrollable table)">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Entitlements gained or lost if this assignment is applied</caption>
              <thead>
                <tr className="text-xs text-muted">
                  {["Entitlement", "Gained by", "Lost by", "Limit changed for"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {preview.entitlement_effect.map((r) => (
                  <tr key={r.code} className="border-t border-default">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">{r.label}</th>
                    <td className="py-1 pr-4">{r.gain}</td>
                    <td className="py-1 pr-4">{r.lose}</td>
                    <td className="py-1 pr-4">{r.limit_changed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          {preview.missing > 0 ? <p className="text-sm">Some ids do not exist. Remove them and preview again before assigning.</p> : null}
          <div>
            <button type="button" className={btn} disabled={preview.missing > 0 || preview.would_change === 0} onClick={() => setOpen(true)}>
              {`Assign ${preview.would_change} ${kind === "user" ? "accounts" : "workspaces"}`}
            </button>
          </div>
        </div>
      ) : null}
      <ActionDialog open={open} title="Assign this plan?" confirmLabel="Assign" askReason={false} onClose={() => setOpen(false)}
        onConfirm={async () => {
          if (!preview) return;
          const ids = parseIds(idsText);
          if (!ids) return;
          const out = await api.admin.bulkAssignPlan(preview.plan_code, kind, ids, preview.preview_revision);
          setPreview(null);
          setNotice(`Assigned: ${out.changed} changed, ${out.unchanged} already on version ${out.version}. Each change is recorded in the audit log.`);
        }}>
        <p>{preview ? `${preview.would_change} ${kind === "user" ? "accounts" : "workspaces"} will move to ${preview.plan_code} (version ${preview.target_version}).` : ""}</p>
        <p>All of them change together or none do. Nothing is charged.</p>
      </ActionDialog>
    </Panel>
  );
}
