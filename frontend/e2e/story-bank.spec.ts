import { expect, test, type Page } from "@playwright/test";

// 04A Story Bank acceptance journey (REQ-OWN-06 S7), mocked at the network layer with an in-memory "server" whose state
// survives page reloads (a restart): create a story, check it is not called verified, link document evidence, confirm,
// choose it for Practice with consent, share it view-only, stop sharing, search, archive and restore, delete.
// No backend, no paid provider call.

const ACCOUNT = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active",
  email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};
const CLAIMS = [
  { id: 11, document_id: 1, version_id: 1, claim_type: "achievement", text: "Reduced latency", edited_text: null, display_text: "Reduced latency", source_page: null, source_section: "block 2", review_state: "accepted" },
  { id: 12, document_id: 1, version_id: 1, claim_type: "skill", text: "Rejected skill", edited_text: null, display_text: "Rejected skill", source_page: null, source_section: "block 3", review_state: "rejected" },
];

const SESSION = { session_id: "sess_story", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2, current_question: { question_id: 1, question: "Question 1: tell me about a decision.", question_type: "behavioural", competency: "judgement", difficulty: "moderate" },
        report_available: false, last_evaluation: null, target_role: "Registered Nurse", deep_dive: null, error: null, error_recoverable: false, cumulative_cost_usd: 0 };

type Story = {
  id: number; title: string; situation: string | null; task: string | null; action: string | null; result: string | null; competencies: string[];
  status: string; opportunity_id: number | null; archived_at: string | null; confirmed_at: string | null; claims: number[]; uses: number;
};

function present(s: Story) {
  const live = s.claims.length > 0;
  const prompts: string[] = [];
  for (const f of ["situation", "task", "action", "result"] as const) if (!(s[f] ?? "").trim()) prompts.push(`${f}_missing`);
  if (s.result && !/\d/.test(s.result)) prompts.push("result_no_figure");
  if (s.competencies.length === 0) prompts.push("no_tags");
  return {
    id: s.id, title: s.title, situation: s.situation, task: s.task, action: s.action, result: s.result, competencies: s.competencies, status: s.status,
    evidence_state: live ? "verified" : "none", verification: live ? "evidence_verified" : s.confirmed_at ? "self_confirmed" : "unverified",
    evidence_claim_ids: s.claims, evidence_answer_ids: [], opportunity_id: s.opportunity_id, archived_at: s.archived_at, confirmed_at: s.confirmed_at,
    use_count: s.uses, last_used_at: null, quality_prompts: prompts, updated_at: "2026-10-22T00:00:00Z",
  };
}

async function mockServer(page: Page, opts: { failList?: boolean } = {}) {
  const db = { next: 1, stories: [] as Story[], grants: [] as { id: number; workspace_id: number; resource_id: string }[], practiceBody: null as null | Record<string, unknown>, allow: false };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^.*\/api\/v1/, "");
    const method = route.request().method();
    const body = () => { try { return route.request().postDataJSON() ?? {}; } catch { return {}; } };
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    const find = (id: string) => db.stories.find((x) => x.id === Number(id));

    if (path === "/auth/me") return json(ACCOUNT);
    if (path === "/capabilities") return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: false });
    if (path === "/documents" && method === "GET") return json({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1, updated_at: null }] });
    if (path === "/documents/1" && method === "GET") return json({ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1, versions: [], claims: CLAIMS });
    if (path === "/opportunities" && method === "GET") return json({ opportunities: [{ id: 3, title: "Nurse at Acme", target_role: "Nurse", status: "active" }] });
    if (path === "/workspaces" && method === "GET") return json({ workspaces: [{ id: 4, name: "Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
    if (path === "/shares/mine") return json({ shares: db.grants.map((g) => ({ id: g.id, owner_user_id: 1, workspace_id: g.workspace_id, resource_type: "story", resource_id: g.resource_id, permission: "view", status: "active", created_at: null, revoked_at: null })) });
    if (path === "/shares" && method === "POST") {
      const b = body();
      const g = { id: 40, workspace_id: Number(b.workspace_id), resource_id: String(b.resource_id) };
      db.grants.push(g);
      return json({ share_id: 40, status: "active", permission: "view" });
    }
    if (path.match(/^\/shares\/\d+$/) && method === "DELETE") { db.grants = []; return json({ status: "revoked" }); }

    if (path === "/stories" && method === "GET") {
      if (opts.failList && !db.allow) return json({ error: { code: "internal", message: "x" } }, 500);
      return json({ stories: db.stories.filter((s) => !s.archived_at).map(present) });
    }
    if (path === "/stories/tags") return json({ tags: [...new Set(db.stories.filter((s) => !s.archived_at).flatMap((s) => s.competencies))].sort() });
    if (path === "/stories/search") {
      const b = body() as { q?: string; archived?: string };
      const mode = b.archived ?? "active";
      const words = (b.q ?? "").toLowerCase().split(/\s+/).filter(Boolean);
      return json({ stories: db.stories.filter((s) => (mode === "all" ? true : mode === "archived" ? !!s.archived_at : !s.archived_at))
        .filter((s) => words.every((w) => [s.title, s.situation, s.task, s.action, s.result, ...s.competencies].join(" ").toLowerCase().includes(w))).map(present) });
    }
    if (path === "/stories" && method === "POST") {
      const b = body() as Partial<Story>;
      const s: Story = { id: db.next++, title: String(b.title), situation: b.situation || null, task: b.task || null, action: b.action || null, result: b.result || null,
        competencies: (b.competencies as string[]) ?? [], status: "user_created", opportunity_id: (b.opportunity_id as number) ?? null, archived_at: null, confirmed_at: null, claims: [], uses: 0 };
      db.stories.push(s);
      return json(present(s), 201);
    }
    const one = path.match(/^\/stories\/(\d+)(\/[a-z]+(?:\/[a-z]+\/\d+)?)?$/);
    if (one) {
      const s = find(one[1]);
      if (!s) return json({ error: { code: "not_found", message: "Story not found." } }, 404);
      const sub = one[2] ?? "";
      if (sub === "" && method === "GET") return json(present(s));
      if (sub === "" && method === "PATCH") {
        const b = body() as Partial<Story>;
        for (const k of ["title", "situation", "task", "action", "result", "competencies"] as const) if (k in b) (s as Record<string, unknown>)[k] = (b as Record<string, unknown>)[k];
        if ("opportunity_id" in b) s.opportunity_id = (b.opportunity_id as number | null) ?? null;
        return json(present(s));
      }
      if (sub === "" && method === "DELETE") { db.stories = db.stories.filter((x) => x.id !== s.id); db.grants = []; return json({ deleted: true }); }
      if (sub === "/archive") { s.archived_at = "2026-10-22T00:00:00Z"; db.grants = []; return json(present(s)); }
      if (sub === "/restore") { s.archived_at = null; return json(present(s)); }
      if (sub === "/confirm") { s.confirmed_at = method === "POST" ? "2026-10-22T00:00:00Z" : null; return json(present(s)); }
      if (sub === "/evidence" && method === "POST") {
        const b = body() as { kind: string; ref_id: number };
        const claim = CLAIMS.find((c) => c.id === b.ref_id && c.review_state !== "rejected");
        if (b.kind !== "claim" || !claim) return json({ error: { code: "not_found", message: "Story not found." } }, 404);
        if (!s.claims.includes(claim.id)) s.claims.push(claim.id);
        return json(present(s));
      }
      const del = sub.match(/^\/evidence\/claim\/(\d+)$/);
      if (del && method === "DELETE") { s.claims = s.claims.filter((c) => c !== Number(del[1])); return json(present(s)); }
    }

    if (path === "/interviews/options") return json({ career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: [] });
    if (path === "/interviews" && method === "POST") {
      db.practiceBody = body() as Record<string, unknown>;
      for (const id of ((db.practiceBody.configuration as Record<string, unknown>)?.story_ids as number[] | undefined) ?? []) { const s = find(String(id)); if (s) s.uses += 1; }
      return json(SESSION);
    }
    if (path === "/interviews" && method === "GET") return json({ sessions: [] });
    if (path.match(/^\/interviews\/[^/]+$/) && method === "GET") return json(SESSION);
    return json({});
  });
  return db;
}

test("Story Bank journey: create, evidence, confirm, use in Practice, share, stop sharing, search, archive, delete, and it all survives a reload", async ({ page }) => {
  const db = await mockServer(page);
  await page.goto("/documents");
  await expect(page.getByText(/No stories yet/)).toBeVisible();

  // 1. Create by hand. The title is required; nothing is invented for the candidate.
  await page.getByRole("button", { name: "New story" }).click();
  await expect(page.getByLabel("Title")).toBeFocused();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Give the story a title.")).toBeVisible();
  await page.getByLabel("Title").fill("Led the ward migration");
  await page.getByLabel("Situation").fill("The ward moved to a new records system.");
  await page.getByLabel("Task").fill("I owned the cut-over plan.");
  await page.getByLabel("Competency tags").fill("Leadership, Planning");
  await page.locator("form").getByLabel("Opportunity").selectOption("3");
  await page.getByRole("button", { name: "Save" }).click();

  const card = page.getByTestId("story-1");
  await expect(card).toContainText("Led the ward migration");
  await expect(card).toContainText("Written by you");
  // 2. Not verified without evidence; the quality prompts only ask for what is missing.
  await expect(card).toContainText("No supporting source");
  await expect(card.getByTestId("quality-prompts")).toContainText("Add the action");
  await expect(card.getByTestId("quality-prompts")).toContainText("Add the result");
  await expect(card).toContainText("Linked to: Nurse at Acme");

  // 3. Link document evidence: only a non-rejected item is offered.
  await card.getByRole("button", { name: "Link evidence" }).click();
  await card.getByLabel("Document", { exact: true }).selectOption("1");
  const claim = card.getByLabel("Item", { exact: true });
  await expect(claim.locator("option", { hasText: "Rejected skill" })).toHaveCount(0);
  await claim.selectOption("11");
  await card.getByRole("button", { name: "Link", exact: true }).click();
  await expect(card).toContainText("Supporting evidence available");
  await expect(card.getByTestId("verification-help")).toContainText("document item from your own upload");

  // 4. A second story only confirmed by the candidate: labelled as theirs, never as evidence.
  await page.getByRole("button", { name: "New story" }).click();
  await page.getByLabel("Title").fill("Calmed a conflict");
  await page.getByLabel("Action").fill("I listened first, then proposed a rota both sides could accept in a short meeting.");
  await page.getByRole("button", { name: "Save" }).click();
  const card2 = page.getByTestId("story-2");
  await card2.getByRole("button", { name: "Confirm this is accurate" }).click();
  await expect(card2).toContainText("Confirmed by you");
  await expect(card2.getByTestId("verification-help")).toContainText("not evidence");
  await expect(card2).not.toContainText("Supporting evidence available");

  // 5. Restart: a reload keeps everything (it lives on the server).
  await page.reload();
  await expect(page.getByTestId("story-1")).toContainText("Supporting evidence available");
  await expect(page.getByTestId("story-2")).toContainText("Confirmed by you");

  // 6. Search and filter by words, through the POST endpoint.
  await page.getByRole("searchbox", { name: "Search" }).fill("conflict rota");
  await expect(page.getByTestId("story-count")).toHaveText("1 stories shown");
  await expect(page.getByTestId("story-2")).toBeVisible();
  await expect(page.getByTestId("story-1")).toHaveCount(0);
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByTestId("story-count")).toHaveText("2 stories shown");

  // 7. Share one story view-only, then stop sharing.
  const first = page.getByTestId("story-1");
  await first.getByRole("button", { name: "Share", exact: true }).click();
  await expect(first).toContainText("view-only access");
  expect(db.grants).toHaveLength(0);                                                      // opening the panel shared nothing
  await first.getByLabel("Workspace", { exact: true }).selectOption("4");
  await first.getByRole("button", { name: "Share view-only" }).click();
  await expect(first).toContainText("Shared with Alpha");
  expect(db.grants).toHaveLength(1);
  await first.getByRole("button", { name: "Stop sharing" }).click();
  await expect(first).toContainText("Not shared with anyone.");
  expect(db.grants).toHaveLength(0);

  // 8. Use it in Practice: chosen one by one, with explicit consent; ids only reach the server.
  await page.goto("/practice");
  await page.getByLabel("Target role").fill("Registered Nurse");
  await page.getByLabel("Industry or sector").fill("healthcare");
  await expect(page.getByRole("combobox", { name: "Career level" })).toBeVisible();
  await page.getByRole("checkbox", { name: /Led the ward migration/ }).check();
  const start = page.getByRole("button", { name: /Start interview/i });
  await expect(start).toBeDisabled();                                                     // chosen, not yet consented
  await page.getByRole("checkbox", { name: /I understand that the stories I selected/ }).check();
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByRole("heading", { name: /Question 1/i })).toBeVisible();
  const cfg = db.practiceBody?.configuration as Record<string, unknown>;
  expect(cfg.story_ids).toEqual([1]);
  expect(cfg.confirm_story_use).toBe(true);
  expect(JSON.stringify(db.practiceBody)).not.toContain("ward moved to a new records system");   // the story text never leaves the server

  // 9. Archive hides it from the default list; restore brings it back; archived stories are read-only.
  await page.goto("/documents");
  await page.getByTestId("story-2").getByRole("button", { name: "Archive" }).click();
  await expect(page.getByTestId("story-2")).toHaveCount(0);
  await page.getByLabel("Show").selectOption("archived");
  await expect(page.getByTestId("story-2")).toContainText("Archived: hidden from search");
  await expect(page.getByTestId("story-2").getByRole("button", { name: "Edit" })).toHaveCount(0);
  await page.getByTestId("story-2").getByRole("button", { name: "Restore" }).click();
  await page.getByLabel("Show").selectOption("active");
  await expect(page.getByTestId("story-2")).toBeVisible();

  // 10. Delete asks first and says what goes; afterwards the story and the empty state are honest.
  await page.getByTestId("story-2").getByRole("button", { name: "Delete" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("any sharing of it ends");
  await dialog.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByTestId("story-2")).toHaveCount(0);
  await page.getByTestId("story-1").getByRole("button", { name: "Delete" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText(/No stories yet/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/No stories yet/)).toBeVisible();
});

test("Story Bank: a failed load is explained, retryable and does not break the page", async ({ page }) => {
  const db = await mockServer(page, { failList: true });
  await page.goto("/documents");
  const alert = page.getByRole("alert").filter({ has: page.getByRole("button", { name: "Try again" }) });
  await expect(alert).toBeVisible();
  db.allow = true;                                                                        // the service recovers; the candidate retries
  await alert.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText(/No stories yet/)).toBeVisible();
});

test("Story Bank: the editor is keyboard-operable, labelled, and Escape returns focus", async ({ page }) => {
  await mockServer(page);
  await page.goto("/documents");
  await page.getByRole("button", { name: "New story" }).focus();
  await page.keyboard.press("Enter");
  const title = page.getByLabel("Title");
  await expect(title).toBeFocused();
  for (const name of ["Situation", "Task", "Action", "Result", "Competency tags"]) await expect(page.getByLabel(name)).toBeVisible();
  await expect(page.getByRole("search", { name: "Search and filter your stories" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Title")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "New story" })).toBeFocused();
});
