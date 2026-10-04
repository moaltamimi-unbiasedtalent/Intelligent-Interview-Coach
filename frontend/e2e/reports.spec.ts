import { expect, test, type Page } from "@playwright/test";

// P10B-W10.12 Admin Reports journey, mocked at the network layer with deterministic fixtures. The real SQL, cohort suppression, no-double-count AI
// usage and mock MRR/ARR arithmetic are proven by tests/test_reporting_w10_12.py and the manual QA; this proves the browser rendering and permission split.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
const account = (perms: string[]) => ({ user_id: 1, email: "ops@example.com", display_name: null, platform_role: "x", tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced",
  career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 });
const M = (o: Record<string, unknown>) => ({ metric_id: "m", label: "Metric", figure: 1, unit: "count", state: "available", coverage: "", note: "", ...o });
const SEC = (o: Record<string, unknown>) => ({ section_id: "s", title: "Section", coverage: "Historical", captured_since: null, note: "", metrics: [], tables: [], ...o });
const REP = (sections: unknown[], o: Record<string, unknown> = {}) => ({ period: "30d", window_start: "2026-09-05T00:00:00+00:00", window_end: "2026-10-05T00:00:00+00:00",
  generated_at: "x", utc: true, privacy: "Aggregates only.", sections, mock_billing: false, label: null, ...o });

const REPORTS: Record<string, unknown> = {
  product: REP([SEC({ section_id: "product", title: "Product", metrics: [M({ metric_id: "registrations", label: "Registrations", figure: 42 }),
    M({ metric_id: "activated", label: "Candidates whose first substantive action fell in the period", figure: null, state: "suppressed" })] })]),
  quality: REP([SEC({ section_id: "quality", title: "Quality", metrics: [M({ metric_id: "fb", label: "Candidates who gave feedback", figure: 18 }),
    M({ metric_id: "ev", label: "Offline evaluator results", figure: null, state: "not_captured", note: "No safe structured store exists." })] })]),
  operations: REP([SEC({ section_id: "jobs", title: "Jobs", coverage: "Current state (W10.9)", metrics: [M({ metric_id: "jobs_failed", label: "Failed", figure: 2 })] }),
    SEC({ section_id: "integrations", title: "Integrations", metrics: [M({ metric_id: "integrations_configured", label: "Configured", figure: 3 })] }),
    SEC({ section_id: "knowledge", title: "Knowledge", metrics: [M({ metric_id: "knowledge_active", label: "Active", figure: 4 })] })]),
  "ai-economics": REP([SEC({ section_id: "ai_economics", title: "AI economics", captured_since: "2026-10-04T10:00:00+00:00", metrics: [
    M({ metric_id: "ai_tokens_known", label: "Known tokens", figure: 120000, unit: "tokens", state: "partial", coverage: "Token coverage 80.0% of usage units" }),
    M({ metric_id: "ai_known_cost_usd", label: "Known cost (USD, partial coverage)", figure: null, state: "not_captured", unit: "usd", note: "Unknown cost is not zero." })] })]),
  commercial: REP([SEC({ section_id: "mock_billing", title: "MOCK BILLING - NOT LIVE REVENUE", metrics: [
    M({ metric_id: "mock_mrr", label: "Mock MRR", figure: null, state: "unavailable", note: "Unconfigured: not zero revenue." })],
    tables: [{ table_id: "mock_recurring", title: "Mock recurring value by currency", columns: ["Priced subscriptions", "Mock MRR", "Mock ARR"], note: "MOCK BILLING - NOT LIVE REVENUE.",
      rows: [{ label: "EUR", cells: [{ figure: 10, suppressed: false }, { figure: 100, suppressed: false }, { figure: 1200, suppressed: false }] }] }] })], { mock_billing: true, label: "MOCK BILLING - NOT LIVE REVENUE" }),
};

async function mock(page: Page, perms: string[]) {
  const asked: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities")) return json(route, CAPS);
    if (path.endsWith("/auth/me")) return json(route, account(perms));
    const m = path.match(/\/admin\/reports\/([a-z-]+)$/);
    if (m) {
      asked.push(m[1]);
      if (m[1] === "commercial" && !perms.includes("platform.reports.commercial.read")) return json(route, { error: { code: "forbidden", message: "x", request_id: "r" } }, 403);
      return json(route, REPORTS[m[1]]);
    }
    return json(route, {});
  });
  return asked;
}

test("W10.12: Reports journey: suppressed vs aggregate, quality, operations, AI economics with unknown cost, and no Commercial without its permission", async ({ page }) => {
  const asked = await mock(page, ["platform.overview.read", "platform.reports.read"]);
  await page.goto("/admin/reports");
  await expect(page.getByRole("heading", { name: "Reports", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByText("42", { exact: true })).toBeVisible();                                   // a sufficient cohort shows its aggregate
  await expect(page.getByText("Suppressed: small cohort").first()).toBeVisible();                       // a small cohort never shows a number
  await page.getByRole("tab", { name: "Quality" }).click();
  await expect(page.getByText("Candidates who gave feedback")).toBeVisible();
  await expect(page.getByText("Not captured").first()).toBeVisible();
  await page.getByRole("tab", { name: "Operations" }).click();
  for (const t of ["Jobs", "Integrations", "Knowledge"]) await expect(page.getByRole("heading", { name: t, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "AI economics" }).click();
  await expect(page.getByText("120000 tokens")).toBeVisible();
  await expect(page.getByText("Token coverage 80.0% of usage units")).toBeVisible();
  await expect(page.getByText("Not captured").first()).toBeVisible();                                    // unknown cost is not $0
  await expect(page.getByText(/\$0|^0$/)).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Commercial" })).toHaveCount(0);
  await expect(page.getByText("MOCK BILLING")).toHaveCount(0);
  expect(asked).not.toContain("commercial");                                                             // the commercial report is never requested without its permission
  await expect(page.getByText(/example\.com|@|user id|session id/i)).toHaveCount(0);                     // no identifiers on the page
});

test("W10.12: a commercial-permission principal sees the large MOCK BILLING warning and mock figures only from configured terms", async ({ page }) => {
  await mock(page, ["platform.overview.read", "platform.reports.commercial.read"]);
  await page.goto("/admin/reports");
  await expect(page.getByRole("tab", { name: "Commercial" })).toBeVisible();
  await expect(page.getByRole("note")).toHaveText("MOCK BILLING — NOT LIVE REVENUE");
  await expect(page.getByText("Mock MRR").first()).toBeVisible();
  await expect(page.getByText("Unconfigured: not zero revenue.")).toBeVisible();
  const row = page.getByRole("row", { name: /EUR/ });
  await expect(row).toContainText("100");
  await expect(row).toContainText("1200");
  await expect(page.getByRole("tab", { name: "Product" })).toHaveCount(0);
});
