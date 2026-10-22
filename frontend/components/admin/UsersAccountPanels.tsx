"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import type { AdminUserDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, btn } from "./ui";

const METHOD_LABEL: Record<string, string> = { password: "Email and password", google: "Google sign-in", sso: "Single sign-on" };
const ACTIVITY_LABEL: Record<string, string> = { "24h": "Within 24 hours", "7d": "Within 7 days", "30d": "Within 30 days", older: "Longer ago", never: "Never signed in" };

type Pending = null | "resend" | "expire" | "delete";

/** Sign-in methods, verification and activity (03C). Counts, buckets and states only: no secret, link, provider subject or timestamp finer than a bucket. */
export function UsersSignInPanel({ d, onDone }: { d: AdminUserDetail; onDone: (m: string) => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.usersManage]);
  const [pending, setPending] = useState<Pending>(null);
  const rev = d.revision;
  const auth = d.auth;
  if (!auth) return null;
  const done = onDone;   // the detail page shows the outcome once
  return (
    <Panel title="Sign-in and verification">
      <KeyValue rows={[
        ["Sign-in methods", auth.methods.length ? auth.methods.map((m) => METHOD_LABEL[m.method] ?? m.method).join(", ") : "None recorded"],
        ["Local sign-in available", auth.local_sign_in ? "Yes" : "No"],
        ["Email verified", auth.email_verified ? "Yes" : "No"],
        ["Outstanding verification links", auth.pending_verification_links],
        ["Last activity", ACTIVITY_LABEL[d.activity?.last_active ?? "never"]],
      ]} />
      {canManage ? (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className={btn} disabled={d.access.is_self || auth.email_verified || d.account.status !== "active" || !rev} onClick={() => setPending("resend")}>
            Resend verification email
          </button>
          <button type="button" className={btn} disabled={d.access.is_self || auth.pending_verification_links === 0 || !rev} onClick={() => setPending("expire")}>
            Expire verification links
          </button>
        </div>
      ) : null}
      <ActionDialog open={pending === "resend"} title="Resend the verification email?" confirmLabel="Resend" reasonRequired onClose={() => setPending(null)}
        onConfirm={async (reason) => {
          if (!rev) return;
          const r = await api.admin.userAction(d.account.user_id, "resend-verification", { expected_revision: rev, reason });
          done(r.mail_accepted ? "Verification email submitted. Earlier links no longer work." : "The email provider did not accept the message. Try again later.");
        }}>
        <p>A new single-use link is sent to the account&apos;s own address through the normal verification flow. Earlier links stop working. Delivery to the inbox is not confirmed.</p>
      </ActionDialog>
      <ActionDialog open={pending === "expire"} title="Expire verification links?" confirmLabel="Expire links" reasonRequired onClose={() => setPending(null)}
        onConfirm={async (reason) => {
          if (!rev) return;
          const r = await api.admin.userAction(d.account.user_id, "expire-verification", { expected_revision: rev, reason });
          done(`${r.links_expired ?? 0} verification link(s) expired.`);
        }}>
        <p>Any verification link already sent to this account stops working. The account can request a new one.</p>
      </ActionDialog>
    </Panel>
  );
}

/** Support and privacy case counts, workspace membership summary and the (privacy-pipeline) deletion request (03C). Counts only: no subject, message or note. */
export function UsersCasesPanel({ d, onDone }: { d: AdminUserDetail; onDone: (m: string) => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canDelete = hasAnyPermission(granted, [P.privacyExecute]);
  const canSupport = hasAnyPermission(granted, [P.supportRead]);
  const canPrivacy = hasAnyPermission(granted, [P.privacyRead]);
  const [pending, setPending] = useState<Pending>(null);
  const c = d.cases;
  const m = d.membership;
  if (!c || !m) return null;
  return (
    <Panel title="Cases and membership">
      <KeyValue rows={[
        ["Support tickets (open / total)", `${c.support_open} / ${c.support_total}`],
        ["Privacy requests (open / total)", `${c.privacy_open} / ${c.privacy_total}`],
        ["Role change awaiting approval", c.pending_role_change ? "Yes" : "No"],
        ["Workspaces (active / total)", `${m.active} / ${m.total}`],
        ["Owns active workspaces", m.owner_of_active],
        ["Open deletion request", c.open_deletion_request_id ? `${c.open_deletion_status ?? "open"} (${c.open_deletion_request_id})` : "None"],
      ]} />
      <p className="flex flex-wrap gap-4 text-xs">
        {canSupport ? <Link href="/admin/support" className="underline underline-offset-2">Open the support queue</Link> : null}
        {canPrivacy ? <Link href="/admin/privacy" className="underline underline-offset-2">Open privacy requests</Link> : null}
      </p>
      {canDelete ? (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className={btn} disabled={d.access.is_self || Boolean(c.open_deletion_request_id) || !d.revision} onClick={() => setPending("delete")}>
            Record deletion request
          </button>
          <span className="text-xs text-muted">Nothing is deleted here. Execution stays in privacy requests.</span>
        </div>
      ) : null}
      <ActionDialog open={pending === "delete"} title="Record an account deletion request?" confirmLabel="Record request" reasonRequired onClose={() => setPending(null)}
        onConfirm={async (reason) => {
          if (!d.revision) return;
          const r = await api.admin.userAction(d.account.user_id, "request-deletion", { expected_revision: d.revision, reason });
          onDone(r.changed ? "Deletion request recorded. Review and execute it in privacy requests." : "A deletion request is already open for this account.");
        }}>
        <p>This creates a privacy request of type deletion. The account stays active and no data is removed until a privacy administrator executes the request through the existing deletion process.</p>
      </ActionDialog>
    </Panel>
  );
}
