import { expect, test, type Page } from "@playwright/test";

// P10B-W10.3 candidate support journey, mocked at the network layer (backend ownership, internal-note
// isolation and atomic audit are proven by the Python suites). Deterministic: no retries, sleeps or raised timeouts.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};
const ACCOUNT = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active",
  email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: [],
  response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true,
};
const REF = "c".repeat(32);

async function mockSupport(page: Page) {
  const state = { created: false, replies: 0 };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    const summary = { public_id: REF, category: "technical", status: "new", subject: "Cannot upload", created_at: "2026-10-01T10:00:00", updated_at: "2026-10-02T10:00:00" };
    const messages = () => [
      { id: 1, author_kind: "candidate", body: "It fails every time.", created_at: "2026-10-01T10:00:00" },
      { id: 2, author_kind: "support", body: "Thanks, we are looking into it.", created_at: "2026-10-02T09:00:00" },
      ...Array.from({ length: state.replies }, (_, i) => ({ id: 3 + i, author_kind: "candidate", body: "Here is more detail.", created_at: "2026-10-02T11:00:00" })),
    ];
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) return json(ACCOUNT);
    if (path.endsWith("/support/tickets") && method === "POST") {
      state.created = true;
      return json(summary, 201);
    }
    if (path.endsWith("/support/tickets")) return json({ items: state.created ? [summary] : [], total: state.created ? 1 : 0, page: 1, page_size: 20 });
    if (path.endsWith(`/support/tickets/${REF}/messages`) && method === "POST") {
      state.replies += 1;
      return json({ ...summary, can_reply: true, messages: messages() });
    }
    if (path.endsWith(`/support/tickets/${REF}`)) return json({ ...summary, can_reply: true, messages: messages() });
    return json({});
  });
}

test("candidate: Help -> Contact Support -> ticket -> thread -> reply", async ({ page }) => {
  await mockSupport(page);
  await page.goto("/help");
  await page.getByRole("link", { name: "Contact Support" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Contact Support" })).toBeVisible();

  await page.getByLabel("Topic").selectOption("technical");
  await page.getByLabel("Subject").fill("Cannot upload");
  await page.getByLabel("What happened?").fill("It fails every time.");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByRole("status").filter({ hasText: REF })).toBeVisible();

  await page.getByRole("link", { name: "Cannot upload" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Cannot upload" })).toBeVisible();
  await expect(page.getByText(`Reference: ${REF}`)).toBeVisible();
  await expect(page.getByText("Thanks, we are looking into it.")).toBeVisible();
  await expect(page.getByText(/internal note/i)).toHaveCount(0);

  await page.getByLabel("Your reply").fill("Here is more detail.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("Here is more detail.")).toBeVisible();
});

test("candidate: an empty form shows associated errors and sends nothing", async ({ page }) => {
  await mockSupport(page);
  let posts = 0;
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/support/tickets")) posts += 1; });
  await page.goto("/support");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByLabel("Topic")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Subject")).toHaveAttribute("aria-invalid", "true");
  expect(posts).toBe(0);
});
