"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import type { AdminWorkspaceDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, apiMessage, btn, field, useAdminResource } from "./ui";

type Pending = null | { kind: "remove"; userId: number; email: string | null } | { kind: "role"; userId: number; email: string | null; role: string };

export function WorkspaceDetailView({ workspaceId }: { workspaceId: number }) {
  return (
    <PermissionGate anyOf={[P.workspaces]}>
      <Body workspaceId={workspaceId} />
    </PermissionGate>
  );
}

function Body({ workspaceId }: { workspaceId: number }) {
  const loaded = useAdminResource(() => api.admin.workspaceDetail(workspaceId), [workspaceId]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

function Detail({ d, reload }: { d: AdminWorkspaceDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.workspacesManage]);
  const w = d.workspace;
  const [pending, setPending] = useState<Pending>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newUser, setNewUser] = useState("");
  const [newRole, setNewRole] = useState(d.workspace_roles[d.workspace_roles.length - 1] ?? "");
  const active = d.members.filter((m) => m.membership_status === "active");

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.admin.addWorkspaceMember(w.id, Number(newUser), newRole);
      setNotice("Member added.");
      setNewUser("");
      reload();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  return (
    <div className="grid gap-4">
      <p><Link href="/admin/workspaces" className="text-sm underline underline-offset-2">Back to workspaces</Link></p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}
      <Panel title="Workspace">
        <KeyValue rows={[["Name", w.name], ["Workspace id", w.id], ["Status", w.status], ["Owner", w.owner_email ?? `Account ${w.owner_user_id}`],
          ["Active members", w.member_count], ["Active owners", d.active_owner_count], ["Active shares", d.active_share_count]]} />
        <p className="text-xs text-muted">Shared items are never listed here; only their count.</p>
      </Panel>

      <Panel title="Members">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Workspace members</caption>
            <thead>
              <tr className="text-xs text-muted">
                {["Member", "Role", "Membership", "Account", ...(canManage ? ["Actions"] : [])].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {d.members.map((m) => (
                <tr key={m.user_id} className="border-t border-default">
                  <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                    <Link href={`/admin/users/${m.user_id}`} className="underline underline-offset-2">{m.email ?? `Account ${m.user_id}`}</Link>
                  </th>
                  <td className="py-1 pr-4">{m.role}</td>
                  <td className="py-1 pr-4">{m.membership_status}</td>
                  <td className="py-1 pr-4">{m.account_status}</td>
                  {canManage ? (
                    <td className="py-1 pr-4">
                      {m.membership_status === "active" ? (
                        <span className="flex flex-wrap gap-2">
                          <button type="button" className={btn}
                            onClick={() => setPending({ kind: "role", userId: m.user_id, email: m.email,
                              role: d.workspace_roles.find((r) => r !== m.role) ?? m.role })}>
                            {`Change role: ${m.email ?? m.user_id}`}
                          </button>
                          <button type="button" className={btn} onClick={() => setPending({ kind: "remove", userId: m.user_id, email: m.email })}>
                            {`Remove: ${m.email ?? m.user_id}`}
                          </button>
                        </span>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {canManage ? (
          <form onSubmit={add} className="flex flex-wrap items-end gap-3" aria-label="Add member">
            <label className="grid gap-1 text-xs text-muted">
              Existing account id
              <input className={field} inputMode="numeric" value={newUser} onChange={(e) => setNewUser(e.target.value.replace(/\D/g, ""))} />
            </label>
            <label className="grid gap-1 text-xs text-muted">
              Workspace role
              <select className={field} value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                {d.workspace_roles.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <button type="submit" className={btn} disabled={!newUser}>Add member</button>
            {error ? <p role="alert" className="text-sm">{error}</p> : null}
          </form>
        ) : <p className="text-xs text-muted">Your role can view membership but not change it.</p>}
        <p className="text-xs text-muted">{active.length} active member(s). A workspace always keeps at least one owner.</p>
      </Panel>

      <ActionDialog open={pending?.kind === "remove"} title="Remove this member?" confirmLabel="Remove member" onClose={() => setPending(null)}
        onConfirm={async () => {
          if (pending?.kind !== "remove") return;
          await api.admin.removeWorkspaceMember(w.id, pending.userId);
          setNotice("Member removed. Their shares into this workspace were revoked.");
          reload();
        }} askReason={false}>
        <p>{pending?.kind === "remove" ? pending.email ?? `Account ${pending.userId}` : ""} loses access to this workspace and their shares into it are revoked.</p>
      </ActionDialog>
      <ActionDialog open={pending?.kind === "role"} title="Change workspace role?" confirmLabel="Change role" onClose={() => setPending(null)}
        onConfirm={async () => {
          if (pending?.kind !== "role") return;
          await api.admin.setWorkspaceMemberRole(w.id, pending.userId, pending.role);
          setNotice("Workspace role changed.");
          reload();
        }} askReason={false}>
        <p>{pending?.kind === "role" ? `Set ${pending.email ?? `account ${pending.userId}`} to ${pending.role}.` : ""}</p>
      </ActionDialog>
    </div>
  );
}
