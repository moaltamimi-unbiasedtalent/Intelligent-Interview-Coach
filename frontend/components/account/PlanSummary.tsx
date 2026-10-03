"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { PlanResponse } from "@/lib/api/types";

/**
 * The candidate's OWN plan, read from the server (never derived from a client-side tier). Premium is a preview:
 * there is no purchase, price, upgrade or payment surface here, and the copy says so. What is "included" is
 * exactly the server-resolved entitlement state; the frontend holds no plan-to-entitlement map.
 */
export function PlanSummary() {
  const t = useT();
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    api.auth.plan().then((p) => (p && p.entitlements ? setPlan(p) : setFailed(true))).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  if (failed) return <ErrorState variant="section" message={t("plan.loadError")} onRetry={load} retryLabel={t("plan.retry")} />;
  if (!plan) return <LoadingState label={t("plan.loading")} />;

  const name = plan.plan_code === "premium" ? t("plan.namePremium") : plan.plan_code === "basic" ? t("plan.nameBasic") : plan.plan_code;
  return (
    <Card>
      <CardBody className="space-y-3" data-testid="plan-summary">
        <h2 className="text-base font-semibold text-foreground">{t("plan.title")}</h2>
        <p className="text-lg font-semibold text-foreground">{name}</p>
        <h3 className="text-sm font-semibold text-foreground">{t("plan.entitlementsTitle")}</h3>
        <ul className="grid gap-1 text-sm">
          {Object.entries(plan.entitlements).map(([key, state]) => (
            <li key={key} className="flex items-center justify-between gap-3">
              <span>{t(`plan.ent_${key}`)}</span>
              <span className="font-medium">{state.enabled ? t("plan.included") : t("plan.notIncluded")}</span>
            </li>
          ))}
        </ul>
        {plan.plan_code === "premium" || !plan.entitlements.premium_preview?.enabled ? (
          <p className="text-sm text-muted">{t("plan.previewNotice")}</p>
        ) : null}
        <p className="text-xs text-muted">{t("plan.noPayments")}</p>
      </CardBody>
    </Card>
  );
}
