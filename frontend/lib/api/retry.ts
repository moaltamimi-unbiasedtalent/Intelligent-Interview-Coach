import { ApiError, type ApiErrorKind } from "./errors";

/**
 * Conservative, bounded transport-level retry (P10B-W9.1).
 *
 * This is NOT autonomous repetition of expensive work: it only re-sends a request the
 * transport failed to complete, and ONLY for operations that are safe to repeat. It never
 * retries writes (POST/PATCH/DELETE) — even keyed/idempotent ones — so career chat, agent
 * messages, Practice answers, uploads, handoffs and memory mutations can never execute twice
 * because of a retry. It never retries client errors (4xx) except a rate-limit (429), and it
 * always stops immediately on abort.
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD";

export interface RetryPolicy {
  /** Additional attempts after the first (so total attempts = maxRetries + 1). */
  maxRetries: number;
  /** Base backoff in ms (grows exponentially). */
  baseDelayMs: number;
  /** Upper bound for a single backoff wait. */
  maxDelayMs: number;
}

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelayMs: 300,
  maxDelayMs: 4000,
};

/** Transient conditions worth retrying for a safe/idempotent request. */
const RETRYABLE_KINDS: ReadonlySet<ApiErrorKind> = new Set<ApiErrorKind>([
  "unreachable", // Ask4Mo API not reached (e.g. backend restarting) — safe to re-send a GET
  "server", // 5xx received — transient server hiccup
  "unavailable", // 502/503/504 — temporary
  "rateLimited", // 429 — honour Retry-After
]);

/** Only genuinely idempotent, side-effect-free methods may be auto-retried. */
function isIdempotent(method: HttpMethod): boolean {
  return method === "GET" || method === "HEAD";
}

/**
 * Whether an error is eligible for an automatic retry given the request method.
 * `offline` is deliberately NOT retryable: the device has no connection, so re-sending
 * would just spin; the UI surfaces the offline state instead.
 */
export function isRetryable(method: HttpMethod, error: unknown): boolean {
  if (!isIdempotent(method)) return false;
  if (!(error instanceof ApiError)) return false;
  return RETRYABLE_KINDS.has(error.kind);
}

/**
 * Backoff for the next attempt (ms). Honours a server-provided Retry-After when present,
 * otherwise exponential backoff (base * 2^attempt) capped at maxDelayMs, plus small jitter.
 * `rand` is injectable so tests are deterministic.
 */
export function backoffDelayMs(
  attempt: number,
  error: unknown,
  policy: RetryPolicy = DEFAULT_RETRY_POLICY,
  rand: () => number = Math.random,
): number {
  if (error instanceof ApiError && error.retryAfterMs != null) {
    return Math.min(error.retryAfterMs, policy.maxDelayMs);
  }
  const exp = policy.baseDelayMs * 2 ** attempt;
  const capped = Math.min(exp, policy.maxDelayMs);
  const jitter = Math.floor(rand() * policy.baseDelayMs);
  return capped + jitter;
}

export interface RunWithRetryOptions {
  policy?: RetryPolicy;
  signal?: AbortSignal;
  /** Injectable wait (defaults to a real, abortable timer). */
  wait?: (ms: number, signal?: AbortSignal) => Promise<void>;
  /** Injectable RNG for deterministic jitter in tests. */
  rand?: () => number;
}

/** Default abortable wait. Rejects with an AbortError immediately if the signal fires. */
export function defaultWait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Run a single-attempt request factory with bounded retry. `attempt` performs exactly one
 * network attempt and throws an {@link ApiError} (or an AbortError) on failure.
 */
export async function runWithRetry<T>(
  method: HttpMethod,
  attempt: () => Promise<T>,
  options: RunWithRetryOptions = {},
): Promise<T> {
  const policy = options.policy ?? DEFAULT_RETRY_POLICY;
  const wait = options.wait ?? defaultWait;
  const rand = options.rand ?? Math.random;
  const signal = options.signal;

  let lastError: unknown;
  for (let i = 0; i <= policy.maxRetries; i += 1) {
    try {
      return await attempt();
    } catch (error) {
      lastError = error;
      // Never swallow an abort, and never retry after one.
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      if (signal?.aborted) throw error;
      const hasBudget = i < policy.maxRetries;
      if (!hasBudget || !isRetryable(method, error)) throw error;
      await wait(backoffDelayMs(i, error, policy, rand), signal);
    }
  }
  // Unreachable in practice (the loop either returns or throws), but keeps types happy.
  throw lastError;
}
