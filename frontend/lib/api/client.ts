import { config } from "../config";
import { ApiError, apiErrorFromBody } from "./errors";
import type { CapabilitiesResponse, HealthResponse } from "./types";

const REQUEST_ID_HEADER = "x-request-id";

interface RequestOptions {
  signal?: AbortSignal;
}

function authHeaders(): Record<string, string> {
  // Transitional local-dev identity only (see lib/config.ts). Omitted when unset.
  return config.devUserSubject ? { "X-User-Subject": config.devUserSubject } : {};
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  { body, signal }: { body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    // Network / CORS / abort — never leak the raw cause to the UI.
    throw new ApiError({
      kind: "network",
      status: null,
      code: "network_error",
      message: "Could not reach the service.",
    });
  }

  const requestId = res.headers.get(REQUEST_ID_HEADER);
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => undefined) : undefined;

  if (!res.ok) {
    throw apiErrorFromBody(res.status, payload, requestId);
  }
  return payload as T;
}

/** Typed FastAPI client. Add new typed methods here rather than calling fetch ad hoc. */
export const api = {
  health: (opts?: RequestOptions) => request<HealthResponse>("GET", "/health", opts),
  capabilities: (opts?: RequestOptions) =>
    request<CapabilitiesResponse>("GET", "/capabilities", opts),
};

export { ApiError };
