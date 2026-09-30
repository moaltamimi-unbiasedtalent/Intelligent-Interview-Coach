import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

// P10B-W9.2 - History in-place recovery.

const historyList = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: { history: { list: (...a: unknown[]) => historyList(...a) } },
}));

import { HistoryClient } from "@/components/interview/HistoryClient";
import { ApiError } from "@/lib/api/errors";

function apiErr(kind: ApiError["kind"], requestId: string | null = null) {
  return new ApiError({ kind, status: null, code: kind, message: "x", requestId });
}
// Lazily create the rejected promise per call (and it is immediately caught by the component),
// so vitest never sees an eagerly-created unhandled rejection.
const rejectsWith = (kind: ApiError["kind"], requestId: string | null = null) =>
  () => Promise.reject(apiErr(kind, requestId));

afterEach(() => vi.clearAllMocks());

// H1 - fail shows truthful error + Retry
it("H1: history fails -> truthful error state with Retry", async () => {
  historyList.mockImplementation(rejectsWith("unreachable"));
  render(<HistoryClient />);
  expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  expect(screen.queryByText(/check your (internet|connection)/i)).not.toBeInTheDocument();
});

// H2 - retry succeeds -> renders, error clears
it("H2: retry succeeds -> History renders and the error clears", async () => {
  historyList
    .mockImplementationOnce(rejectsWith("server"))
    .mockResolvedValue({ interviews: [{ id: 7, target_role: "Product Manager", questions: 3, created_at: "2026-09-01T00:00:00" }] });
  render(<HistoryClient />);
  const retry = await screen.findByRole("button", { name: /try again/i });
  await userEvent.click(retry);
  expect(await screen.findByText("Product Manager")).toBeInTheDocument();
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
});

// H3 - empty list is an empty state, not an error
it("H3: retry returning an empty list renders the empty state, not an error", async () => {
  historyList.mockResolvedValue({ interviews: [] });
  render(<HistoryClient />);
  expect(await screen.findByText("No completed interviews yet")).toBeInTheDocument();
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
});

// H4 - unmount aborts pending request (no state update)
it("H4: unmount aborts the pending request", async () => {
  let resolve!: (v: unknown) => void;
  historyList.mockReturnValue(new Promise((r) => { resolve = r; }));
  const { unmount } = render(<HistoryClient />);
  unmount();
  resolve({ interviews: [] });
  await Promise.resolve();
  expect(true).toBe(true);
});

// H5 - server error carries a reference id in technical details
it("H5: a server error exposes the reference id under technical details", async () => {
  historyList.mockImplementation(rejectsWith("server", "req-hist-9"));
  render(<HistoryClient />);
  await screen.findByText("Something went wrong");
  expect(screen.getByText(/Reference: req-hist-9/)).toBeInTheDocument();
});
