"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { PrivacyQuery } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Pager, Panel, PermissionGate, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";
import { STATUS_LABEL, TYPE_LABEL } from "./privacyLabels";

export function PrivacyView() {
  return (
    <PermissionGate anyOf={[P.privacyRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canExecute = hasAnyPermission(granted, [P.privacyExecute]);
  const [draft, setDraft] = useState<PrivacyQuery>({});
  const [query, setQuery] = useState<PrivacyQuery>({ page: 1 });
  const [confirmBackfill, setConfirmBackfill] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const loaded = useAdminResource(() => api.admin.privacyQueue({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const coverage = useAdminResource(() => api.admin.preparationCoverage(), []);
  const set = (k: keyof PrivacyQuery) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ ...draft, page: 1 });
  };
  const runBackfill = async () => {
    const r = await api.admin.preparationBackfill();
    setNotice(r.created ? "Indexing job queued. A worker must pick it up." : "An indexing job is already queued or running.");
    coverage.reload();
  };
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        Privacy requests from candidates and requests you record from other channels. This area handles requests and workflow state; it never
        shows a candidate&apos;s documents, answers, preparation chats, memories or other private content. Self-service export and deletion
        remain with the candidate. Nothing here is a statement of legal compliance.
      </p>
      <Panel title="Filter the queue">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter privacy requests">
          <label className="grid gap-1 text-xs text-muted">
            Search by reference, account id or email
            <input className={field} value={draft.q ?? ""} onChange={set("q")} maxLength={120} />
          </label>
          <Select name="Status" value={draft.status} options={[["open", "All open"], ...Object.entries(STATUS_LABEL)]} onChange={set("status")} />
          <Select name="Request type" value={draft.request_type} options={Object.entries(TYPE_LABEL)} onChange={set("request_type")} />
          <Select name="Assignee" value={draft.assignee} options={[["unassigned", "Unassigned"], ["me", "Assigned to me"]]} onChange={set("assignee")} />
          <button type="submit" className={btn}>Apply</button>
        </form>
        <p className="text-xs text-muted">Search covers references, account ids and emails only, not request text.</p>
      </Panel>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Request queue">
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No privacy requests match.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Privacy requests</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Request", "Type", "Status", "Candidate", "Assignee", "Submitted", "Job"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((r) => (
                      <tr key={r.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                          <Link href={`/admin/privacy/${r.public_id}`} className="underline underline-offset-2">{r.public_id}</Link>
                          <span className="block text-xs font-normal text-muted">{r.source === "admin_recorded" ? "Recorded by an operator" : "Submitted by the candidate"}</span>
                        </th>
                        <td className="py-1 pr-4">{TYPE_LABEL[r.request_type] ?? r.request_type}</td>
                        <td className="py-1 pr-4"><StatusLabel tone={r.status === "completed" ? "ok" : r.status === "rejected" ? "warn" : "neutral"}>{STATUS_LABEL[r.status] ?? r.status}</StatusLabel></td>
                        <td className="py-1 pr-4">{r.candidate_email ?? (r.user_id !== null ? `Account ${r.user_id}` : "Account removed")}</td>
                        <td className="py-1 pr-4">{r.assignee_email ?? "Unassigned"}</td>
                        <td className="py-1 pr-4">{r.created_at ?? ""}</td>
                        <td className="py-1 pr-4">{r.related_job_id ? <Link href={`/admin/jobs/${r.related_job_id}`} className="underline underline-offset-2">Job</Link> : "None"}</td>
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
      {canExecute ? <RecordForm onDone={loaded.reload} /> : null}
      <ResourceState loaded={coverage}>
        {coverage.state === "ready" ? (
          <Panel title="Preparation-run index">
            <div className="grid gap-3 sm:grid-cols-3">
              <Stat label="Indexed runs" value={coverage.data.indexed_runs} />
              <Stat label="Created since indexing began" value={coverage.data.by_source.created ?? 0} />
              <Stat label="Indexed from history" value={(coverage.data.by_source.backfill ?? 0) + (coverage.data.by_source.lazy ?? 0)} />
            </div>
            <p className="text-xs text-muted">{coverage.data.note}</p>
            {canExecute ? (
              <div className="grid gap-2">
                <div><button type="button" className={btn} onClick={() => setConfirmBackfill(true)}>Index historical runs</button></div>
                {notice ? <p role="status" className="text-sm">{notice}</p> : null}
              </div>
            ) : null}
          </Panel>
        ) : null}
      </ResourceState>
      <ActionDialog open={confirmBackfill} title="Index historical preparation runs?" confirmLabel="Queue indexing" askReason={false}
        onConfirm={runBackfill} onClose={() => setConfirmBackfill(false)}>
        <p className="text-sm">
          A worker looks up runs referenced by saved memories one by one, checks each run&apos;s recorded owner, and indexes only unambiguous
          matches. It does not scan the whole chat store and does not read any chat content.
        </p>
      </ActionDialog>
    </div>
  );
}

function RecordForm({ onDone }: { onDone: () => void }) {
  const [account, setAccount] = useState("");
  const [type, setType] = useState("data_access");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!account.trim()) return setError("Enter the candidate's email or account id.");
    try {
      const r = await api.admin.privacyRecord(account.trim(), type, note.trim());
      setNotice(`Recorded as ${r.public_id}.`);
      setAccount("");
      setNote("");
      onDone();
    } catch (err) {
      setError(apiMessage(err));
    }
  };
  return (
    <Panel title="Record a request received another way">
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" aria-label="Record a privacy request">
        <label className="grid gap-1 text-xs text-muted">Candidate email or account id
          <input className={field} value={account} onChange={(e) => setAccount(e.target.value)} maxLength={320} aria-invalid={error ? true : undefined} aria-describedby={error ? "privacy-record-error" : undefined} />
        </label>
        <label className="grid gap-1 text-xs text-muted">Request type
          <select className={field} value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-muted sm:col-span-2">Short note (what was asked; no private content)
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
        </label>
        <div className="sm:col-span-2 grid gap-2">
          {error ? <p id="privacy-record-error" role="alert" className="text-sm">{error}</p> : null}
          {notice ? <p role="status" className="text-sm">{notice}</p> : null}
          <div><button type="submit" className={btn}>Record request</button></div>
        </div>
      </form>
    </Panel>
  );
}

function Select({ name, value, options, onChange }: { name: string; value?: string; options: string[][]; onChange: (e: { target: { value: string } }) => void }) {
  return (
    <label className="grid gap-1 text-xs text-muted">
      {name}
      <select className={field} value={value ?? ""} onChange={(e) => onChange(e)}>
        <option value="">Any</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}
