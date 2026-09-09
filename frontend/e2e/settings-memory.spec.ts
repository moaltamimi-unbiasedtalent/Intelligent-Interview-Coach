import { expect, test, type Page } from "@playwright/test";

// Real Next.js → API browser flows for P2 memory management, with CONTROLLED,
// stateful responses mocked at the network layer. No backend, no paid calls.

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

function memory(over: Record<string, unknown> = {}) {
  return {
    id: 1, category: "recurring_gap", summary: "Executive communication",
    target_role: "Head of People", pinned: false, source_run_id: null,
    created_at: null, updated_at: null, ...over,
  };
}

/** A stateful in-memory mock of the /memory + /agent surfaces. */
async function mock(page: Page, opts: { memories?: Record<string, unknown>[]; onRun?: Record<string, unknown> } = {}) {
  const store: Record<string, unknown>[] = opts.memories ? [...opts.memories] : [memory()];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);

    if (path.endsWith("/memory/preview")) {
      const role = url.searchParams.get("target_role");
      const items = [...store]
        .filter((m) => !role || m.target_role === role || m.target_role === null)
        .sort((a, b) => Number(b.pinned) - Number(a.pinned))
        .map((m, i) => ({ ...m, order: i, reason: role && m.target_role === role ? "Matches this role" : "General preparation memory" }));
      return json({ target_role: role, load_limit: 10, items });
    }
    const patchMatch = path.match(/\/memory\/(\d+)$/);
    if (patchMatch) {
      const id = Number(patchMatch[1]);
      const idx = store.findIndex((m) => m.id === id);
      if (method === "PATCH") {
        const body = route.request().postDataJSON?.() ?? {};
        store[idx] = { ...store[idx], ...body };
        return json(store[idx]);
      }
      if (method === "DELETE") {
        store.splice(idx, 1);
        return json({ deleted: true, id });
      }
    }
    if (path.endsWith("/memory")) return json({ memories: store });

    if (path.endsWith("/agent/run")) return json(opts.onRun ?? {});
    const resumeMatch = path.match(/\/agent\/runs\/[^/]+\/resume$/);
    if (resumeMatch) {
      const body = route.request().postDataJSON?.() ?? {};
      if (body.memory) store.push({ ...memory({ id: 99, pinned: false }), ...body.memory });
      return json({ ...(opts.onRun ?? {}), status: "completed", awaiting_human_input: false,
                    pending_action: null, response: "Saved.", conversation: [] });
    }
    return json({});
  });
}

test("Flow 1: view → edit → pin → preview → delete in Settings", async ({ page }) => {
  await mock(page);
  await page.goto("/settings");
  await expect(page.getByText("Executive communication")).toBeVisible();

  // Edit
  await page.getByRole("button", { name: /Edit saved memory/ }).click();
  const box = page.getByLabel("Memory");
  await box.fill("Executive communication under pressure");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Executive communication under pressure")).toBeVisible();

  // Pin
  await page.getByRole("button", { name: /^Pin saved memory/ }).click();
  await expect(page.getByRole("button", { name: /Unpin saved memory/ })).toBeVisible();

  // Next-run preview
  await page.getByLabel("Target role (optional)").first().fill("Head of People");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Matches this role")).toBeVisible();

  // Delete (the manageable row disappears; a stale preview snapshot is not the row).
  await page.getByRole("button", { name: /Remove saved memory/ }).click();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByRole("button", { name: /Edit saved memory/ })).toHaveCount(0);
});

test("Flow 2: Coach proposes → edit before saving → approve → visible in Settings", async ({ page }) => {
  const onRun = {
    run_id: "run_e2e", status: "awaiting_human_input", awaiting_human_input: true, response: "",
    tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false,
    memory_count: 0, memory_loaded: [], handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 1, turn_step_count: 1, conversation: [{ role: "user", content: "Prep" }],
    preparation_context: null, cache_hits: 0, cache_misses: 0,
    pending_action: { action_id: "m1", type: "approve_memory", message: "Remember?", options: [],
      data: { category: "recurring_gap", summary: "Original proposal", target_role: "PM" } },
  };
  await mock(page, { memories: [], onRun });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep");
  await page.getByRole("button", { name: "Start preparing" }).click();

  await expect(page.getByText("What will be remembered")).toBeVisible();
  await page.getByRole("button", { name: "Edit before saving" }).click();
  await page.getByLabel("Memory").fill("Edited before saving");
  await page.getByRole("button", { name: "Save" }).click();

  // Now it should be persisted and visible in Settings.
  await page.goto("/settings");
  await expect(page.getByText("Edited before saving")).toBeVisible();
});

test("Flow 3: memory persists across a Settings refresh", async ({ page }) => {
  await mock(page, { memories: [memory({ summary: "Durable detail" })] });
  await page.goto("/settings");
  await expect(page.getByText("Durable detail")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Durable detail")).toBeVisible();
});
