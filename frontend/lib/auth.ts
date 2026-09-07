/**
 * Frontend authentication boundary — a seam, not an implementation.
 *
 * Production authentication (OIDC / an authenticating gateway) is FUTURE WORK
 * (Phase 3C/7). This module exists so the rest of the app depends on a stable
 * `currentIdentity()` seam rather than on any concrete mechanism. Today it only
 * surfaces the optional local-development identity, which the API client sends as
 * the backend's transitional `X-User-Subject` header for data scoping.
 *
 * We never ask the browser user to type X-User-Subject; it comes from
 * NEXT_PUBLIC_DEV_USER_SUBJECT (dev only) or is absent (anonymous dev user).
 */
import { config } from "./config";

export interface Identity {
  subject: string | null;
  isAuthenticated: boolean;
  /** True until a real identity provider is wired in (Phase 3C/7). */
  isTransitional: boolean;
}

export function currentIdentity(): Identity {
  return {
    subject: config.devUserSubject || null,
    isAuthenticated: false,
    isTransitional: true,
  };
}
