import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const start = vi.fn();
const getRun = vi.fn();
const resume = vi.fn();
const cont = vi.fn();
const createInterview = vi.fn();
const push = vi.fn();
const replace = vi.fn();
let searchRun: string | null = null;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(searchRun ? `run=${searchRun}` : ""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: {
      start: (...a: unknown[]) => start(...a),
      getRun: (...a: unknown[]) => getRun(...a),
      resume: (...a: unknown[]) => resume(...a),
      continue: (...a: unknown[]) => cont(...a),
    },
    interviews: { create: (...a: unknown[]) => createInterview(...a) },
  },
}));
const capsRef = { current: { agent_coach_enabled: true } as Record<string, boolean> };
vi.mock("@/lib/useCapabilities", () => ({
  useCapabilities: () => ({ capabilities: { agent_coach_enabled: capsRef.current.agent_coach_enabled }, loading: false, offline: false }),
}));

import { PrepareEntry } from "@/components/preparation/PrepareEntry";
import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";

function runResponse(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "completed", response: "Here is your guidance.",
    tools_used: [], retrieval_used: false, sources: [], citations: [],
    memory_used: false, memory_count: 0, awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 1, turn_step_count: 1,
    conversation: [{ role: "user", content: "Prep for PM" }, { role: "assistant", content: "Here is your guidance." }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    ...over,
  };
}

beforeEach(() => { searchRun = null; capsRef.current.agent_coach_enabled = true; });
afterEach(() => vi.clearAllMocks());

describe("Agent Coach", () => {
  it("starts a run and renders the safe conversation", async () => {
    start.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep for PM");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(start).toHaveBeenCalledWith(expect.objectContaining({ goal: "Prep for PM" }));
    expect(await screen.findByText("Here is your guidance.")).toBeInTheDocument();
  });

  it("renders a role confirmation card and resumes with the selected role", async () => {
    start.mockResolvedValue(runResponse({
      status: "awaiting_human_input", awaiting_human_input: true, response: "",
      conversation: [{ role: "user", content: "Prep" }],
      pending_action: { action_id: "a1", type: "confirm_role", message: "Which role?", options: ["Product Manager", "Technical PM"], data: {} },
    }));
    resume.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(await screen.findByText("Which role?")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Product Manager"));
    await userEvent.click(screen.getByRole("button", { name: "Confirm role" }));
    expect(resume).toHaveBeenCalledWith("run_1", { action_id: "a1", decision: "select", selected_role: "Product Manager" });
  });

  it("shows the exact proposed memory and only persists on Save", async () => {
    start.mockResolvedValue(runResponse({
      status: "awaiting_human_input", awaiting_human_input: true, response: "",
      pending_action: { action_id: "m1", type: "approve_memory", message: "Remember this?", options: [], data: { category: "recurring_gap", summary: "Executive communication", target_role: "Head of People" } },
    }));
    resume.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(await screen.findByText("Executive communication")).toBeInTheDocument();
    expect(resume).not.toHaveBeenCalled();               // nothing persisted before Save
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(resume).toHaveBeenCalledWith("run_1", { action_id: "m1", decision: "approve" });
  });

  it("on practice handoff approval creates an interview and redirects", async () => {
    start.mockResolvedValue(runResponse({
      status: "completed", handoff_approved: true,
      preparation_context: { target_role: "Product Manager", industry: "Tech" },
    }));
    createInterview.mockResolvedValue({ session_id: "sess_9" });
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    await waitFor(() => expect(createInterview).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/practice?session=sess_9"));
  });

  it("restores a bookmarked run from the URL on load", async () => {
    searchRun = "run_42";
    getRun.mockResolvedValue(runResponse({ run_id: "run_42" }));
    render(<AgentPrepareWorkspace />);
    expect(await screen.findByText("Here is your guidance.")).toBeInTheDocument();
    expect(getRun).toHaveBeenCalledWith("run_42", expect.anything());
  });

  it("shows a calm restart when a bookmarked run is gone", async () => {
    searchRun = "run_gone";
    getRun.mockRejectedValue(Object.assign(new Error("nf"), { status: 404, userMessage: "gone" }));
    render(<AgentPrepareWorkspace />);
    expect(await screen.findByText("This preparation session can no longer be resumed.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start new preparation" })).toBeInTheDocument();
  });

  it("falls back to the deterministic workspace when the flag is off", () => {
    capsRef.current.agent_coach_enabled = false;
    render(<PrepareEntry />);
    // The agent first-message prompt is NOT shown; the deterministic Prepare workspace is.
    expect(screen.queryByLabelText("What interview are you preparing for?")).not.toBeInTheDocument();
  });
});
