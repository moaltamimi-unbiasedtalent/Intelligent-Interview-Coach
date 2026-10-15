"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { BillingSummaryView } from "@/lib/api/types";

/**
 * The candidate's OWN billing overview (W12.4D-E). Every word comes from the server's verified local state: a checkout redirect, a session id or an unverified
 * event never reaches this screen. Payment, subscription and access are shown as separate facts. Subscription management, cancellation, payment method and
 * billing-address changes, receipts and invoices belong to Link (the seller of record): this screen explains where, never invents a Link URL, and shows no invoice.
 */
const date = (iso: string | null, locale?: string) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" });
};

export function BillingOverview() {
  const t = useT();
  const [data, setData] = useState<BillingSummaryView | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    api.billing.summary().then((s) => (s && s.state ? setData(s) : setFailed(true))).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  if (failed) {
    return (
      <Card><CardBody className="space-y-3" data-testid="billing-overview">
        <h2 className="text-base font-semibold text-foreground">{t("billing.title")}</h2>
        <Alert tone="warning">{t("billing.loadError")}</Alert>
        <Button variant="ghost" onClick={load}>{t("billing.retry")}</Button>
      </CardBody></Card>
    );
  }
  if (!data) return <LoadingState label={t("billing.title")} />;

  const paid = data.state !== "free" && data.state !== "checkout_pending";
  const period = date(data.current_period_end);
  const ends = date(data.cancellation_effective_at);
  const tone = data.state === "past_due" || data.state === "disputed" ? "warning" : "info";
  return (
    <Card>
      <CardBody className="space-y-3" data-testid="billing-overview">
        <h2 className="text-base font-semibold text-foreground">{t("billing.title")}</h2>
        <div data-testid={`billing-state-${data.state}`}>
          <Alert tone={tone} title={t(`billing.state_${data.state}`)}>{t(`billing.body_${data.state}`)}</Alert>
        </div>
        <dl className="grid gap-1 text-sm">
          <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblPlan")}</dt><dd className="font-medium">{data.entitlement.plan_code === "premium" ? t("plan.namePremium") : t("plan.nameBasic")}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblSubscription")}</dt><dd className="font-medium">{t(`billing.dim_${data.subscription}`)}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblPayment")}</dt><dd className="font-medium">{t(`billing.dim_${data.payment}`)}</dd></div>
          {paid && data.interval ? <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblInterval")}</dt><dd className="font-medium">{data.interval === "year" ? t("billing.intervalYear") : t("billing.intervalMonth")}</dd></div> : null}
          {paid && period ? <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblPeriodEnd")}</dt><dd className="font-medium">{period}</dd></div> : null}
          {ends ? <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblEndsOn")}</dt><dd className="font-medium">{ends}</dd></div> : null}
          {paid && data.verified_at ? <div className="flex justify-between gap-3"><dt className="text-muted">{t("billing.lblVerified")}</dt><dd className="font-medium">{date(data.verified_at)}</dd></div> : null}
        </dl>
        <p className="text-sm"><span className="text-muted">{t("billing.lblAccess")}: </span><span className="font-medium">{data.entitlement.changed_by_billing ? t("billing.accessByBilling") : t("billing.accessNotByBilling")}</span></p>
        {paid ? (
          <div className="space-y-1 text-sm" data-testid="billing-management">
            <h3 className="font-semibold text-foreground">{t("billing.manageTitle")}</h3>
            <p className="text-muted">{t("billing.manageBody")}</p>
            <p className="text-muted">{t("billing.receiptsBody")}</p>
          </div>
        ) : null}
        {data.timeline.length ? (
          <div className="space-y-1 text-sm" data-testid="billing-timeline">
            <h3 className="font-semibold text-foreground">{t("billing.timelineTitle")}</h3>
            <ul className="space-y-0.5 text-muted">{data.timeline.map((e, i) => <li key={i}>{date(e.at) ?? t("billing.notAvailable")}: {t(`billing.tl_${e.kind}`)}</li>)}</ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
