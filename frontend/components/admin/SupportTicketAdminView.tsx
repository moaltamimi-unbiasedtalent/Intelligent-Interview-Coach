"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { AdminTicketDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, apiMessage, btn, field, useAdminResource } from "./ui";

const label = (v: string) => v.replace(/_/g, " ");

export function SupportTicketAdminView({ reference }: { reference: string }) {
  return (
    <PermissionGate anyOf={[P.supportRead]}>
      <Body reference={reference} />
    </PermissionGate>
  );
}

function Body({ reference }: { reference: string }) {
  const loaded = useAdminResource(() => api.admin.supportTicket(reference), [reference]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

type Pending = null | { kind: "status"; value: string } | { kind: "priority"; value: string } | { kind: "assign"; value: number | null };

function Detail({ d, reload }: { d: AdminTicketDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const can = (p: string) => hasAnyPermission(granted, [p]);
  const t = d.ticket;
  const ref = t.public_id;
  const [pending, setPending] = useState<Pending>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<{ reply?: string; note?: string }>({});
  const [busy, setBusy] = useState<"reply" | "note" | null>(null);
  const [assignees, setAssignees] = useState<{ user_id: number; email: string | null }[] | null>(null);
  const closed = t.status === "closed";

  const loadAssignees = () => {
    if (assignees === null && can(P.supportManage)) api.admin.supportAssignees().then(setAssignees).catch(() => setAssignees([]));
  };
  const done = (m: string) => {
    setNotice(m);
    reload();
  };
  const send = (kind: "reply" | "note") => async (e: FormEvent) => {
    e.preventDefault();
    const text = (kind === "reply" ? reply : note).trim();
    if (!text) return setError({ [kind]: "Write something first." });
    setBusy(kind);
    setError({});
    try {
      if (kind === "reply") {
        await api.admin.supportReply(ref, text);
        setReply("");
        done("Reply sent. The candidate sees it on their ticket page.");
      } else {
        await api.admin.supportNote(ref, text);
        setNote("");
        done("Internal note saved. It is never shown to the candidate.");
      }
    } catch (err) {
      setError({ [kind]: apiMessage(err) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-4">
      <p><Link href="/admin/support" className="text-sm underline underline-offset-2">Back to the queue</Link></p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}

      <Panel title="Ticket">
        <KeyValue rows={[
          ["Reference", t.public_id], ["Subject", t.subject], ["Category", label(t.category)], ["Status", label(t.status)],
          ["Priority", t.priority], ["Assignee", t.assignee_email ?? (t.assigned_user_id !== null ? `Account ${t.assigned_user_id}` : "Unassigned")], ["Created", t.created_at ?? "unknown"],
          ["Updated", t.updated_at ?? "unknown"], ["Request id", t.initial_request_id ?? "none"],
          ["Source page", t.source_route ?? "none"], ["Environment", t.source_environment ?? "unknown"],
        ]} />
        {can(P.supportManage) && !closed ? (
          <div className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-xs text-muted">
              Move to
              <select className={field} value="" onChange={(e) => e.target.value && setPending({ kind: "status", value: e.target.value })}>
                <option value="">Choose status</option>
                {t.allowed_statuses.map((s) => <option key={s} value={s}>{label(s)}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-xs text-muted">
              Priority
              <select className={field} value="" onChange={(e) => e.target.value && setPending({ kind: "priority", value: e.target.value })}>
                <option value="">Change priority</option>
                {d.priorities.filter((p) => p !== t.priority).map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-xs text-muted">
              Assignee
              <select className={field} value="" onFocus={loadAssignees} onMouseDown={loadAssignees}
                onChange={(e) => e.target.value !== "" && setPending({ kind: "assign", value: e.target.value === "none" ? null : Number(e.target.value) })}>
                <option value="">Change assignee</option>
                {t.assigned_user_id !== null ? <option value="none">Unassign</option> : null}
                {(assignees ?? []).map((a) => <option key={a.user_id} value={a.user_id}>{a.email ?? `Account ${a.user_id}`}</option>)}
              </select>
            </label>
          </div>
        ) : null}
        <p className="text-xs text-muted">Priority is an internal label. It does not promise a response time.</p>
      </Panel>

      <Panel title="Requester (safe account metadata)">
        {d.account ? (
          <KeyValue rows={[
            ["Email", d.account.email ?? "none"], ["Account id", d.account.user_id], ["Status", d.account.status], ["Tier", d.account.tier],
            ["Interface language", d.account.interface_locale],
          ]} />
        ) : <p className="text-sm text-muted">Account not available.</p>}
        {d.account ? <Link href={`/admin/users/${d.account.user_id}`} className="text-sm underline underline-offset-2">Open account metadata</Link> : null}
        <p className="text-xs text-muted">Support sees only what the candidate sent to Support plus this metadata. CVs, documents, interview answers and Mo chats are not available.</p>
      </Panel>

      <Panel title="Messages (visible to the candidate)">
        <ol className="grid gap-2" aria-label="Customer-visible messages">
          {d.messages.map((m) => (
            <li key={m.id} className="rounded border border-border px-3 py-2">
              <p className="text-xs font-semibold text-muted">{m.author_kind === "support" ? "Support" : "Candidate"} · {m.created_at ?? ""}{m.request_id ? ` · request ${m.request_id}` : ""}</p>
              <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{m.body}</p>
            </li>
          ))}
        </ol>
        {can(P.supportReply) && !closed ? (
          <form onSubmit={send("reply")} className="grid gap-2" aria-label="Reply to the candidate">
            <label htmlFor="sup-reply" className="text-xs text-muted">Reply (the candidate will see this)</label>
            <textarea id="sup-reply" className={`${field} min-h-[96px] py-2`} value={reply} maxLength={5000} onChange={(e) => setReply(e.target.value)}
              aria-invalid={error.reply ? true : undefined} />
            {error.reply ? <p role="alert" className="text-sm">{error.reply}</p> : null}
            <div><button type="submit" className={btn} disabled={busy === "reply"}>Send reply to candidate</button></div>
          </form>
        ) : null}
      </Panel>

      <Panel title="Internal notes (never visible to the candidate)">
        <ol className="grid gap-2" aria-label="Internal notes">
          {d.internal_notes.length === 0 ? <li className="text-sm text-muted">No internal notes.</li> : null}
          {d.internal_notes.map((n) => (
            <li key={n.id} className="rounded border-2 border-dashed border-border bg-surface-2 px-3 py-2">
              <p className="text-xs font-semibold text-muted">Internal note · {n.created_at ?? ""}</p>
              <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{n.body}</p>
            </li>
          ))}
        </ol>
        {can(P.supportNote) ? (
          <form onSubmit={send("note")} className="grid gap-2" aria-label="Add internal note">
            <label htmlFor="sup-note" className="text-xs text-muted">Internal note (staff only)</label>
            <textarea id="sup-note" className={`${field} min-h-[72px] py-2`} value={note} maxLength={5000} onChange={(e) => setNote(e.target.value)}
              aria-invalid={error.note ? true : undefined} />
            {error.note ? <p role="alert" className="text-sm">{error.note}</p> : null}
            <div><button type="submit" className={btn} disabled={busy === "note"}>Save internal note</button></div>
          </form>
        ) : null}
      </Panel>

      <ActionDialog open={pending?.kind === "status"} title="Change ticket status?" confirmLabel="Change status" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          if (pending?.kind !== "status") return;
          await api.admin.supportStatus(ref, pending.value);
          done(`Status changed to ${label(pending.value)}.`);
        }}>
        <p>{pending?.kind === "status" ? `Move this ticket from ${label(t.status)} to ${label(pending.value)}.` : ""}</p>
        {pending?.kind === "status" && pending.value === "closed" ? <p>A closed ticket cannot be changed or replied to.</p> : null}
      </ActionDialog>
      <ActionDialog open={pending?.kind === "priority"} title="Change priority?" confirmLabel="Change priority" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          if (pending?.kind !== "priority") return;
          await api.admin.supportPriority(ref, pending.value);
          done(`Priority set to ${pending.value}.`);
        }}>
        <p>{pending?.kind === "priority" ? `Set priority to ${pending.value}. This is internal and promises nothing to the candidate.` : ""}</p>
      </ActionDialog>
      <ActionDialog open={pending?.kind === "assign"} title="Change assignee?" confirmLabel="Confirm" askReason={false}
        onClose={() => setPending(null)}
        onConfirm={async () => {
          if (pending?.kind !== "assign") return;
          await api.admin.supportAssign(ref, pending.value);
          done(pending.value === null ? "Ticket unassigned." : "Ticket assigned.");
        }}>
        <p>{pending?.kind === "assign" && pending.value === null ? "Remove the current assignee." : "Assign this ticket to the selected operator."}</p>
      </ActionDialog>
    </div>
  );
}
