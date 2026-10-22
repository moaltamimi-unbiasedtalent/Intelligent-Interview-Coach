"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import type { AdminUserDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { UsersPlanPanel } from "./UsersPlanPanel";
import { UsersCasesPanel, UsersSignInPanel } from "./UsersAccountPanels";
import { useStepUp } from "./StepUp";
import { KeyValue, Panel, PermissionGate, ResourceState, Table, btn, field, useAdminResource } from "./ui";

type Pending = null | "deactivate" | "reactivate" | "logout" | "role";

export function UserDetailView({ userId }: { userId: number }) {
  return (
    <PermissionGate anyOf={[P.users]}>
      <Body userId={userId} />
    </PermissionGate>
  );
}

function Body({ userId }: { userId: number }) {
  const loaded = useAdminResource(() => api.admin.userDetail(userId), [userId]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Detail d={loaded.data} reload={loaded.reload} /> : null}
    </ResourceState>
  );
}

function Detail({ d, reload }: { d: AdminUserDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const can = (p: string) => hasAnyPermission(granted, [p]);
  const a = d.account;
  const [pending, setPending] = useState<Pending>(null);
  const [role, setRole] = useState(a.platform_role);
  const [notice, setNotice] = useState<string | null>(null);
  const stepUp = useStepUp();
  // Strict account action: the reason and the account revision this screen was loaded with are sent; a stale screen is refused by the server (409), so reload.
  const strict = async (action: "deactivate" | "reactivate" | "force-signout", reason: string) => {
    if (!d.revision) throw new Error("This account view is out of date. Reload and try again.");
    try {
      return await api.admin.userAction(a.user_id, action, { expected_revision: d.revision, reason });
    } catch (e) {
      reload();
      throw e;
    }
  };
  const done = (msg: string) => {
    setNotice(msg);
    reload();
  };

  return (
    <div className="grid gap-4">
      <p><Link href="/admin/users" className="text-sm underline underline-offset-2">Back to users</Link></p>
      {notice ? <p role="status" className="rounded border border-border px-3 py-2 text-sm">{notice}</p> : null}

      <Panel title="Account">
        <KeyValue rows={[
          ["Email", a.email ?? "none"], ["Account id", a.user_id], ["Status", a.status], ["Legacy tier (display only)", a.tier],
          ["Onboarding", a.onboarding_completed ? "Completed" : "Pending"], ["Interface language", a.interface_locale],
          ["Email verified", a.email_verified ? "Yes" : "No"], ["Created", a.created_at ?? "unknown"], ["Updated", a.updated_at ?? "unknown"],
        ]} />
        {can(P.usersManage) ? (
          <div className="flex flex-wrap items-center gap-3">
            {a.status === "active" ? (
              <button type="button" className={btn} disabled={d.access.is_self || !d.revision} onClick={() => setPending("deactivate")}>
                Deactivate account
              </button>
            ) : (
              <button type="button" className={btn} onClick={() => setPending("reactivate")}>Reactivate account</button>
            )}
            {d.access.is_self ? <span className="text-xs text-muted">You cannot deactivate your own account.</span> : null}
          </div>
        ) : null}
      </Panel>

      <Panel title="Access">
        <KeyValue rows={[["Platform role", a.platform_role], ["Capabilities", d.access.capabilities.length ? d.access.capabilities.join(", ") : "None (candidate account)"]]} />
        {can(P.roleAssign) ? (
          <div className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-xs text-muted">
              Role preset
              <select className={field} value={role} onChange={(e) => setRole(e.target.value)}>
                {d.access.assignable_roles.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <button type="button" className={btn} disabled={role === a.platform_role} onClick={() => setPending("role")}>Request role change</button>
          </div>
        ) : null}
      </Panel>

      <UsersPlanPanel plan={d.plan} userId={a.user_id} revision={d.revision} isSelf={d.access.is_self} onChanged={done} />

      <UsersSignInPanel d={d} onDone={done} />
      <UsersCasesPanel d={d} onDone={done} />

      <Panel title="Sessions">
        <KeyValue rows={[["Active sessions", d.sessions.active_count]]} />
        <Table caption="Active sessions" rows={d.sessions.recent} cols={["created_at", "last_used_at", "expires_at"]} />
        {can(P.sessionsRevoke) ? (
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className={btn} disabled={d.access.is_self || !d.revision} onClick={() => setPending("logout")}>Force logout (revoke all sessions)</button>
            {d.access.is_self ? <span className="text-xs text-muted">You cannot sign out your own sessions from Admin.</span> : null}
          </div>
        ) : null}
      </Panel>

      <Panel title="Workspaces">
        {d.workspaces.length === 0 ? <p className="text-sm text-muted">Not a member of any workspace.</p> : (
          <ul className="grid gap-1 text-sm">
            {d.workspaces.map((w) => (
              <li key={w.workspace_id}>
                <Link href={`/admin/workspaces/${w.workspace_id}`} className="underline underline-offset-2">{w.name}</Link>
                {` - ${w.role}, membership ${w.membership_status}`}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Admin actions on this account">
        <Table caption="Admin audit" rows={d.audit.map((e) => ({ ...e, change: e.context && "before" in e.context ? `${String(e.context.before)} to ${String(e.context.after)}` : "" }))}
          cols={["created_at", "event_type", "result", "actor_user_id", "change", "request_id"]} />
      </Panel>

      <ActionDialog open={pending === "deactivate"} title="Deactivate this account?" confirmLabel="Deactivate"
        onClose={() => setPending(null)}
        reasonRequired
        onConfirm={async (reason) => {
          const r = await strict("deactivate", reason);
          done(`Account deactivated. ${String(r.sessions_revoked ?? 0)} session(s) ended.`);
        }}>
        <p>The person is signed out immediately and cannot sign in until the account is reactivated.</p>
      </ActionDialog>
      <ActionDialog open={pending === "reactivate"} title="Reactivate this account?" confirmLabel="Reactivate"
        onClose={() => setPending(null)}
        reasonRequired
        onConfirm={async (reason) => {
          await strict("reactivate", reason);
          done("Account reactivated. Earlier sessions stay ended; the person must sign in again.");
        }}>
        <p>The person will be able to sign in again. Old sessions are not restored.</p>
      </ActionDialog>
      <ActionDialog open={pending === "logout"} title="Force logout?" confirmLabel="Revoke sessions"
        onClose={() => setPending(null)}
        reasonRequired
        onConfirm={async (reason) => {
          const r = await strict("force-signout", reason);
          done(`${r.sessions_revoked} session(s) revoked.`);
        }}>
        <p>Every live session of this account ends now. The account stays active.</p>
      </ActionDialog>
      <ActionDialog open={pending === "role"} title="Request a platform role change?"
        confirmLabel="Request role change" reasonRequired onClose={() => setPending(null)}
        onConfirm={async (reason) => {
          await stepUp.run(() => api.admin.requestRoleChange(a.user_id, role, reason));
          done(`Role change to ${role} requested. Nothing has changed yet: a different Admin must approve it.`);
        }}>
        <p>Request a change from {a.platform_role} to {role}. The role does not change until a different Admin approves; you will be asked to confirm your password.</p>
        <p>
          <strong>Granting an administrator role gives this account access to the admin area.</strong> You cannot request a change for your own
          account, and the account concerned cannot approve it. Every step is recorded in the audit log.
        </p>
      </ActionDialog>
      {stepUp.dialog}
    </div>
  );
}
