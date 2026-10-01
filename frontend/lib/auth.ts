/**
 * Frontend authentication boundary — a seam, not an implementation.
 *
 * Real accounts use a server-side session in an HttpOnly cookie that the browser sends
 * automatically (credentials: "include"); no token is ever readable by JavaScript. This
 * module is only the seam for the OPTIONAL local-development identity, which the API
 * client sends as the dev-only `X-User-Subject` header. The backend honours that header
 * ONLY in development/test environments and never over a valid session (production is
 * fail-closed). See docs/capstone/p1_e1_identity_platform.md.
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
