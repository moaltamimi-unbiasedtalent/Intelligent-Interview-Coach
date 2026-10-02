"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Pager, Panel, PermissionGate, ResourceState, btn, field, useAdminResource } from "./ui";

export function WorkspacesView() {
  return (
    <PermissionGate anyOf={[P.workspaces]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState({ q: "", status: "", page: 1 });
  const loaded = useAdminResource(() => api.admin.workspaces({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ q, status, page: 1 });
  };
  return (
    <div className="grid gap-4">
      <Panel title="Find workspaces">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Search workspaces">
          <label className="grid gap-1 text-xs text-muted">
            Name or workspace id
            <input className={field} value={q} onChange={(e) => setQ(e.target.value)} maxLength={120} />
          </label>
          <label className="grid gap-1 text-xs text-muted">
            Status
            <select className={field} value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any</option>
              <option value="active">active</option>
              <option value="deactivated">deactivated</option>
            </select>
          </label>
          <button type="submit" className={btn}>Search</button>
        </form>
      </Panel>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Workspaces (metadata only)">
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No workspaces match.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Workspaces</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Workspace", "Status", "Owner", "Members"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((w) => (
                      <tr key={w.id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">
                          <Link href={`/admin/workspaces/${w.id}`} className="underline underline-offset-2">{w.name}</Link>
                          <span className="block text-xs font-normal text-muted">ID {w.id}</span>
                        </th>
                        <td className="py-1 pr-4">{w.status}</td>
                        <td className="py-1 pr-4 [overflow-wrap:anywhere]">{w.owner_email ?? `Account ${w.owner_user_id}`}</td>
                        <td className="py-1 pr-4">{w.member_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pager page={loaded.data.page} pageSize={loaded.data.page_size} total={loaded.data.total}
              onPage={(p) => setQuery({ ...query, page: p })} />
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}
