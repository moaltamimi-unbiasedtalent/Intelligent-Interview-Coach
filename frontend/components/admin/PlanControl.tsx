"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import type { AssignablePlan, SubjectPlan } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, Table, btn, field } from "./ui";

/**
 * Plan panel for one subject (an account or a workspace): current plan, history and a governed change.
 * A plan assignment is an access assignment, not a payment: nothing here charges, prices or invoices.
 */
export function PlanControl({ plan, subject, onChanged }: {
  plan: SubjectPlan | null | undefined;
  subject: { kind: "user" | "workspace"; id: number };
  onChanged: (message: string) => void;
}) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.subscriptionsManage]);
  const [options, setOptions] = useState<AssignablePlan[]>([]);
  const [choice, setChoice] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (canManage) api.admin.assignablePlans().then(setOptions).catch(() => setOptions([]));
  }, [canManage]);

  const cur = plan?.current ?? null;
  const target = options.find((o) => o.plan_code === choice);
  return (
    <Panel title={subject.kind === "user" ? "Plan" : "Workspace plan"}>
      <KeyValue rows={[
        ["Current plan", cur ? `${cur.display_name} (version ${cur.version})` : "No active subscription (Basic access applies)"],
        ["Assigned by", cur ? cur.source.replace(/_/g, " ") : "none"],
        ["Since", cur?.started_at ?? "none"],
      ]} />
      <p className="text-xs text-muted">
        A plan decides which product features are included. It is an access assignment: there is no payment, price or invoice behind it.
        {subject.kind === "workspace" ? " A workspace plan applies only to workspace-scoped features and never raises a member's personal plan." : ""}
      </p>
      {canManage ? (
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-xs text-muted">
            Change plan
            <select className={field} value={choice} onChange={(e) => setChoice(e.target.value)}>
              <option value="">Choose a plan</option>
              {options.filter((o) => o.plan_code !== cur?.plan_code || o.version !== cur?.version).map((o) => (
                <option key={o.plan_code} value={o.plan_code}>{`${o.display_name} (version ${o.version})`}</option>
              ))}
            </select>
          </label>
          <button type="button" className={btn} disabled={!choice} onClick={() => setOpen(true)}>Change plan</button>
        </div>
      ) : null}
      <Table caption="Plan history" rows={(plan?.history ?? []).map((h) => ({ ...h, plan: `${h.display_name} v${h.version}` }))}
        cols={["plan", "status", "source", "started_at", "ended_at"]} />
      <ActionDialog open={open} title="Change plan?" confirmLabel="Change plan" askReason={false} onClose={() => setOpen(false)}
        onConfirm={async () => {
          if (!target) return;
          if (subject.kind === "user") await api.admin.setUserPlan(subject.id, target.plan_code);
          else await api.admin.setWorkspacePlan(subject.id, target.plan_code);
          setChoice("");
          onChanged(`Plan changed to ${target.display_name}. The previous subscription is kept in the history.`);
        }}>
        <p>{target ? `Move this ${subject.kind} to ${target.display_name} (version ${target.version}).` : ""}</p>
        <p>This takes effect immediately for plan-controlled features. It does not charge anything.</p>
      </ActionDialog>
    </Panel>
  );
}
