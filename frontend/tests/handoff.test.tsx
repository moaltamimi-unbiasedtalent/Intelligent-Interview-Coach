import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const create = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/client", () => ({ api: { interviews: { create: (...a: unknown[]) => create(...a) } } }));

import { StartPracticeButton } from "@/components/preparation/StartPracticeButton";

afterEach(() => vi.clearAllMocks());

describe("Practice handoff", () => {
  it("creates an interview from the PreparationContext and navigates to /practice", async () => {
    create.mockResolvedValue({ session_id: "sess_42", state: "AWAITING_ANSWER", question_number: 1, report_available: false, target_role: "Data Analyst" });
    render(<StartPracticeButton prep={{ targetRole: "Data Analyst", requiredSkills: ["SQL"], jobDescription: "JD" }} />);

    await userEvent.click(screen.getByRole("button", { name: /Start interview practice/i }));

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({
        preparation_context: expect.objectContaining({ target_role: "Data Analyst", required_skills: ["SQL"] }),
      }),
    );
    expect(push).toHaveBeenCalledWith("/practice?session=sess_42");
  });

  it("does not create or navigate without a target role", async () => {
    render(<StartPracticeButton prep={{}} />);
    const btn = screen.getByRole("button", { name: /Start interview practice/i });
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(create).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a safe error and does not navigate when creation fails", async () => {
    const { ApiError } = await import("@/lib/api/errors");
    create.mockRejectedValue(new ApiError({ kind: "unavailable", status: 503, code: "not_configured", message: "x", requestId: "r9" }));
    render(<StartPracticeButton prep={{ targetRole: "PM" }} />);
    await userEvent.click(screen.getByRole("button", { name: /Start interview practice/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
