import type { ApiErrorBody } from "./types";

/**
 * A safe, typed API error. `message` is always user-safe (the backend guarantees
 * this); it never carries a stack trace, SQL, provider payload or secret. UI maps
 * `kind` to a calm message rather than rendering the raw body.
 */
export type ApiErrorKind =
  | "network" // couldn't reach the backend
  | "validation" // 4xx — the request/input was rejected
  | "conflict" // 409 — the resource changed concurrently / operation already running
  | "unavailable" // 503 — a service is not configured / temporarily down
  | "server" // 5xx — unexpected
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly requestId: string | null;

  constructor(params: {
    kind: ApiErrorKind;
    status: number | null;
    code: string;
    message: string;
    requestId?: string | null;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.kind = params.kind;
    this.status = params.status;
    this.code = params.code;
    this.requestId = params.requestId ?? null;
  }

  /** A calm, user-facing sentence for this error. */
  get userMessage(): string {
    switch (this.kind) {
      case "network":
        return "We couldn't connect right now. Please check your connection and try again.";
      case "validation":
        return "Please check the information and try again.";
      case "conflict":
        return "This is already being processed. Please wait a moment and try again.";
      case "unavailable":
        return "That feature isn't available right now. Please try again shortly.";
      case "server":
      default:
        return "That request couldn't be processed. Please try again.";
    }
  }
}

export function kindForStatus(status: number): ApiErrorKind {
  if (status >= 500) return "server";
  if (status === 503) return "unavailable";
  if (status === 409) return "conflict";
  if (status >= 400) return "validation";
  return "unknown";
}

export function apiErrorFromBody(
  status: number,
  body: unknown,
  requestId: string | null,
): ApiError {
  const envelope = body as { error?: ApiErrorBody } | undefined;
  const code = envelope?.error?.code ?? "error";
  // Prefer the backend's safe message; fall back to a generic one. We never
  // surface arbitrary body text that isn't part of the known safe envelope.
  const message = envelope?.error?.message ?? "Request failed.";
  const kind = status === 503 ? "unavailable" : kindForStatus(status);
  return new ApiError({
    kind,
    status,
    code,
    message,
    requestId: envelope?.error?.request_id ?? requestId,
  });
}
