import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 04D: onboarding progress must survive (1) a stale /auth/me, (2) a remount while a step save is in flight, (3) a failed save, and (4) the shell's Suspense fallback must never be a second
// copy of the page. Real AuthProvider + real OnboardingClient; only the network client and the router are replaced.

const me = vi.fn();
const onboarding = vi.fn();
const updatePreferences = vi.fn();
const replace = vi.fn();
const push = vi.fn();

function acct(over: Record<string, unknown> = {}): AccountResponse {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: false, onboarding_step: 0, ...over,
  } as AccountResponse;
}

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: { auth: { me: (...a: unknown[]) => me(...a), onboarding: (...a: unknown[]) => onboarding(...a), updatePreferences: (...a: unknown[]) => updatePreferences(...a), logout: vi.fn() } },
  };
});

let pathname = "/onboarding";
let suspendSearchParams: { promise: Promise<void> | null; done: boolean } = { promise: null, done: true };
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace, push }),
  useSearchParams: () => {
    // A hook that suspends like Next's does while a static page is bailing out to client rendering. RouteGuard must NOT depend on it any more.
    if (!suspendSearchParams.done && suspendSearchParams.promise) throw suspendSearchParams.promise;
    return new URLSearchParams();
  },
}));

import type { AccountResponse } from "@/lib/api/types";
import { AuthProvider, useAuth } from "@/components/auth/AuthProvider";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { AppShell } from "@/components/layout/AppShell";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { OnboardingClient } from "@/components/onboarding/OnboardingClient";

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const wrap = (ui: React.ReactNode) => <I18nProvider><AuthProvider>{ui}</AuthProvider></I18nProvider>;

beforeEach(() => { pathname = "/onboarding"; suspendSearchParams = { promise: null, done: true }; });
afterEach(() => vi.clearAllMocks());

describe("AuthProvider: a stale read cannot revert a newer write", () => {
  function Probe({ onReady }: { onReady: (a: ReturnType<typeof useAuth>) => void }) {
    const auth = useAuth();
    useEffect(() => { onReady(auth); });
    return <p data-testid="step">{auth.account ? String(auth.account.onboarding_step) : "none"}</p>;
  }

  it("drops an /auth/me answer that was requested before an account the server returned from a write", async () => {
    const first = deferred<AccountResponse>();
    const second = deferred<AccountResponse>();
    me.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    let auth!: ReturnType<typeof useAuth>;
    render(<AuthProvider><Probe onReady={(a) => { auth = a; }} /></AuthProvider>);
    await act(async () => { first.resolve(acct({ onboarding_step: 0 })); });
    await waitFor(() => expect(screen.getByTestId("step")).toHaveTextContent("0"));
    let late!: Promise<void>;
    act(() => { late = auth.refresh(); });                                     // a read is issued ...
    act(() => { auth.applyAccount(acct({ onboarding_step: 1 })); });           // ... the candidate saves step 1 ...
    await act(async () => { second.resolve(acct({ onboarding_step: 0 })); await late; });   // ... and the OLD read resolves afterwards, carrying step 0
    expect(screen.getByTestId("step")).toHaveTextContent("1");
  });

  it("still adopts a read that was issued after the write", async () => {
    me.mockResolvedValueOnce(acct({ onboarding_step: 0 })).mockResolvedValueOnce(acct({ onboarding_step: 2 }));
    let auth!: ReturnType<typeof useAuth>;
    render(<AuthProvider><Probe onReady={(a) => { auth = a; }} /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("step")).toHaveTextContent("0"));
    act(() => { auth.applyAccount(acct({ onboarding_step: 1 })); });
    await act(async () => { await auth.refresh(); });
    expect(screen.getByTestId("step")).toHaveTextContent("2");
  });
});

describe("OnboardingClient", () => {
  it("a successful save advances the UI and writes exactly once", async () => {
    me.mockResolvedValue(acct());
    onboarding.mockResolvedValue(acct({ onboarding_step: 1 }));
    render(wrap(<OnboardingClient />));
    await userEvent.click(await screen.findByRole("button", { name: "Get started" }));
    await screen.findByText(/Step 2 of 7/);
    expect(onboarding).toHaveBeenCalledTimes(1);
    expect(onboarding).toHaveBeenCalledWith({ step: 1 });
  });

  it("a failed save never advances, shows a recoverable error and a retry can succeed", async () => {
    me.mockResolvedValue(acct());
    onboarding.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(acct({ onboarding_step: 1 }));
    render(wrap(<OnboardingClient />));
    await userEvent.click(await screen.findByRole("button", { name: "Get started" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn’t save this step/i);
    expect(screen.getByText(/Step 1 of 7/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get started" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Get started" }));
    await screen.findByText(/Step 2 of 7/);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(onboarding).toHaveBeenCalledTimes(2);
  });

  it("a remount while a step save is still in flight resumes at the saved step once it lands (the failure: the fresh copy stayed at Step 1)", async () => {
    me.mockResolvedValue(acct());
    const save = deferred<AccountResponse>();
    onboarding.mockReturnValueOnce(save.promise);
    const { rerender } = render(wrap(<OnboardingClient key="a" />));
    await userEvent.click(await screen.findByRole("button", { name: "Get started" }));          // the save is now outstanding
    rerender(wrap(<OnboardingClient key="b" />));                                                // the page is replaced by a fresh copy (hydrates from the stale account: step 0)
    await screen.findByText(/Step 1 of 7/);
    await act(async () => { save.resolve(acct({ onboarding_step: 1 })); });                      // the save lands
    await screen.findByText(/Step 2 of 7/);
    expect(onboarding).toHaveBeenCalledTimes(1);                                                 // no duplicate write
  });

  it("Back is never undone by the saved step (the saved step only moves the UI forward)", async () => {
    me.mockResolvedValue(acct({ onboarding_step: 3 }));
    render(wrap(<OnboardingClient />));
    await screen.findByText(/Step 4 of 7/);
    await userEvent.click(screen.getByRole("button", { name: /back/i }));
    await screen.findByText(/Step 3 of 7/);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText(/Step 3 of 7/)).toBeInTheDocument();
  });

  it("an intentional reload (fresh mount) resumes from the persisted server step", async () => {
    me.mockResolvedValue(acct({ onboarding_step: 2 }));
    render(wrap(<OnboardingClient />));
    await screen.findByText(/Step 3 of 7/);
  });
});

describe("the shell never shows a second copy of the onboarding page", () => {
  let mounts = 0;
  let unmounts = 0;
  function Counted() {
    useEffect(() => { mounts += 1; return () => { unmounts += 1; }; }, []);
    return <p>onboarding copy</p>;
  }

  beforeEach(() => { mounts = 0; unmounts = 0; });

  it("RouteGuard does not suspend on the search params, so the page is mounted once and never swapped (root cause of the reset)", async () => {
    me.mockResolvedValue(acct());
    const gate = deferred<void>();
    suspendSearchParams = { promise: gate.promise, done: false };           // useSearchParams would suspend until released
    render(wrap(<AppShell><Counted /></AppShell>));
    await screen.findByText("onboarding copy");
    expect(screen.getAllByText("onboarding copy")).toHaveLength(1);
    await act(async () => { suspendSearchParams.done = true; gate.resolve(); await gate.promise; });
    await waitFor(() => expect(screen.getAllByText("onboarding copy")).toHaveLength(1));
    expect(mounts).toBe(1);
    expect(unmounts).toBe(0);                                              // the page the candidate used was never thrown away
  });

  it("RouteGuard still sends an authenticated visitor on an auth-only page to the ?next target, read from the location", async () => {
    pathname = "/sign-in";
    window.history.replaceState({}, "", "/sign-in?next=%2Fhistory");
    me.mockResolvedValue(acct({ onboarding_completed: true }));
    render(wrap(<RouteGuard><p>sign in page</p></RouteGuard>));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/history"));
    window.history.replaceState({}, "", "/");
  });

  it("RouteGuard still enforces onboarding on a protected page and authentication on a protected route", async () => {
    pathname = "/prepare";
    me.mockResolvedValue(acct());
    render(wrap(<RouteGuard><p>prepare</p></RouteGuard>));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
  });
});
