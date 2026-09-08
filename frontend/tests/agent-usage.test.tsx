import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const start = vi.fn();
const getRun = vi.fn();
const cont = vi.fn();
const resume = vi.fn();
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
      continue: (...a: unknown[]) => cont(...a),
      resume: (...a: unknown[]) => resume(...a),
    },
    interviews: { create: vi.fn(), options: vi.fn() },
  },
}));

import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";
import { AgentInspector } from "@/components/agent/AgentInspector";

function usage(over: Record<string, unknown> = {}) {
  return {
    agent_model_calls: 2, tool_model_calls: 1, model_calls: 3,
    input_tokens: 5420, output_tokens: 1104, total_tokens: 6524,
    estimated_cost_usd: 0.018, usage_complete: true, missing_usage_sources: [],
    ...over,
  };
}

function runResponse(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "completed", response: "Here is your guidance.",
    tools_used: [], retrieval_used: false, sources: [], citations: [],
    memory_used: false, memory_count: 0, awaiting_human_input: false,
    pending_action: null, handoff_approved: false, events: [], tool_calls: [],
    warnings: [], step_count: 3, turn_step_count: 3,
    conversation: [{ role: "user", content: "Prep" }, { role: "assistant", content: "Here is your guidance." }],
    preparation_context: null, resolved_occupation: null, resolved_geography: null,
    profile: "balanced", usage: usage(), latency_ms: 4100, cache_hits: 1, cache_misses: 2,
    ...over,
  };
}

beforeEach(() => {
  searchRun = null;
  try { window.localStorage.clear(); } catch { /* ignore */ }
});
afterEach(() => vi.clearAllMocks());

describe("Agent profile selector", () => {
  it("renders the three tiers and defaults to Balanced", () => {
    render(<AgentPrepareWorkspace />);
    expect(screen.getByRole("radio", { name: /Fast/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Advanced/ })).toBeInTheDocument();
    const balanced = screen.getByRole("radio", { name: /Balanced/ });
    expect(balanced).toHaveAttribute("aria-checked", "true");
  });

  it("sends the Fast profile to the API when selected", async () => {
    start.mockResolvedValue(runResponse({ profile: "fast" }));
    render(<AgentPrepareWorkspace />);
    await userEvent.click(screen.getByRole("radio", { name: /Fast/ }));
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep for PM");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(start).toHaveBeenCalledWith(expect.objectContaining({ goal: "Prep for PM", profile: "fast" }));
  });

  it("sends the Advanced profile to the API when selected", async () => {
    start.mockResolvedValue(runResponse({ profile: "advanced" }));
    render(<AgentPrepareWorkspace />);
    await userEvent.click(screen.getByRole("radio", { name: /Advanced/ }));
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(start).toHaveBeenCalledWith(expect.objectContaining({ profile: "advanced" }));
  });

  it("defaults to balanced when nothing is chosen", async () => {
    start.mockResolvedValue(runResponse());
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    expect(start).toHaveBeenCalledWith(expect.objectContaining({ profile: "balanced" }));
  });

  it("offers no free-text model field — only the three safe tiers (no raw slug)", () => {
    render(<AgentPrepareWorkspace />);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
    // No candidate-facing raw provider slug anywhere in the setup form.
    expect(screen.queryByText(/openai\//i)).not.toBeInTheDocument();
    expect(screen.queryByText(/gpt-/i)).not.toBeInTheDocument();
  });
});

describe("Candidate usage summary", () => {
  it("shows a subtle complete usage line after a completed turn", async () => {
    start.mockResolvedValue(runResponse({ profile: "fast" }));
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    const line = await screen.findByLabelText("Run usage");
    expect(line).toHaveTextContent("Fast");
    expect(line).toHaveTextContent("3 AI calls");
    expect(line).toHaveTextContent("4.1s");
    expect(line).toHaveTextContent("~$0.02");
  });

  it("says 'usage partial' rather than a false-precise cost when coverage is partial", async () => {
    start.mockResolvedValue(runResponse({
      usage: usage({ usage_complete: false, estimated_cost_usd: null, missing_usage_sources: ["tool:AnalyzeJobDescription"] }),
    }));
    render(<AgentPrepareWorkspace />);
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
    await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
    const line = await screen.findByLabelText("Run usage");
    expect(line).toHaveTextContent("usage partial");
    expect(line).not.toHaveTextContent("$0.00");
  });
});

describe("Inspector usage details", () => {
  it("renders the full safe usage breakdown for a run", async () => {
    searchRun = "run_9";
    getRun.mockResolvedValue(runResponse({ run_id: "run_9" }));
    render(<AgentInspector />);
    expect(await screen.findByText("Usage & performance")).toBeInTheDocument();
    const summary = screen.getByText("Usage & performance").closest("div") as HTMLElement;
    expect(within(summary).getByText("Complete")).toBeInTheDocument();
    expect(within(summary).getByText("5,420")).toBeInTheDocument();  // input tokens, localised
    expect(within(summary).getByText("6,524")).toBeInTheDocument();  // total tokens
    expect(within(summary).getByText("3 (2 / 1)")).toBeInTheDocument();  // agent/tool split
    expect(within(summary).getByText("1 / 2")).toBeInTheDocument();  // cache hits / misses
  });

  it("marks partial coverage honestly in the Inspector", async () => {
    searchRun = "run_p";
    getRun.mockResolvedValue(runResponse({
      run_id: "run_p",
      usage: usage({ usage_complete: false, estimated_cost_usd: null, total_tokens: 120, input_tokens: 100, output_tokens: 20, missing_usage_sources: ["tool:AnalyzeJobDescription"] }),
    }));
    render(<AgentInspector />);
    expect(await screen.findByText("Partial")).toBeInTheDocument();
    expect(screen.getByText("Some tool-internal provider usage was unavailable.")).toBeInTheDocument();
  });
});
