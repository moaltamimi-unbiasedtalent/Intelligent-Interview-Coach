import { expect, test, type Page } from "@playwright/test";

// 03A (REQ-OWN-08): grouped Admin navigation, breadcrumbs, quick navigation, Review and Diagnostics under /admin, and the Candidate More menu.
// Mocked at the network layer; no provider is contacted. Backend authorization (403) is proven by the Python suite, not here.

const ALL_PERMS = ["platform.overview.read", "platform.users.read", "platform.audit.read", "platform.integrations.read", "platform.ai.read", "platform.knowledge.read", "platform.flags.read",
  "platform.billing.read", "platform.jobs.read", "platform.support.read", "platform.workspaces.read", "platform.plans.read", "platform.privacy.read", "platform.reports.read", "platform.security.read"];

const HOME = {
  build: { version: "0.1.0", git_sha: "abc1234", build_time: "2026-10-02T10:00:00Z", environment: "staging", source: "x" },
  migrations: { repository_head: "0039_speech_governance", database_revision: "0039_speech_governance", state: "match", warning: null },
  health: { database: "reachable", providers_probed: false, note: "" },
  rate_limit: { mode: "in_memory_process_local", distributed: false, shared_store_requested: false, note: "" },
  pause: { status: "running", paused: {}, durable: true, note: "" },
  privacy_requests: { status: "restricted", note: "" },
  accounts: { users_total: 5, platform_admins: 1, premium_accounts: 2 }, workspaces: { workspaces_total: 3 },
  diagnostics_links: [], boundary: "Operational metadata only.",
};

function account(role: string, perms: string[]) {
  return { user_id: 1, email: "u@example.com", display_name: null, platform_role: role, tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced",
    career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 };
}

async function mock(page: Page, role: string, perms: string[]) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return json(account(role, perms));
    if (path.endsWith("/capabilities")) return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
      agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true });
    if (path.endsWith("/admin/home")) return json(HOME);
    if (path.endsWith("/admin/readiness")) return json({ capabilities: [], summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "" });
    return json({});
  });
}

const admin = (page: Page) => mock(page, "platform_admin", ALL_PERMS);
const adminNav = (page: Page) => page.getByRole("navigation", { name: "Admin" });

test("sections expand and collapse and are keyboard operable", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await admin(page);
  await page.goto("/admin/review");
  const nav = adminNav(page);
  const section = nav.getByRole("button", { name: /Customers and Workspaces/ });
  await expect(section).toHaveAttribute("aria-expanded", "true");
  await expect(nav.getByRole("link", { name: "Users" })).toBeVisible();
  await section.click();
  await expect(section).toHaveAttribute("aria-expanded", "false");
  await expect(nav.getByRole("link", { name: "Users" })).toBeHidden();
  await section.focus();
  await page.keyboard.press("Enter");
  await expect(section).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await expect(nav.getByRole("link", { name: "Users" })).toBeFocused();
  // Visible focus indicator on a keyboard-focused link.
  const outline = await nav.getByRole("link", { name: "Users" }).evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});

test("all six sections are listed in the approved order with the approved placement", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await admin(page);
  await page.goto("/admin/review");
  const nav = adminNav(page);
  const labels = await nav.getByRole("button", { expanded: true }).allTextContents();
  expect(labels.map((t) => t.replace(/[+−]/g, "").trim())).toEqual([
    "Command Center", "Customers and Workspaces", "Products and Commercial", "AI and Knowledge", "Insights and Operations", "Governance and Settings",
  ]);
  await expect(nav.getByRole("link")).toHaveCount(20);
});

test("breadcrumbs name the section and page and link back to Admin", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await admin(page);
  await page.goto("/admin/billing");
  const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(crumbs).toContainText("Products and Commercial");
  await expect(crumbs.locator("[aria-current='page']")).toHaveText("Billing");
  await expect(adminNav(page).getByRole("link", { name: "Billing" })).toHaveAttribute("aria-current", "page");
  await crumbs.getByRole("link", { name: "Admin" }).click();
  await expect(page).toHaveURL(/\/admin$/);
});

test("quick navigation filters the visible destinations only", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mock(page, "support_operator", ["platform.overview.read", "platform.users.read", "platform.support.read"]);
  await page.goto("/admin");
  const nav = adminNav(page);
  await expect(nav.getByRole("link")).toHaveCount(3);
  const filter = nav.getByRole("searchbox", { name: "Find a section" });
  await filter.fill("support");
  await expect(nav.getByRole("link")).toHaveCount(1);
  await filter.fill("billing");                                          // exists in the product but not permitted: never offered
  await expect(nav.getByRole("link")).toHaveCount(0);
  await expect(nav.getByRole("button", { name: /Products and Commercial/ })).toHaveCount(0);
  await filter.fill("users");
  await page.keyboard.press("Enter");
  await expect(nav.getByRole("link", { name: "Users" })).toBeFocused();
});

test("responsive: at 390px the sections sit inside the menu drawer and nothing overflows", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await admin(page);
  await page.goto("/admin/review");
  const nav = adminNav(page);
  const button = nav.getByRole("button", { name: /Admin menu: Review/ });
  await expect(button).toBeVisible();
  await expect(nav.getByRole("button", { name: /Governance and Settings/ })).toBeHidden();
  await button.click();
  await expect(nav.getByRole("button", { name: /Governance and Settings/ })).toBeVisible();
  await nav.getByRole("button", { name: /Governance and Settings/ }).click();
  await expect(nav.getByRole("link", { name: "Audit" })).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
  await page.keyboard.press("Escape");
  await expect(button).toHaveAttribute("aria-expanded", "false");
});

test("Review and Diagnostics: old URLs redirect for an Admin and the new pages sit in the AI and Knowledge section", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await admin(page);
  for (const [from, to] of [["/review", /\/admin\/review$/], ["/review/rag", /\/admin\/review\/rag$/], ["/review/evaluation", /\/admin\/review\/evaluation$/]] as const) {
    await page.goto(from);
    await expect(page).toHaveURL(to);
  }
  await page.goto("/admin/review");
  await expect(page.getByRole("heading", { name: "Review & Diagnostics" })).toBeVisible();
  await expect(adminNav(page).getByRole("link", { name: "Review / Diagnostics" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("AI and Knowledge");
});

test("Candidate: More has no Review entry and no Admin entry, /review/agent stays reachable, diagnostics redirect to access denied", async ({ page }) => {
  await mock(page, "user", []);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  await expect(page.getByRole("menuitem", { name: /Review/ })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: /Admin/ })).toHaveCount(0);
  await page.goto("/review/agent");
  await expect(page).toHaveURL(/\/review\/agent$/);
  await expect(page.getByText(/access denied/i)).toHaveCount(0);
  await expect(adminNav(page)).toHaveCount(0);
  await page.goto("/review/rag");
  await expect(page).toHaveURL(/\/admin\/review\/rag$/);
  await expect(page.getByText(/access denied/i)).toBeVisible();
});

test("Admin More menu keeps the Admin entry and drops Review", async ({ page }) => {
  await admin(page);
  await page.goto("/prepare");
  await page.getByRole("button", { name: /More/ }).click();
  await expect(page.getByRole("menuitem", { name: /Admin/ })).toHaveAttribute("href", "/admin");
  await expect(page.getByRole("menuitem", { name: /Review/ })).toHaveCount(0);
});
