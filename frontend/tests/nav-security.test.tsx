import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

// P10B-W9.3 - internal Review/Diagnostics visibility + route guard.
// A settable auth mock lets each test act as anonymous / BASIC candidate / platform admin.

type Account = { platform_role: string } | null;
let mockAccount: Account = null;
let mockStatus: "loading" | "authenticated" | "unauthenticated" | "unknown" = "authenticated";

vi.mock("next/navigation", () => ({ usePathname: () => "/app" }));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: mockAccount, status: mockStatus }),
  useAuth: () => ({ account: mockAccount, status: mockStatus }),
}));

import { MoreMenu } from "@/components/layout/MoreMenu";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";

beforeEach(() => {
  mockAccount = { platform_role: "user" };
  mockStatus = "authenticated";
});
afterEach(() => vi.clearAllMocks());

async function openMore() {
  render(<MoreMenu />);
  await userEvent.click(screen.getByRole("button", { name: /More/ }));
  return screen.getByRole("menu");
}

it("BASIC candidate: More menu shows Sources but NOT Review & Diagnostics or Admin", async () => {
  mockAccount = { platform_role: "user" };
  const menu = await openMore();
  expect(within(menu).getByRole("menuitem", { name: /Sources/ })).toBeInTheDocument();
  expect(within(menu).queryByRole("menuitem", { name: /Review & Diagnostics/ })).not.toBeInTheDocument();
  expect(within(menu).queryByRole("menuitem", { name: /Admin/ })).not.toBeInTheDocument();
});

it("platform admin: More menu shows Review & Diagnostics and Admin", async () => {
  mockAccount = { platform_role: "platform_admin" };
  const menu = await openMore();
  expect(within(menu).getByRole("menuitem", { name: /Review & Diagnostics/ })).toHaveAttribute("href", "/review");
  expect(within(menu).getByRole("menuitem", { name: /Admin/ })).toHaveAttribute("href", "/admin");
  expect(within(menu).getByRole("menuitem", { name: /Sources/ })).toBeInTheDocument(); // candidate items remain
});

it("anonymous / unresolved account: no internal items", async () => {
  mockAccount = null;
  const menu = await openMore();
  expect(within(menu).queryByRole("menuitem", { name: /Review & Diagnostics/ })).not.toBeInTheDocument();
  expect(within(menu).queryByRole("menuitem", { name: /Admin/ })).not.toBeInTheDocument();
});

it("RequirePlatformAdmin blocks a BASIC candidate with an access-denied message (not the children)", () => {
  mockAccount = { platform_role: "user" };
  render(
    <RequirePlatformAdmin>
      <div>SECRET DIAGNOSTICS</div>
    </RequirePlatformAdmin>,
  );
  expect(screen.getByText(/access denied/i)).toBeInTheDocument();
  expect(screen.queryByText("SECRET DIAGNOSTICS")).not.toBeInTheDocument();
});

it("RequirePlatformAdmin renders children for a platform admin", () => {
  mockAccount = { platform_role: "platform_admin" };
  render(
    <RequirePlatformAdmin>
      <div>ADMIN DIAGNOSTICS</div>
    </RequirePlatformAdmin>,
  );
  expect(screen.getByText("ADMIN DIAGNOSTICS")).toBeInTheDocument();
});

it("RequirePlatformAdmin shows a neutral loading state while the session resolves (no flash)", () => {
  mockAccount = null;
  mockStatus = "loading";
  render(
    <RequirePlatformAdmin>
      <div>ADMIN DIAGNOSTICS</div>
    </RequirePlatformAdmin>,
  );
  expect(screen.queryByText("ADMIN DIAGNOSTICS")).not.toBeInTheDocument();
  expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
});
