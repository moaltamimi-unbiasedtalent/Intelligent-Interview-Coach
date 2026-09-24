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
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(),
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
});

describe("AccountMenu", () => {
  it("shows the account avatar and sign-out for a real session", async () => {
    me.mockResolvedValue(SESSION_ACCOUNT);
    render(<AuthProvider><AccountMenu /></AuthProvider>);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Your account" })).toHaveAttribute("href", "/account"),
    );
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
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
