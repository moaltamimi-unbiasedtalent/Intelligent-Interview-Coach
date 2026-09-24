import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const me = vi.fn();
const updatePreferences = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: {
      auth: {
        me: (...a: unknown[]) => me(...a),
        updatePreferences: (...a: unknown[]) => updatePreferences(...a),
      },
    },
    ApiError: actual.ApiError,
  };
});

import { AuthProvider } from "@/components/auth/AuthProvider";
import { ResponseDetailPreference } from "@/components/settings/ResponseDetailPreference";

const ACCOUNT = (detail: string) => ({
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: detail,
});

afterEach(() => vi.clearAllMocks());

describe("ResponseDetailPreference", () => {
  it("reflects the current preference and updates it server-side", async () => {
    me.mockResolvedValue(ACCOUNT("brief"));
    updatePreferences.mockResolvedValue(ACCOUNT("detailed"));

    render(<AuthProvider><ResponseDetailPreference /></AuthProvider>);
    await waitFor(() => expect(screen.getByLabelText(/Brief/)).toBeChecked());

    await userEvent.click(screen.getByLabelText(/Detailed/));
    await waitFor(() =>
      expect(updatePreferences).toHaveBeenCalledWith({ response_detail: "detailed" }),
    );
    await waitFor(() => expect(screen.getByLabelText(/Detailed/)).toBeChecked());
  });

  it("explains that nothing is removed", async () => {
    me.mockResolvedValue(ACCOUNT("brief"));
    render(<AuthProvider><ResponseDetailPreference /></AuthProvider>);
    expect(screen.getByText(/nothing is removed/i)).toBeInTheDocument();
  });
});
