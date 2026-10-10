"use client";

/**
 * Opportunity home / overview (P10B Wave 6).
 *
 * One place for a specific job: overview, Company Intelligence, Prepare, Practice, evidence and
 * linked reports, plus a single clear next step. Actions deep-link to the existing surfaces with
 * this opportunity's context (via `?opportunity=<id>`), so the candidate does not re-enter details.
 * Owner-scoped (a foreign id 404s server-side). All copy localized; no emoji, no em dash.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { OpportunityOverview, OpportunityStatus } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { OpportunityStatusBadge } from "@/components/opportunities/OpportunityStatusBadge";
import { JourneyRail } from "@/components/layout/JourneyRail";

const STATUSES: OpportunityStatus[] = ["active", "interviewing", "offer", "closed"];

export function OpportunityHome({ opportunityId }: { opportunityId: number }) {
  const { t } = useI18n();
  const router = useRouter();
  const [o, setO] = useState<OpportunityOverview | null>(null);
  const [error, setError] = useState<"notfound" | "load" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setO(await api.opportunities.get(opportunityId));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? "notfound" : "load");
    }
  }, [opportunityId]);

  useEffect(() => {
    void load();
  }, [load]);

  const setStatus = useCallback(async (status: OpportunityStatus) => {
    setBusy(true);
    try {
      await api.opportunities.update(opportunityId, { status });
      await load();
    } finally {
      setBusy(false);
    }
  }, [opportunityId, load]);

  const archive = useCallback(async () => {
    if (!window.confirm(t("opportunity.archiveConfirm"))) return;
    setBusy(true);
    try {
      await api.opportunities.archive(opportunityId);
      await load();
    } finally {
      setBusy(false);
    }
  }, [opportunityId, load, t]);

  const remove = useCallback(async () => {
    if (!window.confirm(t("opportunity.deleteConfirm"))) return;
    setBusy(true);
    try {
      await api.opportunities.remove(opportunityId);
      router.push("/opportunities");
    } catch {
      setBusy(false);
    }
  }, [opportunityId, router, t]);

  if (error === "notfound") {
    return (
      <section className="mx-auto max-w-content">
        <EmptyState title={t("opportunity.notFound")}
                    action={<Link href="/opportunities"><Button variant="ghost">{t("opportunity.navTitle")}</Button></Link>} />
      </section>
    );
  }
  if (error === "load") {
    return <section className="mx-auto max-w-content"><ErrorState message={t("opportunity.errorLoad")} onRetry={() => void load()} /></section>;
  }
  if (o === null) {
    return <section className="mx-auto max-w-content"><LoadingState label={t("opportunity.overview")} /></section>;
  }

  const q = `?opportunity=${o.id}`;
  // Deterministic best next step from EXISTING state only (JD link, interview count). No inference beyond that.
  const next = !o.job_description_document_id
    ? { body: t("journeyCues.nextAddJd"), cta: t("journeyCues.nextAddJdCta"), href: "/documents" }
    : o.interview_count === 0
      ? { body: t("journeyCues.nextPractice"), cta: t("journeyCues.nextPracticeCta"), href: `/practice${q}` }
      : { body: t("journeyCues.nextReview"), cta: t("journeyCues.nextReviewCta"), href: "/history" };

  return (
    <section className="mx-auto max-w-content space-y-5">
      <PageHeader title={o.title} description={o.target_role}
                  actions={<OpportunityStatusBadge status={o.status} />} />

      <JourneyRail opportunityId={o.id} />

      <Card>
        <CardBody className="flex flex-wrap items-center justify-between gap-3" data-testid="next-step">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("journeyCues.nextStepTitle")}</h2>
            <p className="mt-1 text-sm text-foreground">{next.body}</p>
          </div>
          <Link href={next.href} className="text-sm font-semibold text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2">{next.cta}</Link>
        </CardBody>
      </Card>

      {/* Overview */}
      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground">{t("opportunity.overview")}</h2>
          <dl className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
            <Row label={t("opportunity.role")} value={o.target_role} />
            {o.company_name ? <Row label={t("opportunity.company")} value={o.company_name} /> : null}
            {o.company_location ? <Row label={t("opportunity.location")} value={o.company_location} /> : null}
            {o.company_domain ? <Row label={t("opportunity.website")} value={o.company_domain} /> : null}
            <Row label={t("opportunity.jdStatus")}
                 value={o.job_description_document_id
                   ? (o.jd_available ? t("opportunity.jdLinked") : t("opportunity.jdUnavailable"))
                   : t("opportunity.jdNone")} />
          </dl>
          {/* Status quick-change (bounded; never colour-only). */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-sm text-muted">{t("opportunity.statusLabel")}:</span>
            {STATUSES.map((s) => (
              <button key={s} type="button" disabled={busy || o.status === s} onClick={() => void setStatus(s)}
                      className={`rounded border px-2 py-1 text-xs font-medium disabled:opacity-60 ${o.status === s ? "border-accent text-accent" : "border-border text-muted hover:bg-surface-2"}`}>
                {t(`opportunity.status${s.charAt(0).toUpperCase()}${s.slice(1)}`)}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Actions: Company Intelligence / Prepare / Practice */}
      <div className="grid gap-3 sm:grid-cols-2">
        <ActionCard title={t("opportunity.sectionCompany")} body={t("opportunity.sectionCompanyBody")}
                    href={`/company${q}`} cta={t("opportunity.researchCompany")} />
        <ActionCard title={t("opportunity.sectionPrepare")} body={t("opportunity.sectionPrepareBody")}
                    href={`/prepare${q}`} cta={t("opportunity.openPrepare")} />
        <ActionCard title={t("opportunity.sectionPractice")} body={t("opportunity.sectionPracticeBody")}
                    href={`/practice${q}`} cta={t("opportunity.startPractice")} />
        <ActionCard title={t("opportunity.sectionEvidence")} body={t("opportunity.sectionEvidenceBody")}
                    href="/documents" cta={t("opportunity.manageEvidence")} />
      </div>

      {/* Reports / history */}
      <Card>
        <CardBody className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">{t("opportunity.sectionReports")}</h2>
          <p className="text-sm text-muted">{t("opportunity.sectionReportsBody")}</p>
          <p className="text-sm text-foreground">
            {o.interview_count > 0
              ? t("opportunity.reportsCount", { n: o.interview_count })
              : t("opportunity.noReports")}
          </p>
          <Link href="/history" className="text-sm font-medium text-accent hover:underline">
            {t("opportunity.viewHistory")}
          </Link>
        </CardBody>
      </Card>

      {/* Lifecycle */}
      <div className="flex flex-wrap items-center gap-3">
        {o.status === "archived" ? (
          <Button variant="ghost" onClick={() => void setStatus("active")} disabled={busy}>{t("opportunity.unarchive")}</Button>
        ) : (
          <Button variant="ghost" onClick={archive} disabled={busy}>{t("opportunity.archive")}</Button>
        )}
        <Button variant="ghost" onClick={remove} disabled={busy}>{t("opportunity.delete")}</Button>
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted">{label}:</dt>
      <dd className="min-w-0 break-words text-foreground">{value}</dd>
    </div>
  );
}

function ActionCard({ title, body, href, cta }: { title: string; body: string; href: string; cta: string }) {
  return (
    <Card>
      <CardBody className="flex h-full flex-col gap-2">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="flex-1 text-sm text-muted">{body}</p>
        <Link href={href} className="text-sm font-semibold text-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2">
          {cta}
        </Link>
      </CardBody>
    </Card>
  );
}
