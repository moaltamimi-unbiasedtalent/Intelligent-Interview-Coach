import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HomeEntry } from "@/components/coach/HomeEntry";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("Home entry", () => {
  it("primary CTA navigates to Prepare", async () => {
    render(<HomeEntry />);
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(push).toHaveBeenCalledWith("/prepare");
  });

  it("states data is used only to personalise preparation", () => {
    render(<HomeEntry />);
    expect(
      screen.getByText(/used only to personalise your preparation/i),
    ).toBeInTheDocument();
  });
});
