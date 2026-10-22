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
import type { InvitationPreview } from "@/lib/api/types";
import { roleKey } from "./workspaceUi";

type View =
  | { s: "loading" }
  | { s: "missing" }
  | { s: "ready"; preview: InvitationPreview }
  | { s: "problem"; key: string; signIn?: boolean }
  | { s: "joined" }
  | { s: "declined" };

/** Why a preview/answer failed, as a localized key. The server uses 403 for "verify first" and "different address", 404/409 for gone. */
function problemFor(e: unknown): { key: string; signIn?: boolean } {
  if (e instanceof ApiError) {
    if (e.status === 401 || e.kind === "unauthenticated") return { key: "wsMgmt.acceptSignIn", signIn: true };
    if (e.status === 403) return { key: /verify/i.test(e.message) ? "wsMgmt.acceptVerifyFirst" : "wsMgmt.acceptWrongAccount" };
    if (e.status === 404 || e.status === 409) return { key: "wsMgmt.acceptGone" };
    if (e.kind === "offline") return { key: "states.offline" };
    if (e.kind === "unreachable") return { key: "states.serviceUnreachable" };
  }
  return { key: "wsMgmt.errGeneric" };
}

/**
 * The page an invitation email links to. It shows the invitation (workspace, role, expiry) to the invited, verified account only and
 * lets the person ACCEPT or DECLINE explicitly. Nothing happens by opening the link. The token travels only in this request body.
 */
export function InviteAccept() {
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
      .previewInvitation(raw)
      .then((preview) => { if (live) setView({ s: "ready", preview }); })
      .catch((e) => { if (live) setView({ s: "problem", ...problemFor(e) }); });
    return () => { live = false; };
  }, []);

  const answer = async (accept: boolean) => {
    if (!token) return;
    setBusy(true);
    try {
      if (accept) await api.workspaces.accept(token);
      else await api.workspaces.decline(token);
      setView({ s: accept ? "joined" : "declined" });
    } catch (e) {
      setView({ s: "problem", ...problemFor(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section>
      <PageHeader eyebrow={t("workspaces.eyebrow")} title={t("wsMgmt.acceptTitle")} description={t("wsMgmt.acceptIntro")} />
      {view.s === "loading" && <p className="text-sm text-muted" role="status">{t("states.loading")}…</p>}
      {view.s === "missing" && <Alert tone="warning">{t("wsMgmt.acceptMissingToken")}</Alert>}
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
              <div className="flex gap-2"><dt className="font-semibold">{t("wsMgmt.acceptWorkspace")}</dt><dd>{view.preview.workspace_name}</dd></div>
              <div className="flex gap-2"><dt className="font-semibold">{t("wsMgmt.acceptRoleOffered")}</dt><dd>{t(roleKey(view.preview.role))}</dd></div>
              {view.preview.expires_at && (
                <div><dd className="text-muted">{t("wsMgmt.invitedExpires", { date: formatDate(view.preview.expires_at, { dateStyle: "medium" }) })}</dd></div>
              )}
            </dl>
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy} onClick={() => void answer(true)}>{t("wsMgmt.acceptButton")}</Button>
              <Button variant="ghost" disabled={busy} onClick={() => void answer(false)}>{t("wsMgmt.declineButton")}</Button>
            </div>
          </CardBody>
        </Card>
      )}
      {view.s === "joined" && (
        <div className="grid gap-3">
          <Alert tone="success">{t("wsMgmt.acceptDone")}</Alert>
          <div><ButtonLink href="/workspaces">{t("wsMgmt.openWorkspaceAfter")}</ButtonLink></div>
        </div>
      )}
      {view.s === "declined" && (
        <div className="grid gap-3">
          <Alert tone="info">{t("wsMgmt.acceptDeclined")}</Alert>
          <div><ButtonLink href="/workspaces" variant="ghost">{t("wsMgmt.backToList")}</ButtonLink></div>
        </div>
      )}
    </section>
  );
}
