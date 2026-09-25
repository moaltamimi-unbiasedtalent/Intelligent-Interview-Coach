"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { PRICING_PLANS } from "@/lib/pricing";

// Pricing PRESENTATION only (Capstone P8 §6/§7). No checkout, no card fields, no "Buy now".
// Premium's CTA is a truthful preview request (there is no online purchase path).
export function PricingContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-16">
      <h1 className="text-center text-3xl font-bold md:text-4xl">{t("marketing.pricingTitle")}</h1>
      <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("marketing.pricingSubtitle")}</p>

      <div className="mx-auto mt-10 grid max-w-3xl gap-6 md:grid-cols-2">
        {PRICING_PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`rounded-lg border p-6 ${plan.featured ? "border-accent shadow-soft" : "border-border"} bg-surface`}
            data-testid={`plan-${plan.id}`}
          >
            <h2 className="text-lg font-semibold">{t(plan.nameKey)}</h2>
            <p className="mt-2">
              <span className="text-3xl font-bold">{plan.priceDisplay}</span>{" "}
              <span className="text-sm text-muted">{t(plan.cadenceKey)}</span>
            </p>
            <p className="mt-3 text-sm text-muted">{t(plan.includesKey)}</p>
            <div className="mt-5">
              {/* Truthful CTA: Basic registers (a real free path); Premium requests a preview. */}
              <ButtonLink href={plan.ctaHref} variant={plan.featured ? "primary" : "ghost"}>
                {t(plan.ctaKey)}
              </ButtonLink>
            </div>
            {plan.noteKey ? (
              <p className="mt-3 text-xs text-muted" data-testid={`plan-note-${plan.id}`}>
                {t(plan.noteKey)}
              </p>
            ) : null}
          </div>
        ))}
      </div>

      <p className="mx-auto mt-8 max-w-2xl text-center text-sm text-foreground">
        {t("marketing.pricingAlwaysFree")}
      </p>
      <p className="mx-auto mt-2 max-w-2xl text-center text-xs text-muted" data-testid="no-billing-note">
        {t("marketing.pricingBillingNote")}
      </p>
    </div>
  );
}
