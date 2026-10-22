"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { PlanDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Pager, Panel, PermissionGate, ResourceState, apiMessage, btn, field, useAdminResource, ScrollRegion, Table } from "./ui";

export function PlanDetailView({ versionId }: { versionId: number }) {
  return (
    <PermissionGate anyOf={[P.plansRead]}>
      <Body versionId={versionId} />
    </PermissionGate>
  );
}

function Body({ versionId }: { versionId: number }) {
  const loaded = useAdminResource(() => api.admin.plan(versionId), [versionId]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

type Pending = null | "activate" | "retire" | "restore";

function Detail({ d, reload }: { d: PlanDetail; reload: () => void }) {
  const canManage = hasAnyPermission(adminPermissions(useAuthOptional()?.account), [P.plansManage]);
  const [edits, setEdits] = useState<Record<string, { enabled: boolean; limit: number | null }>>({});
  const [pending, setPending] = useState<Pending>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const value = (key: string) => edits[key] ?? { enabled: d.entitlements.find((e) => e.code === key)!.enabled, limit: d.entitlements.find((e) => e.code === key)!.limit };
  const dirty = Object.keys(edits).length > 0;

  const save = async () => {
    setError(null);
    try {
      await api.admin.updatePlanDraft(d.id, edits, d.revision);
      setEdits({});
      setNotice("Draft saved.");
      reload();
    } catch (e) {
      setError(apiMessage(e));
    }
  };
  const done = (m: string) => {
    setNotice(m);
    reload();
  };

  return (
    <div className="grid gap-4">
      <p><Link href="/admin/plans" className="text-sm underline underline-offset-2">Back to plans</Link></p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      <Panel title="Plan version">
        <KeyValue rows={[
          ["Plan", `${d.display_name} (${d.plan_code})`], ["Version", d.version], ["State", d.status],
          ["Accounts on this version", d.subscribers.users], ["Workspaces on this version", d.subscribers.workspaces],
          ["Created", d.created_at ?? "unknown"], ["Activated", d.activated_at ?? "not activated"], ["Retired", d.retired_at ?? "not retired"],
        ]} />
        <p className="text-xs text-muted">
          {d.editable ? "This draft is editable. Activating it makes it immutable and assignable; nobody is moved automatically."
            : "This version is immutable. To change what a plan includes, create and activate a new version."}
        </p>
      </Panel>

      <Panel title="Entitlements">
        <ScrollRegion label="Entitlements of this plan version (scrollable table)">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Entitlements of this plan version</caption>
            <thead>
              <tr className="text-xs text-muted">
                {["Entitlement", "Type", "Value"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {d.entitlements.map((e) => {
                const v = value(e.code);
                return (
                  <tr key={e.code} className="border-t border-default">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">
                      {e.label}
                      <span className="block text-xs font-normal text-muted">{e.description}</span>
                      {e.bounds.premium_only ? <span className="block text-xs font-normal text-muted">Premium only: it cannot be enabled in the Basic plan.</span> : null}
                      {e.type === "limit" ? (
                        <span className="block text-xs font-normal text-muted">{`Allowed limit: at least ${e.bounds.min_limit ?? 1}${e.bounds.max_limit !== null ? `, at most ${e.bounds.max_limit}` : ""}.`}</span>
                      ) : null}
                    </th>
                    <td className="py-1 pr-4">{e.type}</td>
                    <td className="py-1 pr-4">
                      {d.editable && canManage ? (
                        <span className="flex flex-wrap items-center gap-3">
                          <label className="flex items-center gap-2">
                            <input type="checkbox" checked={v.enabled}
                              onChange={(ev) => setEdits({ ...edits, [e.code]: { enabled: ev.target.checked, limit: ev.target.checked ? v.limit : null } })} />
                            {`Include ${e.label}`}
                          </label>
                          {e.type === "limit" && v.enabled ? (
                            <label className="flex items-center gap-2 text-xs text-muted">
                              Limit (blank = unlimited)
                              <input className={`${field} w-24`} inputMode="numeric" value={v.limit ?? ""}
                                onChange={(ev) => setEdits({ ...edits, [e.code]: { enabled: true, limit: ev.target.value === "" ? null : Number(ev.target.value.replace(/\D/g, "")) || null } })} />
                            </label>
                          ) : null}
                        </span>
                      ) : (
                        <span>{!e.enabled ? "Disabled" : e.limit === null ? "Enabled" : `Limit ${e.limit}`}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollRegion>
        {error ? <p role="alert" className="text-sm">{error}</p> : null}
        {d.editable && canManage ? (
          <div className="flex flex-wrap gap-3">
            <button type="button" className={btn} disabled={!dirty} onClick={save}>Save draft</button>
            <button type="button" className={btn} disabled={dirty} onClick={() => setPending("activate")}>Activate this version</button>
          </div>
        ) : null}
        {d.status === "active" && canManage ? (
          <div><button type="button" className={btn} onClick={() => setPending("retire")}>Retire this version</button></div>
        ) : null}
      </Panel>

      {canManage && d.status !== "draft" ? (
        <Panel title="Rollback">
          <p className="text-xs text-muted">
            To go back to what this version granted, restore it as a new draft. History is never edited and nobody is moved: review the draft,
            then activate it like any other version.
          </p>
          <div><button type="button" className={btn} onClick={() => setPending("restore")}>Restore this version as a new draft</button></div>
        </Panel>
      ) : null}

      <AssignmentHistory versionId={d.id} />

      <ActionDialog open={pending === "activate"} title="Activate this version?" confirmLabel="Activate" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          await api.admin.activatePlan(d.id, d.revision);
          done("Version activated. It is now immutable and assignable; the previous active version was retired and its subscribers stay on it.");
        }}>
        <p>The version becomes immutable. Existing subscribers are not moved and nobody is charged.</p>
      </ActionDialog>
      <ActionDialog open={pending === "restore"} title="Restore as a new draft?" confirmLabel="Restore as draft" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          const out = await api.admin.restorePlanAsDraft(d.id, d.family_revision);
          done(`Draft version ${out.version} created from version ${out.copied_from}. Open it from the plan list to review and activate it.`);
        }}>
        <p>A new draft is created with the entitlements of this version. Existing versions and subscribers are untouched.</p>
      </ActionDialog>
      <ActionDialog open={pending === "retire"} title="Retire this version?" confirmLabel="Retire" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          await api.admin.retirePlan(d.id, d.revision);
          done("Version retired. It can no longer be assigned; existing subscribers keep it.");
        }}>
        <p>No new assignments will be possible. Existing subscriptions stay as they are.</p>
      </ActionDialog>
    </div>
  );
}

function AssignmentHistory({ versionId }: { versionId: number }) {
  const [page, setPage] = useState(1);
  const loaded = useAdminResource(() => api.admin.planVersionAssignments(versionId, page), [versionId, page]);
  return (
    <Panel title="Assignment history">
      <p className="text-xs text-muted">Every assignment to this version, newest first: the subject, its state, how it was assigned and when. Subjects are shown by id only.</p>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            <Table caption="Assignments of this plan version"
              rows={loaded.data.items.map((i) => ({ subject: `${i.subject_type} ${i.subject_id}`, state: i.status, assigned_by: i.source.replace(/_/g, " "), started_at: i.started_at, ended_at: i.ended_at }))}
              cols={["subject", "state", "assigned_by", "started_at", "ended_at"]} />
            <Pager page={loaded.data.page} pageSize={loaded.data.page_size} total={loaded.data.total} onPage={setPage} />
          </>
        ) : null}
      </ResourceState>
    </Panel>
  );
}
