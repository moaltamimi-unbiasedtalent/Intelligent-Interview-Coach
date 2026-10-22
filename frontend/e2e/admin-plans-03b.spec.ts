import { expect, test, type Page } from "@playwright/test";

// 03B (REQ-OWN-02): Admin Plans for exactly Basic and Premium (preview): entitlement matrix and comparison, assignment preview and bulk assignment, effective-access
// explanation, rollback and stale-revision handling. Mocked at the network layer; no provider is contacted. Backend authorization (403) and the revision rules are
// proven by tests/test_admin_plans_03b.py, not here.

const KEYS = ["current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview"];
const bounds = (k: string) => ({ kind: "boolean", min_limit: null, max_limit: null, premium_only: k === "premium_preview" });
const ROWS = [
  { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", enabled_entitlements: 5, total_entitlements: 5, subscribers: { users: 3, workspaces: 1 }, revision: "r2", family_revision: "famP", created_at: null, activated_at: "2026-10-01", retired_at: null },
  { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", enabled_entitlements: 4, total_entitlements: 5, subscribers: { users: 40, workspaces: 0 }, revision: "r1", family_revision: "famB", created_at: null, activated_at: "2026-10-01", retired_at: null },
];
const MATRIX = {
  entitlements: KEYS.map((k) => ({ code: k, label: `Label ${k}`, description: `Desc ${k}`, type: "boolean", bounds: bounds(k) })),
  versions: ROWS.map((r) => ({ id: r.id, plan_code: r.plan_code, version: 1, display_name: r.display_name, status: "active", revision: r.revision,
    values: Object.fromEntries(KEYS.map((k) => [k, { enabled: r.plan_code === "premium" || k !== "premium_preview", limit: null }])) })),
};
const COMPARE = {
  left: { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", subscribers: { users: 40, workspaces: 0 } },
  right: { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", subscribers: { users: 3, workspaces: 1 } },
  rows: KEYS.map((k) => ({ code: k, label: `Label ${k}`, left: { enabled: k !== "premium_preview", limit: null }, right: { enabled: true, limit: null }, differs: k === "premium_preview" })),
  changed: 1, note: "Subscribers stay pinned to their version; comparing or activating a version never moves anyone.",
};
const PREVIEW = {
  plan_code: "premium", target_version: 1, subject_type: "user", requested: 3, found: 3, missing: 0, unchanged: 1, would_change: 2, by_current_plan: { basic: 2, premium: 1, none: 0 },
  entitlement_effect: KEYS.map((k) => ({ code: k, label: `Label ${k}`, gain: k === "premium_preview" ? 2 : 0, lose: 0, limit_changed: 0 })), preview_revision: "prev-1",
};
const EXPLAIN = {
  subject_type: "user", subject_id: 7, plan_code: "basic", plan_version: 1, plan_version_status: "active", source: "subscription",
  items: KEYS.map((k) => ({ code: k, label: `Label ${k}`, allowed: k !== "premium_preview", limit: null, unlimited: k !== "premium_preview", reason: k === "premium_preview" ? "disabled_by_plan_version" : "granted_by_plan_version" })),
  layers: [
    { layer: "authorization", evaluated_here: false, note: "Decided per request." }, { layer: "capability", evaluated_here: false, note: "Decided by the deployment." },
    { layer: "entitlement", evaluated_here: true, note: "What the plan grants." }, { layer: "billing_state", evaluated_here: false, note: "Billing never grants access." },
  ], note: "Plan data only.",
};
const DETAIL = (status: string) => ({
  id: 5, plan_code: "premium", version: 2, display_name: "Premium (preview)", status, editable: status === "draft", revision: "rev-5", family_revision: "fam-5",
  entitlements: KEYS.map((k) => ({ code: k, label: `Label ${k}`, description: "d", type: "boolean", enabled: true, limit: null, bounds: bounds(k) })),
  subscribers: { users: 1, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null,
});

function account(perms: string[]) {
  return { user_id: 1, email: "u@example.com", display_name: null, platform_role: "platform_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
    auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced",
    career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 };
}
const FULL = ["platform.overview.read", "platform.plans.read", "platform.plans.manage", "platform.subscriptions.manage"];

type Seen = { bulk: Record<string, unknown> | null; restore: Record<string, unknown> | null; patch: Record<string, unknown> | null; previewUrl: string | null };
async function mock(page: Page, perms: string[], detailStatus = "retired", patchStatus = 200): Promise<Seen> {
  const seen: Seen = { bulk: null, restore: null, patch: null, previewUrl: null };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return json(account(perms));
    if (path.endsWith("/capabilities")) return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true });
    if (path.endsWith("/admin/plans/matrix")) return json(MATRIX);
    if (path.endsWith("/admin/plans/compare")) return json(COMPARE);
    if (path.endsWith("/admin/plans/explain")) return json(EXPLAIN);
    if (path.endsWith("/admin/plans/assignments/preview")) { seen.previewUrl = url.search; return json(PREVIEW); }
    if (path.endsWith("/admin/plans/assignments/bulk")) { seen.bulk = route.request().postDataJSON(); return json({ plan_code: "premium", version: 1, subject_type: "user", requested: 3, changed: 2, unchanged: 1 }); }
    if (/\/admin\/plans\/versions\/\d+\/restore-as-draft$/.test(path)) { seen.restore = route.request().postDataJSON(); return json({ id: 8, plan_code: "premium", version: 3, copied_from: 2 }); }
    if (/\/admin\/plans\/versions\/\d+\/assignments$/.test(path)) return json({ plan_code: "premium", version: 2, total: 1, page: 1, page_size: 10, items: [{ subject_type: "user", subject_id: 9, status: "active", source: "admin", started_at: "2026-10-02T10:00:00Z", ended_at: null }] });
    if (/\/admin\/plans\/versions\/\d+\/entitlements$/.test(path) && method === "PATCH") {
      seen.patch = route.request().postDataJSON();
      return patchStatus === 200 ? json({ id: 5, changed: ["standard_history"] }) : json({ error: { code: "conflict", message: "The plan changed since it was loaded. Reload and review the current state before trying again." } }, patchStatus);
    }
    if (path.endsWith("/admin/plans/assignable")) return json([{ plan_code: "basic", version: 1, display_name: "Basic" }, { plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
    if (/\/admin\/plans\/\d+$/.test(path)) return json(DETAIL(detailStatus));
    if (path.endsWith("/admin/plans")) return json({ items: ROWS });
    return json({});
  });
  return seen;
}

test("matrix lists every entitlement per version and a comparison names exactly what differs", async ({ page }) => {
  await mock(page, FULL);
  await page.goto("/admin/plans");
  const table = page.getByRole("table", { name: "Registered entitlements by plan version" });
  await expect(table).toBeVisible();
  await expect(table.getByRole("row")).toHaveCount(1 + KEYS.length);
  await expect(table.getByText("Premium only: never enabled in Basic")).toBeVisible();
  await page.getByLabel("Compare this version").selectOption("1");
  await page.getByLabel("with this version").selectOption("2");
  await page.getByRole("button", { name: "Compare versions" }).click();
  await expect(page.getByText("1 of 5 entitlements differ.")).toBeVisible();
  await expect(page.getByText("Differs", { exact: true })).toHaveCount(1);
  await expect(page.getByText(/no prices, payments or invoices/)).toBeVisible();
});

test("assignment preview shows counts, the assignment needs confirmation and quotes the preview revision", async ({ page }) => {
  const seen = await mock(page, FULL);
  await page.goto("/admin/plans");
  await page.getByLabel("Plan to assign").selectOption("premium");
  await page.getByLabel(/Ids \(comma or space separated/).fill("7, 8 9");
  await page.getByRole("button", { name: "Preview effect" }).click();
  await expect(page.getByText(/Requested 3, found 3, not found 0\. 2 would change, 1 already on this version\./)).toBeVisible();
  expect(seen.previewUrl).toContain("ids=7%2C8%2C9");
  await page.getByRole("button", { name: "Assign 2 accounts" }).click();
  await expect(page.getByRole("alertdialog").getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.getByRole("alertdialog").getByRole("button", { name: "Assign", exact: true }).click();
  await expect(page.getByText(/Assigned: 2 changed, 1 already on version 1/)).toBeVisible();
  expect(seen.bulk).toEqual({ plan_code: "premium", subject_type: "user", subject_ids: [7, 8, 9], preview_revision: "prev-1" });
});

test("explanation labels each entitlement with its reason and keeps the four layers separate", async ({ page }) => {
  await mock(page, FULL);
  await page.goto("/admin/plans");
  await page.getByLabel("Subject id").fill("7");
  await page.getByRole("button", { name: "Explain access" }).click();
  await expect(page.getByText("The subject's plan version disables it.")).toBeVisible();
  await expect(page.getByText("Four separate layers")).toBeVisible();
  await expect(page.getByText(/Billing never grants access/)).toBeVisible();
});

test("rollback restores a retired version as a new draft and a stale save is refused with the server message", async ({ page }) => {
  const seen = await mock(page, FULL, "retired");
  await page.goto("/admin/plans/5");
  await expect(page.getByRole("heading", { name: "Assignment history" })).toBeVisible();
  await expect(page.getByText("user 9")).toBeVisible();
  await page.getByRole("button", { name: "Restore this version as a new draft" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Restore as draft" }).click();
  await expect(page.getByText(/Draft version 3 created from version 2/)).toBeVisible();
  expect(seen.restore).toEqual({ expected_revision: "fam-5" });

  await page.unrouteAll({ behavior: "ignoreErrors" });
  const seen2 = await mock(page, FULL, "draft", 409);
  await page.goto("/admin/plans/5");
  await page.getByLabel("Include Label standard_history").uncheck();
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText(/changed since it was loaded/)).toBeVisible();
  expect(seen2.patch).toMatchObject({ expected_revision: "rev-5" });
  await expect(page.getByRole("button", { name: "Save draft" })).toBeEnabled();
});

test("a read-only operator sees matrix, comparison and explanation but no assign, create or rollback control", async ({ page }) => {
  await mock(page, ["platform.overview.read", "platform.plans.read"]);
  await page.goto("/admin/plans");
  await expect(page.getByRole("table", { name: "Registered entitlements by plan version" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Explain effective access" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Assign plans" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Create next draft/ })).toHaveCount(0);
  await page.goto("/admin/plans/5");
  await expect(page.getByRole("heading", { name: "Assignment history" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Restore this version/ })).toHaveCount(0);
});

test("the plans page does not overflow a phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await mock(page, FULL);
  await page.goto("/admin/plans");
  await expect(page.getByRole("heading", { name: "Assign plans" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
