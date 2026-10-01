"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api/client";
import { ApiError, stateKeyForError } from "@/lib/api/errors";
import { config } from "@/lib/config";
import type {
  DocumentSummary,
  MemoryResponse,
  Opportunity,
  ShareGrantOut,
  WorkspaceSummary,
} from "@/lib/api/types";
import { useAuth } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useResource } from "@/lib/hooks/useResource";
import type { ResourceView } from "@/lib/hooks/useResource";

/**
 * Data & Privacy Center (P10B-W9.8). One calm, self-service page over the existing owner-scoped APIs.
 *
 * Every section loads independently, so one failing request degrades only its own region (section-tier
 * ErrorState with a safe GET retry) and never blanks the page. Destructive writes always go through an
 * accessible ConfirmDialog (default focus on Cancel) and are never auto-retried. Wording follows backend
 * truth: Delete = removed now, Archive = hidden but kept, Revoke = future access stops.
 */

type HistoryRow = Record<string, unknown>;

type Pending =
  | { kind: "deleteOpportunity" | "archiveOpportunity"; id: number; name: string }
  | { kind: "deleteDocument"; id: number; name: string }
  | { kind: "deleteMemory"; id: number; name: string }
  | { kind: "deleteInterview"; id: number; name: string }
  | { kind: "revokeShare"; id: number; name: string; workspace: string };

function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`${id}-h`} data-testid={`dp-${id}`} className="space-y-3">
      <div>
        <h2 id={`${id}-h`} className="text-lg font-semibold text-foreground">{title}</h2>
        {intro ? <p className="mt-1 max-w-reading text-sm text-muted">{intro}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function DataPrivacyCenter() {
  const t = useT();
  const router = useRouter();
  const { account, status, refresh } = useAuth();

  const opps = useResource((signal) => api.opportunities.list(true, { signal }).then((r) => r.opportunities as Opportunity[]));
  const docs = useResource((signal) => api.documents.list({ signal }).then((r) => r.documents as DocumentSummary[]));
  const mems = useResource((signal) => api.memory.list(undefined, { signal }).then((r) => r.memories as MemoryResponse[]));
  const ints = useResource((signal) => api.history.list({ signal }).then((r) => r.interviews as HistoryRow[]));
  const shares = useResource((signal) => api.shares.mine({ signal }).then((r) => r.shares as ShareGrantOut[]));
  const spaces = useResource((signal) => api.workspaces.list({ signal }).then((r) => r.workspaces as WorkspaceSummary[]));

  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);

  const errText = (e: ApiError | null) => (e ? t(stateKeyForError(e.kind)) : t("dataPrivacy.actionFailed"));

  const close = () => {
    if (busy) return;
    setPending(null);
    setAccountOpen(false);
    setDialogError(null);
  };

  const workspaceName = (id: number) =>
    spaces.state.data?.find((w) => w.id === id)?.name ?? t("dataPrivacy.workspaceFallback", { id });

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    setDialogError(null);
    try {
      switch (pending.kind) {
        case "deleteOpportunity":
          await api.opportunities.remove(pending.id);
          opps.update((d) => d.filter((o) => o.id !== pending.id));
          break;
        case "archiveOpportunity": {
          const updated = await api.opportunities.archive(pending.id);
          opps.update((d) => d.map((o) => (o.id === pending.id ? { ...o, ...updated } : o)));
          break;
        }
        case "deleteDocument":
          await api.documents.remove(pending.id);
          docs.update((d) => d.filter((x) => x.id !== pending.id));
          break;
        case "deleteMemory":
          await api.memory.remove(pending.id);
          mems.update((d) => d.filter((m) => m.id !== pending.id));
          break;
        case "deleteInterview":
          await api.history.remove(pending.id);
          ints.update((d) => d.filter((i) => Number(i.id) !== pending.id));
          break;
        case "revokeShare":
          await api.shares.revoke(pending.id);
          shares.update((d) => d.filter((s) => s.id !== pending.id));
          break;
      }
      setPending(null);
      setNotice(t("dataPrivacy.removed"));
    } catch (e) {
      // A 404 means it was already gone (e.g. removed in another tab): reflect that and close quietly.
      if (e instanceof ApiError && e.status === 404) {
        setPending(null);
        setNotice(t("dataPrivacy.removed"));
        opps.reload();
        docs.reload();
        mems.reload();
        ints.reload();
        shares.reload();
      } else {
        setDialogError(e instanceof ApiError ? errText(e) : t("dataPrivacy.actionFailed"));
      }
    } finally {
      setBusy(false);
    }
  };

  const deleteAccount = async () => {
    setBusy(true);
    setDialogError(null);
    try {
      await api.auth.deleteAccount();
      await refresh();
      router.replace("/sign-in");
    } catch {
      setDialogError(t("dataPrivacy.accountDeleteFailed"));
      setBusy(false);
    }
  };

  if (status === "loading") return <LoadingState label={t("account.loadingAccount")} />;
  if (!account) return <p className="text-sm text-muted">{t("account.notSignedIn")}</p>;

  const count = (r: ResourceView) => (r.state.data ? r.state.data.length : null);
  const activeOppCount = opps.state.data?.length ?? null;

  const cards: Array<{ id: string; label: string; desc: string; n: number | null; error: boolean }> = [
    { id: "opps", label: t("dataPrivacy.cardOpportunities"), desc: t("dataPrivacy.cardOpportunitiesDesc"), n: activeOppCount, error: opps.state.status === "error" },
    { id: "docs", label: t("dataPrivacy.cardDocuments"), desc: t("dataPrivacy.cardDocumentsDesc"), n: count(docs), error: docs.state.status === "error" },
    { id: "mems", label: t("dataPrivacy.cardMemories"), desc: t("dataPrivacy.cardMemoriesDesc"), n: count(mems), error: mems.state.status === "error" },
    { id: "ints", label: t("dataPrivacy.cardInterviews"), desc: t("dataPrivacy.cardInterviewsDesc"), n: count(ints), error: ints.state.status === "error" },
    { id: "shares", label: t("dataPrivacy.cardShares"), desc: t("dataPrivacy.cardSharesDesc"), n: count(shares), error: shares.state.status === "error" },
    { id: "spaces", label: t("dataPrivacy.cardWorkspaces"), desc: t("dataPrivacy.cardWorkspacesDesc"), n: count(spaces), error: spaces.state.status === "error" },
  ];

  const list = (
    r: ResourceView,
    render: (items: readonly unknown[]) => ReactNode,
    emptyKey = "dataPrivacy.manageEmpty",
  ) => {
    if (r.state.status === "loading") return <LoadingState />;
    if (r.state.status === "error")
      return (
        <ErrorState
          variant="section"
          message={errText(r.state.error)}
          requestId={r.state.error?.requestId}
          retrying={r.state.retrying}
          onRetry={r.reload}
        />
      );
    if (!r.state.data || r.state.data.length === 0) return <p className="text-sm text-muted">{t(emptyKey)}</p>;
    return render(r.state.data);
  };

  const row = (key: string | number, label: string, extra: ReactNode, actions: ReactNode) => (
    <li key={key} className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-2 last:border-0">
      <span className="min-w-0 flex-1 text-sm text-foreground [overflow-wrap:anywhere]">
        {label} {extra}
      </span>
      <span className="flex flex-wrap gap-2">{actions}</span>
    </li>
  );

  const untitled = t("dataPrivacy.itemUntitled");
  const dialogCopy = (() => {
    if (!pending) return null;
    const name = pending.name || untitled;
    switch (pending.kind) {
      case "deleteOpportunity":
        return { title: t("dataPrivacy.confirmDeleteOpportunityTitle"), body: t("dataPrivacy.confirmDeleteOpportunityBody", { name }), label: t("dataPrivacy.confirmDelete") };
      case "archiveOpportunity":
        return { title: t("dataPrivacy.confirmArchiveOpportunityTitle"), body: t("dataPrivacy.confirmArchiveOpportunityBody", { name }), label: t("dataPrivacy.confirmArchive") };
      case "deleteDocument":
        return { title: t("dataPrivacy.confirmDeleteDocumentTitle"), body: t("dataPrivacy.confirmDeleteDocumentBody", { name }), label: t("dataPrivacy.confirmDelete") };
      case "deleteMemory":
        return { title: t("dataPrivacy.confirmDeleteMemoryTitle"), body: t("dataPrivacy.confirmDeleteMemoryBody", { name }), label: t("dataPrivacy.confirmDelete") };
      case "deleteInterview":
        return { title: t("dataPrivacy.confirmDeleteInterviewTitle"), body: t("dataPrivacy.confirmDeleteInterviewBody", { name }), label: t("dataPrivacy.confirmDelete") };
      case "revokeShare":
        return { title: t("dataPrivacy.confirmRevokeTitle"), body: t("dataPrivacy.confirmRevokeBody", { workspace: pending.workspace }), label: t("dataPrivacy.confirmRevoke") };
    }
  })();

  const del = (label: string, onClick: () => void) => (
    <Button variant="ghost" size="sm" onClick={onClick} aria-label={`${t("dataPrivacy.deleteAction")}: ${label}`}>
      {t("dataPrivacy.deleteAction")}
    </Button>
  );

  const exportUrl = `${config.apiBaseUrl}/auth/account/export`;
  const included = ["incAccount", "incOpportunities", "incDocuments", "incStories", "incMemories", "incInterviews", "incFeedback", "incSharing"];
  const excluded = ["excFiles", "excAudit", "excOthers", "excInternal", "excLegal"];
  const retention = ["retentionActive", "retentionDelete", "retentionSecurity", "retentionProviders"];
  const accountDeleted = ["accDelOpportunities", "accDelDocuments", "accDelMemories", "accDelInterviews", "accDelSharing", "accDelAccount"];
  const linkCls = "inline-flex min-h-[44px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2";

  const dialogOpen = (pending !== null && dialogCopy !== null) || accountOpen;

  return (
    <>
    {/* While a dialog is open the page behind it is inert: not focusable and hidden from assistive tech. */}
    <div className="mx-auto w-full max-w-[760px] space-y-10 py-2" data-testid="data-privacy-center" inert={dialogOpen}>
      <div>
        <Link href="/account" className="text-sm text-accent hover:underline">{t("dataPrivacy.backToAccount")}</Link>
        <div className="mt-2">
          <PageHeader eyebrow={t("dataPrivacy.eyebrow")} title={t("dataPrivacy.title")} description={t("dataPrivacy.description")} />
        </div>
        {notice ? (
          <p role="status" className="rounded border border-border bg-surface-2 px-3 py-2 text-sm text-foreground">{notice}</p>
        ) : null}
      </div>

      <Section id="overview" title={t("dataPrivacy.overviewTitle")} intro={t("dataPrivacy.overviewIntro")}>
        <ul className="grid gap-3 sm:grid-cols-2" aria-label={t("dataPrivacy.overviewTitle")}>
          {cards.map((c) => (
            <li key={c.id}>
              <Card className="h-full">
                <CardBody className="space-y-1">
                  <p className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-semibold text-foreground">{c.label}</span>
                    <span className="text-lg font-semibold text-foreground" data-testid={`dp-count-${c.id}`}>
                      {c.error ? "-" : c.n === null ? "…" : c.n}
                    </span>
                  </p>
                  <p className="text-xs text-muted">{c.desc}</p>
                </CardBody>
              </Card>
            </li>
          ))}
          <li className="sm:col-span-2">
            <Card>
              <CardBody className="space-y-1">
                <p className="text-sm font-semibold text-foreground">{t("dataPrivacy.cardAccount")}</p>
                <p className="text-xs text-muted">{t("dataPrivacy.cardAccountDesc")}</p>
              </CardBody>
            </Card>
          </li>
        </ul>
      </Section>

      <Section id="export" title={t("dataPrivacy.exportTitle")} intro={t("dataPrivacy.exportIntro")}>
        <a href={exportUrl} download="ask4mo-my-data.json" className={linkCls} data-testid="dp-export-link">
          {t("dataPrivacy.exportButton")}
        </a>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.exportIncluded")}</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted">
              {included.map((k) => <li key={k}>{t(`dataPrivacy.${k}`)}</li>)}
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.exportExcluded")}</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted">
              {excluded.map((k) => <li key={k}>{t(`dataPrivacy.${k}`)}</li>)}
            </ul>
          </div>
        </div>
      </Section>

      <Section id="manage" title={t("dataPrivacy.manageTitle")} intro={t("dataPrivacy.manageIntro")}>
        <Card><CardBody className="space-y-2" data-testid="dp-manage-opportunities">
          <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.cardOpportunities")}</h3>
          <p className="text-xs text-muted">{t("dataPrivacy.oppNote")}</p>
          {list(opps, (all) => (
            <ul>
              {(all as Opportunity[]).map((o) =>
                row(
                  o.id, o.title || untitled,
                  o.status === "archived" ? <Badge>{t("dataPrivacy.archivedBadge")}</Badge> : null,
                  <>
                    {o.status !== "archived" ? (
                      <Button variant="ghost" size="sm" aria-label={`${t("dataPrivacy.archiveAction")}: ${o.title}`}
                        onClick={() => setPending({ kind: "archiveOpportunity", id: o.id, name: o.title })}>
                        {t("dataPrivacy.archiveAction")}
                      </Button>
                    ) : null}
                    {del(o.title, () => setPending({ kind: "deleteOpportunity", id: o.id, name: o.title }))}
                  </>,
                ),
              )}
            </ul>
          ))}
        </CardBody></Card>

        <Card><CardBody className="space-y-2" data-testid="dp-manage-documents">
          <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.cardDocuments")}</h3>
          <p className="text-xs text-muted">{t("dataPrivacy.docNote")}</p>
          {list(docs, (all) => (
            <ul>
              {(all as DocumentSummary[]).map((d) =>
                row(d.id, d.title || untitled, null,
                  del(d.title, () => setPending({ kind: "deleteDocument", id: d.id, name: d.title }))),
              )}
            </ul>
          ))}
        </CardBody></Card>

        <Card><CardBody className="space-y-2" data-testid="dp-manage-memories">
          <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.cardMemories")}</h3>
          <p className="text-xs text-muted">{t("dataPrivacy.memNote")}</p>
          {list(mems, (all) => (
            <ul>
              {(all as MemoryResponse[]).map((m) =>
                row(m.id, m.summary, null,
                  del(m.summary, () => setPending({ kind: "deleteMemory", id: m.id, name: m.summary }))),
              )}
            </ul>
          ))}
        </CardBody></Card>

        <Card><CardBody className="space-y-2" data-testid="dp-manage-interviews">
          <h3 className="text-sm font-semibold text-foreground">{t("dataPrivacy.cardInterviews")}</h3>
          <p className="text-xs text-muted">{t("dataPrivacy.intNote")}</p>
          {list(ints, (all) => (
            <ul>
              {(all as HistoryRow[]).map((i) => {
                const role = String(i.target_role ?? "") || t("dataPrivacy.itemInterview");
                const when = typeof i.created_at === "string" ? i.created_at.slice(0, 10) : "";
                const label = when ? `${role} (${when})` : role;
                return row(Number(i.id), label, null,
                  del(label, () => setPending({ kind: "deleteInterview", id: Number(i.id), name: label })));
              })}
            </ul>
          ))}
        </CardBody></Card>

        <p className="text-xs text-muted">{t("dataPrivacy.chatNote")}</p>
        <p className="text-xs text-muted">{t("dataPrivacy.feedbackNote")}</p>
      </Section>

      <Section id="sharing" title={t("dataPrivacy.sharingTitle")} intro={t("dataPrivacy.sharingIntro")}>
        {list(shares, (all) => (
          <ul>
            {(all as ShareGrantOut[]).map((s) => {
              const kind = s.resource_type === "interview_report" ? t("dataPrivacy.sharedReport")
                : s.resource_type === "story" ? t("dataPrivacy.sharedStory") : t("dataPrivacy.sharedItem");
              const ws = workspaceName(s.workspace_id);
              return row(s.id, `${kind} #${s.resource_id}`, <span className="text-muted">{t("dataPrivacy.sharedWith", { workspace: ws })}</span>,
                <Button variant="ghost" size="sm" aria-label={`${t("dataPrivacy.revokeAction")}: ${kind} #${s.resource_id}`}
                  onClick={() => setPending({ kind: "revokeShare", id: s.id, name: kind, workspace: ws })}>
                  {t("dataPrivacy.revokeAction")}
                </Button>);
            })}
          </ul>
        ), "dataPrivacy.sharingEmpty")}
        <Link href="/workspaces" className={linkCls}>{t("dataPrivacy.manageWorkspaces")}</Link>
      </Section>

      <Section id="retention" title={t("dataPrivacy.retentionTitle")} intro={t("dataPrivacy.retentionIntro")}>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {retention.map((k) => <li key={k}>{t(`dataPrivacy.${k}`)}</li>)}
        </ul>
      </Section>

      <Section id="legal" title={t("dataPrivacy.legalTitle")} intro={t("dataPrivacy.legalIntro")}>
        <div className="flex flex-wrap gap-2">
          <Link href="/terms" className={linkCls}>{t("dataPrivacy.legalTerms")}</Link>
          <Link href="/privacy" className={linkCls}>{t("dataPrivacy.legalPrivacy")}</Link>
          <Link href="/ai-transparency" className={linkCls}>{t("dataPrivacy.legalAi")}</Link>
        </div>
        <p className="text-sm text-muted">{t("dataPrivacy.legalNotRecorded")}</p>
        <p className="text-xs text-muted">{t("dataPrivacy.legalReview")}</p>
      </Section>

      <Section id="account" title={t("dataPrivacy.accountZoneTitle")}>
        <Card className="border-danger">
          <CardBody className="space-y-3">
            <p className="text-sm text-muted">{t("dataPrivacy.accountZoneBody")}</p>
            <Button variant="ghost" onClick={() => { setDialogError(null); setAccountOpen(true); }} data-testid="dp-delete-account">
              {t("dataPrivacy.accountZoneButton")}
            </Button>
          </CardBody>
        </Card>
      </Section>

    </div>
      <ConfirmDialog
        open={pending !== null && dialogCopy !== null}
        title={dialogCopy?.title ?? ""}
        confirmLabel={dialogCopy?.label ?? ""}
        busy={busy}
        error={dialogError}
        onConfirm={confirm}
        onCancel={close}
        testId="dp-confirm"
      >
        <p>{dialogCopy?.body}</p>
      </ConfirmDialog>

      <ConfirmDialog
        open={accountOpen}
        title={t("dataPrivacy.accountConfirmTitle")}
        confirmLabel={t("dataPrivacy.accountConfirmDelete")}
        cancelLabel={t("dataPrivacy.accountConfirmKeep")}
        busy={busy}
        error={dialogError}
        onConfirm={deleteAccount}
        onCancel={close}
        testId="dp-account-confirm"
      >
        <p>{t("dataPrivacy.accountConfirmIntro")}</p>
        <ul className="list-disc space-y-1 pl-5">
          {accountDeleted.map((k) => <li key={k}>{t(`dataPrivacy.${k}`)}</li>)}
        </ul>
        <p>{t("dataPrivacy.accountConfirmKept")}</p>
        <a href={exportUrl} download="ask4mo-my-data.json" className="text-accent underline">
          {t("dataPrivacy.accountConfirmExport")}
        </a>
      </ConfirmDialog>
    </>
  );
}
