import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, toSupportedLocale } from "@/lib/i18n/locales";
import enDefault from "@/lib/i18n/messages/en";

// Deterministic key set from the English source (the reference catalogue).
function flatKeys(cat: Record<string, Record<string, string>>): string[] {
  const keys: string[] = [];
  for (const ns of Object.keys(cat)) for (const k of Object.keys(cat[ns])) keys.push(`${ns}.${k}`);
  return keys.sort();
}

describe("i18n catalogues", () => {
  it("registers exactly the seven supported locales", () => {
    expect(Object.keys(CATALOGS).sort()).toEqual([...SUPPORTED_LOCALE_CODES].sort());
    expect(SUPPORTED_LOCALE_CODES).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
  });

  it("every locale has the exact same keys as English (complete, no missing/extra)", () => {
    const enKeys = flatKeys(enDefault as never);
    for (const [code, cat] of Object.entries(CATALOGS)) {
      expect({ code, keys: flatKeys(cat as never) }).toEqual({ code, keys: enKeys });
    }
  });

  it("has no blank required translation values in any locale", () => {
    for (const [code, cat] of Object.entries(CATALOGS)) {
      for (const ns of Object.keys(cat)) {
        for (const [k, v] of Object.entries((cat as Record<string, Record<string, string>>)[ns])) {
          expect(`${code}:${ns}.${k}=${String(v).trim().length > 0}`).toContain("=true");
        }
      }
    }
  });

  it("English is a complete non-empty source", () => {
    expect(flatKeys(enDefault as never).length).toBeGreaterThan(60);
  });
});

describe("translate()", () => {
  it("returns the locale string and interpolates vars", () => {
    expect(translate("de", "common.signIn")).toBe("Anmelden");
    expect(translate("en", "auth.passwordHint", { min: 10 })).toContain("10");
  });

  it("falls back to English for a missing key, never undefined/blank", () => {
    // A fabricated missing key returns the key itself (never undefined).
    expect(translate("de", "nonexistent.key")).toBe("nonexistent.key");
  });

  it("treats an unsupported locale safely (falls back)", () => {
    expect(toSupportedLocale("zz")).toBeNull();
    // @ts-expect-error deliberately passing an unsupported locale
    expect(translate("zz", "common.signIn")).toBe("Sign in"); // English fallback
  });
});

// --- provider switching + settings ------------------------------------------

const me = vi.fn();
const updatePreferences = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: { auth: { me: (...a: unknown[]) => me(...a), updatePreferences: (...a: unknown[]) => updatePreferences(...a) } },
    ApiError: actual.ApiError,
  };
});

import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider, useT } from "@/components/i18n/I18nProvider";
import { LanguageSettings } from "@/components/settings/LanguageSettings";

const ACCOUNT = (over: Record<string, unknown> = {}) => ({
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en", ...over,
});

afterEach(() => {
  vi.clearAllMocks();
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

function Probe() {
  const t = useT();
  return <span>{t("nav.prepare")}</span>;
}

describe("I18nProvider", () => {
  it("renders the account's interface_locale (German) once loaded", async () => {
    me.mockResolvedValue(ACCOUNT({ interface_locale: "de" }));
    render(
      <AuthProvider>
        <I18nProvider>
          <Probe />
        </I18nProvider>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("Vorbereiten")).toBeInTheDocument());
  });

  it("defaults to English when unauthenticated", async () => {
    me.mockRejectedValue(new (await import("@/lib/api/client")).ApiError({ kind: "validation", status: 401, code: "unauthorized", message: "x" }));
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByText("Prepare")).toBeInTheDocument();
  });
});

describe("LanguageSettings — three independent controls", () => {
  it("shows interface, conversation and dictation language controls", async () => {
    me.mockResolvedValue(ACCOUNT());
    render(
      <AuthProvider>
        <I18nProvider>
          <LanguageSettings />
        </I18nProvider>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("Interface language")).toBeInTheDocument());
    expect(screen.getByText("Mo conversation language")).toBeInTheDocument();
    expect(screen.getByText("Dictation language")).toBeInTheDocument();
  });

  it("changing conversation language persists it independently (not interface)", async () => {
    me.mockResolvedValue(ACCOUNT());
    updatePreferences.mockResolvedValue(ACCOUNT({ conversation_language: "fr" }));
    render(
      <AuthProvider>
        <I18nProvider>
          <LanguageSettings />
        </I18nProvider>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("Mo conversation language")).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByLabelText("Mo conversation language"), "fr");
    await waitFor(() =>
      expect(updatePreferences).toHaveBeenCalledWith({ conversation_language: "fr" }),
    );
    // It never sent an interface_locale change.
    expect(updatePreferences).not.toHaveBeenCalledWith(
      expect.objectContaining({ interface_locale: expect.anything() }),
    );
  });
});
