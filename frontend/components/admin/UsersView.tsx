"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import type { AdminUserQuery } from "@/lib/admin/types";
import { Pager, Panel, PermissionGate, ResourceState, btn, field, useAdminResource, ScrollRegion } from "./ui";

const STATUSES = ["active", "deactivated", "deletion_requested"];
const ROLES = ["user", "platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"];
const TIERS = ["basic", "premium"];
const SORTS = ["created_at", "updated_at", "email", "status", "role", "workspaces", "last_active"];

export function UsersView() {
  return (
    <PermissionGate anyOf={[P.users]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const [draft, setDraft] = useState<AdminUserQuery>({});
  const [query, setQuery] = useState<AdminUserQuery>({ page: 1 });
  const loaded = useAdminResource(() => api.admin.users({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const set = (k: keyof AdminUserQuery) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ ...draft, page: 1 });
  };
  return (
    <div className="grid gap-4">
      <Panel title="Find accounts">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Search accounts">
          <label className="grid gap-1 text-xs text-muted">
            Email or account id
            <input className={field} value={draft.q ?? ""} onChange={set("q")} maxLength={320} />
          </label>
          <Select label="Status" value={draft.status} options={STATUSES} onChange={set("status")} />
          <Select label="Role" value={draft.role} options={ROLES} onChange={set("role")} />
          <Select label="Tier" value={draft.tier} options={TIERS} onChange={set("tier")} />
          <Select label="Onboarding" value={draft.onboarding} options={["completed", "pending"]} onChange={set("onboarding")} />
          <Select label="Email verified" value={draft.email_verified} options={["true", "false"]} onChange={set("email_verified")} />
          <Select label="Sort by" value={draft.sort} options={SORTS} onChange={set("sort")} any="Newest first" />
          <Select label="Order" value={draft.direction} options={["asc", "desc"]} onChange={set("direction")} any="Default" />
          <Select label="Last active" value={draft.last_active} options={["24h", "7d", "30d", "older", "never"]} onChange={set("last_active")} />
          <Select label="Sign-in method" value={draft.auth_method} options={["password", "other"]} onChange={set("auth_method")} />
          <Select label="Open case" value={draft.open_case} options={["support", "privacy"]} onChange={set("open_case")} />
          <Select label="Workspace member" value={draft.has_workspace} options={["true", "false"]} onChange={set("has_workspace")} />
          <button type="submit" className={btn}>Search</button>
        </form>
      </Panel>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Accounts (metadata only)">
            {loaded.data.items.length === 0 ? (
              <p className="text-sm text-muted">No accounts match.</p>
            ) : (
              <ScrollRegion label="Accounts (scrollable table)">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Accounts</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Account", "Status", "Role", "Tier", "Workspaces", "Sessions", "Last active"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((u) => (
                      <tr key={u.user_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                          <Link href={`/admin/users/${u.user_id}`} className="underline underline-offset-2">
                            {u.email ?? `Account ${u.user_id}`}
                          </Link>
                          <span className="block text-xs font-normal text-muted">ID {u.user_id}</span>
                        </th>
                        <td className="py-1 pr-4">{u.status}</td>
                        <td className="py-1 pr-4">{u.platform_role}</td>
                        <td className="py-1 pr-4">{u.tier}</td>
                        <td className="py-1 pr-4">{u.workspace_count}</td>
                        <td className="py-1 pr-4">{u.active_session_count}</td>
                        <td className="py-1 pr-4">{u.last_activity ?? "unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollRegion>
            )}
            <Pager page={loaded.data.page} pageSize={loaded.data.page_size} total={loaded.data.total}
              onPage={(p) => setQuery({ ...query, page: p })} />
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}

function Select({ label, value, options, onChange, any = "Any" }: { label: string; value?: string; options: string[]; onChange: (e: { target: { value: string } }) => void; any?: string }) {
  return (
    <label className="grid gap-1 text-xs text-muted">
      {label}
      <select className={field} value={value ?? ""} onChange={(e) => onChange(e)}>
        <option value="">{any}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
