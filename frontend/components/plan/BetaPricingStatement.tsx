"use client";

import { useT } from "@/components/i18n/I18nProvider";

/**
 * THE one statement about price and purchase on every candidate surface (04D, CJ-D-02 / I-D02).
 *
 * Ask4Mo is a free, invitation-only private beta: nothing can be purchased and no price applies. Before this, the pricing page, the home page and the footer each carried their
 * own wording, and some said "Premium is EUR 19.99 per month" while the account view said Premium was a preview with nothing to buy. Every surface now renders THIS component (one
 * catalogue key, `betaPricing.statement`, in all eight locales), so the wording cannot drift between surfaces; `frontend/tests/beta-pricing-04d.test.tsx` fails if a candidate surface
 * states a price, a purchase path or its own competing pricing sentence.
 */
export function BetaPricingStatement({ className, testId = "beta-pricing-statement" }: { className?: string; testId?: string }) {
  const t = useT();
  return <p className={className} data-testid={testId}>{t("betaPricing.statement")}</p>;
}
