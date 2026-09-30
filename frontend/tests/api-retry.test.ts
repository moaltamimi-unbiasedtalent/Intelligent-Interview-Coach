import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import {
  backoffDelayMs,
  DEFAULT_RETRY_POLICY,
  isRetryable,
  runWithRetry,
} from "@/lib/api/retry";

function apiErr(kind: ApiError["kind"], status: number | null = null, retryAfterMs: number | null = null) {
  return new ApiError({ kind, status, code: "x", message: "x", retryAfterMs });
}

// A wait that never actually sleeps, so tests are instant and deterministic.
const noWait = () => Promise.resolve();

describe("isRetryable", () => {
  it("retries safe/idempotent GET on transient conditions", () => {
    expect(isRetryable("GET", apiErr("unreachable"))).toBe(true);
    expect(isRetryable("GET", apiErr("server", 500))).toBe(true);
    expect(isRetryable("GET", apiErr("unavailable", 503))).toBe(true);
    expect(isRetryable("GET", apiErr("rateLimited", 429))).toBe(true);
  });

  it("never retries writes (POST/PATCH/DELETE), even on transient conditions", () => {
    for (const m of ["POST", "PATCH", "DELETE"] as const) {
      expect(isRetryable(m, apiErr("unreachable"))).toBe(false);
      expect(isRetryable(m, apiErr("server", 500))).toBe(false);
      expect(isRetryable(m, apiErr("rateLimited", 429))).toBe(false);
    }
  });

  it("never retries ordinary client errors, and never retries offline", () => {
    expect(isRetryable("GET", apiErr("validation", 422))).toBe(false);
    expect(isRetryable("GET", apiErr("notFound", 404))).toBe(false);
    expect(isRetryable("GET", apiErr("forbidden", 403))).toBe(false);
    expect(isRetryable("GET", apiErr("unauthenticated", 401))).toBe(false);
    expect(isRetryable("GET", apiErr("conflict", 409))).toBe(false);
    expect(isRetryable("GET", apiErr("offline"))).toBe(false);
  });

  it("ignores non-ApiError throwables", () => {
    expect(isRetryable("GET", new Error("boom"))).toBe(false);
  });
});

describe("backoffDelayMs", () => {
  it("is deterministic with an injected RNG and grows exponentially", () => {
    const rand = () => 0; // no jitter
    expect(backoffDelayMs(0, apiErr("server", 500), DEFAULT_RETRY_POLICY, rand)).toBe(300);
    expect(backoffDelayMs(1, apiErr("server", 500), DEFAULT_RETRY_POLICY, rand)).toBe(600);
    expect(backoffDelayMs(2, apiErr("server", 500), DEFAULT_RETRY_POLICY, rand)).toBe(1200);
  });

  it("caps at maxDelayMs", () => {
    const rand = () => 0;
    expect(backoffDelayMs(10, apiErr("server", 500), DEFAULT_RETRY_POLICY, rand)).toBe(
      DEFAULT_RETRY_POLICY.maxDelayMs,
    );
  });

  it("honours Retry-After when the server provided one", () => {
    const rand = () => 0;
    expect(backoffDelayMs(0, apiErr("rateLimited", 429, 1500), DEFAULT_RETRY_POLICY, rand)).toBe(1500);
  });

  it("adds bounded jitter from the RNG", () => {
    const rand = () => 0.5; // -> floor(0.5 * base) = 150
    expect(backoffDelayMs(0, apiErr("server", 500), DEFAULT_RETRY_POLICY, rand)).toBe(300 + 150);
  });
});

describe("runWithRetry", () => {
  it("retries a safe GET and eventually succeeds", async () => {
    const attempt = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(apiErr("unreachable"))
      .mockRejectedValueOnce(apiErr("server", 500))
      .mockResolvedValueOnce("ok");
    const out = await runWithRetry("GET", attempt, { wait: noWait, rand: () => 0 });
    expect(out).toBe("ok");
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it("stops after the bounded number of attempts and throws the last error", async () => {
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(apiErr("unreachable"));
    await expect(runWithRetry("GET", attempt, { wait: noWait, rand: () => 0 })).rejects.toBeInstanceOf(
      ApiError,
    );
    // 1 initial + maxRetries (2) = 3 total attempts, never more.
    expect(attempt).toHaveBeenCalledTimes(DEFAULT_RETRY_POLICY.maxRetries + 1);
  });

  it("does NOT retry a write (POST) — runs exactly once", async () => {
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(apiErr("server", 500));
    await expect(runWithRetry("POST", attempt, { wait: noWait })).rejects.toBeInstanceOf(ApiError);
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("does NOT retry an ordinary 4xx on a GET — runs exactly once", async () => {
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(apiErr("validation", 422));
    await expect(runWithRetry("GET", attempt, { wait: noWait })).rejects.toBeInstanceOf(ApiError);
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("stops immediately when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(apiErr("unreachable"));
    await expect(
      runWithRetry("GET", attempt, { wait: noWait, signal: controller.signal }),
    ).rejects.toBeTruthy();
    // The first attempt runs and fails; because the signal is aborted we do not retry.
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("propagates an AbortError from the attempt without retrying", async () => {
    const abortErr = new DOMException("Aborted", "AbortError");
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(abortErr);
    await expect(runWithRetry("GET", attempt, { wait: noWait })).rejects.toBe(abortErr);
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it("aborting during the backoff wait cancels the retry", async () => {
    const controller = new AbortController();
    const attempt = vi.fn<() => Promise<string>>().mockRejectedValue(apiErr("unreachable"));
    // A wait that rejects with AbortError to simulate the signal firing mid-backoff.
    const waitThenAbort = () => Promise.reject(new DOMException("Aborted", "AbortError"));
    await expect(
      runWithRetry("GET", attempt, { wait: waitThenAbort, signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(attempt).toHaveBeenCalledTimes(1);
  });
});
