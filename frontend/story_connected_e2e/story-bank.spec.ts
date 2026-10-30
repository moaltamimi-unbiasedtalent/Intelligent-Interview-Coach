import { readFileSync } from "node:fs";
import { expect, test, type Browser, type Page } from "@playwright/test";

const api = process.env.STORY_API_URL!;
const accounts = JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!, "utf8")) as Record<string, { id: number; email: string }>;
const password = "Synthetic-Story-Test-Password-42";
async function context(browser: Browser) {
  const ctx = await browser.newContext();
  await ctx.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    return host === "localhost" || host === "127.0.0.1" ? route.continue() : route.abort("blockedbyclient");
  });
  return ctx;
}
async function request(page: Page, path: string, method = "GET", body?: object) {
  return page.evaluate(async ({ base, path, method, body }) => {
    const r = await fetch(base + path, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, json: await r.json() };
  }, { base: api, path, method, body });
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect.poll(async () => (await request(page, "/auth/me")).status).toBe(200);
}

test("manual Story Bank persists and enforces Candidate ownership", async ({ browser }) => {
  const owner = await context(browser), other = await context(browser);
  try {
    const a = await owner.newPage(), b = await other.newPage();
    await login(a, accounts.owner.email); await login(b, accounts.other.email);
    const opportunity = await request(a, "/opportunities", "POST", { target_role: "Synthetic role", company_name: "Synthetic employer" });
    expect(opportunity.status).toBe(201);
    const oppId = opportunity.json.id as number;
    await a.goto("/documents");
    await a.getByRole("button", { name: "New story" }).click();
    await a.getByLabel("Title").fill("Synthetic manual story");
    await a.getByLabel("Situation").fill("Synthetic situation");
    await a.getByLabel("Task").fill("Synthetic task");
    await a.getByLabel("Action").fill("Synthetic action");
    await a.getByLabel("Result").fill("Synthetic result");
    await expect(a.locator("form").getByLabel("Opportunity").locator(`option[value="${oppId}"]`)).toHaveCount(1);
    await a.locator("form").getByLabel("Opportunity").selectOption(String(oppId));
    const createdResponse = a.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/stories" && r.request().method() === "POST");
    await a.getByRole("button", { name: "Save", exact: true }).click();
    const created = await createdResponse;
    expect(created.status()).toBe(201);
    const initial = await created.json();
    const storyId = initial.id as number;
    expect(initial.status).toBe("user_created"); expect(initial.verification).toBe("unverified"); expect(initial.opportunity_id).toBe(oppId);
    const card = a.getByTestId(`story-${storyId}`);
    await expect(card).toContainText("Written by you"); await expect(card).toContainText("No supporting source");
    await card.getByRole("button", { name: "Edit", exact: true }).click();
    await a.getByLabel("Result").fill("Synthetic edited result");
    const updatedResponse = a.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/stories/${storyId}` && r.request().method() === "PATCH");
    await a.getByRole("button", { name: "Save", exact: true }).click();
    expect((await updatedResponse).status()).toBe(200);
    await expect(card).toContainText("Synthetic edited result");
    const before = await request(a, `/stories/${storyId}`);
    expect(before.status).toBe(200);
    expect(before.json).toMatchObject({ title: "Synthetic manual story", situation: "Synthetic situation", task: "Synthetic task",
      action: "Synthetic action", result: "Synthetic edited result", opportunity_id: oppId, status: "user_created", verification: "unverified" });
    await a.reload();
    await expect(card).toContainText("Synthetic edited result");
    expect((await request(a, `/stories/${storyId}`)).json.opportunity_id).toBe(oppId);
    const foreignRead = await request(b, `/stories/${storyId}`);
    const foreignEdit = await request(b, `/stories/${storyId}`, "PATCH", { title: "Unauthorized change" });
    expect(foreignRead.status).toBe(404); expect(foreignEdit.status).toBe(404);
    expect(JSON.stringify(foreignRead.json)).not.toContain("Synthetic manual story");
    const ownStory = await request(b, "/stories", "POST", { title: "Other synthetic story", status: "user_created" });
    expect(ownStory.status).toBe(201);
    const foreignAssociation = await request(b, `/stories/${ownStory.json.id}`, "PATCH", { opportunity_id: oppId });
    const foreignCreate = await request(b, "/stories", "POST", { title: "Refused synthetic story", opportunity_id: oppId });
    expect(foreignAssociation.status).toBe(422); expect(foreignCreate.status).toBe(422);
    const after = await request(a, `/stories/${storyId}`);
    expect(after.json).toMatchObject({ title: before.json.title, result: before.json.result, opportunity_id: oppId });
    expect((await request(b, `/stories/${ownStory.json.id}`)).json.opportunity_id).toBeNull();
    const otherList = await request(b, "/stories");
    expect(otherList.json.stories).toHaveLength(1);
    const suggestions = await request(a, "/stories/suggest", "POST", { terms: [], opportunity_id: oppId });
    expect(suggestions.status).toBe(200);
    expect(suggestions.json.suggestions.find((item: { id: number }) => item.id === storyId).requires_approval).toBe(true);
    const noConsent = await request(a, "/interviews", "POST", { configuration: { target_role: "Synthetic role", industry_or_sector: "technology",
      career_level: "senior", number_of_questions: 2, story_ids: [storyId] } });
    expect(noConsent.status).toBe(422);
    expect((await request(a, `/stories/${storyId}`)).json.use_count).toBe(0);
    const fresh = await context(browser);
    try {
      const freshPage = await fresh.newPage(); await login(freshPage, accounts.owner.email); await freshPage.goto("/documents");
      await expect(freshPage.getByTestId(`story-${storyId}`)).toContainText("Synthetic edited result");
      expect((await request(freshPage, `/stories/${storyId}`)).json.opportunity_id).toBe(oppId);
    } finally { await fresh.close(); }
  } finally { await owner.close(); await other.close(); }
});
