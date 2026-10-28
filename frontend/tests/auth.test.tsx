import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const me = vi.fn();
const login = vi.fn();
const logout = vi.fn();
const replace = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    api: {
      auth: {
        me: (...a: unknown[]) => me(...a),
        login: (...a: unknown[]) => login(...a),
        logout: (...a: unknown[]) => logout(...a),
      },
    },
    ApiError: actual.ApiError,
  };
});

let pathname = "/prepare";
let search = "";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));

import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { AccountMenu } from "@/components/auth/AccountMenu";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { SignInForm } from "@/components/auth/SignInForm";

const SESSION_ACCOUNT = {
  user_id: 1, email: "user@example.com", display_name: null,
  platform_role: "user", tier: "basic", status: "active",
  email_verified: true, providers: ["password"], auth_method: "session",
  capabilities: [],
};

function unauthorized() {
  return new ApiError({ kind: "validation", status: 401, code: "unauthorized", message: "Authentication required." });
}

afterEach(() => {
  vi.clearAllMocks();
  pathname = "/prepare";
  search = "";
  window.history.replaceState({}, "", "/");
});

describe("AccountMenu", () => {
  it("opens an account menu exposing Account, Settings and Sign out for a real session", async () => {
    me.mockResolvedValue(SESSION_ACCOUNT);
    render(<AuthProvider><AccountMenu /></AuthProvider>);
    // The header control is now an accessible avatar button that opens a menu
    // (P10B Wave 1: Settings is reachable here, not only via Progress → Manage).
    const trigger = await screen.findByRole("button", { name: "Your account" });
    await userEvent.click(trigger);
    expect(screen.getByRole("menuitem", { name: "Your account" })).toHaveAttribute("href", "/account");
    expect(screen.getByRole("menuitem", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
  });

  it("shows Sign in when unauthenticated", async () => {
    me.mockRejectedValue(unauthorized());
    render(<AuthProvider><AccountMenu /></AuthProvider>);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in"),
    );
  });
});

describe("RouteGuard", () => {
  it("redirects an unauthenticated visitor away from a protected route", async () => {
    pathname = "/progress";
    me.mockRejectedValue(unauthorized());
    render(
      <AuthProvider>
        <RouteGuard><p>secret content</p></RouteGuard>
      </AuthProvider>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in?next=%2Fprogress"));
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("rejects an external next target for an already authenticated user", async () => {
    pathname = "/sign-in";
    window.history.replaceState({}, "", "/sign-in?next=%2F%2Fevil.test");
    me.mockResolvedValue(SESSION_ACCOUNT);
    render(<AuthProvider><RouteGuard><p>child</p></RouteGuard></AuthProvider>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/app"));
    expect(replace).not.toHaveBeenCalledWith("//evil.test");
  });

  it("renders protected content for an authenticated session", async () => {
    pathname = "/progress";
    me.mockResolvedValue(SESSION_ACCOUNT);
    render(
      <AuthProvider>
        <RouteGuard><p>secret content</p></RouteGuard>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("secret content")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders a public route without a session", async () => {
    pathname = "/";
    me.mockRejectedValue(unauthorized());
    render(
      <AuthProvider>
        <RouteGuard><p>home content</p></RouteGuard>
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText("home content")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("SignInForm", () => {
  it("submits credentials and refreshes on success", async () => {
    me.mockResolvedValue(SESSION_ACCOUNT);
    login.mockResolvedValue({ message: "Signed in." });
    render(<AuthProvider><SignInForm /></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correcthorsebattery");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({ email: "user@example.com", password: "correcthorsebattery" }),
    );
  });

  it.each([["%2F%2Fevil.test", "/app"], ["%2Fprepare%3Ftab%3Done%23focus", "/prepare?tab=one#focus"]])(
    "validates the sign-in return destination %s", async (next, expected) => {
      search = `next=${next}`;
      me.mockResolvedValue(SESSION_ACCOUNT);
      login.mockResolvedValue({ message: "Signed in." });
      render(<AuthProvider><SignInForm /></AuthProvider>);
      await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
      await userEvent.type(screen.getByLabelText("Password"), "synthetic-password");
      await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
      await waitFor(() => expect(replace).toHaveBeenCalledWith(expected));
    },
  );

  it("shows a generic error message on failed sign-in", async () => {
    me.mockRejectedValue(unauthorized());
    login.mockRejectedValue(
      new ApiError({ kind: "validation", status: 401, code: "unauthorized", message: "Incorrect email or password." }),
    );
    render(<AuthProvider><SignInForm /></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password-1");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText("Incorrect email or password.")).toBeInTheDocument(),
    );
  });
});
