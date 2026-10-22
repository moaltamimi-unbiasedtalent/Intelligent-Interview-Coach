import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 04A Story Bank (REQ-OWN-06): the editor, the list with search and filters, honest verification labels, archive and delete,
// evidence linking, the Practice picker with consent, and eight-locale parity of every new string. The network is mocked.

const m = {
  list: vi.fn(), search: vi.fn(), tags: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), archive: vi.fn(), restore: vi.fn(),
  confirm: vi.fn(), unconfirm: vi.fn(), attach: vi.fn(), detach: vi.fn(), suggest: vi.fn(), answers: vi.fn(),
  docs: vi.fn(), docGet: vi.fn(), opps: vi.fn(), wsList: vi.fn(), sharesMine: vi.fn(), shareCreate: vi.fn(), shareRevoke: vi.fn(),
};

vi.mock("@/lib/api/client", () => ({
  api: {
    stories: {
      list: (...a: unknown[]) => m.list(...a), search: (...a: unknown[]) => m.search(...a), tags: (...a: unknown[]) => m.tags(...a),
      create: (...a: unknown[]) => m.create(...a), update: (...a: unknown[]) => m.update(...a), remove: (...a: unknown[]) => m.remove(...a),
      archive: (...a: unknown[]) => m.archive(...a), restore: (...a: unknown[]) => m.restore(...a), confirm: (...a: unknown[]) => m.confirm(...a),
      unconfirm: (...a: unknown[]) => m.unconfirm(...a), attachEvidence: (...a: unknown[]) => m.attach(...a), detachEvidence: (...a: unknown[]) => m.detach(...a),
      suggest: (...a: unknown[]) => m.suggest(...a), answerSources: (...a: unknown[]) => m.answers(...a),
    },
    documents: { list: (...a: unknown[]) => m.docs(...a), get: (...a: unknown[]) => m.docGet(...a) },
    opportunities: { list: (...a: unknown[]) => m.opps(...a) },
    workspaces: { list: (...a: unknown[]) => m.wsList(...a) },
    shares: { mine: (...a: unknown[]) => m.sharesMine(...a), create: (...a: unknown[]) => m.shareCreate(...a), revoke: (...a: unknown[]) => m.shareRevoke(...a) },
  },
}));
vi.mock("@/lib/api/errors", () => ({ ApiError: class extends Error { userMessage = "server said no"; } }));

import { StoryBank } from "@/components/stories/StoryBank";
import { StoryPicker, isUsableStory } from "@/components/stories/StoryPicker";
import type { StoryOut } from "@/lib/api/types";

const story = (o: Partial<StoryOut> & { id: number; title: string }): StoryOut => ({
  situation: null, task: null, action: null, result: null, competencies: [], status: "user_created", evidence_state: "none",
  evidence_claim_ids: [], verification: "unverified", evidence_answer_ids: [], opportunity_id: null, archived_at: null, confirmed_at: null,
  use_count: 0, last_used_at: null, quality_prompts: [], updated_at: null, ...o,
});

beforeEach(() => {
  m.tags.mockResolvedValue({ tags: ["Leadership", "Planning"] });
  m.opps.mockResolvedValue({ opportunities: [{ id: 3, title: "Nurse at Acme", target_role: "Nurse", status: "active" }] });
  m.docs.mockResolvedValue({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1 }] });
  m.docGet.mockResolvedValue({ id: 1, claims: [{ id: 11, display_text: "Reduced latency", review_state: "accepted" }, { id: 12, display_text: "Rejected claim", review_state: "rejected" }] });
  m.answers.mockResolvedValue({ sources: [{ answer_id: 7, interview_id: 2, position: 0, question: "Tell me about a challenge." }] });
});
afterEach(() => vi.clearAllMocks());

describe("StoryBank: honest states", () => {
  it("shows the empty state with a way to start, and the filtered-empty state when a filter matches nothing", async () => {
    m.list.mockResolvedValue({ stories: [] });
    m.search.mockResolvedValue({ stories: [] });
    render(<StoryBank />);
    expect(await screen.findByText(/No stories yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New story" })).toBeEnabled();
    await userEvent.type(screen.getByLabelText("Search"), "zzz");
    expect(await screen.findByText("No story matches these filters.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText(/No stories yet/)).toBeInTheDocument();
  });

  it("shows a retryable error and keeps the page usable when loading fails", async () => {
    m.list.mockRejectedValueOnce(new Error("boom")).mockResolvedValue({ stories: [story({ id: 1, title: "Recovered" })] });
    render(<StoryBank />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("We could not load your stories");
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Recovered")).toBeInTheDocument();
  });

  it("announces the number of stories shown in a polite live region", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "A" }), story({ id: 2, title: "B" })] });
    render(<StoryBank />);
    await screen.findByText("A");
    const count = screen.getByTestId("story-count");
    expect(count).toHaveAttribute("aria-live", "polite");
    expect(count.textContent).toBe("2 stories shown");
  });
});

describe("StoryBank: nothing is called verified without evidence", () => {
  it("labels the five states distinctly; a confirmation never reads as evidence", async () => {
    m.list.mockResolvedValue({ stories: [
      story({ id: 1, title: "S1", status: "source_backed", evidence_state: "verified", verification: "evidence_verified", evidence_claim_ids: [4] }),
      story({ id: 2, title: "S2" }),
      story({ id: 3, title: "S3", verification: "self_confirmed", confirmed_at: "2026-10-01T00:00:00Z" }),
      story({ id: 4, title: "S4", verification: "answer_linked", evidence_answer_ids: [9] }),
      story({ id: 5, title: "S5", status: "source_backed", evidence_state: "source_revoked", verification: "source_revoked" }),
    ] });
    render(<StoryBank />);
    await screen.findByText("S1");
    const row = (t: string) => screen.getByText(t).closest("li") as HTMLElement;
    expect(within(row("S1")).getByText("Supporting evidence available")).toBeInTheDocument();
    expect(within(row("S2")).getByText("No supporting source")).toBeInTheDocument();
    expect(within(row("S3")).getByText("Confirmed by you")).toBeInTheDocument();
    expect(within(row("S3")).queryByText("Supporting evidence available")).toBeNull();
    expect(within(row("S3")).getByTestId("verification-help").textContent).toContain("not evidence");
    expect(within(row("S4")).getByText("Linked to your practice answer")).toBeInTheDocument();
    expect(within(row("S4")).queryByText("Supporting evidence available")).toBeNull();
    expect(within(row("S5")).getByText("Supporting source removed")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Evidence verified|verified by|independently verified|fact[- ]checked/);
  });

  it("shows quality prompts that only ask for what is missing", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Thin", quality_prompts: ["result_missing", "action_thin", "result_no_figure"] })] });
    render(<StoryBank />);
    const box = await screen.findByTestId("quality-prompts");
    expect(box.textContent).toContain("Add the result");
    expect(box.textContent).toContain("do not estimate");
  });
});

describe("StoryBank: create, edit, search, archive, delete", () => {
  it("validates the title, then creates a story from the candidate's own words with tags and an Opportunity link", async () => {
    m.list.mockResolvedValue({ stories: [] });
    m.create.mockResolvedValue(story({ id: 9, title: "My story" }));
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "New story" }));
    const title = screen.getByLabelText("Title");
    await waitFor(() => expect(title).toHaveFocus());
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(m.create).not.toHaveBeenCalled();
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert").textContent).toBe("Give the story a title.");
    await userEvent.type(title, "My story");
    await userEvent.type(screen.getByLabelText("Situation"), "A busy ward");
    await userEvent.type(screen.getByLabelText("Competency tags"), "Leadership, planning ,");
    await userEvent.selectOptions(screen.getByLabelText("Opportunity", { selector: "form select" }), "3");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.create).toHaveBeenCalledTimes(1));
    expect(m.create.mock.calls[0][0]).toMatchObject({
      title: "My story", status: "user_created", situation: "A busy ward", task: "", competencies: ["Leadership", "planning"], opportunity_id: 3,
    });
    expect(Object.keys(m.create.mock.calls[0][0])).not.toContain("evidence_state");        // the client never sets verification
  });

  it("closes the editor on Escape and returns focus to the New story button", async () => {
    m.list.mockResolvedValue({ stories: [] });
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "New story" }));
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByLabelText("Title")).toBeNull());
    await waitFor(() => expect(screen.getByRole("button", { name: "New story" })).toHaveFocus());
  });

  it("edits an existing story and sends an explicit null to clear the Opportunity link", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Old", result: "Done", opportunity_id: 3 })] });
    m.update.mockResolvedValue(story({ id: 1, title: "Old" }));
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await userEvent.selectOptions(screen.getByLabelText("Opportunity", { selector: "form select" }), "");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.update).toHaveBeenCalled());
    expect(m.update.mock.calls[0][0]).toBe(1);
    expect(m.update.mock.calls[0][1]).toMatchObject({ title: "Old", result: "Done", opportunity_id: null });
  });

  it("searches through the POST endpoint (never the URL) and filters by how the story is supported", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "One" })] });
    m.search.mockResolvedValue({ stories: [story({ id: 2, title: "Two" })] });
    render(<StoryBank />);
    await screen.findByText("One");
    expect(m.search).not.toHaveBeenCalled();                                              // unfiltered = the plain list
    await userEvent.type(screen.getByLabelText("Search"), "lead");
    await waitFor(() => expect(m.search).toHaveBeenCalledWith({ q: "lead", archived: "active" }));
    await screen.findByText("Two");
    await userEvent.selectOptions(screen.getByLabelText("How it is verified"), "self_confirmed");
    await waitFor(() => expect(m.search).toHaveBeenLastCalledWith({ q: "lead", verification: "self_confirmed", archived: "active" }));
    await userEvent.selectOptions(screen.getByLabelText("Tag"), "Planning");
    await waitFor(() => expect(m.search).toHaveBeenLastCalledWith({ q: "lead", tag: "Planning", verification: "self_confirmed", archived: "active" }));
    expect(screen.getByRole("search", { name: "Search and filter your stories" })).toBeInTheDocument();
  });

  it("archives (the card leaves the active list), then restores from the archived view", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Keep me" })] });
    m.archive.mockResolvedValue(story({ id: 1, title: "Keep me", archived_at: "2026-10-01T00:00:00Z" }));
    m.restore.mockResolvedValue(story({ id: 1, title: "Keep me" }));
    m.search.mockResolvedValue({ stories: [story({ id: 1, title: "Keep me", archived_at: "2026-10-01T00:00:00Z" })] });
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Archive" }));
    await waitFor(() => expect(screen.queryByText("Keep me")).toBeNull());
    await userEvent.selectOptions(screen.getByLabelText("Show"), "archived");
    expect(await screen.findByText("Keep me")).toBeInTheDocument();
    expect(screen.getByText(/Archived: hidden from search/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();                    // an archived story is read-only until restored
    await userEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(m.restore).toHaveBeenCalledWith(1));
  });

  it("deletes only after an explicit confirmation that says what is removed", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Doomed" })] });
    m.remove.mockResolvedValue({ deleted: true });
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(m.remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog.textContent).toContain("any sharing of it ends");
    expect(dialog.textContent).toContain("preparation packs");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(m.remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Doomed")).toBeNull());
  });

  it("links a document item as evidence and a confirmation is a separate action", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Linkable" })] });
    m.attach.mockResolvedValue(story({ id: 1, title: "Linkable", verification: "evidence_verified", evidence_state: "verified", evidence_claim_ids: [11] }));
    m.confirm.mockResolvedValue(story({ id: 1, title: "Linkable", verification: "self_confirmed", confirmed_at: "2026-10-01T00:00:00Z" }));
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Link evidence", expanded: false }));
    await userEvent.selectOptions(await screen.findByLabelText("Document"), "1");
    const claim = await screen.findByLabelText("Item");
    expect(within(claim).queryByText("Rejected claim")).toBeNull();                       // a rejected item can never be linked
    await userEvent.selectOptions(claim, "11");
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    await waitFor(() => expect(m.attach).toHaveBeenCalledWith(1, "claim", 11));
    expect(await screen.findByText("Supporting evidence available")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove link" })).toBeInTheDocument();
  });

  it("links a practice answer by question text only", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Linkable" })] });
    m.attach.mockResolvedValue(story({ id: 1, title: "Linkable", verification: "answer_linked", evidence_answer_ids: [7] }));
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Link evidence", expanded: false }));
    await userEvent.click(screen.getByLabelText("A practice answer"));
    const sel = await screen.findByLabelText("Practice answer");
    expect(within(sel).getByText(/Question 1: Tell me about a challenge/)).toBeInTheDocument();
    await userEvent.selectOptions(sel, "7");
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    await waitFor(() => expect(m.attach).toHaveBeenCalledWith(1, "answer", 7));
    expect(await screen.findByText("Linked to your practice answer")).toBeInTheDocument();
  });

  it("shows a server error without losing the story when an action fails", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Stays" })] });
    m.confirm.mockRejectedValue(new Error("boom"));
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Confirm this is accurate" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Stays")).toBeInTheDocument();
  });
});

describe("StoryPicker (Practice reuse with consent)", () => {
  const stories = [
    story({ id: 1, title: "Alpha", competencies: ["Leadership"] }),
    story({ id: 2, title: "Beta", verification: "evidence_verified", evidence_state: "verified" }),
    story({ id: 3, title: "Gamma", status: "model_suggested" }),
    story({ id: 4, title: "Delta", status: "source_backed", evidence_state: "source_revoked", verification: "source_revoked" }),
  ];

  function Harness({ initial = [] as number[] }) {
    const [ids, setIds] = (require("react") as typeof import("react")).useState<number[]>(initial);
    const [consent, setConsent] = (require("react") as typeof import("react")).useState(false);
    return (
      <>
        <StoryPicker roleText="Senior Nurse Leadership" opportunityId={3} value={ids} onChange={setIds} consent={consent} onConsent={setConsent} />
        <output data-testid="state">{JSON.stringify({ ids, consent })}</output>
      </>
    );
  }
  const state = () => JSON.parse(screen.getByTestId("state").textContent ?? "{}");

  it("mirrors the server rule: unconfirmed suggestions and source-removed stories cannot be chosen", () => {
    expect(isUsableStory(stories[0])).toBe(true);
    expect(isUsableStory(stories[2])).toBe(false);
    expect(isUsableStory(stories[3])).toBe(false);
    expect(isUsableStory({ ...stories[2], confirmed_at: "x" })).toBe(true);
    expect(isUsableStory({ ...stories[0], archived_at: "x" })).toBe(false);
  });

  it("emits ids only; the consent box appears with the first choice, is required, and resets when the last story is unchecked", async () => {
    m.list.mockResolvedValue({ stories });
    render(<Harness />);
    await screen.findByText("Alpha");
    expect(screen.queryByText(/I understand that the stories I selected/)).toBeNull();
    expect(screen.getByRole("checkbox", { name: /Gamma/ })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /Delta/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /Alpha/ }));
    expect(state()).toEqual({ ids: [1], consent: false });
    const consent = screen.getByRole("checkbox", { name: /I understand that the stories I selected/ });
    await userEvent.click(consent);
    expect(state().consent).toBe(true);
    await userEvent.click(screen.getByRole("checkbox", { name: /Alpha/ }));
    expect(state()).toEqual({ ids: [], consent: false });
    expect(screen.getByText("0 of 5 selected")).toBeInTheDocument();
  });

  it("a suggestion is only a proposal: it selects nothing and carries the matched words", async () => {
    m.list.mockResolvedValue({ stories });
    m.suggest.mockResolvedValue({ suggestions: [{ id: 1, title: "Alpha", verification: "unverified", competencies: ["Leadership"], matched: ["leadership"], requires_approval: true }] });
    render(<Harness />);
    await screen.findByText("Alpha");
    await userEvent.click(screen.getByRole("button", { name: "Suggest stories for this role" }));
    await waitFor(() => expect(m.suggest).toHaveBeenCalled());
    expect(m.suggest.mock.calls[0][0]).toEqual({ terms: ["senior", "nurse", "leadership"], opportunity_id: 3 });
    expect(await screen.findByText("Suggested")).toBeInTheDocument();
    expect(screen.getByText("Matches: leadership")).toBeInTheDocument();
    expect(state()).toEqual({ ids: [], consent: false });
  });

  it("stops at five stories", async () => {
    const many = Array.from({ length: 7 }, (_, i) => story({ id: i + 1, title: `Story ${i + 1}` }));
    m.list.mockResolvedValue({ stories: many });
    render(<Harness initial={[1, 2, 3, 4, 5]} />);
    await screen.findByText("Story 1");
    expect(screen.getByRole("checkbox", { name: /Story 6/ })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /Story 1/ })).toBeEnabled();
    expect(screen.getByText(/You can choose up to 5 stories/)).toBeInTheDocument();
  });

  it("is honest and non-blocking when stories cannot load, and when there are none", async () => {
    m.list.mockRejectedValue(new Error("down"));
    const { unmount } = render(<Harness />);
    expect(await screen.findByText(/could not load your stories/)).toBeInTheDocument();
    unmount();
    m.list.mockResolvedValue({ stories: [] });
    render(<Harness />);
    expect(await screen.findByText(/You have no stories yet/)).toBeInTheDocument();
  });
});

describe("StoryBank: sharing is an explicit, view-only, revocable grant", () => {
  it("explains what a member can see, shares only on the click, and stops sharing on request", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 1, title: "Shareable" })] });
    let grants: unknown[] = [];
    m.wsList.mockResolvedValue({ workspaces: [{ id: 4, name: "Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
    m.sharesMine.mockImplementation(async () => ({ shares: grants }));
    m.shareCreate.mockImplementation(async () => { grants = [{ id: 40, owner_user_id: 1, workspace_id: 4, resource_type: "story", resource_id: "1", permission: "view", status: "active", created_at: null, revoked_at: null }]; return { share_id: 40, status: "active" }; });
    m.shareRevoke.mockImplementation(async () => { grants = []; return { status: "revoked" }; });
    render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Share", expanded: false }));
    expect(await screen.findByText(/view-only access to this story/)).toBeInTheDocument();
    expect(screen.getByText(/never see your documents, your practice answers or your Opportunities/)).toBeInTheDocument();
    expect(m.shareCreate).not.toHaveBeenCalled();                                         // opening the panel shares nothing
    expect(screen.getByRole("button", { name: "Share view-only" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Workspace"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Share view-only" }));
    await waitFor(() => expect(m.shareCreate).toHaveBeenCalledWith(4, "story", "1"));
    expect(await screen.findByText("Shared with Alpha")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop sharing" }));
    await waitFor(() => expect(m.shareRevoke).toHaveBeenCalledWith(40));
    expect(await screen.findByText("Not shared with anyone.")).toBeInTheDocument();
  });

  it("offers no share control for an archived story and says so when there is no Workspace", async () => {
    m.list.mockResolvedValue({ stories: [story({ id: 2, title: "Plain" })] });
    m.wsList.mockResolvedValue({ workspaces: [], invited: [] });
    m.sharesMine.mockResolvedValue({ shares: [] });
    const { unmount } = render(<StoryBank />);
    await userEvent.click(await screen.findByRole("button", { name: "Share", expanded: false }));
    expect(await screen.findByText(/not in a Workspace yet/)).toBeInTheDocument();
    unmount();
    m.list.mockResolvedValue({ stories: [story({ id: 3, title: "Gone", archived_at: "2026-10-01T00:00:00Z" })] });
    m.search.mockResolvedValue({ stories: [story({ id: 3, title: "Gone", archived_at: "2026-10-01T00:00:00Z" })] });
    render(<StoryBank />);
    await userEvent.selectOptions(await screen.findByLabelText("Show"), "archived");
    await screen.findByText("Gone");
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
  });
});

describe("eight-locale parity of every Story Bank string", () => {
  const dir = join(__dirname, "../lib/i18n/messages/w04a");
  const load = async (loc: string) => (await import(`../lib/i18n/messages/w04a/${loc}.ts`)).default.storyBank as Record<string, string>;
  const placeholders = (s: string) => (s.match(/\{[a-z]+\}/g) ?? []).sort().join(",");

  it("every locale has exactly the English keys, the same placeholders, no dash punctuation and no emoji", async () => {
    const en = await load("en");
    for (const loc of ["de", "fr", "es", "it", "pt", "nl", "ru"]) {
      const cat = await load(loc);
      expect(Object.keys(cat).sort(), loc).toEqual(Object.keys(en).sort());
      for (const [k, v] of Object.entries(cat)) {
        expect(v.trim().length, `${loc}.${k}`).toBeGreaterThan(0);
        expect(placeholders(v), `${loc}.${k}`).toBe(placeholders(en[k]));
        expect(v, `${loc}.${k}`).not.toMatch(/[—–]/);
        expect(v, `${loc}.${k}`).not.toMatch(/\p{Extended_Pictographic}/u);
      }
    }
    expect(readdirSync(dir).filter((f) => f.endsWith(".ts")).sort()).toEqual(["de.ts", "en.ts", "es.ts", "fr.ts", "index.ts", "it.ts", "nl.ts", "pt.ts", "ru.ts"]);
  });

  it("every key a Story Bank component uses exists in the English catalogue and resolves in every supported locale", async () => {
    const { translate } = await import("@/lib/i18n/catalog");
    const { SUPPORTED_LOCALE_CODES } = await import("@/lib/i18n/locales");
    const root = join(__dirname, "../components/stories");
    const used = new Set<string>();
    for (const f of readdirSync(root)) for (const mt of readFileSync(join(root, f), "utf8").matchAll(/"((?:storyBank|documents)\.[A-Za-z_]+)"/g)) used.add(mt[1]);
    expect(used.size).toBeGreaterThan(60);
    for (const locale of SUPPORTED_LOCALE_CODES) for (const k of used) expect(translate(locale, k), `${locale}.${k}`).not.toBe(k);
  });

  it("the protected slogan is never part of the Story Bank copy", async () => {
    for (const loc of ["en", "de", "fr", "es", "it", "pt", "nl", "ru"]) {
      expect(Object.values(await load(loc)).join(" ")).not.toContain("Ask More");
    }
  });
});
