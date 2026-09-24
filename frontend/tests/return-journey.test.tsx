import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const me = vi.fn();
const listActive = vi.fn();
const historyList = vi.fn();
const progressGet = vi.fn();
const memoryList = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: {
      auth: { me: (...a: unknown[]) => me(...a) },
      interviews: { listActive: (...a: unknown[]) => listActive(...a) },
      history: { list: (...a: unknown[]) => historyList(...a) },
      progress: { get: (...a: unknown[]) => progressGet(...a) },
      memory: { list: (...a: unknown[]) => memoryList(...a) },
    },
    ApiError: actual.ApiError,
  };
});

import { AuthProvider } from "@/components/auth/AuthProvider";
import { ReturnJourney } from "@/components/home/ReturnJourney";

const ACCOUNT = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
};

afterEach(() => vi.clearAllMocks());

describe("ReturnJourney", () => {
  it("shows a continue-practice card when an active session exists", async () => {
    me.mockResolvedValue(ACCOUNT);
    listActive.mockResolvedValue({
      sessions: [{ session_id: "s1", target_role: "Backend Engineer", state: "AWAITING_ANSWER", question_number: 3, questions_planned: 6, updated_at: null }],
    });
    historyList.mockResolvedValue({ interviews: [{}, {}] });
    progressGet.mockResolvedValue({ interviews_completed: 2, answers_evaluated: 8, recent_interviews: [] });
    memoryList.mockResolvedValue({ memories: [{}] });

    render(<AuthProvider><ReturnJourney /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("Welcome back")).toBeInTheDocument());
    expect(screen.getByText(/Backend Engineer/)).toBeInTheDocument();
    expect(screen.getByText(/3 of 6 questions/)).toBeInTheDocument();
    const cont = screen.getByRole("link", { name: /Continue practice/i });
    expect(cont).toHaveAttribute("href", "/practice?session=s1");
    expect(screen.getByRole("link", { name: /History \(2\)/ })).toHaveAttribute("href", "/history");
  });

  it("renders nothing for a first-use account with no activity", async () => {
    me.mockResolvedValue(ACCOUNT);
    listActive.mockResolvedValue({ sessions: [] });
    historyList.mockResolvedValue({ interviews: [] });
    progressGet.mockResolvedValue({ interviews_completed: 0, answers_evaluated: 0, recent_interviews: [] });
    memoryList.mockResolvedValue({ memories: [] });

    const { container } = render(<AuthProvider><ReturnJourney /></AuthProvider>);
    await waitFor(() => expect(me).toHaveBeenCalled());
    // Give the effect a tick; nothing should render.
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText("Welcome back")).not.toBeInTheDocument();
    expect(container.textContent).toBe("");
  });
});
