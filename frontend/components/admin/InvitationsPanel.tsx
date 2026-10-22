"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api/client";
import { adminPermissions, hasAnyPermission, P } from "@/lib/admin/capabilities";
import type { AdminInvitationIssued } from "@/lib/admin/types";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { Panel, ResourceState, ScrollRegion, apiMessage, btn, field, formatCell, useAdminResource } from "./ui";

/**
 * Private-beta invitations (04E). Listing shows state and masked identifiers only. The plaintext code and link are shown ONCE, from the issue response, and live only in
 * this component's state: they are never written to storage, the URL or the console, and are gone after "Done". Nothing is emailed; the operator copies the link.
 */
export function InvitationsPanel() {
  const auth = useAuthOptional();
  const canManage = !!auth && auth.status !== "loading" && hasAnyPermission(adminPermissions(auth.account), [P.usersManage]);
  const loaded = useAdminResource(() => api.admin.invitations({ limit: 25 }));
  const [days, setDays] = useState("14");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<AdminInvitationIssued | null>(null);
  const [copied, setCopied] = useState(false);

  const issue = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.admin.issueInvitation({ expires_in_days: Number(days) || 14, email: email.trim() || null });
      setIssued(res);
      setEmail("");
      loaded.reload();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: number) => {
    setError(null);
    try {
      await api.admin.revokeInvitation(id);
      loaded.reload();
    } catch (err) {
      setError(apiMessage(err));
    }
  };

  const copy = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="grid gap-4">
      {canManage ? (
        <Panel title="Invite a candidate to the private beta">
          <form onSubmit={issue} className="flex flex-wrap items-end gap-3" aria-label="Issue an invitation">
            <label className="grid gap-1 text-xs text-muted">
              Valid for (days, 1 to 30)
              <input className={field} type="number" min={1} max={30} value={days} onChange={(e) => setDays(e.target.value)} />
            </label>
            <label className="grid gap-1 text-xs text-muted">
              Only this email can use it (optional)
              <input className={field} type="email" value={email} maxLength={320} autoComplete="off" onChange={(e) => setEmail(e.target.value)} />
            </label>
            <button type="submit" className={btn} disabled={busy}>{busy ? "Issuing..." : "Issue invitation"}</button>
          </form>
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          {issued ? (
            <div role="status" className="grid gap-2 rounded border border-border p-3 text-sm">
              <p className="font-medium">Copy this link now. It is shown once and cannot be recovered. Nothing was emailed.</p>
              <input className={field + " w-full font-mono"} readOnly value={issued.link} aria-label="Invitation link" onFocus={(e) => e.currentTarget.select()} />
              <div className="flex gap-2">
                <button type="button" className={btn} onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
                <button type="button" className={btn} onClick={() => { setIssued(null); setCopied(false); }}>Done</button>
              </div>
            </div>
          ) : null}
        </Panel>
      ) : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Invitations (state and masked identifiers only)">
            <p className="text-xs text-muted">
              {Object.entries(loaded.data.counts).map(([k, v]) => `${k}: ${v}`).join(", ")}
            </p>
            {loaded.data.items.length === 0 ? (
              <p className="text-sm text-muted">No invitations yet.</p>
            ) : (
              <ScrollRegion label="Invitations (scrollable table)">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Invitations</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Invitation", "State", "Bound to", "Expires", "Redeemed", ""].map((c, i) => (
                        <th key={i} scope="col" className="py-1 pr-4 font-medium">{c || <span className="sr-only">Actions</span>}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((i) => (
                      <tr key={i.id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium">#{i.id}</th>
                        <td className="py-1 pr-4">{i.state}</td>
                        <td className="py-1 pr-4">{i.email_hint ?? "Any email"}</td>
                        <td className="py-1 pr-4">{formatCell(i.expires_at)}</td>
                        <td className="py-1 pr-4">{formatCell(i.redeemed_at)}</td>
                        <td className="py-1 pr-4">
                          {canManage && i.state === "pending" ? (
                            <button type="button" className={btn} onClick={() => revoke(i.id)} aria-label={`Revoke invitation ${i.id}`}>Revoke</button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollRegion>
            )}
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}
