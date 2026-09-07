/**
 * Public frontend configuration. Only NEXT_PUBLIC_* values are read here — no
 * server secrets ever reach the browser (all provider access stays in the Python
 * backend).
 */
export const config = {
  /** Base URL of the FastAPI backend, e.g. http://localhost:8000/api/v1 */
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    "http://localhost:8000/api/v1",
  /**
   * Local-development identity ONLY. Sent as the transitional X-User-Subject
   * header for data scoping — this is NOT production authentication. See
   * lib/auth.ts and docs/sprint4_architecture.md.
   */
  devUserSubject: process.env.NEXT_PUBLIC_DEV_USER_SUBJECT || "",
} as const;
