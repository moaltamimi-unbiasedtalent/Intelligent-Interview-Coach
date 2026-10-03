"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { PrivacyRequestDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, field, useAdminResource } from "./ui";
import { RESULT_LABEL, STATUS_LABEL, TYPE_LABEL, label } from "./privacyLabels";

export function PrivacyDetailView({ id }: { id: string }) {
  return (
    <PermissionGate anyOf={[P.privacyRead]}>
      <Body id={id} />
    </PermissionGate>
  );
}

function Body({ id }: { id: string }) {
  const loaded = useAdminResource(() => api.admin.privacyRequest(id), [id]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

type Pending = null | { kind: "status"; status: string } | { kind: "assign"; me: boolean } | { kind: "delete" };

function Detail({ d, reload }: { d: PrivacyRequestDetail; reload: () => void }) {
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const canExecute = hasAnyPermission(granted, [P.privacyExecute]);
  const [pending, setPending] = useState<Pending>(null);
  const [result, setResult] = useState("information_provided");
  const [notice, setNotice] = useState<string | null>(null);
  const myId = (auth?.account as { user_id?: number } | null | undefined)?.user_id ?? null;
  const run = async () => {
    if (!pending) return;
    if (pending.kind === "status") {
      await api.admin.privacyStatus(d.public_id, pending.status, pending.status === "completed" ? result : undefined);
      setNotice(`Status changed to ${STATUS_LABEL[pending.status]?.toLowerCase() ?? pending.status}.`);
    } else if (pending.kind === "assign") {
      await api.admin.privacyAssign(d.public_id, pending.me ? myId : null);
      setNotice(pending.me ? "Assigned to you." : "Unassigned.");
    } else {
      await api.admin.privacyExecuteDeletion(d.public_id);
      setNotice("Deletion queued. It completes only when all data has been removed.");
    }
    reload();
  };
  const title = !pending ? "" : pending.kind === "status" ? `Change status to ${STATUS_LABEL[pending.status]?.toLowerCase()}?` : pending.kind === "assign" ? (pending.me ? "Assign this request to you?" : "Unassign this request?") : "Delete this account?";
  return (
    <div className="grid gap-4">
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      <Panel title="Request">
        <KeyValue rows={[
          ["Reference", d.public_id],
          ["Type", TYPE_LABEL[d.request_type] ?? d.request_type],
          ["Status", <StatusLabel key="s" tone={d.status === "completed" ? "ok" : d.status === "rejected" ? "warn" : "neutral"}>{STATUS_LABEL[d.status] ?? d.status}</StatusLabel>],
          ["Source", d.source === "admin_recorded" ? "Recorded by an operator" : "Submitted by the candidate"],
          ["Submitted", d.created_at ?? ""],
          ["Acknowledged", d.acknowledged_at ?? "Not yet"],
          ["Completed", d.completed_at ?? "Not yet"],
          ["Result", d.result_category ? RESULT_LABEL[d.result_category] ?? label(d.result_category) : "None yet"],
          ["Assignee", d.assignee_email ?? "Unassigned"],
        ]} />
        <p className="text-sm font-medium">What the candidate wrote</p>
        <p className="whitespace-pre-wrap rounded border border-default p-3 text-sm [overflow-wrap:anywhere]" data-testid="privacy-note">{d.request_note ?? "No note."}</p>
      </Panel>
      <Panel title="Candidate (account metadata only)">
        {d.candidate ? (
          <KeyValue rows={[["Account", d.candidate.user_id], ["Email", d.candidate.email ?? "None"], ["Account status", d.candidate.status], ["Role", d.candidate.platform_role], ["Created", d.candidate.created_at ?? ""]]} />
        ) : <p className="text-sm text-muted">The account no longer exists or the link was cleared.</p>}
        <p className="text-xs text-muted">This page never shows the candidate&apos;s documents, answers, chats, memories or evidence.</p>
      </Panel>
      <Panel title="Recorded legal acceptance">
        {d.legal.length === 0 ? <p className="text-sm text-muted">Not available.</p> : (
          <ul className="grid gap-1 text-sm">
            {d.legal.map((l) => (
              <li key={l.document}>{label(l.document)}: current version {l.current_version ?? "none"}, {l.accepted_current ? `accepted (${l.last_accepted_at ?? ""})` : "no acceptance recorded for the current version"}</li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted">Only recorded acceptances are shown. Accounts that predate recording have none.</p>
      </Panel>
      <Panel title="Related job">
        {d.related_job_id ? <p className="text-sm"><Link href={`/admin/jobs/${d.related_job_id}`} className="underline underline-offset-2">Open the job</Link></p> : <p className="text-sm text-muted">No job linked.</p>}
      </Panel>
      {canExecute ? (
        <Panel title="Actions">
          <div className="flex flex-wrap gap-3">
            {d.assigned_user_id !== myId ? <button type="button" className={btn} onClick={() => setPending({ kind: "assign", me: true })}>Assign to me</button> : null}
            {d.assigned_user_id !== null ? <button type="button" className={btn} onClick={() => setPending({ kind: "assign", me: false })}>Unassign</button> : null}
            {d.allowed_statuses.map((s) => (
              <button key={s} type="button" className={btn} onClick={() => setPending({ kind: "status", status: s })}>Mark {STATUS_LABEL[s]?.toLowerCase() ?? s}</button>
            ))}
            {d.can_execute_deletion ? <button type="button" className={btn} onClick={() => setPending({ kind: "delete" })}>Delete the account</button> : null}
          </div>
          <p className="text-xs text-muted">Deleting runs the same account deletion the candidate can run themselves, as a background job. The request is completed only when everything has been removed; a failure leaves it in progress and can be retried from the job.</p>
        </Panel>
      ) : null}
      <ActionDialog open={pending !== null} title={title} confirmLabel={pending?.kind === "delete" ? "Delete account" : "Confirm"} onConfirm={run} onClose={() => setPending(null)}>
        <p className="text-sm">{pending?.kind === "delete" ? "This permanently deletes the candidate's account and application-controlled data. It cannot be undone." : "The change is recorded in the audit log."}</p>
        {pending?.kind === "status" && pending.status === "completed" ? (
          <label className="grid gap-1 text-xs text-muted">
            Result
            <select className={field} value={result} onChange={(e) => setResult(e.target.value)}>
              {d.result_categories.map((r) => <option key={r} value={r}>{RESULT_LABEL[r] ?? label(r)}</option>)}
            </select>
          </label>
        ) : null}
      </ActionDialog>
      <Panel title="Recent management actions">
        {d.audit.length === 0 ? <p className="text-sm text-muted">None recorded.</p> : (
          <ul className="grid gap-1 text-sm">{d.audit.map((e, i) => <li key={i}>{label(e.event_type.replace("admin.", ""))} ({e.created_at ?? ""})</li>)}</ul>
        )}
      </Panel>
    </div>
  );
}
