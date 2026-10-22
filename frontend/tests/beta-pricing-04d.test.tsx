import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import { PRICING_PLANS } from "@/lib/pricing";

/**
 * 04D (CJ-D-02, I-D02): ONE wording about price and purchase across every candidate surface. Ask4Mo is a free, invitation-only private beta: nothing can be purchased and no price applies.
 * This test FAILS on drift: a surface that renders its own pricing sentence, a currency figure or a purchase claim in any locale of the effective catalogue, or a surface whose statement
 * differs from the single `betaPricing.statement`.
 */

vi.mock("next/image", () => ({ default: (p: Record<string, unknown>) => <img alt={String(p.alt)} src={String(p.src)} /> }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/ui/VerifiedLink", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/components/auth/AuthProvider", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/auth/AuthProvider")>();
  return { ...actual, useAuthOptional: () => ({ status: "unauthenticated", account: null, responseDetail: "brief" }), useAuth: () => ({ status: "unauthenticated", account: null }) };
});

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { MarketingHome } from "@/components/marketing/MarketingHome";
import { PricingContent } from "@/components/marketing/PricingContent";
import { TermsContent } from "@/components/marketing/TermsContent";
import { RegisterForm } from "@/components/auth/RegisterForm";

const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

type Catalog = Record<string, Record<string, string>>;
// A currency figure ($12, 12 EUR, 12,5 €) is a price. Words like "free" or "per month" alone are not.
const CURRENCY_FIGURE = /(?:[€$£]\s?\d)|(?:\d[\d.,]*\s?(?:€|£|\$|EUR|USD|GBP)\b)/i;
// Competitor prices are comparison evidence about OTHER providers (dated, original currencies), not an Ask4Mo price. Admin namespaces are English-only operator surfaces, not candidate surfaces.
const EXEMPT = (ns: string, key: string) => (ns === "pricingV4" && key.startsWith("benchmark")) || ns.startsWith("admin");
// Phrases that would claim a purchase path or an Ask4Mo subscription price.
const PURCHASE_CLAIM = /\b(buy now|subscribe now|purchase(?:d)? (?:securely|online)|upgrade now|checkout now|choose premium|per month for premium|for [€$£]\s?\d)\b/i;

describe("one pricing wording: the catalogue", () => {
  it.each(SUPPORTED_LOCALE_CODES)("%s: the single beta statement exists and states no figure", (locale) => {
    const statement = translate(locale as AppLocale, "betaPricing.statement");
    expect(statement && statement !== "betaPricing.statement").toBe(true);
    expect(statement).not.toMatch(CURRENCY_FIGURE);
    expect(translate(locale as AppLocale, "betaPricing.freeInBeta")).not.toMatch(CURRENCY_FIGURE);
  });

  it.each(SUPPORTED_LOCALE_CODES)("%s: no candidate-facing string in the effective catalogue states a currency figure", (locale) => {
    const catalog = CATALOGS[locale as AppLocale] as unknown as Catalog;
    const offenders: string[] = [];
    for (const [ns, entries] of Object.entries(catalog)) {
      for (const [key, value] of Object.entries(entries)) {
        if (typeof value !== "string" || EXEMPT(ns, key)) continue;
        if (CURRENCY_FIGURE.test(value)) offenders.push(`${ns}.${key}: ${value.slice(0, 80)}`);
      }
    }
    expect(offenders, "price figures in candidate copy (state the beta in betaPricing.statement instead)").toEqual([]);
  });

  it("no English candidate string claims a purchase path or an Ask4Mo subscription price", () => {
    const catalog = CATALOGS.en as unknown as Catalog;
    const offenders: string[] = [];
    for (const [ns, entries] of Object.entries(catalog)) {
      for (const [key, value] of Object.entries(entries)) {
        if (typeof value === "string" && !EXEMPT(ns, key) && PURCHASE_CLAIM.test(value)) offenders.push(`${ns}.${key}: ${value.slice(0, 80)}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the plan model carries no price field and no plan is purchasable", () => {
    for (const plan of PRICING_PLANS) {
      expect(Object.keys(plan).some((k) => /price|cadence|currency|amount/i.test(k))).toBe(false);
      expect(plan.purchasable).toBe(false);
    }
  });
});

describe("one pricing wording: every candidate surface renders THE statement", () => {
  const surfaces: Array<[string, () => React.ReactElement, string]> = [
    ["home", () => <MarketingHome />, "home-beta-pricing"],
    ["footer", () => <MarketingShell><p>x</p></MarketingShell>, "footer-beta-pricing"],
    ["pricing page", () => <PricingContent />, "pricing-billing-note"],
    ["terms", () => <TermsContent />, "terms-beta-pricing"],
    ["registration", () => <RegisterForm />, "register-beta-pricing"],
  ];

  it.each(surfaces)("%s", (_name, ui, testId) => {
    for (const locale of ["en", "de", "ru"] as AppLocale[]) {
      const { unmount } = wrap(ui(), locale);
      const statement = translate(locale, "betaPricing.statement");
      expect(screen.getAllByTestId(testId)[0].textContent).toBe(statement);
      unmount();
    }
  });

  it("the pricing page states no price anywhere and offers no purchase path", () => {
    const { container } = wrap(<PricingContent />);
    const text = container.textContent ?? "";
    // The competitor benchmark table is dated comparison evidence about other providers; everything else on the page must be free of figures.
    const plans = screen.getByTestId("pricing-plans").textContent ?? "";
    expect(plans).not.toMatch(CURRENCY_FIGURE);
    expect(screen.getByTestId("premium-beta-statement").textContent).toBe(translate("en", "betaPricing.statement"));
    expect(container.querySelector('a[href*="checkout"], a[href*="plan=premium"], form[action*="checkout"]')).toBeNull();
    expect(text).toContain(translate("en", "betaPricing.freeInBeta"));
  });
});
