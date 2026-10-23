"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { EmptyStateIllustration } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { MyWorkspaces, OwnershipTransfer, ShareGrantOut } from "@/lib/api/types";
import { TransferBanner } from "./OwnershipTransfer";
import { SharedItemViewer } from "./SharedItemViewer";
import { resourceTypeKey, roleKey, workspaceErrorKey } from "./workspaceUi";

type Notice = { tone: "success" | "danger"; text: string } | null;

export function WorkspacesPanel() {
  const { t, formatDate } = useI18n();
  const nameId = useId();
  const [data, setData] = useState<MyWorkspaces | null>(null);
  const [sharedByMe, setSharedByMe] = useState<ShareGrantOut[]>([]);
  const [sharedWithMe, setSharedWithMe] = useState<ShareGrantOut[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [viewing, setViewing] = useState<ShareGrantOut | null>(null);
  const [transfers, setTransfers] = useState<OwnershipTransfer[]>([]);
  const [transfersFailed, setTransfersFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [ws, mine, withMe] = await Promise.all([
        api.workspaces.list(),
        api.shares.mine(),
        api.shares.withMe(),
      ]);
      setData(ws);
      setSharedByMe(mine.shares);
      setSharedWithMe(withMe.shares);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
    // Pending ownership transfers load on their own: a failure or a malformed answer is an explicit warning here, never a blank page and never a silent "none".
    try {
      setTransfers((await api.workspaces.transfersMine()).transfers);
      setTransfersFailed(false);
    } catch {
      setTransfersFailed(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Older invitation emails linked to /workspaces?token=...: send the person to the explicit accept page (never accept as a side effect of opening a link).
    const token = new URLSearchParams(window.location.search).get("token");
    if (token) window.location.replace(`/workspaces/accept?token=${encodeURIComponent(token)}`);
  }, [refresh]);

  const fail = (e: unknown) => setNotice({ tone: "danger", text: t(workspaceErrorKey(e)) });

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      await api.workspaces.create(name.trim());
      setName("");
      await refresh();
    } catch (e) {
      setNotice({ tone: "danger", text: `${t("wsMgmt.createFailed")} ${t(workspaceErrorKey(e))}` });
    } finally {
      setBusy(false);
    }
  };

  const answer = async (invId: number, accept: boolean) => {
    setBusy(true);
    setNotice(null);
    try {
      if (accept) await api.workspaces.acceptById(invId);
      else await api.workspaces.declineById(invId);
      setNotice({ tone: "success", text: t(accept ? "wsMgmt.joinedNotice" : "wsMgmt.declinedNotice") });
      await refresh();
    } catch {
      setNotice({ tone: "danger", text: t("wsMgmt.invitationFailed") });
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const answerTransfer = async (fn: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      setNotice({ tone: "success", text: success });
    } catch (e) {
      setNotice({ tone: "danger", text: t(workspaceErrorKey(e)) });
    } finally {
      await refresh();
      setBusy(false);
    }
  };

  const leave = async (id: number) => {
    setBusy(true);
    setNotice(null);
    try {
      await api.workspaces.leave(id);
      await refresh();
    } catch {
      setNotice({ tone: "danger", text: t("workspaces.leaveLastOwnerError") });
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (shareId: number) => {
    setBusy(true);
    setNotice(null);
    try {
      await api.shares.revoke(shareId);
      if (viewing?.id === shareId) setViewing(null);
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const header = (
    <PageHeader
      eyebrow={t("workspaces.eyebrow")}
      title={t("workspaces.title")}
      description={t("workspaces.subtitle")}
    />
  );

  if (status === "loading")
    return (
      <section>
        {header}
        <p className="text-sm text-muted" role="status">{t("states.loading")}…</p>
      </section>
    );
  if (status === "error")
    return (
      <section>
        {header}
        <p className="text-sm text-muted" role="alert">{t("states.genericError")}</p>
      </section>
    );

  const shareLabel = (s: ShareGrantOut) => `${t(resourceTypeKey(s.resource_type))} #${s.resource_id}`;

  return (
    <section>
      {header}
      <div className="grid gap-4">
      <Card>
        <CardBody className="grid gap-2">
          <p className="text-sm text-muted">{t("workspaces.privacyNote")}</p>
          <p className="text-xs text-muted">{t("workspaces.vsOpportunity")}</p>
          {notice && <Alert tone={notice.tone}>{notice.text}</Alert>}
          <div className="flex gap-2">
            <label htmlFor={nameId} className="sr-only">{t("workspaces.namePlaceholder")}</label>
            <Input
              id={nameId}
              className="flex-1"
              placeholder={t("workspaces.namePlaceholder")}
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !busy) void create(); }}
            />
            <Button onClick={create} disabled={busy || !name.trim()}>{t("workspaces.create")}</Button>
          </div>
        </CardBody>
      </Card>

      {transfersFailed && <Alert tone="warning">{t("wsTransfer.loadFailed")}</Alert>}
      {transfers.length > 0 && (
        <section className="grid gap-2" aria-labelledby="ws-xfer-h">
          <h2 id="ws-xfer-h" className="text-base font-semibold">{t("wsTransfer.listTitle")}</h2>
          {transfers.map((tr) => (
            <TransferBanner key={tr.id} transfer={tr} showWorkspace busy={busy}
              onCancel={() => void answerTransfer(() => api.workspaces.cancelTransfer(tr.workspace_id), t("wsTransfer.cancelledNotice"))}
              onDecline={() => void answerTransfer(() => api.workspaces.declineTransfer(tr.id), t("wsTransfer.declinedNotice"))} />
          ))}
        </section>
      )}

      {data && data.invited.length > 0 && (
        <section className="grid gap-2" aria-labelledby="ws-invited-h">
          <h2 id="ws-invited-h" className="text-base font-semibold">{t("workspaces.invited")}</h2>
          <p className="text-xs text-muted">{t("wsMgmt.invitedHint")}</p>
          {data.invited.map((inv) => (
            <Card key={inv.id}>
              <CardBody className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{inv.workspace_name ?? `#${inv.workspace_id}`}</p>
                  <p className="text-xs text-muted">
                    {t("wsMgmt.invitedRole", { role: t(roleKey(inv.role)) })}
                    {inv.expires_at ? ` · ${t("wsMgmt.invitedExpires", { date: formatDate(inv.expires_at, { dateStyle: "medium" }) })}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" disabled={busy} onClick={() => answer(inv.id, true)}
                    aria-label={`${t("workspaces.accept")}: ${inv.workspace_name ?? inv.workspace_id}`}>{t("workspaces.accept")}</Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => answer(inv.id, false)}
                    aria-label={`${t("workspaces.decline")}: ${inv.workspace_name ?? inv.workspace_id}`}>{t("workspaces.decline")}</Button>
                </div>
              </CardBody>
            </Card>
          ))}
        </section>
      )}

      <section className="grid gap-2" aria-labelledby="ws-mine-h">
        <h2 id="ws-mine-h" className="text-base font-semibold">{t("workspaces.myWorkspaces")}</h2>
        {data && data.workspaces.length === 0 && (
          <p className="text-sm text-muted">{t("workspaces.emptyWorkspaces")}</p>
        )}
        {data?.workspaces.map((w) => (
          <Card key={w.id}>
            <CardBody className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium">
                  <Link href={`/workspaces/${w.id}`} className="hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{w.name}</Link>
                  {w.status !== "active" && <> <Badge>{t("wsMgmt.archivedBadge")}</Badge></>}
                </p>
                <p className="text-xs text-muted">
                  {t(roleKey(w.my_role))}
                  {" · "}
                  {w.member_count} {t("workspaces.members")}
                </p>
              </div>
              <div className="flex gap-2">
                <Link href={`/workspaces/${w.id}`}
                  className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
                  aria-label={`${t("wsMgmt.openAction")}: ${w.name}`}>
                  {t("wsMgmt.openAction")}
                </Link>
                {w.my_role !== "workspace_owner" && (
                  <Button variant="ghost" size="sm" onClick={() => leave(w.id)} disabled={busy}
                    aria-label={`${t("workspaces.leave")}: ${w.name}`}>{t("workspaces.leave")}</Button>
                )}
              </div>
            </CardBody>
          </Card>
        ))}
      </section>

      {/* Wave 8 B0: a single sharing empty-state illustration, shown once only when BOTH sharing
          lists are empty. The two section headings and their empty messages are retained below. */}
      {sharedByMe.length === 0 && sharedWithMe.length === 0 && (
        <div className="flex justify-center">
          <EmptyStateIllustration
            src="/images/ask4mo/ask4mo-empty-workspaces-sharing-ink.png"
            alt={t("workspaces.sharingIllustrationAlt")}
          />
        </div>
      )}

      <section className="grid gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">{t("workspaces.sharedByMe")}</h2>
          {/* Pilot 2 (P2-01): one obvious route from Workspaces to the canonical sharing-management surface. */}
          <Link href="/account/data#sharing" data-testid="manage-sharing-link"
                className="text-sm font-semibold text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2">
            {t("workspaces.manageSharingLink")}
          </Link>
        </div>
        {sharedByMe.length === 0 && <p className="text-sm text-muted">{t("workspaces.emptyShares")}</p>}
        {sharedByMe.map((s) => (
          <Card key={s.id}>
            <CardBody className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm">{shareLabel(s)}</p>
                {s.workspace_name && <p className="text-xs text-muted">{s.workspace_name}</p>}
              </div>
              <Button variant="ghost" onClick={() => revoke(s.id)} disabled={busy}
                aria-label={`${t("workspaces.revoke")}: ${shareLabel(s)}`}>{t("workspaces.revoke")}</Button>
            </CardBody>
          </Card>
        ))}
      </section>

      <section className="grid gap-2">
        <h2 className="text-base font-semibold">{t("workspaces.sharedWithMe")}</h2>
        {sharedWithMe.length === 0 && <p className="text-sm text-muted">{t("workspaces.emptyShares")}</p>}
        {sharedWithMe.map((s) => (
          <Card key={s.id}>
            <CardBody className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm">{shareLabel(s)}</p>
                <p className="text-xs text-muted">
                  {s.workspace_name ? `${s.workspace_name} · ` : ""}{s.shared_by ? t("wsMgmt.sharedBy", { name: s.shared_by }) : ""}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setViewing(s)}
                aria-label={`${t("wsMgmt.viewShared")}: ${shareLabel(s)}`}>{t("wsMgmt.viewShared")}</Button>
            </CardBody>
          </Card>
        ))}
        {viewing && (
          <SharedItemViewer resourceType={viewing.resource_type} resourceId={viewing.resource_id}
            onClose={() => setViewing(null)} />
        )}
      </section>
      </div>
    </section>
  );
}
