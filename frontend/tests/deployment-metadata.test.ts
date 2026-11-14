import { afterEach, describe, expect, it, vi } from "vitest";
import { cookies } from "next/headers";
import { generateMetadata } from "@/app/layout";
import { BRAND_SLOGAN } from "@/lib/brand";
import { getCatalog } from "@/lib/i18n/catalog";
import { LOCALE_COOKIE } from "@/lib/i18n/cookie";
import { ACTIVE_CANDIDATE_LOCALES } from "@/lib/i18n/locales";
import { DEPLOYMENT_META_NAMES, deploymentMetadata } from "@/lib/deploymentMetadata";

const KEYS = ["APP_GIT_SHA", "APP_BUILD_TIME", "APP_DEPLOY_TAGS"] as const;

afterEach(() => {
  for (const key of KEYS) delete process.env[key];
});

describe("deployment metadata", () => {
  it("reports unknown when the container did not inject provenance", () => {
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "unknown",
      [DEPLOYMENT_META_NAMES.timestamp]: "unknown",
      [DEPLOYMENT_META_NAMES.tags]: "unknown",
    });
  });

  it("exposes the injected commit, timestamp and tags", () => {
    process.env.APP_GIT_SHA = "  00f7ddfba454f3daa946d867d6e131220bb0dc69  ";
    process.env.APP_BUILD_TIME = "2026-11-12T18:40:00Z";
    process.env.APP_DEPLOY_TAGS = 'branch:dockerize,git:v1.0.0,image:ask4mo-local-web';
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "00f7ddfba454f3daa946d867d6e131220bb0dc69",
      [DEPLOYMENT_META_NAMES.timestamp]: "2026-11-12T18:40:00Z",
      [DEPLOYMENT_META_NAMES.tags]: "branch:dockerize,git:v1.0.0,image:ask4mo-local-web",
    });
  });

  it("strips unsafe characters before they reach an HTML meta tag", () => {
    process.env.APP_GIT_SHA = "<script>alert(1)</script>";
    process.env.APP_BUILD_TIME = "2026-11-12T18:40:00Z";
    process.env.APP_DEPLOY_TAGS = 'branch:dockerize,"unsafe"<tag>';
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "scriptalert1/script",
      [DEPLOYMENT_META_NAMES.timestamp]: "2026-11-12T18:40:00Z",
      [DEPLOYMENT_META_NAMES.tags]: "branch:dockerize,unsafetag",
    });
  });
});

vi.mock("next/headers", () => ({ cookies: vi.fn() }));
vi.mock("next/font/google", () => ({ Inter: () => ({ variable: "--font-inter" }) }));
vi.mock("@/components/layout/AppShell", () => ({ AppShell: vi.fn() }));
vi.mock("@/components/layout/ThemeScript", () => ({ ThemeScript: vi.fn() }));
vi.mock("@/components/auth/AuthProvider", () => ({ AuthProvider: vi.fn() }));
vi.mock("@/components/i18n/I18nProvider", () => ({ I18nProvider: vi.fn() }));

function useLocaleCookie(value?: string) {
  const get = vi.fn((name: string) =>
    name === LOCALE_COOKIE && value !== undefined ? { name, value } : undefined,
  );
  vi.mocked(cookies).mockResolvedValue({
    get,
    getAll: vi.fn(),
    has: vi.fn(),
    set: vi.fn(),
    delete: vi.fn(),
    size: value === undefined ? 0 : 1,
    toString: vi.fn(),
    [Symbol.iterator]: vi.fn(),
  });
  return get;
}

describe("root layout metadata", () => {
  it.each(ACTIVE_CANDIDATE_LOCALES)("uses existing %s copy in the title and both descriptions", async (locale) => {
    const get = useLocaleCookie(locale);
    const { common, marketing } = getCatalog(locale);
    const title = `Ask4Mo - ${common.productName}`;
    const description = `${marketing.heroSubtitle} ${BRAND_SLOGAN}`;

    const metadata = await generateMetadata();

    expect(get).toHaveBeenCalledWith(LOCALE_COOKIE);
    expect(metadata.title).toEqual({ default: title, template: "%s · Ask4Mo" });
    expect(metadata.description).toBe(description);
    expect(metadata.openGraph).toEqual({
      title,
      description,
      siteName: "Ask4Mo",
      type: "website",
      images: [{ url: "/brand/ask4mo-logo.svg", width: 1200, height: 630, alt: "Ask4Mo" }],
    });
  });

  it.each([undefined, "zz", "ru"])("falls back to English for a missing or inactive locale (%s)", async (value) => {
    useLocaleCookie(value);
    const metadata = await generateMetadata();

    expect(metadata.title).toMatchObject({ default: "Ask4Mo - Intelligent Interview Coach" });
    expect(metadata.description).toBe(`${getCatalog("en").marketing.heroSubtitle} ${BRAND_SLOGAN}`);
  });

  it("preserves the icon links and sanitized deployment provenance", async () => {
    useLocaleCookie("de-AT");
    process.env.APP_GIT_SHA = "  00f7ddfba454f3daa946d867d6e131220bb0dc69  ";
    process.env.APP_BUILD_TIME = "2026-11-12T18:40:00Z";
    process.env.APP_DEPLOY_TAGS = 'branch:dockerize,"unsafe"<tag>';

    const metadata = await generateMetadata();

    expect(metadata.title).toMatchObject({ default: `Ask4Mo - ${getCatalog("de").common.productName}` });
    expect(metadata.applicationName).toBe("Ask4Mo");
    expect(metadata.icons).toEqual({
      icon: "/brand/ask4mo-mark.svg",
      shortcut: "/brand/ask4mo-mark.svg",
      apple: "/brand/ask4mo-mark.svg",
    });
    expect(metadata.other).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "00f7ddfba454f3daa946d867d6e131220bb0dc69",
      [DEPLOYMENT_META_NAMES.timestamp]: "2026-11-12T18:40:00Z",
      [DEPLOYMENT_META_NAMES.tags]: "branch:dockerize,unsafetag",
    });
  });
});
