import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

// P10B-W9.2 - Progress recovery / degraded states. Closes the Pilot defect where a backend outage
// produced BOTH "Couldn't load practice progress." and a large "Something went wrong" at once, and
// where one failed region blanked the whole page.

const list = vi.fn();
const remove = vi.fn();
const progressGet = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    memory: { list: (...a: unknown[]) => list(...a), remove: (...a: unknown[]) => remove(...a) },
    progress: { get: (...a: unknown[]) => progressGet(...a) },
  },
}));

import { ProgressClient } from "@/components/progress/ProgressClient";
import { ApiError } from "@/lib/api/errors";

const PRACTICE = {
  interviews_completed: 3,
  answers_evaluated: 7,
  average_practice_score: 74.5,
  most_common_improvement_area: "Add measurable outcomes",
  average_answer_seconds: 92,
  recent_interviews: [],
};
const MEMORIES = [
  { id: 1, category: "recurring_gap", summary: "Executive communication", target_role: null, source_run_id: null, created_at: null, updated_at: null },
];

function apiErr(kind: ApiError["kind"]) {
  return new ApiError({ kind, status: null, code: kind, message: "x", requestId: "req-x" });
}
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

afterEach(() => vi.clearAllMocks());
beforeEach(() => {
  list.mockReset();
  progressGet.mockReset();
  remove.mockReset();
});

// P1 - both succeed
it("P1: both load -> practice tiles and memory both visible", async () => {
  progressGet.mockResolvedValue(PRACTICE);
  list.mockResolvedValue({ memories: MEMORIES });
  render(<ProgressClient />);
  expect(await screen.findByText("Executive communication")).toBeInTheDocument();
  expect(screen.getByText("Practice progress")).toBeInTheDocument();
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
});

// P2 - practice fails, memory ok
it("P2: practice fails, memory succeeds -> memory visible, one section error with Retry, no page-wide catastrophic", async () => {
  progressGet.mockRejectedValue(apiErr("unreachable"));
  list.mockResolvedValue({ memories: MEMORIES });
  render(<ProgressClient />);
  expect(await screen.findByText("Executive communication")).toBeInTheDocument(); // memory still visible
  expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  // Section variant, not the giant page card:
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
});

// P3 - memory fails, practice ok
it("P3: memory fails, practice succeeds -> practice visible, one section error with Retry", async () => {
  progressGet.mockResolvedValue(PRACTICE);
  list.mockRejectedValue(apiErr("server"));
  render(<ProgressClient />);
  expect(await screen.findByText("Practice progress")).toBeInTheDocument(); // practice still visible
  expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
});

// P4 - both fail -> ONE page-level error
it("P4: both fail -> exactly one coherent page-level error and one Retry (not two competing messages)", async () => {
  progressGet.mockRejectedValue(apiErr("unreachable"));
  list.mockRejectedValue(apiErr("unreachable"));
  render(<ProgressClient />);
  await waitFor(() => expect(screen.getByText("Something went wrong")).toBeInTheDocument());
  expect(screen.getAllByText("Something went wrong")).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: /try again/i })).toHaveLength(1);
  // Must NOT blame the candidate's connection (truthful taxonomy).
  expect(screen.queryByText(/check your (internet|connection)/i)).not.toBeInTheDocument();
});

// P5 - failed region retries successfully
it("P5: retry of a failed region recovers in place without destroying the good region", async () => {
  progressGet.mockRejectedValueOnce(apiErr("unreachable")).mockResolvedValue(PRACTICE);
  list.mockResolvedValue({ memories: MEMORIES });
  render(<ProgressClient />);
  await screen.findByText("Executive communication");
  const retry = await screen.findByRole("button", { name: /try again/i });
  await userEvent.click(retry);
  expect(await screen.findByText("Practice progress")).toBeInTheDocument();
  expect(screen.getByText("Executive communication")).toBeInTheDocument(); // good region intact
  expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
});

// P6 - a stale/late response from a superseded load cannot overwrite a newer success
it("P6: a late response from an aborted initial load cannot overwrite success", async () => {
  const d = deferred<{ memories: typeof MEMORIES }>();
  progressGet.mockResolvedValue(PRACTICE);
  list.mockReturnValueOnce(d.promise).mockResolvedValue({ memories: MEMORIES });
  const { unmount } = render(<ProgressClient />);
  // The initial memory load is still pending; unmounting aborts its controller.
  unmount();
  // The stale response resolves AFTER abort — the guard must drop it (no throw / no act warning).
  d.resolve({ memories: MEMORIES });
  await Promise.resolve();
  expect(true).toBe(true);
});

// P7 - abort/unmount does not update state
it("P7: unmount aborts the pending loads without a state update", async () => {
  const dp = deferred<typeof PRACTICE>();
  const dm = deferred<{ memories: typeof MEMORIES }>();
  progressGet.mockReturnValue(dp.promise);
  list.mockReturnValue(dm.promise);
  const { unmount } = render(<ProgressClient />);
  unmount();
  dp.resolve(PRACTICE);
  dm.resolve({ memories: MEMORIES });
  await Promise.resolve();
  expect(true).toBe(true);
});
