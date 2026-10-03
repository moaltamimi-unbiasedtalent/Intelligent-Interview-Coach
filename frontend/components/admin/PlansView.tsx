"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, apiMessage, btn, useAdminResource } from "./ui";

export function PlansView() {
  return (
    <PermissionGate anyOf={[P.plansRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const canManage = hasAnyPermission(adminPermissions(useAuthOptional()?.account), [P.plansManage]);
  const loaded = useAdminResource(() => api.admin.plans());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const create = async (code: string) => {
    setError(null);
    try {
      const out = await api.admin.createPlanDraft(code);
      setNotice(`Draft version ${out.version} of ${code} created. Open it to edit.`);
      loaded.reload();
    } catch (e) {
      setError(apiMessage(e));
    }
  };
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        Plans are versioned. A draft can be edited; an active version is immutable and assignable; a retired version keeps its
        existing subscribers. Plans decide product access only: there are no prices, payments or invoices.
      </p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      {error ? <p role="alert" className="text-sm">{error}</p> : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Plan versions">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Plan versions</caption>
                <thead>
                  <tr className="text-xs text-muted">
                    {["Plan", "Version", "Status", "Entitlements", "Subscribers", "Activated"].map((c) => (
                      <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loaded.data.items.map((v) => (
                    <tr key={v.id} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">
                        <Link href={`/admin/plans/${v.id}`} className="underline underline-offset-2">{v.display_name}</Link>
                        <span className="block text-xs font-normal text-muted">{v.plan_code}</span>
                      </th>
                      <td className="py-1 pr-4">{v.version}</td>
                      <td className="py-1 pr-4">{v.status}</td>
                      <td className="py-1 pr-4">{`${v.enabled_entitlements} of ${v.total_entitlements} enabled`}</td>
                      <td className="py-1 pr-4">{`Accounts ${v.subscribers.users}, workspaces ${v.subscribers.workspaces}`}</td>
                      <td className="py-1 pr-4">{v.activated_at ?? "not activated"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {canManage ? (
              <div className="flex flex-wrap gap-2">
                {Array.from(new Set(loaded.data.items.map((v) => v.plan_code))).map((code) => (
                  <button key={code} type="button" className={btn} onClick={() => create(code)}
                    disabled={loaded.data.items.some((v) => v.plan_code === code && v.status === "draft")}>
                    {`Create next draft of ${code}`}
                  </button>
                ))}
              </div>
            ) : null}
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}
