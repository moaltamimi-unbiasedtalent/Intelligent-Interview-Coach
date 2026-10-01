import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { BRAND_SLOGAN } from "@/lib/brand";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";

/**
 * P10B-W9.7A - the ACTUAL authenticated Home (`app/app/page.tsx`) in all 8 locales.
 * The four feature blocks were a hardcoded English tuple array in the server page (invisible to the
 * original scanner), so they stayed English under every other interface language. These tests render the
 * real page component, not catalogue values.
 */

const oppList = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { ...actual.api, opportunities: { list: (...a: unknown[]) => oppList(...a) } } };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/app",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/auth/AuthProvider", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/auth/AuthProvider")>();
  return { ...actual, useAuthOptional: () => ({ status: "authenticated", account: null, responseDetail: "brief" }) };
});

import AppHomePage from "@/app/app/page";
import { I18nProvider } from "@/components/i18n/I18nProvider";

const EN_FEATURES = [
  "Prepare with evidence", "Grounded career information and citations when needed.",
  "Practise with purpose", "Tailored questions based on the role and your preparation context.",
  "Stay in control", "Memory and important handoffs require clear approval.",
  "Improve over time", "Structured feedback, progress and reusable preparation context.",
];
const KEYS = ["feat1", "feat2", "feat3", "feat4"] as const;

beforeEach(() => oppList.mockResolvedValue({ opportunities: [] }));
afterEach(() => vi.clearAllMocks());

function renderHome(locale: AppLocale) {
  return render(
    <I18nProvider initialLocale={locale}>
      <AppHomePage />
    </I18nProvider>,
  );
}

describe("authenticated Home feature blocks + Opportunity action, all 8 locales (real component)", () => {
  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: four localized feature headings + descriptions, labelled CTA, no raw keys, slogan exact`, async () => {
      const { container } = renderHome(locale);
      const blocks = screen.getByTestId("home-feature-blocks");
      for (const k of KEYS) {
        expect(blocks).toHaveTextContent(translate(locale, `home.${k}Title`));
        expect(blocks).toHaveTextContent(translate(locale, `home.${k}Body`));
      }
      if (locale !== "en") {
        // Not one of the original English strings may remain visible.
        for (const s of EN_FEATURES) expect(container.textContent ?? "").not.toContain(s);
        for (const k of KEYS) expect(translate(locale, `home.${k}Title`)).not.toBe(translate("en", `home.${k}Title`));
      }
      // Opportunity action: resolved, visible, labelled (never a blank rectangle).
      const cta = await screen.findByRole("link", { name: translate(locale, "home.opportunityCreate") });
      expect(cta).toHaveAttribute("href", "/opportunities?create=1");
      expect((cta.textContent ?? "").trim().length).toBeGreaterThan(0);
      expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument();
      // No raw translation key anywhere on the page.
      const text = container.textContent ?? "";
      const cat = CATALOGS.en as unknown as Record<string, Record<string, string>>;
      const leaked = Object.keys(cat).flatMap((ns) => Object.keys(cat[ns]).map((k) => `${ns}.${k}`)).filter((full) => text.includes(full));
      expect(leaked, "raw translation keys rendered").toEqual([]);
      // Protected slogan: exactly English in every locale.
      expect(screen.getByText(BRAND_SLOGAN)).toBeInTheDocument();
    });
  }

  it("returning user (existing opportunities): localized primary View action", async () => {
    oppList.mockResolvedValue({ opportunities: [{ id: 1 }] });
    renderHome("ru");
    const view = await screen.findByRole("link", { name: translate("ru", "home.opportunityView") });
    expect(view).toHaveAttribute("href", "/opportunities");
    await waitFor(() => expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument());
  });
});
