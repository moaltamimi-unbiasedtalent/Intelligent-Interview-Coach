"use client";

import { useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { JobDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, useAdminResource } from "./ui";
import { ERROR_LABEL, label, stateText } from "./jobStatus";

export function JobDetailView({ id }: { id: string }) {
  return (
    <PermissionGate anyOf={[P.jobsRead]}>
      <Body id={id} />
    </PermissionGate>
  );
}

function Body({ id }: { id: string }) {
  const loaded = useAdminResource(() => api.admin.job(id), [id]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

function Detail({ d, reload }: { d: JobDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.jobsManage]);
  const [pending, setPending] = useState<null | "retry" | "cancel">(null);
  const [notice, setNotice] = useState<string | null>(null);
  const act = async () => {
    if (pending === "retry") await api.admin.retryJob(d.public_id);
    else await api.admin.cancelJob(d.public_id);
    setNotice(pending === "retry" ? "Job queued for another run." : "Job cancelled.");
    reload();
  };
  return (
    <div className="grid gap-4">
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      <Panel title="Job">
        <KeyValue rows={[
          ["Reference", d.public_id],
          ["Type", d.type_label],
          ["State", <StatusLabel key="s" tone={d.state === "failed" || d.lease.stale ? "warn" : d.state === "succeeded" ? "ok" : "neutral"}>{stateText(d)}</StatusLabel>],
          ["Priority", d.priority],
          ["Attempts", `${d.attempts} of ${d.max_attempts}`],
          ["Manual retries", d.manual_retries],
          ["Created", d.created_at ?? ""],
          ["Updated", d.updated_at ?? ""],
          ["Available from", d.available_at ?? ""],
        ]} />
      </Panel>
      <Panel title="Execution">
        <KeyValue rows={[
          ["Started", d.started_at ?? "Not started"],
          ["Finished", d.finished_at ?? "Not finished"],
          ["Lease", d.lease.held ? (d.lease.stale ? "Held, expired" : "Held") : "Not held"],
          ["Worker", d.lease.owner ?? "None"],
          ["Lease expires", d.lease.expires_at ?? "None"],
          ["Last heartbeat", d.lease.heartbeat_at ?? "None"],
        ]} />
        {d.lease.stale ? <p className="text-sm">The lease has expired. A worker will release it on its next cycle; it is not marked complete.</p> : null}
      </Panel>
      <Panel title="Input summary">
        {Object.keys(d.payload_summary).length === 0 ? <p className="text-sm text-muted">No summary available.</p> :
          <KeyValue rows={Object.entries(d.payload_summary).map(([k, v]) => [label(k), v] as [string, string])} />}
        <p className="text-xs text-muted">Only a safe summary defined by the job type is shown. Raw job input is never displayed.</p>
      </Panel>
      <Panel title="Failure">
        {d.error_category ? (
          <KeyValue rows={[["Problem", ERROR_LABEL[d.error_category] ?? label(d.error_category)], ["Detail", d.error_message ?? ""]]} />
        ) : <p className="text-sm text-muted">No failure recorded.</p>}
      </Panel>
      {canManage && (d.can_retry || d.can_cancel) ? (
        <Panel title="Actions">
          <div className="flex flex-wrap gap-3">
            {d.can_retry ? <button type="button" className={btn} onClick={() => setPending("retry")}>Retry job</button> : null}
            {d.can_cancel ? <button type="button" className={btn} onClick={() => setPending("cancel")}>Cancel queued job</button> : null}
          </div>
          <p className="text-xs text-muted">A running job cannot be cancelled. Retrying requeues this same job; its work must be safe to run again.</p>
        </Panel>
      ) : null}
      <ActionDialog open={pending !== null} title={pending === "retry" ? "Retry this job?" : "Cancel this queued job?"}
        confirmLabel={pending === "retry" ? "Retry job" : "Cancel job"} onConfirm={act} onClose={() => setPending(null)}>
        <p className="text-sm">{pending === "retry" ? "The job returns to the queue with its attempt count reset." : "The job will not run."}</p>
      </ActionDialog>
      <Panel title="Recent management actions">
        {d.audit.length === 0 ? <p className="text-sm text-muted">None recorded.</p> : (
          <ul className="grid gap-1 text-sm">
            {d.audit.map((e, i) => <li key={i}>{label(e.event_type.replace("admin.", ""))} — {e.created_at ?? ""} (request {e.request_id ?? "n/a"})</li>)}
          </ul>
        )}
      </Panel>
    </div>
  );
}
