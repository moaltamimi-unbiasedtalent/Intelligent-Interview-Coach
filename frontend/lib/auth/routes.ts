/**
 * Public / authenticated route boundary (Capstone P1/E1, §13).
 *
 * PUBLIC pages render without a session (marketing/home, help and the auth pages).
 * Everything else is the authenticated product and requires a resolved identity.
 * In development the backend's anonymous fallback resolves an identity, so the guard
 * does not add friction locally; in production an unauthenticated visitor to a
 * protected route is redirected to sign in.
 */

/** Exact public paths (no session required). */
export const PUBLIC_ROUTES = new Set<string>([
  "/",
  "/help",
  "/sign-in",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
]);

/** Auth pages a signed-in user should be bounced away from (to the app home). */
export const AUTH_ONLY_ROUTES = new Set<string>([
  "/sign-in",
  "/register",
  "/forgot-password",
  "/reset-password",
]);

export function isPublicRoute(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  // Allow public sub-paths of /help (e.g. /help/topic) if any are added later.
  return pathname.startsWith("/help/");
}

export function isProtectedRoute(pathname: string): boolean {
  return !isPublicRoute(pathname);
}
