import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P10B-W9.5 — Tutorial v2: account-scoped state, Opportunity-centred step model, 0 dead targets,
// localized chrome, shared-browser isolation, replay.

const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/app",
  useRouter: () => ({ push, replace: vi.fn() }),
}));

// Settable account scope (for shared-browser isolation).
let mockUserId: number | null = 1;
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => (mockUserId == null ? null : { account: { user_id: mockUserId }, status: "authenticated" }),
}));

import { TutorialController, START_TOUR_EVENT } from "@/components/tutorial/TutorialController";
import { ASK4MO_TUTORIAL_VERSION, TUTORIAL_STEPS } from "@/lib/tutorial/steps";
import enMessages from "@/lib/i18n/messages/en";

function stateFor(userId: number | string) {
  return JSON.parse(window.localStorage.getItem(`ask4mo.tutorial:${userId}`) || "{}");
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  mockUserId = 1;
  push.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("Tutorial v2 — structure", () => {
  it("T1: includes Opportunity, role/JD, evidence, Prepare, Practice, Progress, History", () => {
    const ids = TUTORIAL_STEPS.map((s) => s.id);
    for (const id of ["opportunities", "role-jd", "evidence", "prepare", "practice", "progress", "history"]) {
      expect(ids).toContain(id);
    }
  });

  it("T2: Opportunity appears before Prepare and Practice", () => {
    const ids = TUTORIAL_STEPS.map((s) => s.id);
    expect(ids.indexOf("opportunities")).toBeLessThan(ids.indexOf("prepare"));
    expect(ids.indexOf("opportunities")).toBeLessThan(ids.indexOf("practice"));
  });

  it("T3: zero permanently-dead targets (every target is a known-existing anchor; others route-only)", () => {
    const KNOWN = new Set([
      "home-start", "opportunity-entry", "target-role", "ask-mo", "sources", "memory",
      "progress", "history", "help",
    ]);
    for (const s of TUTORIAL_STEPS) {
      expect(s.route.startsWith("/")).toBe(true);
      if (s.target) expect(KNOWN.has(s.target)).toBe(true); // else: intentionally route-only
    }
    expect(ASK4MO_TUTORIAL_VERSION).toBe(2);
  });

  it("T10: every tutorial step + chrome key exists in the English catalogue", () => {
    const tut = enMessages.tutorial as Record<string, string>;
    for (const s of TUTORIAL_STEPS) {
      expect(tut[s.titleKey.replace("tutorial.", "")]).toBeTruthy();
      expect(tut[s.bodyKey.replace("tutorial.", "")]).toBeTruthy();
    }
    for (const k of ["start", "later", "skip", "back", "next", "finish", "close", "learnMore", "openHelp", "stepOf", "welcomeCreate", "welcomeTour", "welcomeWorkspace"]) {
      expect(tut[k]).toBeTruthy();
    }
  });
});

describe("Tutorial v2 — controller", () => {
  it("shows a non-blocking first-visit invitation on Home", () => {
    render(<TutorialController />);
    expect(screen.getByRole("dialog", { name: "Welcome to Ask4Mo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start tour" })).toBeInTheDocument();
  });

  it("T8: starts, advances across routes, goes back, shows localized progress", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    expect(screen.getByText("Welcome to your workspace")).toBeInTheDocument();
    expect(screen.getByText("1 of 9")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" })); // -> opportunities (/app)
    expect(screen.getByText("Keep one job together")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" })); // -> role-jd (/prepare)
    expect(screen.getByText("Add the role and job description")).toBeInTheDocument();
    expect(push).toHaveBeenCalledWith("/prepare");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Keep one job together")).toBeInTheDocument();
  });

  it("T6: 'Maybe later' dismisses (account-scoped) and does not auto-reopen", () => {
    const { unmount } = render(<TutorialController />);
    fireEvent.click(screen.getByRole("button", { name: "Maybe later" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stateFor(1).dismissed).toBe(true);
    unmount();
    render(<TutorialController />);
    expect(screen.queryByRole("dialog", { name: "Welcome to Ask4Mo" })).not.toBeInTheDocument();
  });

  it("T5: completing marks completed=version 2 and does not auto-reopen", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    for (let i = 0; i < TUTORIAL_STEPS.length - 1; i++) {
      await userEvent.click(screen.getByRole("button", { name: "Next" }));
    }
    expect(screen.getByText(`${TUTORIAL_STEPS.length} of ${TUTORIAL_STEPS.length}`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(stateFor(1).completed).toBe(true);
    expect(stateFor(1).version).toBe(2);
  });

  it("T7: can be replayed via the start-tour event even after completion", async () => {
    window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, completed: true, dismissed: false, lastStep: 8 }));
    render(<TutorialController />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // no auto-invite
    fireEvent(window, new CustomEvent(START_TOUR_EVENT));
    expect(await screen.findByText("Welcome to your workspace")).toBeInTheDocument(); // starts at step 1
  });

  it("T4: a completed account does not suppress another account's tour on the same browser", () => {
    // Account 1 completes.
    window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, completed: true, dismissed: false, lastStep: 8 }));
    mockUserId = 1;
    const { unmount } = render(<TutorialController />);
    expect(screen.queryByRole("dialog", { name: "Welcome to Ask4Mo" })).not.toBeInTheDocument();
    unmount();
    // Account 2 on the same browser still gets its own invitation.
    mockUserId = 2;
    render(<TutorialController />);
    expect(screen.getByRole("dialog", { name: "Welcome to Ask4Mo" })).toBeInTheDocument();
  });

  it("Escape closes the tour", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("auto-starts once from the Welcome flag, then clears it", async () => {
    window.sessionStorage.setItem("ask4mo.tutorial.autostart", "2");
    render(<TutorialController />);
    expect(await screen.findByText("Welcome to your workspace")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("ask4mo.tutorial.autostart")).toBeNull();
  });

  it("stores NO candidate data — only version/step/completed/dismissed", async () => {
    render(<TutorialController />);
    await userEvent.click(screen.getByRole("button", { name: "Start tour" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    const keys = Object.keys(stateFor(1)).sort();
    expect(keys).toEqual(["completed", "dismissed", "lastStep", "version"]);
  });
});
