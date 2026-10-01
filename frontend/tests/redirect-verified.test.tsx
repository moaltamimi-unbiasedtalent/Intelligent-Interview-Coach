import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { REDIRECT_VERIFY_MS, redirectVerified } from "@/lib/auth/redirect";

/**
 * P10B-W9.7B - the route guard's redirect must be VERIFIED. A soft `router.replace()` issued ~100-300 ms after
 * load is occasionally dropped by the Next router (no error, no history change); the guard's effect never
 * re-runs, so without verification the redirect is lost forever (CI: "Browser E2E / onboarding gate" flake,
 * reproduced at ~8% on a 2-vCPU Linux runner). These tests pin the verify -> soft retry -> hard fallback ladder.
 */

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function setup(pathnames: string[]) {
  const replace = vi.fn();
  const hardNavigate = vi.fn();
  let i = 0;
  const getPathname = vi.fn(() => pathnames[Math.min(i++, pathnames.length - 1)]);
  const cleanup = redirectVerified({ replace }, "/onboarding", { getPathname, hardNavigate });
  return { replace, hardNavigate, getPathname, cleanup };
}

describe("redirectVerified", () => {
  it("issues the soft navigation immediately and stops once the pathname landed (no retry, no hard nav)", () => {
    const { replace, hardNavigate } = setup(["/onboarding"]);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenCalledWith("/onboarding");
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 5);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(hardNavigate).not.toHaveBeenCalled();
  });

  it("a DROPPED soft navigation is retried once, then landing stops the verification", () => {
    const { replace, hardNavigate } = setup(["/prepare", "/onboarding"]);
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS); // check 1: still /prepare -> soft retry
    expect(replace).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 5); // check 2: landed
    expect(replace).toHaveBeenCalledTimes(2);
    expect(hardNavigate).not.toHaveBeenCalled();
  });

  it("if both soft attempts are dropped it falls back to a hard navigation, exactly once", () => {
    const { replace, hardNavigate } = setup(["/prepare"]);
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 2);
    expect(replace).toHaveBeenCalledTimes(2);
    expect(hardNavigate).toHaveBeenCalledTimes(1);
    expect(hardNavigate).toHaveBeenCalledWith("/onboarding");
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 10); // verification is over
    expect(hardNavigate).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenCalledTimes(2);
  });

  it("cleanup cancels verification (guard inputs changed / unmounted)", () => {
    const { replace, hardNavigate, cleanup } = setup(["/prepare"]);
    cleanup();
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 10);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(hardNavigate).not.toHaveBeenCalled();
  });

  it("compares the pathname only (a ?next= query does not count as 'not landed')", () => {
    const replace = vi.fn();
    const hardNavigate = vi.fn();
    redirectVerified({ replace }, "/sign-in?next=%2Fprogress", { getPathname: () => "/sign-in", hardNavigate });
    vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 5);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(hardNavigate).not.toHaveBeenCalled();
  });
});

// --- RouteGuard integration: the guard itself must use the verified redirect ---------------------
const replace = vi.fn();
let guardAuth: { status: string; account: unknown } = { status: "loading", account: null };
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/prepare",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/auth/AuthProvider", () => ({ useAuth: () => guardAuth }));

import { RouteGuard } from "@/components/auth/RouteGuard";

describe("RouteGuard uses the verified redirect", () => {
  beforeEach(() => replace.mockReset());

  it("new account (onboarding incomplete) on /prepare: a dropped /onboarding redirect is retried", () => {
    guardAuth = { status: "authenticated", account: { onboarding_completed: false } };
    const { unmount } = render(<RouteGuard><p>child</p></RouteGuard>);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenCalledWith("/onboarding");
    // jsdom's location never changes (the soft navigation was "dropped"), so the guard retries.
    act(() => { vi.advanceTimersByTime(REDIRECT_VERIFY_MS); });
    expect(replace).toHaveBeenCalledTimes(2);
    unmount(); // cleanup cancels the pending hard fallback (no real navigation in jsdom)
  });

  it("anonymous visitor: the sign-in redirect is verified the same way", () => {
    guardAuth = { status: "unauthenticated", account: null };
    const { unmount } = render(<RouteGuard><p>child</p></RouteGuard>);
    expect(replace).toHaveBeenCalledWith("/sign-in?next=%2Fprepare");
    act(() => { vi.advanceTimersByTime(REDIRECT_VERIFY_MS); });
    expect(replace).toHaveBeenCalledTimes(2);
    unmount();
  });

  it("completed account: no redirect, no timers", () => {
    guardAuth = { status: "authenticated", account: { onboarding_completed: true } };
    render(<RouteGuard><p>child</p></RouteGuard>);
    act(() => { vi.advanceTimersByTime(REDIRECT_VERIFY_MS * 5); });
    expect(replace).not.toHaveBeenCalled();
  });
});
