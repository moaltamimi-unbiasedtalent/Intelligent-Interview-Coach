import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push, replace: vi.fn() }),
}));

import { TutorialController, START_TOUR_EVENT } from "@/components/tutorial/TutorialController";
import { ASK4MO_TUTORIAL_VERSION } from "@/lib/tutorial/steps";

function tutorialState() {
  return JSON.parse(window.localStorage.getItem("ask4mo.tutorial") || "{}");
}

beforeEach(() => {
  window.localStorage.clear();
  push.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("Guided tour", () => {
  it("shows a non-blocking first-visit invitation on Home", () => {
    render(<TutorialController />);
    expect(screen.getByRole("dialog", { name: "Welcome to Ask4Mo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start tour" })).toBeInTheDocument();
  });

  it("starts, advances, goes back, and shows progress", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    expect(screen.getByText("Start with your goal")).toBeInTheDocument();
    expect(screen.getByText("1 of 12")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Give Mo the right context")).toBeInTheDocument();
    expect(screen.getByText("2 of 12")).toBeInTheDocument();
    // Route-aware: advancing toward a /prepare step asks the router to navigate.
    expect(push).toHaveBeenCalledWith("/prepare");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Start with your goal")).toBeInTheDocument();
  });

  it("'Maybe later' dismisses and does not auto-reopen on re-render", () => {
    const { unmount } = render(<TutorialController />);
    fireEvent.click(screen.getByRole("button", { name: "Maybe later" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(tutorialState().dismissed).toBe(true);
    unmount();
    render(<TutorialController />);
    expect(screen.queryByRole("dialog", { name: "Welcome to Ask4Mo" })).not.toBeInTheDocument();
  });

  it("completing marks completed and does not auto-reopen", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    for (let i = 0; i < 11; i++) {
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
    }
    expect(screen.getByText("12 of 12")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(tutorialState().completed).toBe(true);
    expect(tutorialState().version).toBe(ASK4MO_TUTORIAL_VERSION);
  });

  it("can be replayed via the start-tour event even after completion", async () => {
    window.localStorage.setItem("ask4mo.tutorial", JSON.stringify({ version: ASK4MO_TUTORIAL_VERSION, completed: true, dismissed: false, lastStep: 11 }));
    render(<TutorialController />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // no auto-invite
    fireEvent(window, new CustomEvent(START_TOUR_EVENT));
    expect(await screen.findByText("Start with your goal")).toBeInTheDocument();
  });

  it("Escape closes the tour", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stores NO candidate data — only version/step/completed/dismissed", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    const keys = Object.keys(tutorialState()).sort();
    expect(keys).toEqual(["completed", "dismissed", "lastStep", "version"]);
  });
});
