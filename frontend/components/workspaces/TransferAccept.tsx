"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { OwnershipTransferPreview } from "@/lib/api/types";
import { formerRoleKey } from "./OwnershipTransfer";

type View =
  | { s: "loading" }
  | { s: "missing" }
  | { s: "ready"; preview: OwnershipTransferPreview }
  | { s: "problem"; key: string; signIn?: boolean }
  | { s: "done"; workspaceId: number }
  | { s: "declined" };

/** Why a preview or an answer failed, as a localized key. 403 = verify first or a different account; 404/409 = gone. A malformed answer is a generic error, never a success. */
function problemFor(e: unknown): { key: string; signIn?: boolean } {
  if (e instanceof ApiError) {
    if (e.status === 401 || e.kind === "unauthenticated") return { key: "wsTransfer.acceptSignIn", signIn: true };
    if (e.status === 403) return { key: /verify/i.test(e.message) ? "wsTransfer.acceptVerifyFirst" : "wsTransfer.acceptWrongAccount" };
    if (e.status === 404 || e.status === 409) return { key: "wsTransfer.acceptGone" };
    if (e.kind === "offline") return { key: "states.offline" };
    if (e.kind === "unreachable") return { key: "states.serviceUnreachable" };
  }
  return { key: "wsMgmt.errGeneric" };
}

/**
 * The page the ownership-transfer email links to. It shows the proposal (workspace, who proposed it, what changes) to the bound, verified account only and lets the
 * person ACCEPT or DECLINE explicitly. Opening the link changes nothing. The one-time token is sent only in request bodies, never as a query string to the API.
 */
export function TransferAccept() {
  const { t, formatDate } = useI18n();
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<View>({ s: "loading" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("token");
    if (!raw) { setView({ s: "missing" }); return; }
    setToken(raw);
    let live = true;
    api.workspaces
      .previewTransfer(raw)
      .then((preview) => { if (live) setView({ s: "ready", preview }); })
      .catch((e) => { if (live) setView({ s: "problem", ...problemFor(e) }); });
    return () => { live = false; };
  }, []);

  const accept = async () => {
    if (!token || view.s !== "ready") return;
    setBusy(true);
    try {
      const ws = await api.workspaces.acceptTransfer(token);
      setView({ s: "done", workspaceId: ws.id });
    } catch (e) {
      setView({ s: "problem", ...problemFor(e) });
    } finally {
      setBusy(false);
    }
  };

  const decline = async () => {
    if (view.s !== "ready") return;
    setBusy(true);
    try {
      await api.workspaces.declineTransfer(view.preview.id);
      setView({ s: "declined" });
    } catch (e) {
      setView({ s: "problem", ...problemFor(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section>
      <PageHeader eyebrow={t("workspaces.eyebrow")} title={t("wsTransfer.acceptPageTitle")} description={t("wsTransfer.acceptIntro")} />
      {view.s === "loading" && <p className="text-sm text-muted" role="status">{t("states.loading")}…</p>}
      {view.s === "missing" && <Alert tone="warning">{t("wsTransfer.acceptMissingToken")}</Alert>}
      {view.s === "problem" && (
        <div className="grid gap-3">
          <Alert tone="warning">{t(view.key)}</Alert>
          {view.signIn && <p><Link href="/sign-in" className="text-sm font-semibold text-accent hover:underline">{t("common.signIn")}</Link></p>}
        </div>
      )}
      {view.s === "ready" && (
        <Card>
          <CardBody className="grid gap-3">
            <dl className="grid gap-1 text-sm">
              <div className="flex gap-2"><dt className="font-semibold">{t("wsTransfer.acceptWorkspace")}</dt><dd>{view.preview.workspace_name}</dd></div>
              <div className="flex gap-2"><dt className="font-semibold">{t("wsTransfer.acceptFrom")}</dt><dd>{view.preview.counterpart_label}</dd></div>
              {view.preview.expires_at && (
                <div><dd className="text-muted">{t("wsMgmt.invitedExpires", { date: formatDate(view.preview.expires_at, { dateStyle: "medium" }) })}</dd></div>
              )}
            </dl>
            <ul className="list-disc pl-5 text-sm text-muted">
              <li>{t("wsTransfer.acceptYouBecome")}</li>
              <li>{t("wsTransfer.acceptFormerRole", { role: t(formerRoleKey(view.preview.former_owner_role)) })}</li>
              <li>{t("wsTransfer.acceptSharesNote")}</li>
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy} onClick={() => void accept()}>{t("wsTransfer.acceptButton")}</Button>
              <Button variant="ghost" disabled={busy} onClick={() => void decline()}>{t("wsTransfer.acceptDeclineButton")}</Button>
            </div>
          </CardBody>
        </Card>
      )}
      {view.s === "done" && (
        <div className="grid gap-3">
          <Alert tone="success">{t("wsTransfer.acceptDone")}</Alert>
          <div><ButtonLink href={`/workspaces/${view.workspaceId}`}>{t("wsTransfer.openWorkspace")}</ButtonLink></div>
        </div>
      )}
      {view.s === "declined" && (
        <div className="grid gap-3">
          <Alert tone="info">{t("wsTransfer.acceptDeclinedDone")}</Alert>
          <div><ButtonLink href="/workspaces" variant="ghost">{t("wsMgmt.backToList")}</ButtonLink></div>
        </div>
      )}
    </section>
  );
}
