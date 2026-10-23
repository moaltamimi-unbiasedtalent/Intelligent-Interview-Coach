import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import { PRICE_BENCHMARK, PRICING_PLANS } from "@/lib/pricing";
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
import { ProductContent } from "@/components/marketing/ProductContent";
import { ResearchEvidence } from "@/components/marketing/ResearchEvidence";
import { JourneyRail } from "@/components/layout/JourneyRail";

const t = (k: string, l: AppLocale = "en") => translate(l, k);
const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

describe("floating marketing navigation", () => {
  it("keeps one Product destination, the language control and the sign-in / CTA state", () => {
    authState.status = "unauthenticated";
    wrap(<MarketingShell><p>body</p></MarketingShell>);
    const header = screen.getByTestId("marketing-header");
    for (const item of MARKETING_NAV) expect(within(header).getAllByRole("link", { name: t(item.key) }).length).toBeGreaterThan(0);
    const hrefs: string[] = MARKETING_NAV.map((n) => n.href);
    for (const h of ["/product", "/pricing", "/trust", "/about"]) expect(hrefs).toContain(h);
    expect(hrefs).not.toContain("/getting-started");
    expect(hrefs).not.toContain("/help");
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
  it("has the required sections, the six steps, the 15-minute checklist and the Trust / AI links", () => {
    const { container } = wrap(<GettingStartedContent />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(t("gettingStarted.title"));
    for (const id of ["story", "workflow", "steps", "first-15"]) expect(container.querySelector(`#${id}`)).not.toBeNull();
    expect(container.querySelectorAll("#steps ol > li")).toHaveLength(6);
    expect(container.querySelectorAll("#first-15 li")).toHaveLength(6);
    for (const href of ["/trust", "/ai-transparency"]) expect(container.querySelector(`a[href="${href}"]`)).not.toBeNull();
    expect(container.querySelector('a[href="/help"]')).toBeNull();
    expect(container.querySelector("video")).toBeNull();
  });

  it("combines product features, differentiation and How it works on Product", () => {
    const { container } = wrap(<ProductContent />);
    expect(MARKETING_NAV.some((n) => String(n.href) === "/getting-started")).toBe(false);
    expect(MARKETING_NAV.find((n) => n.href === "/product")).toBeTruthy();
    expect(container.querySelector("#how-it-works")).not.toBeNull();
    expect(container.textContent).toContain(t("marketing.featureCompanyTitle"));
    expect(container.textContent).toContain(t("marketing.whyTitle"));
    expect(container.querySelector('img[src$="ask4mo-about-human-conversation.png"]')).not.toBeNull();
    expect(container.querySelector('img[src$="ask4mo-v4-candidate-story-practice-v5.png"]')).toBeNull();
    expect(container.querySelector('img[src$="ask4mo-v4-candidate-story-practice-v4.png"]')).toBeNull();
    expect(container.querySelector('img[src$="ask4mo-product-connected-system-editorial.png"]')).toBeNull();
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
  it("keeps Basic free and presents Premium as NOT available (no price offer, no purchase link) (W12.4D-P3)", () => {
    // 04D: no price figure exists on a plan any more (Ask4Mo is a free, invitation-only private beta); the one statement says so.
    expect(PRICING_PLANS.every((p) => !("priceDisplay" in p))).toBe(true);
    const premium = PRICING_PLANS.find((p) => p.id === "premium")!;
    expect(premium.ctaKind).toBe("unavailable");
    expect(premium.ctaHref).toBeNull();
    expect(premium.purchasable).toBe(false);
    const { container } = wrap(<PricingContent />);
    expect(container.querySelector('a[href^="/register?plan=premium"]')).toBeNull();                 // no purchase path
    expect(container.querySelector('a[href*="checkout"], form[action*="checkout"]')).toBeNull();
    expect(screen.getByTestId("premium-status").textContent).toContain(t("planUx.pricing_notAvailable"));
    expect(screen.getByTestId("premium-beta-statement").textContent).toBe(t("betaPricing.statement"));
    expect(screen.getByTestId("beta-free").textContent).toBe(t("betaPricing.freeInBeta"));
    expect(screen.getByTestId("plan-status-premium").textContent).toContain(t("marketing.planPremiumCta"));
    expect(screen.getByTestId("plan-note-premium").textContent).toContain(t("marketing.planPremiumNote"));
    expect(container.querySelector("input[type=text],input[name*=card i]")).toBeNull();
  });

  it("removes the internal Available today entitlement table from the public page", () => {
    const { container } = wrap(<PricingContent />);
    expect(container.querySelector('[data-testid="available-today"]')).toBeNull();
    expect(container.textContent).not.toContain(t("pricingV4.availableTitle"));
  });

  it("puts the proposed split under a visibly labelled launch-package section, and keeps benchmark honest", () => {
    const { container } = wrap(<PricingContent />);
    const section = screen.getByTestId("pricing-plans");
    expect(section.textContent).toContain(t("pricingV4.considerLabel"));
    expect(section.textContent).toContain(t("pricingV4.consider1"));
    expect(container.querySelector('[data-testid="available-today"]')).toBeNull();
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
  it("shows the static story after the hero and links to the combined Product workflow", () => {
    const { container } = wrap(<MarketingHome />);
    expect(container.querySelector("[data-testid=candidate-story]")).not.toBeNull();
    expect(container.querySelector('a[href="/product#how-it-works"]')).not.toBeNull();
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
  const NAMESPACES = ["v4nav", "gettingStarted", "homeStory", "pricingV4", "journeyCues", "workflow", "researchEvidence"];
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

describe("V4.3 refinements", () => {
  it("adds the founder's requested statement to Home", () => {
    const { container } = wrap(<MarketingHome />);
    expect(container.textContent).toContain("I've spent my career helping organisations find the right talent.");
    expect(container.textContent).toContain("Mo Al-Tamimi, Founder & CEO - Ask4Mo");
  });

  it("presents independent research as context, links to the original sources and avoids claiming Ask4Mo outcomes", () => {
    const { container } = wrap(<ResearchEvidence />);
    expect(container.firstElementChild?.className).toContain("bg-[#e9e2f0]");
    expect(container.firstElementChild?.className).not.toContain("bg-[#183f42]");
    expect(container.textContent).toContain("36% → 63%");
    expect(container.textContent).toContain("358");
    expect(container.textContent).toContain(t("researchEvidence.caveat"));
    expect(container.textContent).toContain("not Ask4Mo results");
    const sources = within(container).getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(sources).toContain("https://www.gov.uk/government/publications/stem-recharge-programme-evaluation/stem-recharge-programme-evaluation");
    expect(sources).toContain("https://www.sciencedirect.com/science/article/pii/S0001879123000726");
  });

  it("restores a richer, controllable product-facts carousel on the homepage", () => {
    const { container } = wrap(<MarketingHome />);
    const carousel = screen.getByTestId("proof-carousel");
    expect(carousel.className).toContain("bg-[#183f42]");
    expect(carousel.textContent).toContain(t("marketing.systemTitle"));
    expect(carousel.textContent).toContain(t("marketing.systemLead"));
    expect(within(carousel).getAllByRole("button", { name: /fact/i })).toHaveLength(4);
    fireEvent.click(within(carousel).getByRole("button", { name: "Go to fact 3 of 4" }));
    expect(carousel.textContent).not.toMatch(/[€$£]\s?\d/);                       // 04D: no price figure on a candidate surface
    expect(carousel.textContent).toContain(t("marketing.pricingBasicIncludes"));
    expect(within(carousel).getByRole("button", { name: t("proofCarousel.resume") })).toBeInTheDocument();
    expect(container.querySelector('img[src$="ask4mo-v4-candidate-story-practice-v5.png"]')).not.toBeNull();
  });

  it("workflow map names the stages in the required order and shows the same order as a readable sequence", () => {
    wrap(<WorkflowMap />);
    const seq = screen.getByTestId("workflow-sequence");
    const labels = within(seq).getAllByRole("tab").map((b) => b.getAttribute("aria-label"));
    expect(labels).toEqual(["Opportunity", "Company research", "Evidence", "Preparation", "Practice", "Feedback", "Progress"]);
    fireEvent.click(within(seq).getByRole("tab", { name: "Practice" }));
    expect(screen.getByRole("tab", { name: /Practice/ })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: /Feedback/ })).toHaveAttribute("aria-selected", "true");
  });
});

describe("founder portrait (About)", () => {
  it("shows the approved local portrait with the exact alt text, replaces the monogram and is never hotlinked", async () => {
    const { AboutContent } = await import("@/components/marketing/AboutContent");
    const { container } = wrap(<AboutContent />);
    const img = container.querySelector('img[src$="mo-al-tamimi-founder-portrait.jpg"]')!;
    expect(img).not.toBeNull();
    expect(img.getAttribute("alt")).toBe("Mo Al-Tamimi, founder of Ask4Mo.");
    expect(img.getAttribute("src")).not.toMatch(/linkedin|licdn/i);
    expect(container.textContent).not.toMatch(/\bMA\b/);                       // monogram replaced
    expect(container.querySelector('a[href="https://www.linkedin.com/in/moaltamimi/"]')).not.toBeNull();
    expect(container.textContent).toContain("Founder & CEO of Ask4Mo, CHRO and Founder & CEO of Unbiased Talent");
    expect(container.textContent).toContain("Talent is everywhere. Opportunity isn't always.");
    for (const locale of SUPPORTED_LOCALE_CODES) expect(t("about.founderPortraitAlt", locale).length, locale).toBeGreaterThan(10);
  });

  it("the portrait appears only on the About page", async () => {
    const { MarketingHome } = await import("@/components/marketing/MarketingHome");
    const { GettingStartedContent: GS } = await import("@/components/marketing/GettingStartedContent");
    for (const C of [MarketingHome, GS, PricingContent]) {
      const { container, unmount } = wrap(<C />);
      expect(container.querySelector('img[src*="founder-portrait"]')).toBeNull();
      unmount();
    }
  });
});

describe("Trust page hierarchy", () => {
  it("leads with a concise privacy promise and progressively discloses the detailed controls", async () => {
    const { TrustContent } = await import("@/components/marketing/TrustContent");
    const { container } = wrap(<TrustContent />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(t("trust.privateTerm"));
    expect(container.querySelectorAll("details")).toHaveLength(4);
    expect(container.querySelectorAll('details[open]')).toHaveLength(0);
  });
});
