/**
 * Public / authenticated route boundary (Capstone P1/E1 · P8 §3).
 *
 * P8 introduces a public marketing front door at `/` and moves the authenticated candidate
 * home to `/app`. MARKETING routes are public and render the marketing chrome (no app nav);
 * the authenticated product (`/app`, `/prepare`, …) requires a resolved identity and renders
 * the app chrome. Auth pages and Help remain public. Everything not listed is protected.
 * In development the backend's anonymous fallback resolves an identity, so the guard adds no
 * local friction; in production an unauthenticated visitor to a protected route is redirected.
 */

/** Where an authenticated candidate lands (post-login, brand link inside the app). */
export const APP_HOME = "/app";

/** Public marketing pages (rendered with marketing chrome, no session required). */
export const MARKETING_ROUTES = new Set<string>([
  "/",
  "/product",
  "/pricing",
  "/trust",
  "/privacy",
  "/terms",
  "/ai-transparency",
  "/about",
]);

/** Exact public paths (no session required): marketing + help + auth pages. */
export const PUBLIC_ROUTES = new Set<string>([
  ...MARKETING_ROUTES,
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

export function isMarketingRoute(pathname: string): boolean {
  return MARKETING_ROUTES.has(pathname);
}

export function isPublicRoute(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  // Allow public sub-paths of /help (e.g. /help/topic) if any are added later.
  return pathname.startsWith("/help/");
}

export function isProtectedRoute(pathname: string): boolean {
  return !isPublicRoute(pathname);
}
