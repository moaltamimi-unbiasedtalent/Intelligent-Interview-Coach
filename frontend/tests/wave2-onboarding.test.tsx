import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// P10B Wave 2 — premium onboarding: navigation, resume, review, completion routing, and the
// bounded coaching-style control (with its scoring-independence note).

const onboarding = vi.fn();
const updatePreferences = vi.fn();
const replace = vi.fn();
const refresh = vi.fn();

let account: Record<string, unknown> = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
  status: "active", email_verified: true, providers: ["password"], auth_method: "session",
  capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en",
  coaching_style: "balanced", career_geography: "", target_role: "",
  onboarding_completed: false, onboarding_step: 0,
};

vi.mock("@/lib/api/client", () => ({
  api: {
    auth: {
      onboarding: (...a: unknown[]) => onboarding(...a),
      updatePreferences: (...a: unknown[]) => updatePreferences(...a),
    },
  },
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));

vi.mock("@/components/auth/AuthProvider", () => {
  const value = () => ({
    account, status: "authenticated", isRealSession: true, responseDetail: "brief",
    setResponseDetail: vi.fn(), refresh, signOut: vi.fn(),
  });
  return { useAuth: value, useAuthOptional: value };
});

import { OnboardingClient } from "@/components/onboarding/OnboardingClient";
import { CoachingStyleField } from "@/components/settings/CoachingStyleField";

afterEach(() => vi.clearAllMocks());

describe("Wave 2 — CoachingStyleField", () => {
  it("offers the four bounded styles as radios and states scoring is unchanged", async () => {
    const onChange = vi.fn();
    render(<CoachingStyleField value="balanced" onChange={onChange} />);
    for (const name of ["Supportive", "Balanced", "Direct", "Challenging"]) {
      expect(screen.getByRole("radio", { name: new RegExp(name) })).toBeInTheDocument();
    }
    expect(screen.getByText(/not how your interview performance is scored/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /Challenging/ }));
    expect(onChange).toHaveBeenCalledWith("challenging");
  });
});

describe("Wave 2 — OnboardingClient", () => {
  it("walks Welcome → About → Career and persists step + fields (no auto-start)", async () => {
    onboarding.mockResolvedValue(account);
    updatePreferences.mockResolvedValue(account);
    render(<OnboardingClient />);

    // Welcome step.
    expect(screen.getByRole("heading", { name: /set up Mo around you/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Get started" }));
    await waitFor(() => expect(onboarding).toHaveBeenCalledWith({ step: 1 }));

    // About You — enter a preferred name, continue.
    const nameInput = await screen.findByRole("textbox");
    await userEvent.type(nameInput, "Jo");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(updatePreferences).toHaveBeenCalledWith({ display_name: "Jo" }));

    // Nothing was auto-started (no interview/agent) and we never left to /app yet.
    expect(replace).not.toHaveBeenCalled();
  });

  it("resumes from the persisted onboarding_step", async () => {
    account = { ...account, onboarding_step: 3 };
    render(<OnboardingClient />);
    // Step 4 of 7 is the Coaching step.
    await waitFor(() => expect(screen.getByText(/Step 4 of 7/i)).toBeInTheDocument());
    account = { ...account, onboarding_step: 0 }; // reset for other tests
  });

  it("shows a recoverable error on completion failure, does not navigate, and retry succeeds", async () => {
    account = { ...account, onboarding_step: 6 }; // start on the Review step
    updatePreferences.mockResolvedValue(account);
    // First completion attempt fails; the retry succeeds.
    onboarding.mockRejectedValueOnce(new Error("server")).mockResolvedValue(account);
    render(<OnboardingClient />);

    const enter = await screen.findByRole("button", { name: "Enter Ask4Mo" });
    await userEvent.click(enter);

    // Announced, recoverable error; stayed put (no navigation to /app).
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn.?t complete your setup/i);
    expect(alert).toHaveTextContent(/choices are saved/i);
    expect(replace).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled(); // never refreshed/entered the app on failure

    // Retry: clears the error, completes, refreshes, enters /app.
    await userEvent.click(screen.getByRole("button", { name: "Enter Ask4Mo" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app"));
    expect(refresh).toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    account = { ...account, onboarding_step: 0 }; // reset for other tests
  });
});
