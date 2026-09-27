"use client";

/**
 * Client-side route boundary (Capstone P1/E1, §13).
 *
 * Protected pages require a resolved identity. An unauthenticated visitor is sent to
 * sign in (preserving where they were going via `?next=`). This is UX only — it is
 * NOT the security control: every protected API call is authorized server-side, so a
 * user navigating directly to a protected page still cannot read another user's data.
 */

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { isProtectedRoute, AUTH_ONLY_ROUTES, APP_HOME } from "@/lib/auth/routes";
import { LoadingState } from "@/components/ui/States";

export function RouteGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const params = useSearchParams();
  const { status, account } = useAuth();

  const protectedRoute = isProtectedRoute(pathname);
  const authOnly = AUTH_ONLY_ROUTES.has(pathname);
  const onOnboarding = pathname === "/onboarding";
  // First-run gate (P10B Wave 2): a signed-in account that has not completed onboarding is sent to
  // /onboarding before normal product use. Existing accounts are backfilled to completed, so they
  // are never blocked. The gate never fires on /onboarding itself (no loop) or on public routes.
  const needsOnboarding =
    status === "authenticated" && account !== null && account.onboarding_completed === false;

  useEffect(() => {
    if (status === "loading") return;
    if (protectedRoute && status === "unauthenticated") {
      const next = encodeURIComponent(pathname);
      router.replace(`/sign-in?next=${next}`);
    } else if (authOnly && status === "authenticated") {
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : APP_HOME);
    } else if (needsOnboarding && protectedRoute && !onOnboarding) {
      router.replace("/onboarding");
    }
  }, [status, protectedRoute, authOnly, needsOnboarding, onOnboarding, pathname, params, router]);

  // Block a protected page only while identity is still loading, or while a
  // definitively-unauthenticated visitor is being redirected. An "unknown" status
  // (backend unreachable) renders the page — the server still enforces authorization.
  if (protectedRoute && (status === "loading" || status === "unauthenticated")) {
    return <LoadingState label="Checking your session" />;
  }
  return <>{children}</>;
}
