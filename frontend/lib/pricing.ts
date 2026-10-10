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

/**
 * "Available today" table (v4). Mirrors the AUTHORITATIVE backend plan definitions (`src/entitlements.py`
 * DEFAULT_PLANS) key for key; `tests/test_pricing_truth_v4.py` fails if the two ever disagree. Only entitlement keys the
 * server enforces appear here. Nothing about limits (one Opportunity, three sessions, Fast only) is listed because the
 * server has no such entitlement: those ideas live in CONSIDERATION_ROWS and are labelled "under consideration".
 */
export interface AvailableTodayRow {
  /** Backend entitlement key. */
  key: "current_market_research" | "standard_history" | "standard_progress" | "standard_model_profiles" | "premium_preview";
  labelKey: string;
  basic: boolean;
  premium: boolean;
  /** Premium preview is not purchasable; render it as "preview only" rather than "included". */
  preview?: boolean;
}

export const AVAILABLE_TODAY: AvailableTodayRow[] = [
  { key: "current_market_research", labelKey: "pricingV4.rowResearch", basic: true, premium: true },
  { key: "standard_history", labelKey: "pricingV4.rowHistory", basic: true, premium: true },
  { key: "standard_progress", labelKey: "pricingV4.rowProgress", basic: true, premium: true },
  { key: "standard_model_profiles", labelKey: "pricingV4.rowModels", basic: true, premium: true },
  { key: "premium_preview", labelKey: "pricingV4.rowPremiumPreview", basic: false, premium: true, preview: true },
];

/** Proposed package ideas: NOT enforced by the backend, NOT a commitment, shown only under a visible "under consideration" label. */
export const CONSIDERATION_ROWS: string[] = [
  "pricingV4.consider1", "pricingV4.consider2", "pricingV4.consider3", "pricingV4.consider4", "pricingV4.consider5",
  "pricingV4.consider6", "pricingV4.consider7", "pricingV4.consider8", "pricingV4.consider9", "pricingV4.consider10",
];

/** Coaching-format comparison rows: [row label key, ask4mo key, coach key, course key] (neutral trade-offs). */
export const COACHING_COMPARISON: [string, string, string, string][] = [
  ["pricingV4.rowPayment", "pricingV4.payAsk4mo", "pricingV4.payCoach", "pricingV4.payCourse"],
  ["pricingV4.rowAvailability", "pricingV4.availAsk4mo", "pricingV4.availCoach", "pricingV4.availCourse"],
  ["pricingV4.rowContext", "pricingV4.ctxAsk4mo", "pricingV4.ctxCoach", "pricingV4.ctxCourse"],
  ["pricingV4.rowRepetition", "pricingV4.repAsk4mo", "pricingV4.repCoach", "pricingV4.repCourse"],
  ["pricingV4.rowFeedback", "pricingV4.fbAsk4mo", "pricingV4.fbCoach", "pricingV4.fbCourse"],
  ["pricingV4.rowBestUse", "pricingV4.useAsk4mo", "pricingV4.useCoach", "pricingV4.useCourse"],
  ["pricingV4.rowLimit", "pricingV4.limAsk4mo", "pricingV4.limCoach", "pricingV4.limCourse"],
];

/**
 * Dated public-price benchmark (reviewed 9 October 2026). Indicative examples, NOT a formal average. Prices stay in their
 * original currencies: nothing is converted and no percentage saving is computed anywhere.
 */
export const PRICE_BENCHMARK_REVIEWED = "2026-10-09";
export const PRICE_BENCHMARK: { provider: string; url: string; price: string; note: string }[] = [
  { provider: "BPW Akademie, Germany", url: "https://www.bpw-akademie.de/interview-coaching", price: "€250 plus VAT for about 2.5 hours", note: "About €100/hour before VAT" },
  { provider: "Fluent in Tech", url: "https://www.fluentintechcoaching.com/pricing/", price: "€750 for five 60-75 minute sessions", note: "€150/session" },
  { provider: "Cloud Ninja Tech, Germany", url: "https://cloudninjatech.digital/pricing/", price: "€210 for a 75-minute mock interview", note: "About €168/hour equivalent" },
  { provider: "HappyHire, UK", url: "https://www.wearehappyhire.com/answers/interview-coaching-guide", price: "£60/hour", note: "Its guide states roughly £50-£150/hour" },
  { provider: "DW Performance Consulting, UK", url: "https://www.dw-performanceconsulting.com/interview-coaching-services", price: "£120 for 60 minutes", note: "£100-£110/session in blocks" },
  { provider: "Elite Careers Coach, UK", url: "https://www.elitecareerscoach.co.uk/pricing", price: "£125 for a 60-minute mock interview", note: "2026-27 introductory price" },
  { provider: "Ali Waters Associates, UK", url: "https://www.aliwatersassociates.co.uk/InterviewCoaching/Fees.php", price: "£155-£195/hour by career stage", note: "Lower rates for multiple sessions" },
  { provider: "Anson Reed, UK", url: "https://www.ansonreed.com/pricing.html", price: "£275 for 1.5 hours; £350 for two hours", note: "About £175-£183/hour equivalent" },
  { provider: "Bloor Engineering, UK", url: "https://bloorengineering.com/coaching", price: "£200 for a 60-minute session", note: "Role-specific mock and written debrief" },
  { provider: "IGotAnOffer, US", url: "https://igotanoffer.com/en/interview-coaching", price: "Two to five credits per one-hour session; about $50 per credit", note: "Roughly $100-$250/hour before volume discounts" },
  { provider: "The Muse, US", url: "https://www.themuse.com/gift-of-coaching", price: "$155 Mentor, $329 Coach, $659 Master Coach", note: "Package tiers, not hourly equivalents" },
];
