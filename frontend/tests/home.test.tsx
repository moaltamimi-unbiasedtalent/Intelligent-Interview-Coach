import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HomeEntry } from "@/components/coach/HomeEntry";
import { clearPrepareDraft, readPrepareDraft } from "@/lib/prepareDraft";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

beforeEach(() => { push.mockClear(); clearPrepareDraft(); });
afterEach(() => clearPrepareDraft());

describe("Home entry", () => {
  it("transfers the typed goal into a draft and navigates to Prepare (no URL leak)", async () => {
    render(<HomeEntry />);
    await userEvent.type(
      screen.getByLabelText("What interview are you preparing for?"),
      "Executive HR Director role at a fashion company",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ask Mo" }));

    expect(push).toHaveBeenCalledWith("/prepare"); // §24: no ?goal= in the URL
    expect(readPrepareDraft()).toEqual({
      source: "home",
      action: "start",
      goal: "Executive HR Director role at a fashion company",
    });
  });

  it("disables the CTA and does nothing for whitespace-only input (§6/§23)", async () => {
    render(<HomeEntry />);
    const start = screen.getByRole("button", { name: "Ask Mo" });
    expect(start).toBeDisabled();
    await userEvent.type(screen.getByLabelText("What interview are you preparing for?"), "   ");
    expect(start).toBeDisabled();
    expect(push).not.toHaveBeenCalled();
    expect(readPrepareDraft()).toBeNull();
  });

  it("the job-description shortcut writes a jd draft and navigates (§29)", async () => {
    render(<HomeEntry />);
    await userEvent.click(screen.getByRole("button", { name: /Paste a job description/ }));
    expect(push).toHaveBeenCalledWith("/prepare");
    expect(readPrepareDraft()).toEqual({ source: "home", action: "job_description" });
  });

  it("the background shortcut writes a background draft (no CV-upload claim) (§16/§30)", async () => {
    render(<HomeEntry />);
    expect(screen.queryByText(/Add your CV/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Add your background/ }));
    expect(push).toHaveBeenCalledWith("/prepare");
    expect(readPrepareDraft()).toEqual({ source: "home", action: "candidate_background" });
  });

  it("states data is used only to personalise preparation", () => {
    render(<HomeEntry />);
    expect(
      screen.getByText(/used only to personalise your preparation/i),
    ).toBeInTheDocument();
  });
});
