import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

// Regression for the Prepare → Practice handoff validation bug: after an approved
// handoff, the completion form ("One last detail…") must appear ONLY for the specific
// missing-config error — never for any 422 — and a valid Fashion / executive completion
// must navigate to Practice. Uses fully mocked API (no backend / provider).

const start = vi.fn();
const getRun = vi.fn();
const resume = vi.fn();
const create = vi.fn();
const options = vi.fn();
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/api/client", () => ({
  api: {
    agent: {
      start: (...a: unknown[]) => start(...a),
      getRun: (...a: unknown[]) => getRun(...a),
      resume: (...a: unknown[]) => resume(...a),
      continue: vi.fn(),
    },
    interviews: {
      create: (...a: unknown[]) => create(...a),
      options: (...a: unknown[]) => options(...a),
    },
    memory: { list: vi.fn(), update: vi.fn(), remove: vi.fn(), preview: vi.fn() },
  },
}));

import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";

/** A run that is already past HITL with an APPROVED handoff, so HandoffRunner fires. */
function approvedRun(over: Record<string, unknown> = {}) {
  return {
    run_id: "run_1", status: "completed", awaiting_human_input: false, response: "",
    tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false,
    memory_count: 0, memory_loaded: [], handoff_approved: true, events: [], tool_calls: [],
    warnings: [], step_count: 3, turn_step_count: 3,
    conversation: [{ role: "user", content: "Prep" }],
    preparation_context: { target_role: "Senior PM" },
    cache_hits: 0, cache_misses: 0, pending_action: null,
    ...over,
  };
}

const missingConfig = new ApiError({
  kind: "validation", status: 422, code: "missing_interview_handoff_config",
  message: "Add the missing industry and career level to start practice.",
});

beforeEach(() => {
  options.mockResolvedValue({
    career_levels: ["entry", "mid", "senior", "executive"], interview_types: ["behavioural"],
  });
  start.mockResolvedValue(approvedRun());
});
afterEach(() => vi.clearAllMocks());

async function startSession() {
  render(<AgentPrepareWorkspace />);
  await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "Prep");
  await userEvent.click(screen.getByRole("button", { name: "Start preparing" }));
}

describe("Practice handoff completion", () => {
  it("shows the completion form ONLY for the missing-config error", async () => {
    create.mockRejectedValueOnce(missingConfig);
    await startSession();
    expect(await screen.findByText("One last detail before practice")).toBeInTheDocument();
  });

  it("does NOT show the completion form for a generic 422", async () => {
    create.mockRejectedValueOnce(new ApiError({
      kind: "validation", status: 422, code: "validation_error",
      message: "We couldn't set up practice from these details. Please review the industry and career level and try again.",
    }));
    await startSession();
    // The safe backend message is shown; the form is not.
    expect(await screen.findByText(/couldn't set up practice/i)).toBeInTheDocument();
    expect(screen.queryByText("One last detail before practice")).not.toBeInTheDocument();
  });

  it("completes with Fashion + executive and navigates to Practice", async () => {
    create.mockRejectedValueOnce(missingConfig);
    create.mockResolvedValueOnce({ session_id: "sess_42" });
    await startSession();
    await screen.findByText("One last detail before practice");

    await userEvent.type(screen.getByLabelText("Industry / sector"), "Fashion");
    await userEvent.selectOptions(screen.getByLabelText("Career level"), "executive");
    await userEvent.click(screen.getByRole("button", { name: /Start practice/ }));

    // Second create carries the supplied gap-fillers.
    const secondCall = create.mock.calls[1];
    expect(secondCall[0]).toMatchObject({ industry_or_sector: "Fashion", career_level: "executive" });
    expect(push).toHaveBeenCalledWith("/practice?session=sess_42&from=coach");
  });

  it("shows a busy label while the completion submits", async () => {
    create.mockRejectedValueOnce(missingConfig);
    let resolveCreate: (v: unknown) => void = () => {};
    create.mockImplementationOnce(() => new Promise((res) => { resolveCreate = res; }));
    await startSession();
    await screen.findByText("One last detail before practice");

    await userEvent.type(screen.getByLabelText("Industry / sector"), "Fashion");
    await userEvent.selectOptions(screen.getByLabelText("Career level"), "executive");
    await userEvent.click(screen.getByRole("button", { name: /Start practice/ }));

    expect(await screen.findByRole("button", { name: "Starting practice…" })).toBeDisabled();
    resolveCreate({ session_id: "sess_9" });
  });

  it("surfaces a safe conflict message (409) without the completion form", async () => {
    create.mockRejectedValueOnce(new ApiError({
      kind: "conflict", status: 409, code: "conflict",
      message: "Interview setup is already being processed. Please wait a moment.",
    }));
    await startSession();
    expect(await screen.findByText(/already being processed/i)).toBeInTheDocument();
    expect(screen.queryByText("One last detail before practice")).not.toBeInTheDocument();
  });

  it("uses GET /interviews/options for career levels (no hard-coded taxonomy)", async () => {
    create.mockRejectedValueOnce(missingConfig);
    await startSession();
    await screen.findByText("One last detail before practice");
    expect(options).toHaveBeenCalled();
    const select = screen.getByLabelText<HTMLSelectElement>("Career level");
    // The options load asynchronously — wait for the returned "executive" option to be
    // rendered rather than reading the select before the promise commits to state.
    expect(await within(select).findByRole("option", { name: "executive" })).toBeInTheDocument();
  });
});
