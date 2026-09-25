import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

// Role-aware Admin navigation (Capstone P6.5 closure §7): the Admin item is visible ONLY to
// a PLATFORM_ADMIN, derived from trusted account state — never a client override — and never
// flashes during loading. Hiding the link is UX only; the API stays authoritative.

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

const me = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: { auth: { me: (...a: unknown[]) => me(...a), updatePreferences: vi.fn() } },
    ApiError: actual.ApiError,
  };
});

import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { MoreMenu } from "@/components/layout/MoreMenu";

const ACCOUNT = (role: string) => ({
  user_id: 1, email: "u@example.com", display_name: null, platform_role: role,
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
});

function renderMenu() {
  return render(
    <AuthProvider>
      <I18nProvider initialLocale="en">
        <MoreMenu />
      </I18nProvider>
    </AuthProvider>,
  );
}

afterEach(() => {
  me.mockReset();
});

describe("role-aware Admin navigation", () => {
  it("shows Admin to a platform admin", async () => {
    me.mockResolvedValue(ACCOUNT("platform_admin"));
    renderMenu();
    await waitFor(() => expect(me).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /more/i }));
    await waitFor(() => expect(screen.getByRole("menuitem", { name: /Admin/i })).toBeInTheDocument());
  });

  it("does NOT show Admin to a normal user", async () => {
    me.mockResolvedValue(ACCOUNT("user"));
    renderMenu();
    await waitFor(() => expect(me).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /more/i }));
    // The other menu items render, but Admin does not.
    await waitFor(() => expect(screen.getByRole("menuitem", { name: /Workspaces/i })).toBeInTheDocument());
    expect(screen.queryByRole("menuitem", { name: /Admin/i })).toBeNull();
  });

  it("does NOT flash Admin before the session resolves", async () => {
    // me never resolves during this assertion window → account stays null → no Admin item.
    me.mockReturnValue(new Promise(() => {}));
    renderMenu();
    await userEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(screen.queryByRole("menuitem", { name: /Admin/i })).toBeNull();
  });
});
