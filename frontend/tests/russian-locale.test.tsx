import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { APP_LOCALES, SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";
import { TUTORIAL_STEPS } from "@/lib/tutorial/steps";
import { isSpeechOutputLocale, SUPPORTED_TTS_LOCALES } from "@/lib/speech/ttsLocales";

/**
 * P10B-W9.7 - Russian as the 8th interface/conversation language (R1-R16).
 * Deterministic UI tests (no network/model). Russian here is an ENGINEERING translation; these tests
 * prove completeness and independence, not native-speaker quality.
 */

const me = vi.fn();
const updatePreferences = vi.fn();
const oppList = vi.fn();
const memList = vi.fn();
const progressGet = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: {
      auth: { me: (...a: unknown[]) => me(...a), updatePreferences: (...a: unknown[]) => updatePreferences(...a) },
      opportunities: { list: (...a: unknown[]) => oppList(...a) },
      memory: { list: (...a: unknown[]) => memList(...a), remove: vi.fn() },
      progress: { get: (...a: unknown[]) => progressGet(...a) },
    },
    ApiError: actual.ApiError,
  };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/app",
  useSearchParams: () => new URLSearchParams(),
}));

import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider, useT } from "@/components/i18n/I18nProvider";
import { LanguageMenu } from "@/components/i18n/LanguageMenu";
import { LanguageSettings } from "@/components/settings/LanguageSettings";
import { OpportunityEntry } from "@/components/home/OpportunityEntry";
import { HomeHero } from "@/components/home/HomeHero";
import { StageProgress } from "@/components/preparation/StageProgress";
import { InterviewAnswerComposer } from "@/components/interview/InterviewAnswerComposer";
import { ProgressClient } from "@/components/progress/ProgressClient";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { HelpCenter } from "@/components/help/HelpCenter";
import { TrustContent } from "@/components/marketing/TrustContent";
import { PrivacyContent } from "@/components/marketing/PrivacyContent";
import { TutorialLauncher } from "@/components/tutorial/TutorialLauncher";
import { CAREER_GEOGRAPHIES } from "@/components/settings/CareerGeographyField";
import { DICTATION_LANGUAGES } from "@/components/ui/DictationControl";

const CYR = /[Ѐ-ӿ]/;
const ru = (key: string, vars?: Record<string, string | number>) => translate("ru", key, vars);
const en = (key: string) => translate("en", key);

function inRu(ui: React.ReactNode) {
  return render(<I18nProvider initialLocale="ru">{ui}</I18nProvider>);
}

const ACCOUNT = (over: Record<string, unknown> = {}) => ({
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "ru", conversation_language: "en", career_geography: "de", ...over,
});

// Real AuthProvider by default (LanguageSettings tests); a test may stub the optional auth hook
// (OpportunityEntry only needs `status`) by setting `authOverride`.
let authOverride: { status: string } | null = null;
vi.mock("@/components/auth/AuthProvider", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/auth/AuthProvider")>();
  return {
    ...actual,
    useAuthOptional: () => authOverride ?? actual.useAuthOptional(),
  };
});

beforeEach(() => {
  authOverride = null;
  me.mockReset(); updatePreferences.mockReset(); oppList.mockReset(); memList.mockReset(); progressGet.mockReset();
});
afterEach(() => {
  vi.clearAllMocks();
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

// ---------------------------------------------------------------------------------------------
describe("R3 + R4 - Russian catalogue completeness (no raw keys, no silent English fallback)", () => {
  const enCat = CATALOGS.en as unknown as Record<string, Record<string, string>>;
  const ruCat = CATALOGS.ru as unknown as Record<string, Record<string, string>>;

  it("R3: Russian has EXACT key parity with English (all namespaces, merged fragments included)", () => {
    const flat = (c: Record<string, Record<string, string>>) =>
      Object.keys(c).flatMap((ns) => Object.keys(c[ns]).map((k) => `${ns}.${k}`)).sort();
    expect(flat(ruCat)).toEqual(flat(enCat));
    expect(flat(ruCat).length).toBeGreaterThan(1400);
  });

  it("R3: every Russian value is non-blank and keeps the same {placeholders} as English", () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");
    for (const ns of Object.keys(enCat)) {
      for (const [k, v] of Object.entries(enCat[ns])) {
        const r = ruCat[ns][k];
        expect(r && r.trim().length > 0, `${ns}.${k} blank`).toBe(true);
        expect(ph(r), `${ns}.${k} placeholders`).toBe(ph(v));
      }
    }
  });

  it("R4: no value is a raw translation key and a representative lookup never returns its key", () => {
    for (const ns of Object.keys(ruCat)) {
      for (const [k, v] of Object.entries(ruCat[ns])) {
        expect(v).not.toBe(`${ns}.${k}`);
        // A leaked key is a value that names a REAL catalogue key (e.g. "help.gs1q"); a placeholder such
        // as "acme.com" merely has the same shape and is a legitimate example value.
        const [n2, k2] = v.split(".");
        const namesRealKey = /^[a-z][A-Za-z0-9]*\.[A-Za-z0-9_]+$/.test(v) && !!ruCat[n2] && k2 in ruCat[n2];
        expect(namesRealKey, `${ns}.${k} is a raw translation key`).toBe(false);
      }
    }
    for (const key of ["nav.prepare", "states.retry", "help.gs1q", "tutorial.s1Title", "trust.privateTerm"]) {
      expect(ru(key)).not.toBe(key);
    }
  });

  it("no normal Russian surface relies on English: every non-Cyrillic value is an explicit brand/token", () => {
    // The ONLY Russian values without Cyrillic: brand/product tokens, plan names, format names,
    // placeholders/examples. Anything else here would be an English fallback in disguise.
    const ALLOWED = new Set([
      "Ask4Mo", BRAND_SLOGAN, "Basic", "Premium", "Agent Inspector", "Knowledge & RAG", "DE", "acme.com",
      "Markdown", "JSON", "v{n}", "name@example.com", "Mo", "€0",
    ]);
    const offenders: string[] = [];
    for (const ns of Object.keys(ruCat)) {
      for (const [k, v] of Object.entries(ruCat[ns])) {
        if (!CYR.test(v) && !ALLOWED.has(v)) offenders.push(`${ns}.${k} = ${v}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------
describe("R1 + R2 + R13 - selector, switching and <html lang>", () => {
  it("R1: the canonical registry labels Russian with the native name 'Русский' (single source)", () => {
    expect(APP_LOCALES.find((l) => l.code === "ru")?.nativeLabel).toBe("Русский");
    expect(SUPPORTED_LOCALE_CODES).toContain("ru");
  });

  it("R1/R2/R13: the language menu offers Русский; selecting it switches chrome and sets <html lang=ru>", async () => {
    function Probe() {
      const t = useT();
      return <span data-testid="probe">{t("nav.prepare")}</span>;
    }
    render(
      <I18nProvider initialLocale="en">
        <LanguageMenu />
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent(en("nav.prepare"));
    await userEvent.click(screen.getByTestId("language-menu-button"));
    await userEvent.click(screen.getByRole("menuitemradio", { name: /Русский/ }));
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent(ru("nav.prepare")));
    expect(ru("nav.prepare")).toMatch(CYR);
    expect(document.documentElement.lang).toBe("ru");
  });
});

// ---------------------------------------------------------------------------------------------
describe("R5-R12 - representative surfaces render Russian", () => {
  it("R5: Tutorial v2 - all 9 steps and the replay launcher are Russian", () => {
    expect(TUTORIAL_STEPS).toHaveLength(9);
    for (const s of TUTORIAL_STEPS) {
      for (const key of [s.titleKey, s.bodyKey]) {
        expect(ru(key), key).toMatch(CYR);
        expect(ru(key), key).not.toBe(en(key));
      }
    }
    inRu(<TutorialLauncher />);
    expect(screen.getByRole("button", { name: ru("common.takeTour") })).toBeInTheDocument();
    expect(ru("common.takeTour")).toMatch(CYR);
  });

  it("R6: Opportunity entry renders Russian (no English copy)", async () => {
    authOverride = { status: "authenticated" };
    oppList.mockResolvedValue({ opportunities: [] });
    inRu(<OpportunityEntry />);
    expect(screen.getByRole("heading", { name: ru("home.opportunityTitle") })).toBeInTheDocument();
    expect(screen.getByText(ru("home.opportunityBody"))).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: ru("home.opportunityCreate") })).toHaveAttribute(
      "href", "/opportunities?create=1",
    );
    expect(screen.queryByText(/prepare for a specific job/i)).not.toBeInTheDocument();
  });

  it("R7: Prepare chrome (stage progress) renders Russian", () => {
    inRu(<StageProgress current="Understand" />);
    expect(screen.getByRole("list", { name: ru("prepare.progressStagesAria") })).toBeInTheDocument();
    expect(ru("prepare.progressStagesAria")).toMatch(CYR);
  });

  it("R8: Practice chrome (answer composer) renders Russian", () => {
    inRu(<InterviewAnswerComposer value="" onChange={() => {}} onSubmit={() => {}} busy={false} />);
    expect(screen.getByRole("button", { name: ru("practice.submitAnswer") })).toBeInTheDocument();
    expect(screen.getByLabelText(ru("practice.answerLabel"))).toBeInTheDocument();
  });

  it("R9: Progress renders Russian; History namespace is fully Russian", async () => {
    memList.mockResolvedValue({ memories: [] });
    progressGet.mockResolvedValue({
      interviews_completed: 0, answers_evaluated: 0, average_practice_score: null,
      most_common_improvement_area: null, average_answer_seconds: null, recent_interviews: [],
    });
    inRu(<ProgressClient />);
    expect(await screen.findByRole("heading", { name: ru("progress.title") })).toBeInTheDocument();
    for (const [k, v] of Object.entries((CATALOGS.ru as unknown as Record<string, Record<string, string>>).history)) {
      expect(v, `history.${k}`).toMatch(CYR);
    }
  });

  it("R10: shared error / loading chrome renders Russian", () => {
    inRu(
      <>
        <ErrorState message="msg" requestId="req-1" onRetry={() => {}} />
        <LoadingState />
      </>,
    );
    expect(screen.getByRole("button", { name: ru("states.retry") })).toBeInTheDocument();
    expect(screen.getByText(ru("states.technicalDetails"))).toBeInTheDocument();
    expect(screen.getByText(ru("states.loading"))).toBeInTheDocument();
  });

  it("R11: Help renders Russian titles and bodies, localized search and no-result message", async () => {
    inRu(<HelpCenter />);
    expect(screen.getByRole("heading", { name: ru("help.gsTitle") })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: ru("help.gs1q") })).toBeInTheDocument();
    expect(screen.getByText(ru("help.gs1a"))).toBeInTheDocument();
    expect(screen.queryByText("What is Ask4Mo?")).not.toBeInTheDocument();
    // Cyrillic search with Unicode case handling (query upper-case, content lower-case).
    await userEvent.type(screen.getByLabelText(ru("help.searchLabel")), "СОБЕСЕДОВАН");
    expect(screen.getAllByRole("heading", { level: 3 }).length).toBeGreaterThan(0);
    await userEvent.clear(screen.getByLabelText(ru("help.searchLabel")));
    await userEvent.type(screen.getByLabelText(ru("help.searchLabel")), "zzzznomatchxyz");
    expect(screen.getByText(ru("help.noMatch", { query: "zzzznomatchxyz" }))).toBeInTheDocument();
  });

  it("R12: Trust and Privacy (legal) public copy renders Russian", () => {
    inRu(
      <>
        <TrustContent />
        <PrivacyContent />
      </>,
    );
    expect(screen.getByText(ru("trust.privateTerm"))).toBeInTheDocument();
    expect(ru("trust.privateTerm")).toMatch(CYR);
    expect(screen.queryByText("Private by default")).not.toBeInTheDocument();
    for (const ns of ["privacy", "terms", "aiTransparency", "about", "trust"]) {
      for (const [k, v] of Object.entries((CATALOGS.ru as unknown as Record<string, Record<string, string>>)[ns])) {
        expect(v, `${ns}.${k}`).toMatch(CYR);
      }
    }
  });
});

// ---------------------------------------------------------------------------------------------
describe("R14 - interface, conversation and dictation stay independent", () => {
  it("Russian interface + English conversation: chrome is Russian, conversation stays en, dictation unaffected", async () => {
    me.mockResolvedValue(ACCOUNT({ interface_locale: "ru", conversation_language: "en" }));
    render(
      <AuthProvider>
        <I18nProvider>
          <LanguageSettings />
        </I18nProvider>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText(ru("settings.interfaceLanguage"))).toBeInTheDocument());
    expect((screen.getByLabelText(ru("settings.interfaceLanguage")) as HTMLSelectElement).value).toBe("ru");
    const conv = screen.getByLabelText(ru("settings.conversationLanguage")) as HTMLSelectElement;
    expect(conv.value).toBe("en");
    // Both interface and conversation selectors offer Русский (8 options); the dictation selector does NOT.
    const interfaceOpts = Array.from((screen.getByLabelText(ru("settings.interfaceLanguage")) as HTMLSelectElement).options);
    expect(interfaceOpts.map((o) => o.value)).toContain("ru");
    expect(Array.from(conv.options).map((o) => o.value)).toContain("ru");
    const dict = screen.getByLabelText(ru("settings.dictationLanguage")) as HTMLSelectElement;
    expect(Array.from(dict.options).some((o) => o.value.startsWith("ru"))).toBe(false);
    expect(Array.from(dict.options)).toHaveLength(7);
    expect(dict.value).toMatch(/^en-US$/); // never silently selects a fake Russian dictation locale
  });

  it("English interface + Russian conversation: choosing Russian conversation sends ONLY conversation_language", async () => {
    me.mockResolvedValue(ACCOUNT({ interface_locale: "en", conversation_language: "en" }));
    updatePreferences.mockResolvedValue(ACCOUNT({ interface_locale: "en", conversation_language: "ru" }));
    render(
      <AuthProvider>
        <I18nProvider>
          <LanguageSettings />
        </I18nProvider>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("Mo conversation language")).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByLabelText("Mo conversation language"), "ru");
    await waitFor(() => expect(updatePreferences).toHaveBeenCalledWith({ conversation_language: "ru" }));
    expect(updatePreferences).not.toHaveBeenCalledWith(expect.objectContaining({ interface_locale: expect.anything() }));
    expect(document.documentElement.lang).toBe("en"); // chrome remains English
  });
});

// ---------------------------------------------------------------------------------------------
describe("R15 - Russian does not alter geography, speech capability or taxonomy", () => {
  it("Russia is not a labour market and no Russian market label exists", () => {
    expect((CAREER_GEOGRAPHIES as readonly string[]).includes("ru")).toBe(false);
    expect(Object.keys((CATALOGS.ru as unknown as Record<string, Record<string, string>>).geography)).not.toContain("ru");
    expect(Object.keys((CATALOGS.en as unknown as Record<string, Record<string, string>>).geography)).not.toContain("ru");
  });

  it("speech capability lists are unchanged: no Russian dictation / playback / live voice", () => {
    expect(DICTATION_LANGUAGES.map((l) => l.code)).toEqual(
      ["en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL"],
    );
    expect(SUPPORTED_TTS_LOCALES).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
    expect(isSpeechOutputLocale("ru")).toBe(false);
    expect(isSpeechOutputLocale("ru-RU")).toBe(false);
    expect(isSpeechOutputLocale("de")).toBe(true);
    expect(isSpeechOutputLocale(undefined)).toBe(true); // unset => English default
  });

  it("voice help explains Russian is interface/conversation only (no implied speech support)", () => {
    for (const code of SUPPORTED_LOCALE_CODES) {
      const a = translate(code, "voice.hLangA");
      expect(a.length).toBeGreaterThan(50);
    }
    expect(translate("en", "voice.hLangA")).toMatch(/Russian is available as an interface and conversation language/);
    expect(ru("voice.hLangA")).toMatch(/Русский доступен как язык интерфейса и язык общения/);
  });
});

// ---------------------------------------------------------------------------------------------
describe("R16 - the protected slogan renders unchanged in a Russian interface", () => {
  it("Home hero shows exactly the English slogan under the Russian interface", () => {
    inRu(<HomeHero />);
    expect(screen.getByText(BRAND_SLOGAN)).toBeInTheDocument();
  });
});
