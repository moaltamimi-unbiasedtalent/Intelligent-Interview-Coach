import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";

/** P10B-W9.10 - public positioning copy: allowed claims render, prohibited claims and named competitors never do. */

vi.mock("next/image", () => ({ default: (p: Record<string, unknown>) => <span data-img={String(p.alt)} /> }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));

import { MarketingHome } from "@/components/marketing/MarketingHome";
import { ProductContent } from "@/components/marketing/ProductContent";

const t = (k: string) => translate("en", k);
const PROHIBITED = /gdpr[- ]compliant|100\s?%\s*(secure|private)|completely private|enterprise-grade|bias-free|fully unbiased|all answers (are )?verified|human[- ]reviewed|guarantee|best interview coach|better than|more accurate than|revolutionary|game-changing|cutting-edge|supercharge|unlock your potential/i;
const COMPETITORS = /chatgpt|openai|gemini|copilot|claude|final round|big interview|yoodli|huru|linkedin/i;

describe("public positioning copy", () => {
  it("home renders the Opportunity-centred story and the corrected claims", () => {
    const { container } = render(<MarketingHome />);
    const text = container.textContent ?? "";
    expect(text).toContain(t("marketing.heroTitle"));
    expect(text).toContain(t("marketing.whyTitle"));
    expect(t("marketing.whyTitle")).toBe("What makes Ask4Mo different");
    expect(text).toContain(t("marketing.why2Body"));
    expect(text).toContain(t("marketing.ctaBody"));
    expect(t("marketing.ctaBody")).not.toMatch(/upgrade/i); // Premium is a preview, not a purchase path
    expect(t("marketing.featurePrepareBody")).toMatch(/when career evidence is used/);
  });

  it("no prohibited claim and no named competitor appears on the public product pages (all 8 locales' marketing copy too)", () => {
    for (const C of [MarketingHome, ProductContent]) {
      const { container, unmount } = render(<C />);
      expect(container.textContent).not.toMatch(PROHIBITED);
      expect(container.textContent).not.toMatch(COMPETITORS);
      unmount();
    }
    const keys = ["heroTitle", "heroSubtitle", "featurePrepareBody", "featurePracticeBody", "howStep4Body", "howStep5Body", "whyTitle", "why1Body", "why2Body", "why3Body", "why4Body", "ctaBody"];
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const v = translate(locale, `marketing.${k}`);
        expect(v, `${locale}.${k}`).not.toBe(`marketing.${k}`);
        expect(v, `${locale}.${k}`).not.toMatch(PROHIBITED);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
      }
      expect(translate(locale, "common.tagline")).toBe(BRAND_SLOGAN);
    }
  });

  it("changed claims are translated (not left in English) in every other locale", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      if (locale === "en") continue;
      for (const k of ["featurePrepareBody", "featurePracticeBody", "whyTitle", "ctaBody"]) {
        expect(translate(locale, `marketing.${k}`), `${locale}.${k}`).not.toBe(t(`marketing.${k}`));
      }
    }
  });

  it("keeps Trust and Data & privacy reachable from public copy", () => {
    const { container } = render(<ProductContent />);
    expect(container.querySelector('a[href="/register"], a[href="/trust"], a[href="/pricing"]')).not.toBeNull();
  });
});
