import type { ApiErrorBody } from "./types";

/**
 * A safe, typed API error. `message` is always user-safe (the backend guarantees
 * this); it never carries a stack trace, SQL, provider payload or secret. UI maps
 * `kind` to a calm message rather than rendering the raw body.
 *
 * P10B-W9.1: the taxonomy distinguishes "the device is offline" (`offline`) from
 * "Ask4Mo's API could not be reached" (`unreachable`) — the second must NEVER blame
 * the candidate's own internet connection — and no longer collapses every HTTP status
 * into one bucket. A well-formed 5xx received by the browser is an Ask4Mo `server`
 * problem, not a network failure.
 */
export type ApiErrorKind =
  | "offline" // the browser itself reports the device is offline
  | "unreachable" // Ask4Mo's API could not be reached; NOT provably the user's connection
  | "unauthenticated" // 401 — session missing/expired
  | "forbidden" // 403 — authenticated but not allowed
  | "notFound" // 404 — resource does not exist
  | "validation" // 422 / other 4xx — the request/input was rejected
  | "conflict" // 409 — concurrent change / operation already running
  | "rateLimited" // 429 — too many requests (honour Retry-After)
  | "unavailable" // 502/503/504 or an intentional service-unavailable response
  | "server" // 5xx received normally — an Ask4Mo server problem
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly requestId: string | null;
  /** Milliseconds the server asked us to wait (parsed from Retry-After), if any. */
  readonly retryAfterMs: number | null;

  constructor(params: {
    kind: ApiErrorKind;
    status: number | null;
    code: string;
    message: string;
    requestId?: string | null;
    retryAfterMs?: number | null;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.kind = params.kind;
    this.status = params.status;
    this.code = params.code;
    this.requestId = params.requestId ?? null;
    this.retryAfterMs = params.retryAfterMs ?? null;
  }

  /**
   * A calm, user-facing English sentence for this error. This is the FALLBACK: the
   * localizable source of truth for the same copy lives in the i18n `states` namespace
   * (see {@link stateKeyForError}); W9.6 wires product surfaces to it. Keep these strings
   * in sync with `lib/i18n/messages/en.ts` `states.*`.
   */
  get userMessage(): string {
    switch (this.kind) {
      case "offline":
        return "You're offline. Check your internet connection and try again.";
      case "unreachable":
        return "Ask4Mo can't reach the service right now. Please try again shortly.";
      case "unauthenticated":
        return "Your session has expired. Please sign in again.";
      case "forbidden":
        return "You don't have access to that.";
      case "notFound":
        return "We couldn't find what you were looking for.";
      case "validation":
        return "Please check the information and try again.";
      case "conflict":
        return "This is already being processed. Please wait a moment and try again.";
      case "rateLimited":
        return "You've made too many requests. Please wait a moment and try again.";
      case "unavailable":
        return "Ask4Mo is temporarily unavailable. Please try again shortly.";
      case "server":
        return "Ask4Mo hit a problem while processing that request. Please try again.";
      default:
        return "That request couldn't be processed. Please try again.";
    }
  }
}

/**
 * The i18n key (in the `states` namespace) for an error kind. Pure and framework-free so
 * it can be used from the API layer; a component resolves it with `translate()`/`useT()`.
 */
export function stateKeyForError(kind: ApiErrorKind): string {
  switch (kind) {
    case "offline":
      return "states.offline";
    case "unreachable":
      return "states.serviceUnreachable";
    case "unauthenticated":
      return "states.sessionExpired";
    case "forbidden":
      return "states.forbidden";
    case "notFound":
      return "states.notFound";
    case "validation":
      return "states.validationError";
    case "conflict":
      return "states.conflict";
    case "rateLimited":
      return "states.rateLimited";
    case "unavailable":
      return "states.serviceUnavailable";
    case "server":
      return "states.serverError";
    default:
      return "states.genericError";
  }
}

/**
 * Classify a failed `fetch()` (the response never arrived) truthfully. If the browser
 * itself reports the device offline, it is `offline`; otherwise it is `unreachable` — an
 * Ask4Mo/backend/CORS problem we must NOT blame on the candidate's own connection.
 */
export function unreachableError(isOnline: boolean): ApiError {
  const offline = isOnline === false;
  return new ApiError({
    kind: offline ? "offline" : "unreachable",
    status: null,
    code: offline ? "offline" : "unreachable",
    message: offline ? "You're offline." : "Could not reach Ask4Mo.",
  });
}

export function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthenticated";
  if (status === 403) return "forbidden";
  if (status === 404) return "notFound";
  if (status === 409) return "conflict";
  if (status === 429) return "rateLimited";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  if (status >= 500) return "server";
  if (status >= 400) return "validation"; // 400/422/etc — input rejected
  return "unknown";
}

/**
 * Parse a Retry-After header (delta-seconds, or an HTTP-date) into milliseconds.
 * Returns null when absent/unparseable so callers fall back to their own backoff.
 */
export function parseRetryAfter(header: string | null): number | null {
  if (!header) return null;
  const secs = Number(header);
  if (Number.isFinite(secs)) return Math.max(0, secs * 1000);
  const when = Date.parse(header);
  if (!Number.isNaN(when)) return Math.max(0, when - Date.now());
  return null;
}

export function apiErrorFromBody(
  status: number,
  body: unknown,
  requestId: string | null,
  retryAfterMs: number | null = null,
): ApiError {
  const envelope = body as { error?: ApiErrorBody } | undefined;
  const code = envelope?.error?.code ?? "error";
  // Prefer the backend's safe message; fall back to a generic one. We never
  // surface arbitrary body text that isn't part of the known safe envelope.
  const message = envelope?.error?.message ?? "Request failed.";
  return new ApiError({
    kind: kindForStatus(status),
    status,
    code,
    message,
    requestId: envelope?.error?.request_id ?? requestId,
    retryAfterMs,
  });
}
