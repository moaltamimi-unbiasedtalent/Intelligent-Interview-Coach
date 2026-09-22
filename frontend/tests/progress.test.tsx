import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const list = vi.fn();
const remove = vi.fn();
const progressGet = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    memory: { list: (...a: unknown[]) => list(...a), remove: (...a: unknown[]) => remove(...a) },
    progress: { get: (...a: unknown[]) => progressGet(...a) },
  },
}));

const EMPTY_PROGRESS = {
  interviews_completed: 0,
  answers_evaluated: 0,
  average_practice_score: null,
  most_common_improvement_area: null,
  average_answer_seconds: null,
  recent_interviews: [],
};

import { ProgressClient } from "@/components/progress/ProgressClient";

const memories = [
  { id: 1, category: "recurring_gap", summary: "Executive communication", target_role: "Head of People", source_run_id: null, created_at: null, updated_at: null },
  { id: 2, category: "strength", summary: "Board communication", target_role: null, source_run_id: null, created_at: null, updated_at: null },
];

afterEach(() => vi.clearAllMocks());

// PracticeProgress fetches /progress; default to an empty (no-practice) response so
// the memory-focused tests are unaffected (it renders nothing when there is no practice).
beforeEach(() => progressGet.mockResolvedValue(EMPTY_PROGRESS));

describe("Progress — preparation memory", () => {
  it("renders saved memories under friendly group labels", async () => {
    list.mockResolvedValue({ memories });
    render(<ProgressClient />);

    expect(await screen.findByText("Executive communication")).toBeInTheDocument();
    expect(screen.getByText("Board communication")).toBeInTheDocument();
    // Friendly group headings, not raw category codes.
    expect(screen.getByText("Priorities")).toBeInTheDocument();
    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.queryByText("recurring_gap")).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing is saved", async () => {
    list.mockResolvedValue({ memories: [] });
    render(<ProgressClient />);
    expect(await screen.findByText("Nothing saved yet.")).toBeInTheDocument();
  });

  it("requires confirmation before removing, then calls the API", async () => {
    list.mockResolvedValue({ memories });
    remove.mockResolvedValue({ deleted: true, id: 1 });
    render(<ProgressClient />);
    await screen.findByText("Executive communication");

    // First click reveals a confirm affordance; it does NOT delete immediately.
    await userEvent.click(screen.getByRole("button", { name: /Remove saved memory: Executive communication/ }));
    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByText("Remove this?")).toBeInTheDocument();

    // Cancel keeps the item.
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(remove).not.toHaveBeenCalled();

    // Confirm deletes and removes it from the list.
    await userEvent.click(screen.getByRole("button", { name: /Remove saved memory: Executive communication/ }));
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Executive communication")).not.toBeInTheDocument());
  });

  it("shows a safe error state when the API fails", async () => {
    list.mockRejectedValue(Object.assign(new Error("boom"), { userMessage: "Couldn't load your preparation memory.", requestId: "req-1" }));
    render(<ProgressClient />);
    expect(await screen.findByText("Couldn't load your preparation memory.")).toBeInTheDocument();
  });

  it("never displays an internal user id", async () => {
    list.mockResolvedValue({ memories });
    const { container } = render(<ProgressClient />);
    await screen.findByText("Executive communication");
    expect(container.textContent).not.toMatch(/user_id/i);
  });

  it("shows the target role chip only when present", async () => {
    list.mockResolvedValue({ memories });
    render(<ProgressClient />);
    const gap = (await screen.findByText("Executive communication")).closest("div");
    expect(within(gap as HTMLElement).getByText("Head of People")).toBeInTheDocument();
  });
});

describe("Progress — practice metrics", () => {
  it("shows practice tiles and a linked recent session when practice exists", async () => {
    list.mockResolvedValue({ memories: [] });
    progressGet.mockResolvedValue({
      interviews_completed: 3,
      answers_evaluated: 7,
      average_practice_score: 74.5,
      most_common_improvement_area: "Add measurable outcomes",
      average_answer_seconds: 92,
      recent_interviews: [
        { id: 36, target_role: "Backend Software Engineer", mode: null, status: "completed", questions: 3, created_at: "2026-09-21T09:28:28" },
      ],
    });
    render(<ProgressClient />);

    expect(await screen.findByText("Practice progress")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // sessions
    expect(screen.getByText("74.5/100")).toBeInTheDocument(); // average score
    expect(screen.getByText("Add measurable outcomes")).toBeInTheDocument();
    // Recent session links to its history detail page.
    const link = screen.getByRole("link", { name: /Backend Software Engineer/ });
    expect(link).toHaveAttribute("href", "/history/36");
  });

  it("renders no practice section (and no crash) when there is no practice", async () => {
    list.mockResolvedValue({ memories });
    progressGet.mockResolvedValue(EMPTY_PROGRESS);
    render(<ProgressClient />);
    // Memory still renders; the practice section stays absent (honest empty behaviour).
    await screen.findByText("Executive communication");
    expect(screen.queryByText("Practice progress")).not.toBeInTheDocument();
  });
});
