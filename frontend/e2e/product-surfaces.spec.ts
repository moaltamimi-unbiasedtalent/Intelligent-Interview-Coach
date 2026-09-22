import { expect, test, type Page } from "@playwright/test";

// Post-release product-surface fixes (Progress, History detail, Sources links,
// Review & Diagnostics evaluation). Real Next.js → API browser flow with CONTROLLED
// responses mocked at the network layer (page.route). No backend, no paid calls.

const PROGRESS = {
  interviews_completed: 3,
  answers_evaluated: 7,
  average_practice_score: 74.5,
  most_common_improvement_area: "Add measurable outcomes",
  average_answer_seconds: 92,
  recent_interviews: [
    { id: 36, target_role: "Backend Software Engineer", mode: null, status: "completed", questions: 3, created_at: "2026-09-21T09:28:28" },
  ],
};

const HISTORY_LIST = {
  interviews: [
    { id: 36, target_role: "Backend Software Engineer", mode: null, status: "completed", questions: 3, created_at: "2026-09-21T09:28:28" },
  ],
};

const HISTORY_DETAIL = {
  interview: {
    id: 36,
    configuration: { target_role: "Backend Software Engineer" },
    mode: null,
    status: "completed",
    created_at: "2026-09-21T09:28:28",
    questions: [],
    report: {
      report: {
        overall_readiness_score: 82,
        performance_summary: "Solid, evidence-based answers.",
        strongest_competencies: ["REST API design"],
        development_priorities: ["Quantify outcomes"],
      },
      usage: null,
      cost_usd: null,
    },
  },
};

const SOURCES = {
  sources: [
    { source_id: "onet", title: "O*NET Database", group: "occupations", source_type: "occupation_taxonomy", source_url: "https://www.onetcenter.org/", provider: "official", country: "US", reference_year: null },
    { source_id: "internal_kb", title: "Governed dataset", group: "narrative", source_type: "internal", source_url: null, provider: "official", country: null, reference_year: 2025 },
  ],
};

const EVALUATION = {
  available: true,
  metrics: { faithfulness: 0.4051, context_precision: 0.554 },
  run_config: { timestamp: "20260902_090140", status: "COMPLETE", case_count: 35, evaluator_model: "openai/gpt-4o-mini" },
};

async function mockAll(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_surface" }, body: JSON.stringify(body) });
    if (url.includes("/history/interviews/")) return json(HISTORY_DETAIL);
    if (url.includes("/history/interviews")) return json(HISTORY_LIST);
    if (url.includes("/progress")) return json(PROGRESS);
    if (url.includes("/knowledge/sources")) return json(SOURCES);
    if (url.includes("/knowledge/snapshot")) return json({ documents: 31, chunks: 14087, document_types: 6 });
    if (url.includes("/evaluation/latest")) return json(EVALUATION);
    if (url.includes("/memory")) return json({ memories: [] });
    return json({});
  });
}

test("progress: shows persisted practice metrics with a linked recent session", async ({ page }) => {
  await mockAll(page);
  await page.goto("/progress");
  await expect(page.getByRole("heading", { name: "Practice progress" })).toBeVisible();
  await expect(page.getByText("74.5/100")).toBeVisible();
  await expect(page.getByText("Add measurable outcomes")).toBeVisible();
  await expect(page.getByRole("link", { name: /Backend Software Engineer/ })).toHaveAttribute("href", "/history/36");
});

test("history: a session row opens its detail report", async ({ page }) => {
  await mockAll(page);
  await page.goto("/history");
  await page.getByRole("link", { name: /Backend Software Engineer/ }).click();
  await expect(page).toHaveURL(/\/history\/36$/);
  await expect(page.getByText("Performance review")).toBeVisible();
  await expect(page.getByText("82")).toBeVisible();
  await expect(page.getByText("Solid, evidence-based answers.")).toBeVisible();
});

test("sources: public source is a safe external link; governed source is inspectable, not fabricated", async ({ page }) => {
  await mockAll(page);
  await page.goto("/sources");
  const link = page.getByRole("link", { name: "O*NET Database" });
  await expect(link).toHaveAttribute("href", "https://www.onetcenter.org/");
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  // The governed source without a public URL is shown but never linked.
  await expect(page.getByText("Governed dataset")).toBeVisible();
  await expect(page.getByRole("link", { name: "Governed dataset" })).toHaveCount(0);
});

test("review/evaluation: shows offline metrics read-only, clearly not live analytics", async ({ page }) => {
  await mockAll(page);
  await page.goto("/review/evaluation");
  await expect(page.getByText("faithfulness")).toBeVisible();
  await expect(page.getByText("0.405")).toBeVisible();
  await expect(page.getByText(/never triggers a paid evaluation/i)).toBeVisible();
});
