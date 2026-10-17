import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import en from "@/lib/i18n/messages/w12p4b/en";

const getOverview = vi.fn();
const getCompare = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const errors = await vi.importActual<typeof import("@/lib/api/errors")>("@/lib/api/errors");
  return { ApiError: errors.ApiError, api: { progressAnalytics: { get: (...a: unknown[]) => getOverview(...a), compare: (...a: unknown[]) => getCompare(...a) } } };
});

import { PremiumAnalytics } from "@/components/progress/PremiumAnalytics";

const wrap = (locale: (typeof SUPPORTED_LOCALE_CODES)[number] = "en") =>
  render(<I18nProvider initialLocale={locale}><PremiumAnalytics fallback={<p data-testid="planned">planned</p>} /></I18nProvider>);
const COMMERCIAL = /upgrade|checkout|subscribe now|buy now|purchase|pay now|price|€|\$/i;
const dim = (v: number | null) => ({ average: v, answers_measured: v === null ? 0 : 3 });
const point = (id: number, score: number | null, extra = {}) => ({ interview_id: id, date: `2026-01-0${id}T00:00:00+00:00`, practice_score: score, answers_scored: score === null ? 0 : 3, low_sample: false,
  report_score: null, target_role: "Nurse", career_level: "mid", opportunity_id: null, question_count: 3, rubric: {}, ...extra });
const ready = (over = {}) => ({ state: "ready", truncated: false, analyzed_limit: 500, counts: { completed_interviews: 2, scored_interviews: 2, unscored_interviews: 0 },
  points: [point(1, 60), point(2, 75)], summary: { first_score: 60, latest_score: 75, change: 15, direction: "improved", comparable_context: true, average_score: 67.5, best_score: 75 },
  distribution: { "0-39": 0, "40-59": 0, "60-79": 2, "80-100": 0 },
  rubric: { dimensions: [{ id: "relevance", average: 8, answers_measured: 6 }, { id: "structure", average: 5, answers_measured: 6 }, { id: "evidence", average: null, answers_measured: 0 }], strongest: "relevance", weakest: "structure" },
  by_question_type: [{ type: "case_study", average_score: 70, answers_scored: 6 }], frequency: { last_30_days: 2, last_90_days: 2, by_month: [] },
  improvement_areas: [{ area: "clarity", count: 3, origin: "model_generated" }], filters: { roles: ["Nurse"], opportunity_ids: [] }, methodology: [], limitations: [], ...over });

beforeEach(() => { getOverview.mockReset(); getCompare.mockReset(); window.localStorage.clear(); });

describe("Premium analytics presentation (server measurements only)", () => {
  it.each(["feature_disabled", "not_entitled"])("renders the planned fallback and nothing else for %s", async (state) => {
    getOverview.mockResolvedValue({ state, points: [], truncated: false });
    wrap();
    await waitFor(() => expect(getOverview).toHaveBeenCalled());
    expect(screen.getByTestId("planned")).toBeTruthy();
    expect(screen.queryByTestId("premium-analytics")).toBeNull();
    expect(screen.queryByTestId("analytics-chart")).toBeNull();
  });

  it("falls back on a failed or malformed response and ignores localStorage plan tampering", async () => {
    window.localStorage.setItem("plan", "premium");
    getOverview.mockRejectedValue(new Error("down"));
    wrap();
    await waitFor(() => expect(getOverview).toHaveBeenCalled());
    expect(screen.getByTestId("planned")).toBeTruthy();
    getOverview.mockResolvedValue({ nope: 1 });
    wrap();
    await waitFor(() => expect(getOverview).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("premium-analytics")).toBeNull();
  });

  it("no_data shows an explicit empty state with no chart", async () => {
    getOverview.mockResolvedValue({ ...ready(), state: "no_data", points: [], summary: null, counts: { completed_interviews: 0, scored_interviews: 0, unscored_interviews: 0 } });
    wrap();
    const root = await screen.findByTestId("premium-analytics");
    expect(root.textContent).toContain(translate("en", "analyticsUx.noData"));
    expect(screen.queryByTestId("analytics-chart")).toBeNull();
  });

  it("insufficient_data explains what is needed and shows no change figure", async () => {
    getOverview.mockResolvedValue(ready({ state: "insufficient_data", points: [point(1, 70)], summary: { first_score: 70, latest_score: 70, change: null, direction: null, comparable_context: null, average_score: 70, best_score: 70 } }));
    wrap();
    expect(await screen.findByTestId("analytics-insufficient")).toBeTruthy();
    expect(screen.queryByTestId("analytics-change")).toBeNull();
    expect(screen.queryByTestId("analytics-compare")).toBeNull();
  });

  it("ready shows the server's trend, a labelled chart, a text-alternative table, the change with a non-colour marker and the rubric", async () => {
    getOverview.mockResolvedValue(ready());
    wrap();
    await screen.findByTestId("premium-analytics");
    expect(screen.getByTestId("analytics-chart").getAttribute("role")).toBe("img");
    expect(screen.getByTestId("analytics-chart").getAttribute("aria-label")).toContain("60");
    const rows = within(screen.getByTestId("analytics-table")).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(screen.getByTestId("analytics-change").textContent).toMatch(/\+15.*▲/);
    const rubric = screen.getByTestId("analytics-rubric");
    expect(rubric.querySelectorAll("li")).toHaveLength(3);
    expect(rubric.querySelector('[data-dimension="evidence"]')?.textContent).toContain(translate("en", "analyticsUx.notMeasured"));
    expect(rubric.textContent).toContain(translate("en", "analyticsUx.highest"));
    expect(screen.getByTestId("premium-analytics").textContent).not.toMatch(COMMERCIAL);
    expect(screen.getByTestId("premium-analytics").querySelectorAll("a").length).toBe(0);
  });

  it("an unscored point is a missing value, never a zero", async () => {
    getOverview.mockResolvedValue(ready({ points: [point(1, null), point(2, 75)] }));
    wrap();
    const table = await screen.findByTestId("analytics-table");
    expect(within(table).getAllByRole("row")[1].textContent).toContain(translate("en", "analyticsUx.notMeasured"));
  });

  it("states truncation and warns about a differing context", async () => {
    getOverview.mockResolvedValue(ready({ truncated: true, summary: { first_score: 60, latest_score: 75, change: 15, direction: "improved", comparable_context: false, average_score: 67.5, best_score: 75 } }));
    wrap();
    expect((await screen.findByTestId("analytics-truncated")).textContent).toContain("500");
    expect(screen.getByTestId("premium-analytics").textContent).toContain(translate("en", "analyticsUx.contextDiffers"));
  });

  it("compares two chosen interviews using only the server result and shows limitations", async () => {
    getOverview.mockResolvedValue(ready());
    getCompare.mockResolvedValue({ state: "ready", base: point(1, 60), target: point(2, 45), score_difference: -15, direction: "declined", comparability: "limited",
      comparability_reasons: ["different_role", "low_sample"], limitations: [], methodology: [], rubric_differences: [{ id: "relevance", base: 8, target: 5, difference: -3 }, { id: "structure", base: null, target: 5, difference: null }] });
    wrap();
    await screen.findByTestId("analytics-compare");
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareBase")), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareTarget")), { target: { value: "2" } });
    const result = await screen.findByTestId("analytics-compare-result");
    expect(getCompare).toHaveBeenCalledWith(1, 2);
    expect(result.textContent).toContain("-15");
    expect(result.textContent).toContain("▼");
    expect(result.textContent).toContain(translate("en", "analyticsUx.rDifferentRole"));
    expect(result.textContent).toContain(translate("en", "analyticsUx.compareLimits"));
    expect(result.textContent).toContain(translate("en", "analyticsUx.notMeasured"));
  });

  it("does not request a comparison for the same interview twice", async () => {
    getOverview.mockResolvedValue(ready());
    wrap();
    await screen.findByTestId("analytics-compare");
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareBase")), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareTarget")), { target: { value: "1" } });
    expect(getCompare).not.toHaveBeenCalled();
  });

  it("a failed comparison shows a calm alert", async () => {
    getOverview.mockResolvedValue(ready());
    getCompare.mockRejectedValue(new Error("x"));
    wrap();
    await screen.findByTestId("analytics-compare");
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareBase")), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(translate("en", "analyticsUx.compareTarget")), { target: { value: "2" } });
    expect((await screen.findByRole("alert")).textContent).toContain(translate("en", "analyticsUx.compareError"));
  });

  it("offers an opportunity filter only when links exist and re-queries the server", async () => {
    getOverview.mockResolvedValue(ready({ filters: { roles: [], opportunity_ids: [7] } }));
    wrap();
    const select = await screen.findByLabelText(translate("en", "analyticsUx.filterLabel"));
    fireEvent.change(select, { target: { value: "7" } });
    await waitFor(() => expect(getOverview).toHaveBeenLastCalledWith(7));
  });
});

describe("analytics copy in all eight locales", () => {
  it("every key resolves, is translated, has no em dash and no commercial wording", () => {
    const keys = Object.keys(en.analyticsUx);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const text = translate(locale, `analyticsUx.${k}`);
        expect(text, `${locale} ${k}`).not.toBe(`analyticsUx.${k}`);
        expect(text).not.toContain("—");
        expect(text).not.toMatch(COMMERCIAL);
      }
      expect(translate(locale, "analyticsUx.chartLabel", { n: 2, first: 1, latest: 2 })).not.toContain("{");
    }
    for (const locale of SUPPORTED_LOCALE_CODES.filter((l) => l !== "en")) {
      expect(translate(locale, "analyticsUx.title")).not.toBe(translate("en", "analyticsUx.title"));
    }
  });
});
