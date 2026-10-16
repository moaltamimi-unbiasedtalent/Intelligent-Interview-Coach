"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { StatusChip } from "@/components/plan/StatusChip";
import { CAPABILITIES, STATUS_ORDER, capabilityLabelKey, statusKey, type CapabilityCell } from "@/lib/plan/capabilities";

/**
 * The owner-approved Basic and Premium overview (W12.4D-P3). Presentation only: it states what the plans are PLANNED to include and says, per cell, whether that is
 * available now, applies only once plans are active, is not built yet, or waits for commercial activation. It holds no plan state, grants nothing, shows no price and
 * has no purchase action. Laid out as a list of cards (not a wide table) so it never overflows a narrow screen.
 */
export function PlanOverview({ headingLevel = 2 }: { headingLevel?: 2 | 3 }) {
  const t = useT();
  const H = (headingLevel === 2 ? "h2" : "h3") as "h2" | "h3";
  const Sub = (headingLevel === 2 ? "h3" : "h4") as "h3" | "h4";
  const cell = (label: string, c: CapabilityCell) => (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 space-y-1.5 text-sm text-foreground">
        <p className="break-words">{t(c.textKey)}</p>
        {c.status !== "none" ? <StatusChip status={c.status} label={t(statusKey(c.status))} /> : null}
      </dd>
    </div>
  );
  return (
    <Card>
      <CardBody className="space-y-4" data-testid="plan-overview">
        <div>
          <H className="text-base font-semibold text-foreground">{t("planUx.title")}</H>
          <p className="mt-1 text-sm text-muted">{t("planUx.lead")}</p>
        </div>
        <section aria-labelledby="plan-legend">
          <Sub id="plan-legend" className="text-sm font-semibold text-foreground">{t("planUx.legendTitle")}</Sub>
          <ul className="mt-2 flex flex-wrap gap-2" data-testid="plan-legend">
            {STATUS_ORDER.map((s) => (
              <li key={s}><StatusChip status={s} label={t(statusKey(s))} /></li>
            ))}
          </ul>
        </section>
        <ul className="grid gap-3" data-testid="plan-capabilities">
          {CAPABILITIES.map((cap) => (
            <li key={cap.id} className="rounded-lg border border-border bg-surface p-3" data-capability={cap.id}>
              <Sub className="text-sm font-semibold text-foreground">{t(capabilityLabelKey(cap.id))}</Sub>
              <dl className="mt-2 grid gap-3 sm:grid-cols-2">
                {cell(t("planUx.colBasic"), cap.basic)}
                {cell(t("planUx.colPremium"), cap.premium)}
              </dl>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">{t("planUx.footnote")}</p>
      </CardBody>
    </Card>
  );
}
