// Centralized pricing/product-plan configuration (Capstone P8 §6/§7).
//
// Pricing PRESENTATION only — there is NO billing, checkout, card storage or subscription
// charging anywhere in this product (that is explicitly out of scope). Values are the current
// product hypothesis and are easy to change in one place. Premium is a PREVIEW: the CTA
// requests access, it never claims a purchase path.
//
// Annual pricing is intentionally omitted until the product owner explicitly approves a value
// (the ~€199/year figure remains an internal hypothesis, not a public commitment).

export type PlanId = "basic" | "premium";

export interface PricingPlan {
  id: PlanId;
  /** i18n keys (rendered via useT) — never hard-coded display strings. */
  nameKey: string;
  priceDisplay: string; // a currency figure is data, not translated copy
  cadenceKey: string;
  ctaKey: string;
  includesKey: string;
  noteKey?: string;
  featured?: boolean;
  /** Truthful CTA: 'register' (a real free path) or 'request' (preview, no purchase). */
  ctaKind: "register" | "request";
  ctaHref: string;
}

export const PRICING_CURRENCY = "EUR";

export const PRICING_PLANS: PricingPlan[] = [
  {
    id: "basic",
    nameKey: "marketing.planBasicName",
    priceDisplay: "€0",
    cadenceKey: "marketing.planBasicCadence",
    ctaKey: "marketing.planBasicCta",
    includesKey: "marketing.pricingBasicIncludes",
    ctaKind: "register",
    ctaHref: "/register",
  },
  {
    id: "premium",
    nameKey: "marketing.planPremiumName",
    priceDisplay: "€19.99",
    cadenceKey: "marketing.planPremiumCadence",
    ctaKey: "marketing.planPremiumCta",
    includesKey: "marketing.pricingPremiumIncludes",
    noteKey: "marketing.planPremiumNote",
    featured: true,
    // Premium cannot be purchased online (no billing) — the CTA is a truthful preview request
    // that routes to registration (Basic), where the account can later be upgraded by an
    // operator. It NEVER implies checkout.
    ctaKind: "request",
    ctaHref: "/register?plan=premium-preview",
  },
];

/** There is no billing in this product. Public copy must reflect this. */
export const BILLING_ENABLED = false;
