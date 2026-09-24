"use client";

/**
 * Client-side authentication context (Capstone P1/E1).
 *
 * Resolves the current account from `GET /auth/me` (the session travels in an
 * HttpOnly cookie sent automatically — never read by JS). Exposes the account, a
 * coarse status and a `refresh()` so pages can update the header after sign-in/out.
 * A 401 means "not signed in" (production); development returns an anonymous or
 * dev-header identity, which we treat as a usable session so local work is friction-free.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { AccountResponse } from "@/lib/api/types";

// "unknown" = identity could not be determined (backend unreachable / non-401 error).
// It is deliberately distinct from "unauthenticated" (a definitive 401): the route
// guard must NOT bounce a user to sign-in just because a request failed transiently.
type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "unknown";

interface AuthContextValue {
  account: AccountResponse | null;
  status: AuthStatus;
  /** True when the identity is a real signed-in session (not the dev fallback). */
  isRealSession: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AccountResponse | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const refresh = useCallback(async () => {
    try {
      const me = await api.auth.me();
      setAccount(me);
      setStatus("authenticated");
    } catch (err) {
      setAccount(null);
      if (err instanceof ApiError && err.status === 401) {
        // Definitive: not signed in → the guard may redirect to sign in.
        setStatus("unauthenticated");
      } else {
        // Transient/network/unknown: do NOT lock the user out. The server still
        // enforces authorization on every protected call, so rendering is safe.
        setStatus("unknown");
      }
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignore — a failed logout still clears local state; the cookie is server-managed.
    }
    setAccount(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      account,
      status,
      isRealSession: account?.auth_method === "session",
      refresh,
      signOut,
    }),
    [account, status, refresh, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
