import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { hydrated, registerWithInvitation, signIn, T } from "../e2e/journey/definition";
import type { JourneyEnv } from "../e2e/journey/env";

const api = process.env.CANDIDATE_API_URL!;
const codes = (JSON.parse(readFileSync(process.env.JOURNEY_INVITATIONS_FILE!, "utf8")) as {codes: string[]}).codes;
const password = "Synthetic-Candidate-Test-Password-42";
const env: JourneyEnv = { mode: "real", variant: "healthy", locale: "en", invitationCode: codes[0],
  email: "candidate-one@example.test", password, displayName: "Synthetic Candidate", probeUninvited: false };

async function register(page: Page, email: string, code: string | null) {
  return page.evaluate(async ({ api, email, code, password }) => {
    const response = await fetch(`${api}/auth/register`, { method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password, display_name: "Synthetic", locale: "en", invitation_code: code }) });
    return { status: response.status, body: await response.json() };
  }, { api, email, code, password });
}
async function loginStatus(page: Page, email: string) {
  return page.evaluate(async ({ api, email, password }) => {
    const response = await fetch(`${api}/auth/login`, { method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
    return response.status;
  }, { api, email, password });
}
async function me(page: Page) {
  return page.evaluate(async (base) => {
    const r = await fetch(`${base}/auth/me`, { credentials: "include" });
    return { status: r.status, body: await r.json() };
  }, api);
}

test("connected invitation and onboarding remain scoped and persistent", async ({ browser, baseURL }) => {
  const context = await browser.newContext();
  await context.route("**/*", async route => {
    const host = new URL(route.request().url()).hostname;
    return host === "localhost" || host === "127.0.0.1" ? route.continue() : route.abort("blockedbyclient");
  });
  try {
    const page = await context.newPage();
    await page.goto("/register");
    const missing = await register(page, "missing@example.test", null);
    const invalid = await register(page, "invalid@example.test", "invalid-synthetic-code");
    expect(missing.status).toBe(403); expect(invalid.status).toBe(403);
    expect(missing.body.error.code).toBe("invitation_required"); expect(invalid.body.error.code).toBe("invitation_required");
    expect(await loginStatus(page, "missing@example.test")).not.toBe(200);
    expect(await loginStatus(page, "invalid@example.test")).not.toBe(200);
    await registerWithInvitation(page, env);
    expect(new URL(page.url()).hash).toBe("");
    const replay = await register(page, "replay@example.test", env.invitationCode);
    expect(replay.status).toBe(403); expect(replay.body.error.code).toBe("invitation_required");
    expect(await loginStatus(page, "replay@example.test")).not.toBe(200);
    await signIn(page, env);
    await expect(page).toHaveURL(/\/onboarding$/);
    await hydrated(page, "main button, #main button");
    const finish = page.getByRole("button", { name: T("en", "onboarding.finish") });
    const forward = page.getByRole("button", { name: T("en", "onboarding.getStarted") }).or(page.getByRole("button", { name: T("en", "onboarding.next"), exact: true }));
    for (let step = 1; step < 7; step++) {
      await expect(page.getByRole("status").filter({ hasText: `Step ${step} of 7` })).toBeVisible();
      await forward.first().click();
      await expect(page.getByRole("status").filter({ hasText: `Step ${step + 1} of 7` })).toBeVisible();
    }
    await expect(finish).toBeVisible();
    await finish.click();
    await expect(page.getByRole("heading", { name: T("en", "onboarding.completeTitle") })).toBeVisible();
    const before = await me(page);
    expect(before.status).toBe(200); expect(before.body.onboarding_completed).toBe(true);
    await page.reload();
    const after = await me(page);
    expect(after.status).toBe(200); expect(after.body.user_id).toBe(before.body.user_id); expect(after.body.onboarding_completed).toBe(true);
    expect(new URL(page.url()).origin).toBe(new URL(baseURL!).origin);
    const created = await page.evaluate(async base => {
      const r = await fetch(`${base}/opportunities`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_role: "Synthetic role", title: "Synthetic private opportunity" }) });
      return { status: r.status, body: await r.json() };
    }, api);
    expect(created.status).toBe(201);
    const second = await browser.newContext();
    await second.route("**/*", async route => {
      const host = new URL(route.request().url()).hostname;
      return host === "localhost" || host === "127.0.0.1" ? route.continue() : route.abort("blockedbyclient");
    });
    try {
      const other = await second.newPage();
      const otherEnv = { ...env, email: "candidate-two@example.test", invitationCode: codes[1] };
      await registerWithInvitation(other, otherEnv);
      await signIn(other, otherEnv);
      await expect(other).toHaveURL(/\/onboarding$/);
      const foreign = await other.evaluate(async ({base, id}) => {
        const r = await fetch(`${base}/opportunities/${id}`, { credentials: "include" });
        return { status: r.status, text: await r.text() };
      }, { base: api, id: created.body.id });
      expect(foreign.status).toBe(404);
      expect(foreign.text).not.toContain("Synthetic private opportunity");
      expect((await me(other)).body.user_id).not.toBe(before.body.user_id);
    } finally { await second.close(); }
  } finally { await context.close(); }
});
