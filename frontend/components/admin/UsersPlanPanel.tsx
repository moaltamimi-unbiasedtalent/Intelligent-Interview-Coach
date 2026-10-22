"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import type { AssignablePlan, SubjectPlan } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, Table, btn, field } from "./ui";

/**
 * Plan panel for ONE account (03C). The change goes through the strict account action: reason and the account revision are mandatory, the server
 * refuses a stale screen and a change to your own plan. A plan is an access assignment, not a payment: nothing here charges, prices or invoices.
 */
export function UsersPlanPanel({ plan, userId, revision, isSelf, onChanged }: {
  plan: SubjectPlan | null | undefined;
  userId: number;
  revision: string | undefined;
  isSelf: boolean;
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
    <Panel title="Plan">
      <KeyValue rows={[
        ["Current plan", cur ? `${cur.display_name} (version ${cur.version})` : "No active subscription (Basic access applies)"],
        ["Assigned by", cur ? cur.source.replace(/_/g, " ") : "none"],
        ["Since", cur?.started_at ?? "none"],
      ]} />
      <p className="text-xs text-muted">
        A plan decides which product features are included. It is an access assignment: there is no payment, price or invoice behind it.
      </p>
      {canManage ? (
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-xs text-muted">
            Change plan
            <select className={field} value={choice} onChange={(e) => setChoice(e.target.value)} disabled={isSelf}>
              <option value="">Choose a plan</option>
              {options.filter((o) => o.plan_code !== cur?.plan_code || o.version !== cur?.version).map((o) => (
                <option key={o.plan_code} value={o.plan_code}>{`${o.display_name} (version ${o.version})`}</option>
              ))}
            </select>
          </label>
          <button type="button" className={btn} disabled={!choice || isSelf || !revision} onClick={() => setOpen(true)}>Change plan</button>
          {isSelf ? <span className="text-xs text-muted">You cannot change your own plan.</span> : null}
        </div>
      ) : null}
      <Table caption="Plan history" rows={(plan?.history ?? []).map((h) => ({ ...h, plan: `${h.display_name} v${h.version}` }))}
        cols={["plan", "status", "source", "started_at", "ended_at"]} />
      <ActionDialog open={open} title="Change plan?" confirmLabel="Change plan" reasonRequired onClose={() => setOpen(false)}
        onConfirm={async (reason) => {
          if (!target || !revision) return;
          await api.admin.userAction(userId, "assign-plan", { expected_revision: revision, reason, plan_code: target.plan_code });
          setChoice("");
          onChanged(`Plan changed to ${target.display_name}. The previous subscription is kept in the history.`);
        }}>
        <p>{target ? `Move this account to ${target.display_name} (version ${target.version}).` : ""}</p>
        <p>This takes effect immediately for plan-controlled features. It does not charge anything.</p>
      </ActionDialog>
    </Panel>
  );
}
