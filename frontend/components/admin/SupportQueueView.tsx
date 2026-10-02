"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import type { AdminTicketQuery } from "@/lib/admin/types";
import { Pager, Panel, PermissionGate, ResourceState, btn, field, useAdminResource } from "./ui";

const STATUSES = ["new", "triaged", "in_progress", "waiting_for_customer", "resolved", "closed"];
const CATEGORIES = ["account_login", "opportunity", "prepare", "practice_interview", "documents", "ai_response",
  "billing", "privacy", "accessibility", "technical", "data_issue", "other"];
const PRIORITIES = ["low", "normal", "high", "urgent"];
const label = (v: string) => v.replace(/_/g, " ");

export function SupportQueueView() {
  return (
    <PermissionGate anyOf={[P.supportRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const [draft, setDraft] = useState<AdminTicketQuery>({});
  const [query, setQuery] = useState<AdminTicketQuery>({ page: 1 });
  const loaded = useAdminResource(() => api.admin.supportTickets({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const set = (k: keyof AdminTicketQuery) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ ...draft, page: 1 });
  };
  return (
    <div className="grid gap-4">
      <Panel title="Filter the queue">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter support tickets">
          <label className="grid gap-1 text-xs text-muted">
            Reference, email or account id
            <input className={field} value={draft.q ?? ""} onChange={set("q")} maxLength={320} />
          </label>
          <Select name="Status" value={draft.status} options={STATUSES} onChange={set("status")} />
          <Select name="Category" value={draft.category} options={CATEGORIES} onChange={set("category")} />
          <Select name="Priority" value={draft.priority} options={PRIORITIES} onChange={set("priority")} />
          <Select name="Assignee" value={draft.assignee} options={["unassigned", "me"]} onChange={set("assignee")} />
          <button type="submit" className={btn}>Apply</button>
        </form>
        <p className="text-xs text-muted">Search covers ticket references and account identifiers only, not message text.</p>
      </Panel>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Tickets">
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No tickets match.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Support tickets</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Ticket", "Status", "Priority", "Category", "Assignee", "Updated"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((tk) => (
                      <tr key={tk.id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                          <Link href={`/admin/support/${tk.public_id}`} className="underline underline-offset-2">{tk.subject}</Link>
                          <span className="block text-xs font-normal text-muted">{tk.owner_email ?? `Account ${tk.owner_user_id}`}</span>
                        </th>
                        <td className="py-1 pr-4">{label(tk.status)}</td>
                        <td className="py-1 pr-4">{tk.priority}</td>
                        <td className="py-1 pr-4">{label(tk.category)}</td>
                        <td className="py-1 pr-4">{tk.assignee_email ?? (tk.assigned_user_id !== null ? `Account ${tk.assigned_user_id}` : "Unassigned")}</td>
                        <td className="py-1 pr-4">{tk.updated_at ?? ""}</td>
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

function Select({ name, value, options, onChange }: { name: string; value?: string; options: string[]; onChange: (e: { target: { value: string } }) => void }) {
  return (
    <label className="grid gap-1 text-xs text-muted">
      {name}
      <select className={field} value={value ?? ""} onChange={(e) => onChange(e)}>
        <option value="">Any</option>
        {options.map((o) => <option key={o} value={o}>{label(o)}</option>)}
      </select>
    </label>
  );
}
