import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const start = vi.fn();
const getRun = vi.fn();
const resume = vi.fn();
const cont = vi.fn();
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: { start: (...a: unknown[]) => start(...a), getRun: (...a: unknown[]) => getRun(...a),
             resume: (...a: unknown[]) => resume(...a), continue: (...a: unknown[]) => cont(...a) },
    interviews: { create: vi.fn(), options: vi.fn() },
    memory: { list: vi.fn(), update: vi.fn(), remove: vi.fn(), preview: vi.fn() },
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
    conversation: [{ role: "user", content: "Prep" }, { role: "assistant", content: "Here is your guidance." }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    cache_hits: 0, cache_misses: 0, ...over,
  };
}

const APPROVE = {
  status: "awaiting_human_input", awaiting_human_input: true, response: "",
  pending_action: { action_id: "m1", type: "approve_memory", message: "Remember?", options: [],
    data: { category: "recurring_gap", summary: "Stakeholder communication", target_role: "PM" } },
};

beforeEach(() => resume.mockResolvedValue(runResponse()));
afterEach(() => vi.clearAllMocks());

async function toApproval() {
  start.mockResolvedValue(runResponse(APPROVE));
  render(<AgentPrepareWorkspace />);
  await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
  await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
  expect(await screen.findByText("What will be remembered")).toBeInTheDocument();
}

describe("Memory approval card (edit-before-save)", () => {
  it("shows the exact memory that would be saved", async () => {
    await toApproval();
    expect(screen.getByText("Stakeholder communication")).toBeInTheDocument();
    expect(screen.getByText("PM")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit before saving" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("approves as-is with no memory override", async () => {
    await toApproval();
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(resume).toHaveBeenCalledWith("run_1", { action_id: "m1", decision: "approve" });
  });

  it("edits before saving and sends the edited memory", async () => {
    await toApproval();
    await userEvent.click(screen.getByRole("button", { name: "Edit before saving" }));
    const box = screen.getByLabelText("Memory");
    await userEvent.clear(box);
    await userEvent.type(box, "Refined fact");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(resume).toHaveBeenCalledWith("run_1", {
      action_id: "m1", decision: "approve",
      memory: { category: "recurring_gap", summary: "Refined fact", target_role: "PM" },
    });
  });

  it("rejects without saving", async () => {
    await toApproval();
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(resume).toHaveBeenCalledWith("run_1", { action_id: "m1", decision: "reject" });
  });
});

describe("Memory-loaded cue", () => {
  it("shows the count and inspectable summaries when memory was used", async () => {
    start.mockResolvedValue(runResponse({
      memory_used: true, memory_count: 2,
      memory_loaded: [
        { category: "recurring_gap", summary: "Stakeholder comms", target_role: "PM" },
        { category: "strength", summary: "Data fluency", target_role: null },
      ],
    }));
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(await screen.findByText("Using 2 saved preparation memories")).toBeInTheDocument();
    expect(screen.getByText(/Stakeholder comms/)).toBeInTheDocument();
    expect(screen.getByText(/Data fluency/)).toBeInTheDocument();
  });

  it("shows no cue when no memory was used", async () => {
    start.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    await screen.findByText("Here is your guidance.");
    expect(screen.queryByText(/saved preparation memor/)).not.toBeInTheDocument();
  });
});
