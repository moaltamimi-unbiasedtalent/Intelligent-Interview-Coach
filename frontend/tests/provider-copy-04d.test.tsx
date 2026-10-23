import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import { apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { parseRecentRuns } from "@/components/agent/RecentRuns";

/**
 * 04D (DEMO-02): accurate provider-failure copy by STABLE CODE (never English matching), the AI mode indicator, and the run-list shape validation.
 */

const caps = { value: { capabilities: { ai_provider_mode: "offline" } as Record<string, unknown>, loading: false, offline: false } };
vi.mock("@/lib/useCapabilities", () => ({ useCapabilities: () => caps.value }));

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { ProviderModeIndicator } from "@/components/layout/ProviderModeIndicator";

const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);
const body = (code: string, status = 503) => apiErrorFromBody(status, { error: { code, message: "SERVER ENGLISH TEXT THAT MUST NEVER BE SHOWN", request_id: "r" } }, "r");

describe("provider failures are classified by stable code", () => {
  it("ai_not_configured and not_configured are 'AI not configured'; ai_provider_unavailable is 'service failed this time'", () => {
    expect(body("ai_not_configured").kind).toBe("aiNotConfigured");
    expect(body("not_configured").kind).toBe("unavailable");                             // the generic configuration refusal (e.g. retrieval refused in a hosted environment) stays generic
    expect(body("ai_provider_unavailable").kind).toBe("aiUnavailable");
    expect(stateKeyForError("aiNotConfigured")).toBe("states.aiNotConfigured");
    expect(stateKeyForError("aiUnavailable")).toBe("states.aiProviderUnavailable");
  });

  it("the original defect is gone: a bare service_unavailable stays generic, an AI cause never does", () => {
    expect(body("service_unavailable").kind).toBe("unavailable");
    expect(body("ai_not_configured").userMessage).not.toBe(body("service_unavailable").userMessage);
    expect(body("ai_provider_unavailable").userMessage).not.toBe(body("ai_not_configured").userMessage);
  });

  it("the English fallbacks never carry the server text, a provider name or a key hint", () => {
    for (const code of ["ai_not_configured", "ai_provider_unavailable"]) {
      const e = body(code);
      expect(e.userMessage).not.toMatch(/SERVER ENGLISH|openrouter|api[_ ]?key|environment variable/i);
    }
  });

  it.each(SUPPORTED_LOCALE_CODES)("%s: both causes are localized, distinct from each other and from the generic message, and name no provider", (locale) => {
    const L = locale as AppLocale;
    const notConfigured = translate(L, "states.aiNotConfigured");
    const unavailable = translate(L, "states.aiProviderUnavailable");
    const generic = translate(L, "states.serviceUnavailable");
    for (const m of [notConfigured, unavailable]) {
      expect(m).not.toBe("states.aiNotConfigured");
      expect(m).not.toMatch(/openrouter|api[_ ]?key|sk-/i);
    }
    expect(new Set([notConfigured, unavailable, generic]).size).toBe(3);
    if (locale !== "en") {
      expect(notConfigured).not.toBe(translate("en", "states.aiNotConfigured"));         // a real translation, not the English fallback
      expect(unavailable).not.toBe(translate("en", "states.aiProviderUnavailable"));
    }
  });
});

describe("the AI mode indicator", () => {
  const show = (mode: unknown, loading = false, offline = false) => {
    caps.value = { capabilities: mode === undefined ? {} : { ai_provider_mode: mode as string }, loading, offline };
    return wrap(<ProviderModeIndicator />);
  };

  it.each([
    ["live", "providerMode.live"],
    ["offline", "providerMode.offline"],
    ["not_configured", "providerMode.notConfigured"],
    ["unknown", "providerMode.unknown"],
  ])("shows %s truthfully", (mode, key) => {
    show(mode);
    const el = screen.getByTestId("ai-provider-mode");
    expect(el).toHaveAttribute("data-mode", mode);
    expect(el.textContent).toContain(translate("en", key));
    expect(el.getAttribute("role")).toBeNull();                                         // a standing fact, not a live-region announcement
  });

  it("a non-live mode states what it means for the candidate; live is configuration, not health", () => {
    show("not_configured");
    expect(screen.getByTestId("ai-provider-mode").textContent).toContain(translate("en", "providerMode.notConfiguredHint"));
    expect(translate("en", "providerMode.liveHint")).toMatch(/not a health check/i);
    expect(translate("en", "providerMode.offlineHint")).toMatch(/not real coaching/i);
  });

  it("shows nothing while loading, when the backend is unreachable, or when the server states no mode (never claims live)", () => {
    for (const [mode, loading, offline] of [["live", true, false], ["live", false, true], [undefined, false, false]] as const) {
      const { container, unmount } = show(mode, loading, offline);
      expect(container.querySelector("[data-testid=ai-provider-mode]")).toBeNull();
      unmount();
    }
  });

  it("an unrecognised mode value is not rendered", () => {
    const { container } = show("something-else");
    expect(container.querySelector("[data-testid=ai-provider-mode]")).toBeNull();
  });

  it.each(SUPPORTED_LOCALE_CODES)("%s: every mode label and hint exists and is localized", (locale) => {
    for (const k of ["label", "live", "offline", "notConfigured", "unknown", "liveHint", "offlineHint", "notConfiguredHint", "unknownHint"]) {
      const v = translate(locale as AppLocale, `providerMode.${k}`);
      expect(v && v !== `providerMode.${k}`).toBe(true);
    }
  });
});

describe("the owner-scoped run list validates its shape at the client boundary", () => {
  const run = { run_id: "abc", state: "ready", created_at: "2026-01-01T00:00:00", updated_at: null };

  it("accepts a well-formed list", () => {
    expect(parseRecentRuns({ runs: [run], limit: 10 })).toEqual([{ run_id: "abc", state: "ready", created_at: "2026-01-01T00:00:00", updated_at: null }]);
    expect(parseRecentRuns({ runs: [], limit: 10 })).toEqual([]);
  });

  it.each([
    ["no body", undefined],
    ["an empty object", {}],
    ["runs is not an array", { runs: "x" }],
    ["an item without an id", { runs: [{ state: "ready" }] }],
    ["an unknown state", { runs: [{ run_id: "a", state: "weird" }] }],
    ["a purge state that must never be listed", { runs: [{ run_id: "a", state: "purge_failed" }] }],
    ["a null item", { runs: [null] }],
  ])("rejects %s (an explicit error, never a silent empty list)", (_label, input) => {
    expect(parseRecentRuns(input)).toBeNull();
  });

  it("every locale has the run-list copy", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const catalog = CATALOGS[locale as AppLocale] as unknown as Record<string, Record<string, string>>;
      for (const k of ["title", "hint", "empty", "open", "started", "stateStarted", "stateReady", "stateFailed", "loadError"]) expect(catalog.recentRuns?.[k], `${locale}.recentRuns.${k}`).toBeTruthy();
    }
  });
});
