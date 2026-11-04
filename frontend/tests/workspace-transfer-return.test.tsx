import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  pathname: "/workspaces/transfer/accept",
  router: { replace: vi.fn() },
}));
const identity = vi.hoisted(() => ({
  status: "unauthenticated" as "loading" | "unauthenticated" | "authenticated",
  account: null as null | { onboarding_completed: boolean },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => navigation.router,
}));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => identity,
}));
vi.mock("@/components/i18n/I18nProvider", () => ({
  useT: () => (key: string) => key,
}));
vi.mock("@/lib/auth/redirect", () => ({
  redirectVerified: vi.fn((router: { replace: (href: string) => void }, target: string) => {
    router.replace(target);
    return () => undefined;
  }),
}));

import { RouteGuard, transferReturnDestination } from "@/components/auth/RouteGuard";

const TRANSFER_PATH = "/workspaces/transfer/accept";
const LOCAL_ORIGIN = "https://app.example.test";

beforeEach(() => {
  navigation.pathname = TRANSFER_PATH;
  identity.status = "unauthenticated";
  identity.account = null;
  window.history.replaceState({}, "", "/");
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("transfer-specific return destination", () => {
  it.each([
    { label: "issued URL-safe token", search: "?token=synthetic_Qt9-Ab_-43", token: "synthetic_Qt9-Ab_-43" },
    { label: "encoded plus", search: "?token=part%2Btail", token: "part+tail" },
    { label: "untrimmed spaces", search: "?token=%20part%20", token: " part " },
    { label: "encoded query separator", search: "?token=part%2Ftail", token: "part/tail" },
    { label: "encoded hash value", search: "?token=part%23tail", token: "part#tail" },
    { label: "valid Unicode", search: "?token=%F0%9F%92%A1", token: "💡" },
  ])("preserves the exact $label without double encoding", ({ search, token }) => {
    const destination = transferReturnDestination(TRANSFER_PATH, search);
    const parsed = new URL(destination, LOCAL_ORIGIN);
    expect(parsed.origin).toBe(LOCAL_ORIGIN);
    expect(parsed.pathname).toBe(TRANSFER_PATH);
    expect([...parsed.searchParams.keys()]).toEqual(["token"]);
    expect(parsed.searchParams.get("token")).toBe(token);
    expect(parsed.hash).toBe("");
    expect(destination).toBe(TRANSFER_PATH + "?" + new URLSearchParams({ token }).toString());
  });

  it.each([
    { label: "ASCII", token: "a".repeat(512) },
    { label: "Unicode codepoint", token: "💡".repeat(512) },
  ])("accepts the existing 512-$label limit", ({ token }) => {
    const destination = transferReturnDestination(
      TRANSFER_PATH,
      "?" + new URLSearchParams({ token }).toString(),
    );
    expect(new URL(destination, LOCAL_ORIGIN).searchParams.get("token")).toBe(token);
  });

  it("discards unrelated parameters and the fragment", () => {
    expect(transferReturnDestination(
      TRANSFER_PATH,
      "?next=%2F%2Fevil.example.test&token=synthetic&tracking=discard#discarded",
    )).toBe(TRANSFER_PATH + "?token=synthetic");
  });

  it.each([
    { label: "no query", search: "" },
    { label: "no token", search: "?next=%2Fapp" },
    { label: "empty token", search: "?token=" },
    { label: "token key without a value", search: "?token" },
    { label: "duplicate equal tokens", search: "?token=one&token=one" },
    { label: "duplicate distinct tokens", search: "?token=one&token=two" },
    { label: "duplicate empty token", search: "?token=one&token=" },
    { label: "encoded token-name alias", search: "?%74oken=one" },
    { label: "encoded duplicate token-name alias", search: "?token=one&tok%65n=two" },
    { label: "incomplete percent escape", search: "?token=%" },
    { label: "invalid percent escape", search: "?token=%GG" },
    { label: "incomplete UTF-8", search: "?token=%E0%A4" },
    { label: "invalid UTF-8", search: "?token=%FF" },
    { label: "overlong UTF-8", search: "?token=%C0%AF" },
    { label: "encoded surrogate", search: "?token=%ED%A0%80" },
    { label: "lone high surrogate", search: "?token=\ud800" },
    { label: "lone low surrogate", search: "?token=\udc00" },
    { label: "encoded control", search: "?token=one%0Atwo" },
    { label: "double-encoded control", search: "?token=one%250Atwo" },
    { label: "encoded backslash", search: "?token=one%5Ctwo" },
    { label: "double-encoded backslash", search: "?token=one%255Ctwo" },
    { label: "raw control", search: "?token=one\u0000two" },
    { label: "malformed unrelated parameter", search: "?token=one&other=%GG" },
    { label: "literal percent rejected by the existing validator", search: "?token=%25literal" },
    { label: "oversized ASCII token", search: "?token=" + "a".repeat(513) },
    { label: "oversized Unicode token", search: "?token=" + "💡".repeat(513) },
  ])("uses the existing bare-path fallback for $label", ({ search }) => {
    expect(transferReturnDestination(TRANSFER_PATH, search)).toBe(TRANSFER_PATH);
  });

  it.each([
    "/progress",
    "/prepare",
    "/admin",
    "/workspaces/invite",
    "/workspaces/transfer/accept/",
    "/workspaces/transfer/%61ccept",
  ])("retains pathname-only returns for %s", (pathname) => {
    expect(transferReturnDestination(pathname, "?token=synthetic&next=%2Fapp#discard"))
      .toBe(pathname);
  });

  it("does not copy query or fragment from an unexpected pathname input", () => {
    expect(transferReturnDestination("/progress?token=discard#discard", "?token=other"))
      .toBe("/progress");
  });

  it.each([
    "//evil.example.test",
    "/\\evil.example.test",
    "/%2f%2fevil.example.test",
    "/%252f%252fevil.example.test",
    "/%5cevil.example.test",
    "/%255cevil.example.test",
    "/bad%",
    "/bad%00",
    "/x\n",
    "https://evil.example.test",
    "javascript:alert(1)",
    "/sign-in",
    "/%73ign-in",
    "/%2573ign-in",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/a/../admin",
  ])("retains the unchanged redirect validator for %s", (pathname) => {
    expect(transferReturnDestination(pathname, "?token=synthetic")).toBe("/app");
  });
});

describe("RouteGuard transfer return integration", () => {
  it("redirects using the current token-only query while keeping protected children hidden", async () => {
    window.history.replaceState({}, "", TRANSFER_PATH + "?token=synthetic&tracking=discard#discard");
    render(<RouteGuard><span>protected-preview</span></RouteGuard>);

    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith(
      "/sign-in?next=" + encodeURIComponent(TRANSFER_PATH + "?token=synthetic"),
    ));
    expect(screen.queryByText("protected-preview")).toBeNull();
  });

  it("uses the bare transfer path when the query has an ambiguous token", async () => {
    window.history.replaceState({}, "", TRANSFER_PATH + "?token=one&token=two");
    render(<RouteGuard><span>protected-preview</span></RouteGuard>);

    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith(
      "/sign-in?next=" + encodeURIComponent(TRANSFER_PATH),
    ));
  });

  it("retains the ordinary pathname-only redirect", async () => {
    navigation.pathname = "/progress";
    window.history.replaceState({}, "", "/progress?token=discard&tab=discard");
    render(<RouteGuard><span>protected-content</span></RouteGuard>);

    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith("/sign-in?next=%2Fprogress"));
  });

  it("does not redirect before identity is resolved", () => {
    identity.status = "loading";
    window.history.replaceState({}, "", TRANSFER_PATH + "?token=synthetic");
    render(<RouteGuard><span>protected-preview</span></RouteGuard>);
    expect(navigation.router.replace).not.toHaveBeenCalled();
    expect(screen.queryByText("protected-preview")).toBeNull();
  });

  it("renders an authenticated recipient's preview without an unnecessary redirect", () => {
    identity.status = "authenticated";
    identity.account = { onboarding_completed: true };
    window.history.replaceState({}, "", TRANSFER_PATH + "?token=synthetic");
    render(<RouteGuard><span>protected-preview</span></RouteGuard>);
    expect(screen.getByText("protected-preview")).toBeInTheDocument();
    expect(navigation.router.replace).not.toHaveBeenCalled();
  });

  it("keeps the validated transfer destination for an authenticated sign-in return", async () => {
    identity.status = "authenticated";
    identity.account = { onboarding_completed: true };
    navigation.pathname = "/sign-in";
    const destination = TRANSFER_PATH + "?token=synthetic";
    window.history.replaceState({}, "", "/sign-in?next=" + encodeURIComponent(destination));
    render(<RouteGuard><span>sign-in-child</span></RouteGuard>);

    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith(destination));
  });
});

