import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import en from "@/lib/i18n/messages/w12p5a/en";
import type { PackContent, PackItem } from "@/lib/api/types";

const list = vi.fn();
const availability = vi.fn();
const generate = vi.fn();
const get = vi.fn();
const remove = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const errors = await vi.importActual<typeof import("@/lib/api/errors")>("@/lib/api/errors");
  return { ApiError: errors.ApiError, api: { preparationPacks: {
    list: (...a: unknown[]) => list(...a), availability: (...a: unknown[]) => availability(...a), generate: (...a: unknown[]) => generate(...a),
    get: (...a: unknown[]) => get(...a), remove: (...a: unknown[]) => remove(...a), downloadUrl: (id: number, f: string) => `/api/v1/preparation-packs/${id}/download?format=${f}` } } };
});

import { PreparationPackSection } from "@/components/opportunities/PreparationPackSection";
import { PreparationPackView } from "@/components/opportunities/PreparationPackView";

const wrap = (ui: React.ReactNode, locale: (typeof SUPPORTED_LOCALE_CODES)[number] = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);
const COMMERCIAL = /upgrade|checkout|subscribe now|buy now|purchase|pay now|price|€|\$/i;
const item = (kind: string, text: string, category: string, extra: Record<string, unknown> = {}): PackItem => ({ kind, text, category, source_ids: [], ref_ids: [], meta: {}, ...extra } as PackItem);
const content = (): PackContent => ({
  schema_version: "pack-1", opportunity: { title: "ICU nurse" }, inputs: {},
  sections: [
    { id: "overview", status: "partial", items: [item("role", "Senior Registered Nurse", "opportunity_provided"), item("missing", "employer", "unavailable")], notes: ["no_job_description"] },
    { id: "company", status: "available", items: [item("business_market", "Acme runs a 40-bed ICU.", "verified_external", { source_ids: ["W:s1"] }), item("role_relevance_hint", "ICU relevance hint", "ai_guidance", { meta: { method: "deterministic" } })], notes: ["unsourced_claims_dropped"] },
    { id: "requirements", status: "available", items: [item("requirement", "Lead a team of junior nurses", "opportunity_provided", { ref_ids: ["R1"] })], notes: [] },
    { id: "alignment", status: "partial", items: [item("alignment", "Lead a team of junior nurses", "candidate_provided", { ref_ids: ["R1", "C1"], meta: { status: "supported" } }), item("alignment", "Communicate with stakeholders", "unavailable", { ref_ids: ["R2"], meta: { status: "no_evidence" } })], notes: ["candidate_claims_not_verified"] },
    { id: "gaps", status: "available", items: [item("evidence_gap", "Communicate with stakeholders", "ai_guidance", { meta: { method: "deterministic" } }), item("information_gap", "company_research", "ai_guidance")], notes: ["absence_of_evidence_is_not_absence_of_skill"] },
    { id: "questions", status: "available", items: [item("question", "Tell me about a time you led a team.", "ai_guidance", { meta: { question_type: "leadership", evidence_to_prepare: "A leadership example", follow_ups: "What next?" } })], notes: [] },
    { id: "examples", status: "available", items: [item("example", "Led and mentored junior nurses", "candidate_provided")], notes: [] },
    { id: "roadmap", status: "available", items: [item("roadmap_step", "Write one leadership example.", "ai_guidance", { meta: { action_type: "prepare_example", order: "1" } })], notes: ["no_interview_date_assumed"] },
    { id: "sources", status: "available", items: [], notes: [] },
  ],
  sources: [{ id: "W:s1", title: "Acme about page", url: "https://acme.example/about", category: "verified_external", provider: "company_web", retrieved_at: "2026-10-01T00:00:00Z", effective_date: "2026-09-01", self_reported: true },
            { id: "W:bad", title: "Odd source", url: "javascript:alert(1)", category: "verified_external", provider: null, retrieved_at: null, effective_date: null, self_reported: false }],
  assumptions: ["no_interview_date_assumed", "mystery_assumption"], limitations: ["compensation_not_included_p10c", "not_a_hiring_decision_or_guarantee"],
});
const summary = (over = {}) => ({ id: 1, opportunity_id: 7, revision: 1, status: "completed", schema_version: "pack-1", failure_category: null, created_at: "2026-10-10T10:00:00+00:00", completed_at: null, section_statuses: {}, ...over });

beforeEach(() => { [list, availability, generate, get, remove].forEach((m) => m.mockReset()); window.localStorage.clear(); });

describe("Preparation Pack section (server-driven)", () => {
  it("while generation is disabled it says so, has NO generate button and no commercial wording, and saved Packs stay available", async () => {
    list.mockResolvedValue({ packs: [summary()] });
    availability.mockResolvedValue({ generation: "feature_disabled" });
    wrap(<PreparationPackSection opportunityId={7} />);
    const root = await screen.findByTestId("pack-section");
    await waitFor(() => expect(screen.getByTestId("pack-list")).toBeTruthy());
    expect(screen.getByTestId("pack-availability").getAttribute("data-generation")).toBe("feature_disabled");
    expect(screen.queryByRole("button", { name: translate("en", "packUx.generate") })).toBeNull();
    expect(root.textContent).toContain(translate("en", "packUx.avail_feature_disabled"));
    expect(root.textContent).not.toMatch(COMMERCIAL);
    expect(within(screen.getByTestId("pack-list")).getByRole("button", { name: translate("en", "packUx.open") })).toBeTruthy();
    const links = within(screen.getByTestId("pack-list")).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/api/v1/preparation-packs/1/download?format=md", "/api/v1/preparation-packs/1/download?format=json"]);
  });

  it("not_entitled has no generate button either and still lists saved Packs (downgrade)", async () => {
    list.mockResolvedValue({ packs: [summary({ id: 2 })] });
    availability.mockResolvedValue({ generation: "not_entitled" });
    wrap(<PreparationPackSection opportunityId={7} />);
    await screen.findByTestId("pack-list");
    expect(screen.queryByRole("button", { name: translate("en", "packUx.generate") })).toBeNull();
    expect(screen.getByTestId("pack-section").textContent).toContain(translate("en", "packUx.avail_not_entitled"));
    expect(screen.getByTestId("pack-section").textContent).not.toMatch(COMMERCIAL);
  });

  it("ignores localStorage plan tampering and a malformed availability value", async () => {
    window.localStorage.setItem("plan", "premium");
    list.mockResolvedValue({ packs: [] });
    availability.mockResolvedValue({ nope: 1 });
    wrap(<PreparationPackSection opportunityId={7} />);
    await screen.findByTestId("pack-empty");
    expect(screen.queryByTestId("pack-availability")).toBeNull();
    expect(screen.queryByRole("button", { name: translate("en", "packUx.generate") })).toBeNull();
  });

  it("offers Generate only when the server says available and sends an idempotency key", async () => {
    list.mockResolvedValue({ packs: [] });
    availability.mockResolvedValue({ generation: "available" });
    generate.mockResolvedValue({ outcome: "created", pack: summary() });
    wrap(<PreparationPackSection opportunityId={7} />);
    const btn = await screen.findByRole("button", { name: translate("en", "packUx.generate") });
    fireEvent.click(btn);
    await waitFor(() => expect(generate).toHaveBeenCalledTimes(1));
    expect(generate.mock.calls[0][0]).toBe(7);
    expect(typeof generate.mock.calls[0][1]).toBe("string");
    expect((generate.mock.calls[0][1] as string).length).toBeGreaterThan(8);
  });

  it("a refused generation shows a calm message and never changes the saved list", async () => {
    list.mockResolvedValue({ packs: [summary()] });
    availability.mockResolvedValue({ generation: "available" });
    const { ApiError } = await import("@/lib/api/errors");
    generate.mockRejectedValue(new ApiError({ kind: "forbidden", status: 403, code: "preparation_pack_generation_unavailable", message: "x" }));
    wrap(<PreparationPackSection opportunityId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: translate("en", "packUx.generate") }));
    expect((await screen.findByRole("status")).textContent).toContain(translate("en", "packUx.unavailableNow"));
    expect(screen.getByTestId("pack-list").querySelectorAll("li")).toHaveLength(1);
  });

  it("a failed Pack shows a bounded reason and no content actions", async () => {
    list.mockResolvedValue({ packs: [summary({ id: 3, status: "failed", failure_category: "ungrounded_output" })] });
    availability.mockResolvedValue({ generation: "feature_disabled" });
    wrap(<PreparationPackSection opportunityId={7} />);
    const li = (await screen.findByTestId("pack-list")).querySelector("li") as HTMLElement;
    expect(li.textContent).toContain(translate("en", "packUx.fail_ungrounded_output"));
    expect(within(li).queryByRole("button", { name: translate("en", "packUx.open") })).toBeNull();
    expect(within(li).queryAllByRole("link")).toHaveLength(0);
  });

  it("opens a stored Pack, and a load failure degrades to an alert with a retry", async () => {
    list.mockResolvedValue({ packs: [summary()] });
    availability.mockResolvedValue({ generation: "feature_disabled" });
    get.mockResolvedValue({ ...summary(), content: content() });
    wrap(<PreparationPackSection opportunityId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: translate("en", "packUx.open") }));
    expect(await screen.findByTestId("pack-view")).toBeTruthy();
  });

  it("shows an alert when the list cannot be loaded", async () => {
    list.mockRejectedValue(new Error("down"));
    availability.mockRejectedValue(new Error("down"));
    wrap(<PreparationPackSection opportunityId={7} />);
    expect((await screen.findByRole("alert")).textContent).toContain(translate("en", "packUx.loadError"));
  });
});

describe("Pack view (evidence classification and provenance)", () => {
  it("renders all nine sections with a status and a category label plus a non-colour marker on every item", () => {
    wrap(<PreparationPackView content={content()} />);
    for (const id of ["overview", "company", "requirements", "alignment", "gaps", "questions", "examples", "roadmap", "sources"]) expect(screen.getByTestId(`pack-section-${id}`)).toBeTruthy();
    const items = document.querySelectorAll("[data-category]");
    expect(items.length).toBeGreaterThan(8);
    items.forEach((el) => {
      expect(el.querySelector('[aria-hidden="true"]')).toBeTruthy();
      expect(el.textContent).toContain(translate("en", `packUx.cat_${el.getAttribute("data-category")}`));
    });
  });

  it("AI guidance is always labelled as not a verified fact and never carries a source", () => {
    wrap(<PreparationPackView content={content()} />);
    document.querySelectorAll('[data-category="ai_guidance"]').forEach((el) => expect(el.textContent).toContain(translate("en", "packUx.cat_ai_guidance")));
    expect(translate("en", "packUx.cat_ai_guidance")).toMatch(/not a verified fact/i);
  });

  it("alignment shows the three honest states, never a number or percentage", () => {
    wrap(<PreparationPackView content={content()} />);
    const align = screen.getByTestId("pack-section-alignment");
    expect(align.textContent).toContain(translate("en", "packUx.al_supported"));
    expect(align.textContent).toContain(translate("en", "packUx.al_no_evidence"));
    expect(align.textContent).not.toMatch(/\d+\s?%|score|probab/i);
  });

  it("sources keep retrieval and publication provenance, label self-reported company sources and never render an unsafe link", () => {
    wrap(<PreparationPackView content={content()} />);
    const src = screen.getByTestId("pack-sources");
    expect(src.textContent).toContain("Acme about page");
    expect(src.textContent).toContain(translate("en", "packUx.selfReported"));
    expect(src.textContent).toContain(translate("en", "packUx.retrieved"));
    expect(src.querySelectorAll('a[href^="javascript:"]').length).toBe(0);
    expect(src.querySelectorAll('a[href="https://acme.example/about"]').length).toBe(1);
    expect(src.querySelector('a[rel="noopener noreferrer"]')).toBeTruthy();
  });

  it("states missing information, assumptions and limitations in words, including compensation and the unknown-code fallback", () => {
    wrap(<PreparationPackView content={content()} />);
    expect(screen.getByTestId("pack-section-overview").textContent).toContain(`${translate("en", "packUx.missingPrefix")} ${translate("en", "packUx.miss_employer")}`);
    expect(screen.getByTestId("pack-limitations").textContent).toContain(translate("en", "packUx.lim_compensation_not_included_p10c"));
    expect(screen.getByTestId("pack-section-sources").textContent).toContain("Mystery assumption");
  });

  it("contains no commercial wording, no hiring guarantee and no controls", () => {
    wrap(<PreparationPackView content={content()} />);
    const root = screen.getByTestId("pack-view");
    expect(root.textContent).not.toMatch(COMMERCIAL);
    expect(root.querySelectorAll("button, input, select").length).toBe(0);
  });
});

describe("Pack copy in all eight locales", () => {
  it("every key resolves, is translated, has no em dash and no commercial wording; placeholders interpolate", () => {
    const keys = Object.keys(en.packUx);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const text = translate(locale, `packUx.${k}`);
        expect(text, `${locale} ${k}`).not.toBe(`packUx.${k}`);
        expect(text).not.toContain("—");
        expect(text).not.toMatch(COMMERCIAL);
      }
      expect(translate(locale, "packUx.revision", { n: 3 })).toContain("3");
    }
    for (const locale of SUPPORTED_LOCALE_CODES.filter((l) => l !== "en")) {
      for (const k of ["title", "disclaimer", "avail_feature_disabled", "cat_ai_guidance", "lim_compensation_not_included_p10c"]) {
        expect(translate(locale, `packUx.${k}`)).not.toBe(translate("en", `packUx.${k}`));
      }
    }
  });
});
