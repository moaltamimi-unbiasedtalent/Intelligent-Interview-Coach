"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { PlanComparison, PlanEntitlementValue } from "@/lib/admin/types";
import { Panel, ResourceState, ScrollRegion, apiMessage, btn, field, useAdminResource } from "./ui";

const show = (v: PlanEntitlementValue) => (!v.enabled ? "Disabled" : v.limit === null ? "Enabled" : `Limit ${v.limit}`);

/**
 * Entitlement matrix (every registered entitlement against every plan version) and a two-version comparison. Read-only:
 * comparing never changes a version and never moves a subscriber.
 */
export function PlanMatrixPanel() {
  const loaded = useAdminResource(() => api.admin.planMatrix());
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [result, setResult] = useState<PlanComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  const compare = async () => {
    setError(null);
    setResult(null);
    try {
      setResult(await api.admin.comparePlans(Number(left), Number(right)));
    } catch (e) {
      setError(apiMessage(e));
    }
  };

  return (
    <Panel title="Entitlement matrix">
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            <ScrollRegion label="Entitlement matrix (scrollable table)">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Registered entitlements by plan version</caption>
                <thead>
                  <tr className="text-xs text-muted">
                    <th scope="col" className="py-1 pr-4 font-medium">Entitlement</th>
                    {loaded.data.versions.map((v) => (
                      <th key={v.id} scope="col" className="py-1 pr-4 font-medium">{`${v.display_name} v${v.version} (${v.status})`}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loaded.data.entitlements.map((e) => (
                    <tr key={e.code} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">
                        {e.label}
                        {e.bounds.premium_only ? <span className="block text-xs font-normal text-muted">Premium only: never enabled in Basic</span> : null}
                      </th>
                      {loaded.data.versions.map((v) => (
                        <td key={v.id} className="py-1 pr-4">{show(v.values[e.code])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid gap-1 text-xs text-muted">
                Compare this version
                <select className={field} value={left} onChange={(e) => setLeft(e.target.value)}>
                  <option value="">Choose a version</option>
                  {loaded.data.versions.map((v) => <option key={v.id} value={v.id}>{`${v.display_name} v${v.version} (${v.status})`}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-xs text-muted">
                with this version
                <select className={field} value={right} onChange={(e) => setRight(e.target.value)}>
                  <option value="">Choose a version</option>
                  {loaded.data.versions.map((v) => <option key={v.id} value={v.id}>{`${v.display_name} v${v.version} (${v.status})`}</option>)}
                </select>
              </label>
              <button type="button" className={btn} disabled={!left || !right} onClick={compare}>Compare versions</button>
            </div>
          </>
        ) : null}
      </ResourceState>
      {error ? <p role="alert" className="text-sm">{error}</p> : null}
      {result ? (
        <div className="grid gap-2" aria-live="polite">
          <p className="text-sm" role="status">
            {result.changed === 0 ? "These versions grant exactly the same entitlements." : `${result.changed} of ${result.rows.length} entitlements differ.`}
          </p>
          <ScrollRegion label="Version comparison (scrollable table)">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Comparison of two plan versions</caption>
              <thead>
                <tr className="text-xs text-muted">
                  <th scope="col" className="py-1 pr-4 font-medium">Entitlement</th>
                  <th scope="col" className="py-1 pr-4 font-medium">{`${result.left.display_name} v${result.left.version}`}</th>
                  <th scope="col" className="py-1 pr-4 font-medium">{`${result.right.display_name} v${result.right.version}`}</th>
                  <th scope="col" className="py-1 pr-4 font-medium">Difference</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.code} className="border-t border-default">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">{r.label}</th>
                    <td className="py-1 pr-4">{show(r.left)}</td>
                    <td className="py-1 pr-4">{show(r.right)}</td>
                    <td className="py-1 pr-4">{r.differs ? "Differs" : "Same"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <p className="text-xs text-muted">{`Accounts on the first version: ${result.left.subscribers.users}, on the second: ${result.right.subscribers.users}. ${result.note}`}</p>
        </div>
      ) : null}
    </Panel>
  );
}
