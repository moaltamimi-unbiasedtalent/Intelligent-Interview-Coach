import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const start = vi.fn();
const getRun = vi.fn();
const fbGet = vi.fn();
const fbSubmit = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: { start: (...a: unknown[]) => start(...a), getRun: (...a: unknown[]) => getRun(...a), resume: vi.fn(), continue: vi.fn() },
    interviews: { create: vi.fn(), options: vi.fn() },
    memory: { list: vi.fn(), update: vi.fn(), remove: vi.fn(), preview: vi.fn() },
    feedback: { get: (...a: unknown[]) => fbGet(...a), submit: (...a: unknown[]) => fbSubmit(...a), remove: vi.fn() },
  },
}));

import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";

function runResponse(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "completed", response: "Here is your guidance.",
    tools_used: [], retrieval_used: false, sources: [], citations: [],
    memory_used: false, memory_count: 0, memory_loaded: [], awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 1, turn_step_count: 1,
    conversation: [{ role: "user", content: "Prep" }, { role: "assistant", content: "Here is your guidance.", response_id: "run_1:1" }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    cache_hits: 0, cache_misses: 0, ...over,
  };
}

async function startRun(over: Record<string, unknown> = {}) {
  start.mockResolvedValue(runResponse(over));
  render(<AgentPrepareWorkspace />);
  await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
  await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
}

beforeEach(() => { fbGet.mockResolvedValue(null); fbSubmit.mockResolvedValue({ id: 1 }); });
afterEach(() => vi.clearAllMocks());

describe("Agent answer feedback", () => {
  it("shows feedback on a completed answer and submits with the response_id", async () => {
    await startRun();
    await screen.findByText("Here is your guidance.");
    const helpful = await screen.findByRole("button", { name: "Helpful" });
    await userEvent.click(helpful);
    expect(fbSubmit).toHaveBeenCalledWith({ surface: "agent_answer", target_id: "run_1:1", rating: "helpful", comment: null });
  });

  it("is hidden while awaiting a human decision", async () => {
    await startRun({
      status: "awaiting_human_input", awaiting_human_input: true, response: "",
      pending_action: { action_id: "a1", type: "confirm_role", message: "Which role?", options: ["PM"], data: {} },
      conversation: [{ role: "user", content: "Prep" }],
    });
    expect(await screen.findByText("Which role?")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Helpful" })).not.toBeInTheDocument();
  });

  it("is hidden on a failed run", async () => {
    await startRun({ status: "failed", response: "", conversation: [{ role: "user", content: "Prep" }] });
    expect(screen.queryByRole("button", { name: "Helpful" })).not.toBeInTheDocument();
  });
});
