import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { ACTIVE_CANDIDATE_LOCALES, type AppLocale } from "@/lib/i18n/locales";

// REQ-LANG-05 (engineering verification only, not native review): the real Story Bank, picker and sharing panel render and work
// in every selectable Candidate language, every visible string comes from that language's catalogue, and the state labels stay distinct.

const m = { list: vi.fn(), create: vi.fn(), tags: vi.fn(), opps: vi.fn(), ws: vi.fn(), shares: vi.fn() };
vi.mock("@/lib/api/client", () => ({
  api: {
    stories: { list: (...a: unknown[]) => m.list(...a), create: (...a: unknown[]) => m.create(...a), tags: (...a: unknown[]) => m.tags(...a), suggest: vi.fn().mockResolvedValue({ suggestions: [] }) },
    opportunities: { list: (...a: unknown[]) => m.opps(...a) },
    workspaces: { list: (...a: unknown[]) => m.ws(...a) },
    shares: { mine: (...a: unknown[]) => m.shares(...a), create: vi.fn(), revoke: vi.fn() },
  },
}));
vi.mock("@/lib/api/errors", () => ({ ApiError: class extends Error { userMessage = "x"; } }));

import { StoryBank } from "@/components/stories/StoryBank";
import { StoryPicker } from "@/components/stories/StoryPicker";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import type { StoryOut } from "@/lib/api/types";

const base = { situation: "S", task: "T", action: "A".repeat(50), result: "R 5", competencies: ["x"], evidence_claim_ids: [], evidence_answer_ids: [], opportunity_id: null, archived_at: null, use_count: 0, last_used_at: null, quality_prompts: [], updated_at: null };
const states: StoryOut[] = [
  { ...base, id: 1, title: "One", status: "source_backed", evidence_state: "verified", verification: "evidence_verified", confirmed_at: null },
  { ...base, id: 2, title: "Two", status: "user_created", evidence_state: "none", verification: "unverified", confirmed_at: null },
  { ...base, id: 3, title: "Three", status: "user_created", evidence_state: "none", verification: "self_confirmed", confirmed_at: "x" },
  { ...base, id: 4, title: "Four", status: "user_created", evidence_state: "none", verification: "answer_linked", confirmed_at: null },
  { ...base, id: 5, title: "Five", status: "source_backed", evidence_state: "source_revoked", verification: "source_revoked", confirmed_at: null, quality_prompts: ["result_no_figure", "no_tags"] },
];

beforeEach(() => {
  m.list.mockResolvedValue({ stories: states });
  m.tags.mockResolvedValue({ tags: [] });
  m.opps.mockResolvedValue({ opportunities: [] });
  m.ws.mockResolvedValue({ workspaces: [{ id: 4, name: "Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
  m.shares.mockResolvedValue({ shares: [] });
});
afterEach(() => vi.clearAllMocks());

const LOCALES = [...ACTIVE_CANDIDATE_LOCALES] as AppLocale[];

describe.each(LOCALES)("Story Bank in %s", (locale) => {
  const T = (k: string, v?: Record<string, string | number>) => translate(locale, k, v);

  it("renders the list, the five distinct state labels, the quality prompts and the controls from this language's catalogue", async () => {
    render(<I18nProvider initialLocale={locale}><StoryBank /></I18nProvider>);
    await screen.findByText("One");
    const row = (t: string) => screen.getByText(t).closest("li") as HTMLElement;
    const labels = [
      [row("One"), T("documents.evVerified")], [row("Two"), T("documents.evNone")], [row("Three"), T("storyBank.v_self_confirmed")],
      [row("Four"), T("storyBank.v_answer_linked")], [row("Five"), T("documents.evRevoked")],
    ] as const;
    for (const [el, label] of labels) expect(within(el).getByText(label)).toBeInTheDocument();
    expect(new Set(labels.map(([, l]) => l)).size).toBe(5);                                  // five different words, in every language
    expect(within(row("Five")).getByTestId("quality-prompts").textContent).toContain(T("storyBank.q_result_no_figure"));
    expect(screen.getByRole("button", { name: T("storyBank.newStory") })).toBeInTheDocument();
    expect(screen.getByRole("search", { name: T("storyBank.searchRegion") })).toBeInTheDocument();
    expect(screen.getByTestId("story-count").textContent).toBe(T("storyBank.resultsCount", { n: 5 }));
    if (locale !== "en") {
      expect(T("storyBank.newStory")).not.toBe(translate("en", "storyBank.newStory"));         // genuinely translated, not an English fallback
      expect(T("storyBank.pickerConsent")).not.toBe(translate("en", "storyBank.pickerConsent"));
    }
  });

  it("creates a story: localized validation, localized labels, and the create call carries the typed words", async () => {
    m.list.mockResolvedValue({ stories: [] });
    m.create.mockResolvedValue({ ...states[1], id: 9 });
    render(<I18nProvider initialLocale={locale}><StoryBank /></I18nProvider>);
    await userEvent.click(await screen.findByRole("button", { name: T("storyBank.newStory") }));
    await userEvent.click(screen.getByRole("button", { name: T("common.save") }));
    expect(screen.getByRole("alert").textContent).toBe(T("storyBank.titleRequired"));
    await userEvent.type(screen.getByLabelText(T("storyBank.fieldTitle")), "Ein Titel");
    await userEvent.type(screen.getByLabelText(T("storyBank.fieldResult")), "Ergebnis");
    await userEvent.click(screen.getByRole("button", { name: T("common.save") }));
    await waitFor(() => expect(m.create).toHaveBeenCalled());
    expect(m.create.mock.calls[0][0]).toMatchObject({ title: "Ein Titel", result: "Ergebnis", status: "user_created" });
  });

  it("the Practice picker and the sharing panel are localized and keep consent explicit", async () => {
    function Harness() {
      const [ids, setIds] = (require("react") as typeof import("react")).useState<number[]>([]);
      const [c, setC] = (require("react") as typeof import("react")).useState(false);
      return <StoryPicker roleText="x" value={ids} onChange={setIds} consent={c} onConsent={setC} />;
    }
    const { unmount } = render(<I18nProvider initialLocale={locale}><Harness /></I18nProvider>);
    await screen.findByText("One");
    expect(screen.getByRole("group", { name: T("storyBank.pickerTitle") })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: new RegExp("One") }));
    expect(screen.getByRole("checkbox", { name: T("storyBank.pickerConsent") })).not.toBeChecked();
    expect(screen.getByText(T("storyBank.pickerSelected", { n: 1, max: 5 }))).toBeInTheDocument();
    unmount();
    render(<I18nProvider initialLocale={locale}><StoryBank /></I18nProvider>);
    await screen.findByText("One");
    await userEvent.click(within(screen.getByText("One").closest("li") as HTMLElement).getByRole("button", { name: T("storyBank.shareToggle") }));
    expect(await screen.findByText(T("storyBank.shareExplain"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T("storyBank.shareAction") })).toBeDisabled();
  });
});
