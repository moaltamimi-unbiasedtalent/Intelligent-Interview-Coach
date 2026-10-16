"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { StatusChip } from "@/components/plan/StatusChip";
import { api } from "@/lib/api/client";
import type { UsageQuotaFeature, UsageQuotasResponse } from "@/lib/api/types";

/**
 * Usage-allowance presentation (W12.4D-P4-A) over GET /usage-quotas. It renders ONLY what the server reports about the caller's own account: while commercial
 * quota enforcement is disabled the server returns `enforcement_active: false` and this component renders NOTHING (no allowance is ever invented, shown or
 * implied). A feature without an approved allowance is shown as not set up, never with a number. No upgrade prompt, price or checkout link exists here, and
 * the component holds no plan-to-allowance rule: it cannot grant or compute anything.
 */
const NAME: Record<string, string> = { practice_session: "quotaUx.f_practice_session", career_ai: "quotaUx.f_career_ai" };
const STATUS: Record<UsageQuotaFeature["status"], { key: string; chip: "available" | "planned" | "pending" | "unavailable" }> = {
  available: { key: "quotaUx.st_available", chip: "available" },
  exhausted: { key: "quotaUx.st_exhausted", chip: "pending" },
  not_configured: { key: "quotaUx.st_not_configured", chip: "planned" },
  unavailable: { key: "quotaUx.st_unavailable", chip: "unavailable" },
};
const PERIOD: Record<string, string> = { hour: "quotaUx.per_hour", day: "quotaUx.per_day", month: "quotaUx.per_month" };

export function UsageQuotaPanel() {
  const { t, formatDate, formatNumber } = useI18n();
  const [data, setData] = useState<UsageQuotasResponse | null>(null);
  useEffect(() => {
    let live = true;
    api.usageQuotas.get().then((r) => { if (live && r && Array.isArray(r.features)) setData(r); }).catch(() => { /* non-critical: nothing is shown */ });
    return () => { live = false; };
  }, []);
  if (!data || !data.enforcement_active) return null;
  const rows = data.features.filter((f) => NAME[f.feature] && STATUS[f.status]);
  if (!rows.length) return null;
  return (
    <Card>
      <CardBody className="space-y-3" data-testid="usage-quotas">
        <h2 className="text-base font-semibold text-foreground">{t("quotaUx.title")}</h2>
        <p className="text-sm text-muted">{t("quotaUx.lead")}</p>
        <ul className="grid gap-2">
          {rows.map((f) => {
            const known = f.status === "available" || f.status === "exhausted";
            return (
              <li key={f.feature} className="rounded-lg border border-border bg-surface p-3" data-feature={f.feature} data-status={f.status}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-foreground">{t(NAME[f.feature])}</p>
                  <StatusChip status={STATUS[f.status].chip} label={t(STATUS[f.status].key)} />
                </div>
                {known && typeof f.allowance === "number" && typeof f.used === "number" ? (
                  <p className="mt-1 text-sm text-muted">
                    {t("quotaUx.used")}: {formatNumber(f.used)} / {formatNumber(f.allowance)}{f.period && PERIOD[f.period] ? ` ${t(PERIOD[f.period])}` : ""}
                    {" · "}{t("quotaUx.remaining")}: {formatNumber(f.remaining ?? 0)}
                    {f.reset_at ? ` · ${t("quotaUx.resets")}: ${formatDate(f.reset_at, { dateStyle: "medium", timeStyle: "short" })}` : ""}
                  </p>
                ) : f.status === "not_configured" ? (
                  <p className="mt-1 text-sm text-muted">{t("quotaUx.notConfigured")}</p>
                ) : null}
                {f.status === "exhausted" ? <p className="mt-1 text-sm text-muted">{t("quotaUx.exhaustedNote")}</p> : null}
              </li>
            );
          })}
        </ul>
      </CardBody>
    </Card>
  );
}
