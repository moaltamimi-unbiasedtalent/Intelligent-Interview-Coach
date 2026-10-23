import { expect, test } from "@playwright/test";

// MOCKED NETWORK / scripted browser transport. No real model, API, private data or cost.
test("Candidate sees progress, stops the same admitted run and can start again", async ({ page }) => {
  const rid = "a".repeat(32);
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();
    const body = url.includes("/capabilities") ? {
      career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
      agent_coach_enabled: true, agent_streaming_enabled: true, agentic_rag: true, agent_memory: true,
      human_in_the_loop: true, live_interview_enabled: false, ai_provider_mode: "offline",
    } : {};
    return route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.addInitScript(({ id }) => {
    const original = window.fetch;
    let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
    const encoder = new TextEncoder();
    const emit = (kind: string, body: unknown) => controller?.enqueue(encoder.encode(`event: ${kind}\ndata: ${JSON.stringify(body)}\n\n`));
    window.fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/agent/run/stream")) {
        return new Response(new ReadableStream({ start(c) {
          controller = c;
          emit("run", { run_id: id });
          emit("progress", { event_type: "tool_started" });
        } }), { headers: { "content-type": "text/event-stream" } });
      }
      if (url.endsWith(`/agent/runs/${id}/cancel`)) {
        emit("stopping", { status: "cancelled", settlement_pending: true });
        emit("result", {
          run_id: id, status: "cancelled", response: "", tools_used: [], retrieval_used: false,
          sources: [], citations: [], memory_used: false, memory_count: 0, awaiting_human_input: false,
          pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [],
          step_count: 1, turn_step_count: 1, conversation: [{ role: "user", content: "Prepare with me" }],
          preparation_context: null, resolved_occupation: null, resolved_geography: null,
        });
        controller?.close();
        return new Response(JSON.stringify({ run_id: id, status: "cancelled", settlement_pending: true }), { headers: { "content-type": "application/json" } });
      }
      return original(input, init);
    };
  }, { id: rid });
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prepare with me");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByTestId("agent-stream-progress")).toContainText("Using preparation tools");
  await expect(page).toHaveURL(new RegExp(`run=${rid}`));
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText(/This request was stopped/)).toBeVisible();
  await page.getByRole("button", { name: "Start new preparation" }).click();
  await expect(page.getByRole("button", { name: "Start preparing" })).toBeVisible();
});
