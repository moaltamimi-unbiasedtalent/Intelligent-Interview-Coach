import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const submit = vi.fn();
const remove = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: { feedback: { get: (...a: unknown[]) => get(...a), submit: (...a: unknown[]) => submit(...a), remove: (...a: unknown[]) => remove(...a) } },
}));

import { FeedbackControl } from "@/components/feedback/FeedbackControl";

beforeEach(() => { get.mockResolvedValue(null); submit.mockResolvedValue({ id: 1 }); });
afterEach(() => vi.clearAllMocks());

describe("FeedbackControl", () => {
  it("renders Helpful / Not helpful with aria-pressed", async () => {
    render(<FeedbackControl surface="agent_answer" targetId="run1:1" />);
    expect(await screen.findByRole("button", { name: "Helpful" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Not helpful" })).toHaveAttribute("aria-pressed", "false");
  });

  it("submits Helpful and reflects the selection", async () => {
    render(<FeedbackControl surface="agent_answer" targetId="run1:1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Helpful" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({ surface: "agent_answer", target_id: "run1:1", rating: "helpful", comment: null }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Helpful" })).toHaveAttribute("aria-pressed", "true"));
  });

  it("shows a comment box after Not helpful and submits the comment", async () => {
    render(<FeedbackControl surface="final_report" targetId="s1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Not helpful" }));
    const box = await screen.findByLabelText(/What could be better/);
    await userEvent.type(box, "Too generic");
    await userEvent.click(screen.getByRole("button", { name: "Save comment" }));
    await waitFor(() => expect(submit).toHaveBeenLastCalledWith({ surface: "final_report", target_id: "s1", rating: "not_helpful", comment: "Too generic" }));
  });

  it("shows an error and preserves input when saving fails", async () => {
    // The rating persists; the follow-up comment save fails.
    submit
      .mockResolvedValueOnce({ id: 1 })
      .mockRejectedValueOnce(Object.assign(new Error("x"), { userMessage: "Couldn't save your feedback. Please try again." }));
    render(<FeedbackControl surface="agent_answer" targetId="run1:1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Not helpful" }));
    const box = await screen.findByLabelText(/What could be better/);
    await userEvent.type(box, "keep me");
    await userEvent.click(screen.getByRole("button", { name: "Save comment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't save your feedback");
    expect((screen.getByLabelText(/What could be better/) as HTMLTextAreaElement).value).toBe("keep me");
  });

  it("restores a saved rating after refresh", async () => {
    get.mockResolvedValue({ id: 1, surface: "agent_answer", target_id: "run1:1", rating: "helpful", comment: null, created_at: null, updated_at: null });
    render(<FeedbackControl surface="agent_answer" targetId="run1:1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Helpful" })).toHaveAttribute("aria-pressed", "true"));
  });
});
