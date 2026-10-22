"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Field";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ShareGrantOut, WorkspaceDetail as Detail, WorkspaceMember } from "@/lib/api/types";
import { SharedItemViewer } from "./SharedItemViewer";
import { loadShareableItems, resourceTypeKey, roleKey, workspaceErrorKey } from "./workspaceUi";

type Notice = { tone: "success" | "danger" | "warning" | "info"; text: string } | null;
type Pending =
  | { kind: "remove"; member: WorkspaceMember }
  | { kind: "transfer"; member: WorkspaceMember }
  | { kind: "leave" }
  | { kind: "archive" }
  | { kind: "delete" }
  | null;

const selectCls =
  "min-h-[36px] rounded-lg border border-border bg-surface px-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-1";

/** One workspace: people, invitations, what is shared, settings. Every control reflects server-derived capabilities; the server re-checks every action. */
export function WorkspaceDetail({ workspaceId }: { workspaceId: number }) {
  const { t, formatDate } = useI18n();
  const router = useRouter();
  const ids = useId();
  const [ws, setWs] = useState<Detail | null>(null);
  const [shares, setShares] = useState<ShareGrantOut[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "gone" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [typedName, setTypedName] = useState("");
  const [renameTo, setRenameTo] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("workspace_member");
  const [viewing, setViewing] = useState<ShareGrantOut | null>(null);

  const load = useCallback(async () => {
    try {
      const [detail, sh] = await Promise.all([api.workspaces.get(workspaceId), api.workspaces.shares(workspaceId)]);
      setWs(detail);
      setRenameTo(detail.name);
      setShares(sh.shares);
      setState("ready");
    } catch (e) {
      setState(e instanceof ApiError && e.status === 404 ? "gone" : "error");
    }
  }, [workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const caps = ws?.capabilities;
  const archived = ws ? ws.status !== "active" : false;

  const run = async (fn: () => Promise<unknown>, success?: string) => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      if (success) setNotice({ tone: "success", text: success });
      await load();
      return true;
    } catch (e) {
      setNotice({ tone: "danger", text: t(workspaceErrorKey(e)) });
      return false;
    } finally {
      setBusy(false);
    }
  };

  const closeDialog = () => { if (busy) return; setPending(null); setDialogError(null); setTypedName(""); };

  const confirmPending = async () => {
    if (!pending || !ws) return;
    const needsName = pending.kind === "transfer" || pending.kind === "delete";
    if (needsName && typedName.trim() !== ws.name) { setDialogError(t("wsMgmt.errValidation")); return; }
    setBusy(true);
    setDialogError(null);
    try {
      if (pending.kind === "remove") {
        await api.workspaces.removeMember(ws.id, pending.member.user_id);
        setNotice({ tone: "success", text: t("wsMgmt.memberRemoved") });
      } else if (pending.kind === "transfer") {
        await api.workspaces.transfer(ws.id, pending.member.user_id, typedName.trim());
        setNotice({ tone: "success", text: t("wsMgmt.transferred") });
      } else if (pending.kind === "leave") {
        await api.workspaces.leave(ws.id);
        router.push("/workspaces");
        return;
      } else if (pending.kind === "archive") {
        await api.workspaces.archive(ws.id);
        setNotice({ tone: "success", text: t("wsMgmt.archivedNotice") });
      } else if (pending.kind === "delete") {
        await api.workspaces.remove(ws.id, typedName.trim());
        router.push("/workspaces");
        return;
      }
      setPending(null);
      setTypedName("");
      await load();
    } catch (e) {
      setDialogError(t(workspaceErrorKey(e)));
    } finally {
      setBusy(false);
    }
  };

  const header = (title: string) => (
    <PageHeader eyebrow={t("workspaces.eyebrow")} title={title} description={t("wsMgmt.peopleOnlyNote")} />
  );

  if (state === "loading")
    return <section>{header(t("workspaces.title"))}<p className="text-sm text-muted" role="status">{t("states.loading")}…</p></section>;
  if (state === "error")
    return (
      <section>
        {header(t("workspaces.title"))}
        <p className="text-sm text-muted" role="alert">{t("states.genericError")}</p>
        <Button variant="ghost" size="sm" onClick={() => void load()}>{t("states.retry")}</Button>
      </section>
    );

  if (state === "gone" || !ws)
    return (
      <section>
        {header(t("workspaces.title"))}
        <p className="text-sm text-muted" role="alert">{t("wsMgmt.errNotFound")}</p>
        <p className="mt-3"><Link href="/workspaces" className="text-sm font-semibold text-accent hover:underline">{t("wsMgmt.backToList")}</Link></p>
      </section>
    );
  const memberName = (m: WorkspaceMember) => (m.is_me ? `${m.label} (${t("wsMgmt.you")})` : m.label);
  const pendingInvites = ws.pending_invitations ?? [];
  const shareLabel = (s: ShareGrantOut) => `${t(resourceTypeKey(s.resource_type))} #${s.resource_id}`;
  const dialogName = pending && "member" in pending ? pending.member.label : ws.name;

  return (
    <section>
      <p className="mb-2"><Link href="/workspaces" className="text-sm font-semibold text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("wsMgmt.backToList")}</Link></p>
      <PageHeader
        eyebrow={t(roleKey(ws.my_role))}
        title={ws.name}
        description={t("wsMgmt.peopleOnlyNote")}
        actions={archived ? <Badge>{t("wsMgmt.archivedBadge")}</Badge> : undefined}
      />
      <div className="grid gap-4">
        {notice && <Alert tone={notice.tone}>{notice.text}</Alert>}
        {archived && <Alert tone="warning">{t("wsMgmt.archivedBanner")}</Alert>}
        <p className="text-xs text-muted">{t("wsMgmt.roleHelp")}</p>

        <section className="grid gap-2" aria-labelledby={`${ids}-members`}>
          <h2 id={`${ids}-members`} className="text-base font-semibold">{t("wsMgmt.sectionMembers")} ({ws.member_count})</h2>
          <ul className="grid gap-2">
            {ws.members.map((m) => (
              <li key={m.user_id}>
                <Card><CardBody className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{memberName(m)} <Badge>{t(roleKey(m.role))}</Badge></p>
                    <p className="text-xs text-muted">
                      {m.email ? `${m.email} · ` : ""}{m.joined_at ? t("wsMgmt.joinedOn", { date: formatDate(m.joined_at, { dateStyle: "medium" }) }) : ""}
                    </p>
                  </div>
                  {!m.is_me && (
                    <div className="flex flex-wrap items-center gap-2">
                      {caps?.can_change_roles && m.role !== "workspace_owner" && !archived && (
                        <Button size="sm" variant="ghost" disabled={busy}
                          aria-label={`${m.role === "workspace_admin" ? t("wsMgmt.makeMember") : t("wsMgmt.makeAdmin")}: ${m.label}`}
                          onClick={() => run(() => api.workspaces.setMemberRole(ws.id, m.user_id, m.role === "workspace_admin" ? "workspace_member" : "workspace_admin"), t("wsMgmt.roleChanged"))}>
                          {m.role === "workspace_admin" ? t("wsMgmt.makeMember") : t("wsMgmt.makeAdmin")}
                        </Button>
                      )}
                      {caps?.can_transfer && (
                        <Button size="sm" variant="ghost" disabled={busy} aria-label={`${t("wsMgmt.transferAction")}: ${m.label}`}
                          onClick={() => setPending({ kind: "transfer", member: m })}>{t("wsMgmt.transferAction")}</Button>
                      )}
                      {caps?.can_remove_members && m.role !== "workspace_owner" && (m.role === "workspace_member" || caps.can_change_roles) && (
                        <Button size="sm" variant="ghost" disabled={busy} aria-label={`${t("wsMgmt.removeMember")}: ${m.label}`}
                          onClick={() => setPending({ kind: "remove", member: m })}>{t("wsMgmt.removeMember")}</Button>
                      )}
                    </div>
                  )}
                </CardBody></Card>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">{t("wsMgmt.memberLimitNote", { max: ws.limits?.max_members ?? 100 })}</p>
          {caps?.can_leave && (
            <div><Button variant="ghost" size="sm" disabled={busy} onClick={() => setPending({ kind: "leave" })}>{t("workspaces.leave")}</Button></div>
          )}
          {!caps?.can_leave && <p className="text-xs text-muted">{t("wsMgmt.ownerMustTransfer")}</p>}
        </section>

        {(caps?.can_invite || pendingInvites.length > 0) && (
          <section className="grid gap-2" aria-labelledby={`${ids}-inv`}>
            <h2 id={`${ids}-inv`} className="text-base font-semibold">{t("wsMgmt.sectionInvitations")}</h2>
            {caps?.can_invite && (
              <Card><CardBody className="grid gap-2">
                <h3 className="text-sm font-semibold">{t("wsMgmt.inviteTitle")}</h3>
                <form className="flex flex-wrap items-end gap-2" onSubmit={async (e) => {
                  e.preventDefault();
                  if (!inviteEmail.trim()) return;
                  setBusy(true); setNotice(null);
                  try {
                    const r = await api.workspaces.invite(ws.id, inviteEmail.trim(), inviteRole);
                    setNotice({ tone: r.email_delivery === "submitted" ? "success" : "warning", text: t(r.email_delivery === "submitted" ? "wsMgmt.inviteSubmitted" : "wsMgmt.inviteNotSubmitted") });
                    setInviteEmail("");
                    await load();
                  } catch (err) {
                    setNotice({ tone: "danger", text: t(workspaceErrorKey(err)) });
                  } finally { setBusy(false); }
                }}>
                  <div className="grid gap-1">
                    <label htmlFor={`${ids}-email`} className="text-xs font-semibold">{t("wsMgmt.inviteEmail")}</label>
                    <Input id={`${ids}-email`} type="email" autoComplete="off" value={inviteEmail} maxLength={320} required
                      onChange={(e) => setInviteEmail(e.target.value)} className="min-w-[16rem]" />
                  </div>
                  {caps.can_invite_admin && (
                    <div className="grid gap-1">
                      <label htmlFor={`${ids}-role`} className="text-xs font-semibold">{t("wsMgmt.inviteRole")}</label>
                      <select id={`${ids}-role`} className={selectCls} value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                        <option value="workspace_member">{t("wsMgmt.roleMember")}</option>
                        <option value="workspace_admin">{t("wsMgmt.roleAdmin")}</option>
                      </select>
                    </div>
                  )}
                  <Button type="submit" disabled={busy || !inviteEmail.trim()}>{t("wsMgmt.inviteSend")}</Button>
                </form>
                <p className="text-xs text-muted">{t("wsMgmt.inviteHint", { hours: ws.limits?.invitation_ttl_hours ?? 72 })}</p>
              </CardBody></Card>
            )}
            <h3 className="text-sm font-semibold">{t("wsMgmt.pendingTitle")}</h3>
            {pendingInvites.length === 0 && <p className="text-sm text-muted">{t("wsMgmt.pendingEmpty")}</p>}
            <ul className="grid gap-2">
              {pendingInvites.map((inv) => (
                <li key={inv.id}>
                  <Card><CardBody className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm">{inv.email} <Badge>{t(roleKey(inv.role))}</Badge> {inv.status === "expired" && <Badge tone="medium">{t("wsMgmt.pendingExpired")}</Badge>}</p>
                      {inv.expires_at && <p className="text-xs text-muted">{t("wsMgmt.invitedExpires", { date: formatDate(inv.expires_at, { dateStyle: "medium" }) })}</p>}
                    </div>
                    <Button size="sm" variant="ghost" disabled={busy || (inv.role === "workspace_admin" && !caps?.can_invite_admin)}
                      aria-label={`${t("wsMgmt.revokeInvite")}: ${inv.email}`}
                      onClick={() => run(() => api.workspaces.revokeInvitation(ws.id, inv.id), t("wsMgmt.inviteRevoked"))}>
                      {t("wsMgmt.revokeInvite")}
                    </Button>
                  </CardBody></Card>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="grid gap-2" aria-labelledby={`${ids}-shared`}>
          <h2 id={`${ids}-shared`} className="text-base font-semibold">{t("wsMgmt.sectionShared")}</h2>
          {shares.length === 0 && <p className="text-sm text-muted">{t("wsMgmt.sharedEmpty")}</p>}
          <ul className="grid gap-2">
            {shares.map((s) => (
              <li key={s.id}>
                <Card><CardBody className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm">{shareLabel(s)}</p>
                    <p className="text-xs text-muted">{s.mine ? t("wsMgmt.sharedByYou") : t("wsMgmt.sharedBy", { name: s.shared_by ?? "" })}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" aria-label={`${t("wsMgmt.viewShared")}: ${shareLabel(s)}`} onClick={() => setViewing(s)}>{t("wsMgmt.viewShared")}</Button>
                    {s.mine && (
                      <Button size="sm" variant="ghost" disabled={busy} aria-label={`${t("wsMgmt.stopSharing")}: ${shareLabel(s)}`}
                        onClick={async () => { const ok = await run(() => api.shares.revoke(s.id), t("wsMgmt.shareStopped")); if (ok && viewing?.id === s.id) setViewing(null); }}>
                        {t("wsMgmt.stopSharing")}
                      </Button>
                    )}
                  </div>
                </CardBody></Card>
              </li>
            ))}
          </ul>
          {viewing && <SharedItemViewer resourceType={viewing.resource_type} resourceId={viewing.resource_id} onClose={() => setViewing(null)} />}
          {archived ? <p className="text-sm text-muted">{t("wsMgmt.shareArchived")}</p> : <ShareItemForm workspaceId={ws.id} disabled={busy} onShared={async () => { setNotice({ tone: "success", text: t("wsMgmt.shareDone") }); await load(); }} onError={(e) => setNotice({ tone: "danger", text: t(workspaceErrorKey(e)) })} />}
        </section>

        {(caps?.can_rename || caps?.can_archive || caps?.can_restore || caps?.can_delete) && (
          <section className="grid gap-2" aria-labelledby={`${ids}-settings`}>
            <h2 id={`${ids}-settings`} className="text-base font-semibold">{t("wsMgmt.sectionSettings")}</h2>
            <Card><CardBody className="grid gap-3">
              {caps?.can_rename && (
                <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (renameTo.trim() && renameTo.trim() !== ws.name) void run(() => api.workspaces.rename(ws.id, renameTo.trim()), t("wsMgmt.renamed")); }}>
                  <div className="grid gap-1">
                    <label htmlFor={`${ids}-name`} className="text-xs font-semibold">{t("wsMgmt.settingsRename")}</label>
                    <Input id={`${ids}-name`} value={renameTo} maxLength={120} onChange={(e) => setRenameTo(e.target.value)} className="min-w-[16rem]" />
                  </div>
                  <Button type="submit" variant="ghost" disabled={busy || !renameTo.trim() || renameTo.trim() === ws.name}>{t("wsMgmt.renameSave")}</Button>
                </form>
              )}
              <div className="flex flex-wrap gap-2">
                {caps?.can_archive && <Button variant="ghost" size="sm" disabled={busy} onClick={() => setPending({ kind: "archive" })}>{t("wsMgmt.archiveAction")}</Button>}
                {caps?.can_restore && <Button variant="ghost" size="sm" disabled={busy} onClick={() => void run(() => api.workspaces.restore(ws.id), t("wsMgmt.restored"))}>{t("wsMgmt.restoreAction")}</Button>}
                {caps?.can_delete && <Button variant="ghost" size="sm" disabled={busy} onClick={() => setPending({ kind: "delete" })}>{t("wsMgmt.deleteAction")}</Button>}
              </div>
            </CardBody></Card>
          </section>
        )}
      </div>

      <ConfirmDialog
        open={pending !== null}
        title={
          pending?.kind === "remove" ? t("wsMgmt.removeTitle", { name: dialogName })
          : pending?.kind === "transfer" ? t("wsMgmt.transferTitle", { name: dialogName })
          : pending?.kind === "leave" ? t("wsMgmt.leaveTitle")
          : pending?.kind === "archive" ? t("wsMgmt.archiveTitle")
          : t("wsMgmt.deleteTitle")
        }
        confirmLabel={
          pending?.kind === "remove" ? t("wsMgmt.removeConfirm")
          : pending?.kind === "transfer" ? t("wsMgmt.transferConfirm")
          : pending?.kind === "leave" ? t("wsMgmt.leaveConfirm")
          : pending?.kind === "archive" ? t("wsMgmt.archiveConfirm")
          : t("wsMgmt.deleteConfirm")
        }
        busy={busy}
        error={dialogError}
        onConfirm={() => void confirmPending()}
        onCancel={closeDialog}
        testId="workspace-confirm"
      >
        <p>
          {pending?.kind === "remove" ? t("wsMgmt.removeBody", { name: dialogName })
            : pending?.kind === "transfer" ? t("wsMgmt.transferBody", { name: dialogName })
            : pending?.kind === "leave" ? t("wsMgmt.leaveBody")
            : pending?.kind === "archive" ? t("wsMgmt.archiveBody")
            : t("wsMgmt.deleteBody")}
        </p>
        {(pending?.kind === "transfer" || pending?.kind === "delete") && (
          <div className="mt-3 grid gap-1">
            <label htmlFor={`${ids}-confirm`} className="text-xs font-semibold">{t("wsMgmt.confirmNameLabel")}</label>
            <Input id={`${ids}-confirm`} value={typedName} autoComplete="off" onChange={(e) => setTypedName(e.target.value)} />
          </div>
        )}
      </ConfirmDialog>
    </section>
  );
}

/** Share one of YOUR items into the workspace. Needs the explicit consent checkbox; VIEW-only. */
function ShareItemForm({ workspaceId, disabled, onShared, onError }: {
  workspaceId: number; disabled: boolean; onShared: () => Promise<void> | void; onError: (e: unknown) => void;
}) {
  const { t } = useI18n();
  const ids = useId();
  const [type, setType] = useState<"story" | "interview_report">("story");
  const [items, setItems] = useState<Array<{ id: string; label: string }>>([]);
  const [loaded, setLoaded] = useState(false);
  const [itemId, setItemId] = useState("");
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let live = true;
    setLoaded(false);
    setItemId("");
    const load = loadShareableItems(type, api);
    load.then((rows) => { if (live) { setItems(rows); setLoaded(true); } })
      .catch(() => { if (live) { setItems([]); setLoaded(true); } });
    return () => { live = false; };
  }, [type]);

  const submit = async () => {
    if (!itemId || !consent) return;
    setSending(true);
    try {
      await api.shares.create(workspaceId, type, itemId, true);
      setConsent(false);
      setItemId("");
      await onShared();
    } catch (e) {
      onError(e);
    } finally {
      setSending(false);
    }
  };

  return (
    <Card><CardBody className="grid gap-2">
      <h3 className="text-sm font-semibold">{t("wsMgmt.shareTitle")}</h3>
      <div className="flex flex-wrap items-end gap-2">
        <div className="grid gap-1">
          <label htmlFor={`${ids}-type`} className="text-xs font-semibold">{t("wsMgmt.shareType")}</label>
          <select id={`${ids}-type`} className={selectCls} value={type} onChange={(e) => setType(e.target.value as "story" | "interview_report")}>
            <option value="story">{t("wsMgmt.typeStory")}</option>
            <option value="interview_report">{t("wsMgmt.typeReport")}</option>
          </select>
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${ids}-item`} className="text-xs font-semibold">{t("wsMgmt.shareItem")}</label>
          <select id={`${ids}-item`} className={selectCls} value={itemId} disabled={items.length === 0} onChange={(e) => setItemId(e.target.value)}>
            <option value="" />
            {items.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}
          </select>
        </div>
      </div>
      {loaded && items.length === 0 && <p className="text-sm text-muted">{t("wsMgmt.shareNoItems")}</p>}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>{t("wsMgmt.shareConsent")}</span>
      </label>
      <div><Button disabled={disabled || sending || !itemId || !consent} onClick={() => void submit()}>{t("wsMgmt.shareAction")}</Button></div>
    </CardBody></Card>
  );
}
