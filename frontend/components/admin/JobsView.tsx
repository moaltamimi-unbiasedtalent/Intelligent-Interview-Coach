"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { JobQuery } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { Pager, Panel, PermissionGate, ResourceState, Stat, StatusLabel, btn, field, useAdminResource } from "./ui";
import { ERROR_LABEL, STATE_LABEL, label, stateText } from "./jobStatus";

const STATES = Object.keys(STATE_LABEL);
const PRIORITIES = ["low", "normal", "high"];

export function JobsView() {
  return (
    <PermissionGate anyOf={[P.jobsRead]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.jobsManage]);
  const [draft, setDraft] = useState<JobQuery>({});
  const [query, setQuery] = useState<JobQuery>({ page: 1 });
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const types = useAdminResource(() => api.admin.jobTypes(), []);
  const diag = useAdminResource(() => api.admin.jobDiagnostics(), []);
  const loaded = useAdminResource(() => api.admin.jobs({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const set = (k: keyof JobQuery) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ ...draft, page: 1 });
  };
  const runDiagnostic = async () => {
    const r = await api.admin.enqueueJob("diagnostic_noop", { label: "Console check" });
    setNotice(r.created ? "Diagnostic job queued. A worker must pick it up." : "An equivalent job is already active.");
    loaded.reload();
    diag.reload();
  };
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        Jobs run in a separate worker process, never in the web API. A queued job only moves when a worker has reported in recently.
        Payloads are never shown here, only a safe summary.
      </p>
      <ResourceState loaded={diag}>
        {diag.state === "ready" ? (
          <Panel title="Queue and workers">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Queued" value={diag.data.queue.queued} />
              <Stat label="Running" value={diag.data.queue.running} />
              <Stat label="Failed" value={diag.data.queue.failed} />
              <Stat label="Stale leases" value={diag.data.queue.stale_leases} />
              <Stat label="Waiting to retry" value={diag.data.queue.retry_waiting} />
              <Stat label="Oldest ready job (seconds)" value={diag.data.queue.oldest_ready_age_seconds ?? "None waiting"} />
              <Stat label="Workers seen recently" value={diag.data.workers.seen_recently} />
              <Stat label="Last worker report" value={diag.data.workers.last_seen_at ?? "Never"} />
            </div>
            {diag.data.workers.seen_recently === 0 && diag.data.queue.queued > 0 ? (
              <p role="status" className="text-sm"><StatusLabel tone="warn">No worker has reported recently, so queued jobs will not run.</StatusLabel></p>
            ) : null}
            <p className="text-xs text-muted">
              Worker presence comes from worker reports only (within {diag.data.workers.stale_after_seconds} seconds). Queue size never implies a healthy worker.
            </p>
          </Panel>
        ) : null}
      </ResourceState>
      <Panel title="Filter the queue">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter jobs">
          <label className="grid gap-1 text-xs text-muted">
            Job reference
            <input className={field} value={draft.q ?? ""} onChange={set("q")} maxLength={64} />
          </label>
          <Select name="State" value={draft.state} options={STATES.map((s) => [s, STATE_LABEL[s as keyof typeof STATE_LABEL]])} onChange={set("state")} />
          <Select name="Job type" value={draft.job_type} onChange={set("job_type")}
            options={types.state === "ready" ? types.data.map((t) => [t.job_type, t.label]) : []} />
          <Select name="Priority" value={draft.priority} options={PRIORITIES.map((p) => [p, p])} onChange={set("priority")} />
          <button type="submit" className={btn}>Apply</button>
        </form>
        <p className="text-xs text-muted">Search covers the job reference only, not job input.</p>
      </Panel>
      {canManage ? (
        <Panel title="Operational diagnostic">
          <p className="text-sm text-muted">Queue a no-op job to confirm a worker is running and picking up work.</p>
          <div><button type="button" className={btn} onClick={() => setConfirm(true)}>Queue diagnostic job</button></div>
          {notice ? <p role="status" className="text-sm">{notice}</p> : null}
        </Panel>
      ) : null}
      <ActionDialog open={confirm} title="Queue a diagnostic job?" confirmLabel="Queue job" askReason={false}
        onConfirm={runDiagnostic} onClose={() => setConfirm(false)}>
        <p className="text-sm">This queues a job that does nothing except prove the queue and a worker are working.</p>
      </ActionDialog>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Job list">
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No jobs match.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Jobs</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Job", "State", "Priority", "Attempts", "Available", "Created", "Finished", "Problem"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((j) => (
                      <tr key={j.public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                          <Link href={`/admin/jobs/${j.public_id}`} className="underline underline-offset-2">{j.type_label}</Link>
                          <span className="block text-xs font-normal text-muted">{j.public_id}</span>
                        </th>
                        <td className="py-1 pr-4"><StatusLabel tone={j.state === "failed" || j.lease.stale ? "warn" : j.state === "succeeded" ? "ok" : "neutral"}>{stateText(j)}</StatusLabel></td>
                        <td className="py-1 pr-4">{j.priority}</td>
                        <td className="py-1 pr-4">{j.attempts} of {j.max_attempts}</td>
                        <td className="py-1 pr-4">{j.available_at ?? ""}</td>
                        <td className="py-1 pr-4">{j.created_at ?? ""}</td>
                        <td className="py-1 pr-4">{j.finished_at ?? "Not finished"}</td>
                        <td className="py-1 pr-4">{j.error_category ? (ERROR_LABEL[j.error_category] ?? label(j.error_category)) : "None"}</td>
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
