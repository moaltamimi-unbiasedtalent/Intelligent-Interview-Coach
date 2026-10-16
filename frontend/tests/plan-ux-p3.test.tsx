import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { ApiError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { CAPABILITIES, STATUS_ORDER } from "@/lib/plan/capabilities";
import en from "@/lib/i18n/messages/w12p3/en";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(""), useRouter: () => ({ push() {}, replace() {} }), usePathname: () => "/account" }));

const getProfiles = vi.fn();
const historyGet = vi.fn();
const submitAnswer = vi.fn();
const interviewGet = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const errors = await vi.importActual<typeof import("@/lib/api/errors")>("@/lib/api/errors");
  return {
    ApiError: errors.ApiError,
    api: {
      modelProfiles: { get: (...a: unknown[]) => getProfiles(...a) },
      history: { get: (...a: unknown[]) => historyGet(...a), list: vi.fn(), remove: vi.fn() },
      reports: { exportMarkdownUrl: () => "#", exportJsonUrl: () => "#" },
      interviews: { get: (...a: unknown[]) => interviewGet(...a), submitAnswer: (...a: unknown[]) => submitAnswer(...a), options: vi.fn() },
    },
  };
});

import { HistoryAccessNotice } from "@/components/plan/HistoryAccessNotice";
import { ModelProfilePanel } from "@/components/plan/ModelProfilePanel";
import { PlanOverview } from "@/components/plan/PlanOverview";
import { SessionTransitionNotice } from "@/components/plan/SessionTransitionNotice";
import { HistoryDetailClient } from "@/components/interview/HistoryDetailClient";
import { useInterview } from "@/components/interview/useInterview";

const wrap = (ui: React.ReactNode, locale: (typeof SUPPORTED_LOCALE_CODES)[number] = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);
const t = (key: string, locale: (typeof SUPPORTED_LOCALE_CODES)[number] = "en") => translate(locale, key);
const COMMERCIAL = /upgrade|checkout|subscribe now|buy now|purchase|pay now|price|€|\$|medium/i;

beforeEach(() => { vi.clearAllMocks(); try { localStorage.clear(); } catch { /* ignore */ } });

describe("plan overview: the owner-approved matrix with truthful statuses", () => {
  it("lists all 13 capabilities and each cell states its status in text", () => {
    wrap(<PlanOverview />);
    const items = screen.getByTestId("plan-capabilities").querySelectorAll("li[data-capability]");
    expect(items).toHaveLength(13);
    expect(CAPABILITIES.map((c) => c.id)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]);
    const legend = screen.getByTestId("plan-legend").textContent ?? "";
    for (const s of STATUS_ORDER) expect(legend).toContain(t(`planUx.status_${s}`));
    for (const chip of Array.from(document.querySelectorAll("[data-status]"))) expect((chip.textContent ?? "").trim().length).toBeGreaterThan(8);   // never colour alone
  });

  it("never presents a planned or inactive item as live", () => {
    const status = (id: number, plan: "basic" | "premium") => CAPABILITIES.find((c) => c.id === id)![plan].status;
    expect(status(9, "premium")).toBe("planned");            // attempt comparison: not built (P4)
    expect(status(10, "premium")).toBe("planned");           // preparation pack: not built (P5-A)
    expect(status(13, "premium")).toBe("planned");           // real-time voice: future, not in the initial launch
    expect(status(7, "premium")).toBe("planned");            // trends and comparisons: not built
    expect(status(6, "basic")).toBe("entitlement");          // the history rule is not active
    expect(status(11, "basic")).toBe("entitlement");         // model-profile enforcement is not active
    expect(status(1, "premium")).toBe("pending");            // allowances are not approved
    expect(status(8, "premium")).toBe("pending");
    expect(CAPABILITIES.filter((c) => c.premium.status === "available").map((c) => c.id)).toEqual([2, 3, 4, 5, 12]);   // only what really works today
    for (const c of CAPABILITIES) expect(["none", "planned", "entitlement", "available", "pending", "unavailable"]).toContain(c.basic.status);
  });

  it("has no purchase, upgrade, price or Medium wording and no button or link that could start a payment", () => {
    const { container } = wrap(<PlanOverview />);
    expect(container.textContent ?? "").not.toMatch(COMMERCIAL);
    expect(container.querySelectorAll("button, a, form, input")).toHaveLength(0);
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: every plan key resolves, no raw key, no English leak (except the official profile names), no em dash`, () => {
      const keys = Object.keys(en.planUx);
      expect(keys.length).toBeGreaterThan(60);
      for (const k of keys) {
        const v = t(`planUx.${k}`, locale);
        expect(v, `${locale}.${k}`).not.toBe(`planUx.${k}`);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
        if (locale !== "en" && !/^(models_(fast|balanced|advanced)|cell_modelBasic|colBasic)$/.test(k)) {
          expect(v, `${locale}.${k} must not be the English string`).not.toBe((en.planUx as Record<string, string>)[k]);
        }
      }
      const { container } = wrap(<PlanOverview />, locale);
      expect(container.textContent ?? "").not.toMatch(/planUx\./);
      expect(container.textContent ?? "").not.toMatch(/\bmedium\b/i);
    });
  }
});

describe("model-profile presentation over the server catalogue", () => {
  const catalogue = (selector_active: boolean, authorized: string[], def = "balanced") => ({
    selector_active, default: def,
    profiles: ["fast", "balanced", "advanced"].map((id) => ({ id, authorized: authorized.includes(id), description: "server text" })),
  });

  it("exposes NO selector and says so while the server reports selector_active false", async () => {
    getProfiles.mockResolvedValue(catalogue(false, ["fast", "balanced", "advanced"]));
    wrap(<ModelProfilePanel />);
    const panel = await screen.findByTestId("model-profiles");
    expect(panel.getAttribute("data-selector-active")).toBe("false");
    expect(panel.textContent).toContain(t("planUx.models_leadInactive"));
    expect(panel.querySelectorAll("button, input, select, a, [role=radio], [role=option]")).toHaveLength(0);
    expect(panel.textContent).not.toContain(t("planUx.models_available"));           // no per-profile availability claim while inactive
    expect(panel.textContent).toContain(t("planUx.models_noClaims"));
  });

  it("shows only what the server authorized: Basic gets Fast only", async () => {
    getProfiles.mockResolvedValue(catalogue(true, ["fast"], "fast"));
    wrap(<ModelProfilePanel />);
    const panel = await screen.findByTestId("model-profiles");
    const state = (id: string) => panel.querySelector(`[data-profile="${id}"]`)!.getAttribute("data-authorized");
    expect([state("fast"), state("balanced"), state("advanced")]).toEqual(["true", "false", "false"]);
    expect(panel.querySelector('[data-profile="fast"]')!.textContent).toContain(t("planUx.models_isDefault"));
    expect(panel.querySelector('[data-profile="balanced"]')!.textContent).toContain(t("planUx.models_notAvailable"));
  });

  it("shows all three for Premium with Balanced as the default", async () => {
    getProfiles.mockResolvedValue(catalogue(true, ["fast", "balanced", "advanced"]));
    wrap(<ModelProfilePanel />);
    const panel = await screen.findByTestId("model-profiles");
    expect(Array.from(panel.querySelectorAll("[data-profile]")).map((n) => n.getAttribute("data-authorized"))).toEqual(["true", "true", "true"]);
    expect(panel.querySelector('[data-profile="balanced"]')!.textContent).toContain(t("planUx.models_isDefault"));
  });

  it("uses only the official names, no provider id, no price, no comparative claim, and ignores any browser-stored plan", async () => {
    localStorage.setItem("plan", "premium");
    localStorage.setItem("ask4mo.plan", JSON.stringify({ plan_code: "premium", entitlements: { premium_preview: { enabled: true } } }));
    getProfiles.mockResolvedValue({ ...catalogue(true, ["fast"], "fast"), profiles: catalogue(true, ["fast"], "fast").profiles.concat([{ id: "medium" as never, authorized: true, description: "x" }]) });
    wrap(<ModelProfilePanel />);
    const panel = await screen.findByTestId("model-profiles");
    expect(panel.querySelectorAll("[data-profile]")).toHaveLength(3);                // an unknown id (for example "medium") is never rendered
    expect(panel.querySelector('[data-profile="advanced"]')!.getAttribute("data-authorized")).toBe("false");   // browser storage cannot grant anything
    const text = panel.textContent ?? "";
    expect(text).not.toMatch(/openai\/|gpt|upgrade|checkout|price|€|\$|medium|better|faster|best|guarantee/i);
    for (const name of ["Fast", "Balanced", "Advanced"]) expect(text).toContain(name);
  });

  it("falls back to an honest section error if the catalogue cannot be read", async () => {
    getProfiles.mockRejectedValue(new Error("x"));
    wrap(<ModelProfilePanel />);
    await waitFor(() => expect(screen.getByText(t("planUx.models_loadError"))).toBeInTheDocument());
  });
});

describe("history access messaging", () => {
  it("shows nothing when the server reports no restriction (gate disabled) and nothing when nothing is hidden", () => {
    const { container, rerender } = wrap(<HistoryAccessNotice access={{ restricted: false, window: null, hidden_count: 0 }} shown={6} />);
    expect(container.textContent).toBe("");
    rerender(<I18nProvider initialLocale="en"><HistoryAccessNotice access={{ restricted: true, window: 3, hidden_count: 0 }} shown={3} /></I18nProvider>);
    expect(container.textContent).toBe("");
  });

  it("when restricted says the older interviews are retained, not deleted, with no upgrade or purchase action", () => {
    wrap(<HistoryAccessNotice access={{ restricted: true, window: 3, hidden_count: 4 }} shown={3} />);
    const box = screen.getByTestId("history-access-notice");
    expect(box.textContent).toContain("3");
    expect(box.textContent).toContain("4");
    expect(box.textContent).toMatch(/not been deleted/i);
    expect(box.textContent).not.toMatch(COMMERCIAL);
    expect(box.querySelectorAll("a")).toHaveLength(1);                                // only the link to the account page (data rights)
    expect(box.querySelector("a")!.getAttribute("href")).toBe("/account");
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: the restricted-history notice renders without raw keys`, () => {
      const { container } = wrap(<HistoryAccessNotice access={{ restricted: true, window: 3, hidden_count: 2 }} shown={3} />, locale);
      expect(container.textContent ?? "").not.toMatch(/planUx\.|\{n\}|\{shown\}/);
    });
  }
});

describe("an owned interview outside the history view (detail page)", () => {
  it("is explained as retained and never presented as deleted or as a paywall", async () => {
    historyGet.mockRejectedValue(new ApiError({ kind: "historyRestricted", status: 403, code: "history_not_available", message: "x" }));
    wrap(<HistoryDetailClient reportId="12" />);
    const box = await screen.findByTestId("history-restricted");
    expect(box.textContent).toContain(t("states.historyRestricted"));
    expect(box.textContent).toContain(t("planUx.detail_preserved"));
    expect(box.textContent).not.toMatch(COMMERCIAL);
    expect(screen.queryByText(t("history.notFoundTitle"))).toBeNull();                // not the "not found" state
  });

  it("a genuine 404 is still the distinct not-found state", async () => {
    historyGet.mockRejectedValue(new ApiError({ kind: "notFound", status: 404, code: "not_found", message: "x" }));
    wrap(<HistoryDetailClient reportId="99" />);
    await waitFor(() => expect(screen.getByText(t("history.notFoundTitle"))).toBeInTheDocument());
    expect(screen.queryByTestId("history-restricted")).toBeNull();
  });
});

describe("existing session transition (a profile this account can no longer use)", () => {
  it("explains why, confirms saved work and offers a NEW session, with no upgrade or checkout action", () => {
    wrap(<SessionTransitionNotice />);
    const box = screen.getByTestId("session-transition-notice");
    expect(box.textContent).toContain(t("planUx.transition_why"));
    expect(box.textContent).toContain(t("planUx.transition_preserved"));
    expect(box.textContent).toMatch(/not been switched/i);
    expect(box.textContent).toMatch(/nothing is deleted or regenerated/i);
    expect(box.textContent).not.toMatch(COMMERCIAL);
    const links = Array.from(box.querySelectorAll("a"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/practice"]);
    expect(box.querySelectorAll("button, form")).toHaveLength(0);
    expect(box.getAttribute("role")).toBe("region");
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: the transition notice is localized`, () => {
      const { container } = wrap(<SessionTransitionNotice />, locale);
      expect(container.textContent ?? "").not.toMatch(/planUx\./);
      expect(container.textContent).toContain(t("planUx.transition_newSession", locale));
    });
  }

  it("the interview controller flags a refused continuation without changing or regenerating anything", async () => {
    interviewGet.mockResolvedValue({ session_id: "s1", state: "AWAITING_ANSWER" });
    submitAnswer.mockRejectedValue(new ApiError({ kind: "modelProfileRestricted", status: 403, code: "model_profile_not_authorized", message: "x" }));
    const { result } = renderHook(() => useInterview("s1"));
    await waitFor(() => expect(result.current.state).not.toBeNull());
    expect(result.current.needsNewSession).toBe(false);
    let ok = true;
    await act(async () => { ok = await result.current.submitAnswer("my answer"); });
    expect(ok).toBe(false);
    expect(result.current.needsNewSession).toBe(true);
    expect(result.current.actionError).toBeNull();                                    // not shown as a generic error
    expect(result.current.state).toMatchObject({ session_id: "s1", state: "AWAITING_ANSWER" });   // the stored session state is unchanged
    expect(interviewGet).toHaveBeenCalledTimes(1);                                    // nothing was reloaded or regenerated
  });

  it("other failures keep the ordinary error path", async () => {
    interviewGet.mockResolvedValue({ session_id: "s1", state: "AWAITING_ANSWER" });
    submitAnswer.mockRejectedValue(new ApiError({ kind: "server", status: 500, code: "internal_error", message: "x" }));
    const { result } = renderHook(() => useInterview("s1"));
    await waitFor(() => expect(result.current.state).not.toBeNull());
    await act(async () => { await result.current.submitAnswer("a"); });
    expect(result.current.needsNewSession).toBe(false);
    expect(result.current.actionError).not.toBeNull();
  });
});
