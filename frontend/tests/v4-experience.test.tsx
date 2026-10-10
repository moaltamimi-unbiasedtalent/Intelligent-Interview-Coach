import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import { BILLING_ENABLED, AVAILABLE_TODAY, PRICE_BENCHMARK, PRICING_PLANS } from "@/lib/pricing";
import { JOURNEY_STAGES } from "@/lib/journey";

/** Ask4Mo v4 experience: floating marketing navigation, Getting Started, static candidate story, workflow map, plan table truthfulness, journey cues. */

vi.mock("next/image", () => ({ default: (p: Record<string, unknown>) => <img alt={String(p.alt)} src={String(p.src)} data-testid="next-image" /> }));
vi.mock("next/link", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));
vi.mock("@/components/ui/VerifiedLink", () => ({ default: ({ href, children, ...r }: { href: string; children: React.ReactNode }) => <a href={href} {...r}>{children}</a> }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
const authState = { status: "unauthenticated" as "unauthenticated" | "authenticated" };
vi.mock("@/components/auth/AuthProvider", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/auth/AuthProvider")>();
  return { ...actual, useAuthOptional: () => ({ status: authState.status, account: null, responseDetail: "brief" }) };
});

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { MarketingShell, MARKETING_NAV } from "@/components/marketing/MarketingShell";
import { GettingStartedContent } from "@/components/marketing/GettingStartedContent";
import { CandidateStory } from "@/components/marketing/CandidateStory";
import { WorkflowMap } from "@/components/marketing/WorkflowMap";
import { PricingContent } from "@/components/marketing/PricingContent";
import { MarketingHome } from "@/components/marketing/MarketingHome";
import { JourneyRail } from "@/components/layout/JourneyRail";

const t = (k: string, l: AppLocale = "en") => translate(l, k);
const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

describe("floating marketing navigation", () => {
  it("keeps every current route plus How it works, the language control and the sign-in / CTA state", () => {
    authState.status = "unauthenticated";
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    const header = screen.getByTestId("marketing-header");
    for (const item of MARKETING_NAV) expect(within(header).getAllByRole("link", { name: t(item.key) }).length).toBeGreaterThan(0);
    const hrefs = MARKETING_NAV.map((n) => n.href);
    for (const h of ["/product", "/getting-started", "/pricing", "/trust", "/about", "/help"]) expect(hrefs).toContain(h);
    expect(within(header).getByRole("link", { name: t("marketing.getStarted") })).toHaveAttribute("href", "/register");
    expect(within(header).getByRole("link", { name: t("marketing.signIn") })).toHaveAttribute("href", "/sign-in");
  });

  it("shows the signed-in CTA instead of sign-in for an authenticated visitor", () => {
    authState.status = "authenticated";
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    expect(screen.getByRole("link", { name: t("marketing.goToApp") })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: t("marketing.signIn") })).toBeNull();
    authState.status = "unauthenticated";
  });

  it("has a skip link that is first in tab order and targets the main region", () => {
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    const skip = screen.getByRole("link", { name: t("v4nav.skipToContent") });
    expect(skip).toHaveAttribute("href", "#main");
    expect(skip.className).toMatch(/focus:not-sr-only/);
    expect(document.getElementById("main")).not.toBeNull();
  });

  it("floats 20px from the top, compacts (never hides) on scroll and honours reduced motion", () => {
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    const header = screen.getByTestId("marketing-header");
    expect(header.className).toMatch(/\bsticky\b/);
    expect(header.className).toMatch(/\bpt-5\b/); // 1.25rem = 20px float
    expect(header).toHaveAttribute("data-scrolled", "false");
    act(() => { Object.defineProperty(window, "scrollY", { value: 120, configurable: true }); window.dispatchEvent(new Event("scroll")); });
    expect(header).toHaveAttribute("data-scrolled", "true");
    expect(header.className).not.toMatch(/\bhidden\b|-translate-y-full/);
    expect(header.innerHTML).toMatch(/motion-reduce:transition-none/);
    act(() => { Object.defineProperty(window, "scrollY", { value: 0, configurable: true }); window.dispatchEvent(new Event("scroll")); });
  });

  it("offsets in-page anchors for the floating bar and restores it on unmount", () => {
    const { unmount } = wrap(<MarketingShell><p>body</p></MarketingShell>);
    expect(document.documentElement.style.scrollPaddingTop).toBe("7rem");
    unmount();
    expect(document.documentElement.style.scrollPaddingTop).toBe("");
  });

  it("mobile menu: toggles with aria-expanded, closes with Escape and returns focus, and traps Tab", () => {
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    const toggle = screen.getByRole("button", { name: t("v4nav.menuLabel") });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: t("marketing.navAriaMobile") })).toBeNull();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("navigation", { name: t("marketing.navAriaMobile") });
    const links = within(menu).getAllByRole("link");
    expect(links.length).toBeGreaterThanOrEqual(MARKETING_NAV.length);
    expect(document.activeElement).toBe(links[0]);
    // Focus order is toggle -> menu links. Shift+Tab from the toggle wraps to the last link; Tab from the last link wraps to the toggle.
    toggle.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(links[links.length - 1]);
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(toggle);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(toggle);
  });
});

describe("static candidate story", () => {
  it("renders still images only (no video), with meaningful alt text and the fictional/AI disclosure, in every locale", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const { container, unmount } = wrap(<CandidateStory />, locale);
      expect(container.querySelector("video")).toBeNull();
      const imgs = Array.from(container.querySelectorAll("img"));
      expect(imgs).toHaveLength(5);
      for (const img of imgs) {
        expect(img.getAttribute("alt")!.length, `${locale} alt`).toBeGreaterThan(20);
        expect(img.getAttribute("alt")).not.toMatch(/^gettingStarted\./);
        expect(img.getAttribute("src")).toMatch(/ask4mo-v4-candidate-story-.*\.png$/);
      }
      expect(screen.getByTestId("story-disclosure").textContent).toContain(t("gettingStarted.storyDisclosure", locale));
      unmount();
    }
    expect(t("gettingStarted.storyDisclosure")).toBe("Fictional candidate story. Imagery is AI-generated.");
    expect(t("gettingStarted.storyNotTestimonial")).toMatch(/does not describe a real person, a real customer or a job offer/);
  });

  it("labels the patterns and reflection scenes as product direction (not current functionality); the Home entry shows only the three current scenes", () => {
    const { container, unmount } = wrap(<CandidateStory />);
    const labelled = Array.from(container.querySelectorAll("li")).filter((li) => li.querySelector("[data-testid=direction-label]"));
    expect(labelled.map((l) => l.getAttribute("data-scene"))).toEqual(["patterns", "reflection"]);
    expect(container.textContent).toContain(t("gettingStarted.directionNote"));
    unmount();
    const home = wrap(<CandidateStory compact />);
    expect(home.container.querySelectorAll("img")).toHaveLength(3);
    expect(home.container.querySelector("[data-testid=direction-label]")).toBeNull();
  });

  it("never implies a job offer, a testimonial or a customer", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of ["sceneRejectionCaption", "scenePracticeCaption", "sceneReadyCaption", "scenePatternsCaption", "sceneReflectionCaption", "storyLead"]) {
        expect(t(`gettingStarted.${k}`, locale)).not.toMatch(/\b(offer|hired|got the job|testimonial|customer)\b/i);
      }
    }
  });
});

describe("Getting Started page", () => {
  it("has the required sections, the six steps, the 15-minute checklist and the Help / Trust / AI links", () => {
    const { container } = wrap(<GettingStartedContent />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("gettingStarted.title"));
    for (const id of ["story", "workflow", "steps", "first-15"]) expect(container.querySelector(`#${id}`)).not.toBeNull();
    expect(container.querySelectorAll("#steps ol > li")).toHaveLength(6);
    expect(container.querySelectorAll("#first-15 li")).toHaveLength(6);
    for (const href of ["/help", "/trust", "/ai-transparency"]) expect(container.querySelector(`a[href="${href}"]`)).not.toBeNull();
    expect(container.querySelector("video")).toBeNull();
  });

  it("is reachable from How it works without removing /product", () => {
    expect(MARKETING_NAV.find((n) => n.href === "/getting-started")).toBeTruthy();
    expect(MARKETING_NAV.find((n) => n.href === "/product")).toBeTruthy();
  });
});

describe("workflow map", () => {
  it("every node exposes what you do, what Ask4Mo contributes, what stays private and the next action", () => {
    wrap(<WorkflowMap />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(JOURNEY_STAGES.length);
    for (const [i, stage] of JOURNEY_STAGES.entries()) {
      fireEvent.click(tabs[i]);
      const panel = screen.getByRole("tabpanel");
      expect(tabs[i]).toHaveAttribute("aria-selected", "true");
      for (const k of ["Do", "Ask4mo", "Private", "Next"]) expect(panel.textContent).toContain(t(`workflow.${stage}${k}`));
      for (const k of ["factYouDo", "factAsk4mo", "factPrivate", "factNext"]) expect(panel.textContent).toContain(t(`gettingStarted.${k}`));
    }
  });

  it("supports arrow, Home and End keyboard selection with roving tabindex", () => {
    wrap(<WorkflowMap />);
    const tabs = screen.getAllByRole("tab");
    tabs[0].focus();
    expect(tabs[0]).toHaveAttribute("tabindex", "0");
    expect(tabs[1]).toHaveAttribute("tabindex", "-1");
    fireEvent.keyDown(tabs[0], { key: "ArrowRight" });
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(tabs[1]);
    fireEvent.keyDown(tabs[1], { key: "End" });
    expect(tabs[tabs.length - 1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(tabs[tabs.length - 1], { key: "ArrowRight" });
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(tabs[0], { key: "ArrowLeft" });
    expect(tabs[tabs.length - 1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(tabs[tabs.length - 1], { key: "Home" });
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  });

  it("uses the static SVG only as a no-script fallback", () => {
    const { container } = wrap(<WorkflowMap />);
    expect(container.querySelectorAll("noscript")).toHaveLength(1);
  });
});

describe("pricing truthfulness (v4)", () => {
  it("keeps billing off, Basic free and Premium an indicative preview with no purchase path", () => {
    expect(BILLING_ENABLED).toBe(false);
    expect(PRICING_PLANS.find((p) => p.id === "basic")!.priceDisplay).toBe("€0");
    const premium = PRICING_PLANS.find((p) => p.id === "premium")!;
    expect(premium.priceDisplay).toBe("€19.99");
    expect(premium.ctaKind).toBe("request");
    const { container } = wrap(<PricingContent />);
    // No purchase control: only the truthful register / preview-request links exist (negated statements in the copy are fine).
    const controls = [...container.querySelectorAll("a,button")].map((e) => e.textContent ?? "").join(" | ");
    expect(controls).not.toMatch(/\b(buy|checkout|subscribe now|purchase|pay now|add to cart)\b/i);
    expect(container.querySelector("input[type=text],input[name*=card i]")).toBeNull();
    expect(screen.getByTestId("no-billing-note")).toBeInTheDocument();
  });

  it("the Available today table lists exactly the backend entitlement keys and nothing invented", () => {
    expect(AVAILABLE_TODAY.map((r) => r.key).sort()).toEqual(["current_market_research", "premium_preview", "standard_history", "standard_model_profiles", "standard_progress"]);
    wrap(<PricingContent />);
    const table = screen.getByTestId("available-today");
    const premiumRow = table.querySelector('[data-entitlement="premium_preview"]')!;
    expect(premiumRow.textContent).toContain(t("pricingV4.previewOnly"));
    expect(premiumRow.textContent).not.toContain(t("pricingV4.included"));
    // No limit-based feature is presented as available today.
    expect(table.textContent).not.toMatch(/1 Opportunity|one Opportunity|three saved|3 sessions|unlimited/i);
  });

  it("puts the proposed split under a visibly labelled 'under consideration' section, and keeps benchmark honest", () => {
    const { container } = wrap(<PricingContent />);
    const section = screen.getByTestId("under-consideration");
    expect(section.textContent).toContain(t("pricingV4.considerLabel"));
    expect(section.textContent).toContain(t("pricingV4.consider1"));
    expect(container.querySelector('[data-testid="available-today"]')!.textContent).not.toContain(t("pricingV4.consider1"));
    const bench = screen.getByTestId("price-benchmark");
    expect(bench.textContent).toContain(t("pricingV4.benchmarkDate"));
    expect(bench.textContent).toContain(t("pricingV4.benchmarkNoConvert"));
    expect(bench.textContent).not.toMatch(/\d\s?%|cheaper than|you save/i);
    expect(PRICE_BENCHMARK.every((b) => /^https:\/\//.test(b.url))).toBe(true);
    expect(screen.getByTestId("complements-note").textContent).toContain(t("pricingV4.complements"));
    expect(t("pricingV4.complements")).toMatch(/does not replace human judgment/);
  });

  it("the comparison offers neutral trade-offs without a savings claim in any locale", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of ["coachingLead", "benchmarkLead", "benchmarkNoConvert", "complements", "point1", "point2", "point3"]) {
        const v = t(`pricingV4.${k}`, locale);
        expect(v, `${locale}.${k}`).not.toMatch(/\d\s?%/);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
      }
    }
  });
});

describe("home entry", () => {
  it("shows the static story after the hero and links to Getting Started", () => {
    const { container } = wrap(<MarketingHome />);
    expect(container.querySelector("[data-testid=candidate-story]")).not.toBeNull();
    expect(container.querySelector('a[href="/getting-started"]')).not.toBeNull();
    expect(container.querySelector("video")).toBeNull();
    expect(container.textContent).toContain(t("marketing.heroTitle"));
  });
});

describe("journey rail", () => {
  it("shows seven stages in order, marks 'You are here' and links only to existing routes", () => {
    wrap(<JourneyRail current="prepare" opportunityId={7} />);
    const rail = screen.getByTestId("journey-rail");
    const links = within(rail).getAllByRole("link");
    expect(links).toHaveLength(7);
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/opportunities/7", "/company?opportunity=7", "/documents", "/prepare?opportunity=7", "/practice?opportunity=7", "/history", "/progress"]);
    const here = links.filter((l) => l.getAttribute("aria-current") === "step");
    expect(here).toHaveLength(1);
    expect(here[0].textContent).toContain(t("journeyCues.stagePrepare"));
    expect(screen.getByTestId("you-are-here").textContent).toContain(t("journeyCues.youAreHere"));
  });
});

describe("v4 translations", () => {
  const NAMESPACES = ["v4nav", "gettingStarted", "homeStory", "pricingV4", "journeyCues", "workflow"];
  // Tokens that legitimately stay identical across languages.
  const SAME_OK = /^(Ask4Mo|Mo|Basic|Premium|Fast|Example|€|£|\$|\{)/;

  it("every v4 key exists in all eight locales and none is a missing-key fallback", () => {
    for (const ns of NAMESPACES) {
      const en = (CATALOGS.en as unknown as Record<string, Record<string, string>>)[ns];
      expect(Object.keys(en).length).toBeGreaterThanOrEqual(3);
      for (const locale of SUPPORTED_LOCALE_CODES) {
        const cat = (CATALOGS[locale] as unknown as Record<string, Record<string, string>>)[ns];
        expect(Object.keys(cat).sort(), `${locale}.${ns} keys`).toEqual(Object.keys(en).sort());
        for (const k of Object.keys(en)) {
          expect(t(`${ns}.${k}`, locale), `${locale}.${ns}.${k}`).not.toBe(`${ns}.${k}`);
          expect(cat[k], `${locale}.${ns}.${k}`).not.toMatch(/[—–]/);
        }
      }
    }
  });

  it("non-English locales are actually translated (no English placeholder left) and keep interpolation placeholders", () => {
    for (const locale of SUPPORTED_LOCALE_CODES.filter((l) => l !== "en")) {
      let same = 0, total = 0;
      for (const ns of NAMESPACES) {
        const en = (CATALOGS.en as unknown as Record<string, Record<string, string>>)[ns];
        const cat = (CATALOGS[locale] as unknown as Record<string, Record<string, string>>)[ns];
        for (const k of Object.keys(en)) {
          total += 1;
          if (cat[k] === en[k] && !SAME_OK.test(en[k])) same += 1;
          expect((cat[k].match(/\{\w+\}/g) ?? []).sort(), `${locale}.${ns}.${k} placeholders`).toEqual((en[k].match(/\{\w+\}/g) ?? []).sort());
        }
      }
      expect(same / total, `${locale} identical-to-English ratio`).toBeLessThan(0.08);
    }
  });

  it("the protected slogan is not duplicated in the v4 namespaces", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const ns of NAMESPACES) {
        for (const v of Object.values((CATALOGS[locale] as unknown as Record<string, Record<string, string>>)[ns])) expect(v).not.toMatch(/Ask More\. Be More\./);
      }
    }
  });
});
