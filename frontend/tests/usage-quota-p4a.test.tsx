import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import en from "@/lib/i18n/messages/w12p4a/en";

const getQuotas = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const errors = await vi.importActual<typeof import("@/lib/api/errors")>("@/lib/api/errors");
  return { ApiError: errors.ApiError, api: { usageQuotas: { get: (...a: unknown[]) => getQuotas(...a) } } };
});

import { UsageQuotaPanel } from "@/components/plan/UsageQuotaPanel";

const wrap = (locale: (typeof SUPPORTED_LOCALE_CODES)[number] = "en") => render(<I18nProvider initialLocale={locale}><UsageQuotaPanel /></I18nProvider>);
const COMMERCIAL = /upgrade|checkout|subscribe|buy now|purchase|pay now|price|€|\$/i;

beforeEach(() => { getQuotas.mockReset(); window.localStorage.clear(); });

describe("usage-quota presentation (server-reported only)", () => {
  it("renders nothing while enforcement is disabled: no allowance is invented", async () => {
    getQuotas.mockResolvedValue({ enforcement_active: false, policy_version: null, features: [] });
    const { container } = wrap();
    await waitFor(() => expect(getQuotas).toHaveBeenCalled());
    expect(container.textContent).toBe("");
    expect(screen.queryByTestId("usage-quotas")).toBeNull();
  });

  it("renders nothing when the request fails or the payload is malformed", async () => {
    getQuotas.mockRejectedValue(new Error("down"));
    const a = wrap();
    await waitFor(() => expect(getQuotas).toHaveBeenCalled());
    expect(a.container.textContent).toBe("");
    getQuotas.mockResolvedValue({ nope: true });
    const b = wrap();
    await waitFor(() => expect(getQuotas).toHaveBeenCalledTimes(2));
    expect(b.container.textContent).toBe("");
  });

  it("shows exactly the server's usage, remaining allowance and reset time", async () => {
    getQuotas.mockResolvedValue({ enforcement_active: true, policy_version: "synthetic", features: [
      { feature: "practice_session", unit: "session_started", status: "available", period: "day", allowance: 5, used: 2, remaining: 3, reset_at: "2026-10-18T00:00:00+00:00" },
      { feature: "career_ai", unit: "ai_generation", status: "exhausted", period: "hour", allowance: 1, used: 1, remaining: 0, reset_at: "2026-10-17T11:00:00+00:00" },
    ] });
    wrap();
    const panel = await screen.findByTestId("usage-quotas");
    const rows = panel.querySelectorAll("li");
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute("data-status")).toBe("available");
    expect(rows[0].textContent).toContain("2 / 5");
    expect(rows[0].textContent).toContain("3");
    expect(rows[1].getAttribute("data-status")).toBe("exhausted");
    expect(rows[1].textContent).toContain(translate("en", "quotaUx.exhaustedNote"));
  });

  it("a feature with no approved allowance carries no number", async () => {
    getQuotas.mockResolvedValue({ enforcement_active: true, policy_version: "p4a-unconfigured", features: [{ feature: "practice_session", unit: "session_started", status: "not_configured" }] });
    wrap();
    const panel = await screen.findByTestId("usage-quotas");
    expect(panel.textContent).toContain(translate("en", "quotaUx.notConfigured"));
    expect(panel.textContent).not.toMatch(/\b\d+\b/);
  });

  it("ignores unknown features and never offers a link, button or commercial wording; localStorage cannot change anything", async () => {
    window.localStorage.setItem("plan", "premium");
    getQuotas.mockResolvedValue({ enforcement_active: true, policy_version: "s", features: [
      { feature: "mystery", unit: "x", status: "available", allowance: 99, used: 0, remaining: 99 },
      { feature: "career_ai", unit: "ai_generation", status: "available", period: "month", allowance: 4, used: 0, remaining: 4, reset_at: "2026-11-01T00:00:00+00:00" },
    ] });
    wrap();
    const panel = await screen.findByTestId("usage-quotas");
    expect(panel.querySelectorAll("li")).toHaveLength(1);
    expect(panel.querySelectorAll("a, button, input, select").length).toBe(0);
    expect(panel.textContent).not.toMatch(COMMERCIAL);
    expect(panel.textContent).not.toContain("99");
  });
});

describe("exhaustion error state", () => {
  it("maps the stable server code to a localized state and carries no commercial wording", () => {
    const err = apiErrorFromBody(429, { error: { code: "usage_quota_exhausted", message: "m", request_id: "r", feature: "practice_session", period: "day", reset_at: "2026-10-18T00:00:00+00:00", retry_after_seconds: 60 } }, "r", 60_000);
    expect(err.kind).toBe("quotaExhausted");
    expect(stateKeyForError(err.kind)).toBe("states.usageQuotaExhausted");
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const text = translate(locale, "states.usageQuotaExhausted");
      expect(text).not.toBe("states.usageQuotaExhausted");
      expect(text).not.toMatch(COMMERCIAL);
      if (locale !== "en") expect(text).not.toBe(translate("en", "states.usageQuotaExhausted"));
    }
  });

  it("every quota key resolves in all eight locales, with no em dash and no raw key", () => {
    const keys = Object.keys(en.quotaUx).map((k) => `quotaUx.${k}`);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const text = translate(locale, k);
        expect(text, `${locale} ${k}`).not.toBe(k);
        expect(text).not.toContain("—");
        expect(text).not.toMatch(COMMERCIAL);
      }
    }
  });
});
