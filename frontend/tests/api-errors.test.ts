import { describe, expect, it } from "vitest";

import {
  apiErrorFromBody,
  kindForStatus,
  parseRetryAfter,
  stateKeyForError,
  unreachableError,
} from "@/lib/api/errors";

describe("kindForStatus", () => {
  it("classifies 409 as conflict (not generic validation)", () => {
    expect(kindForStatus(409)).toBe("conflict");
  });

  it("keeps other 4xx as validation and 5xx as server", () => {
    expect(kindForStatus(422)).toBe("validation");
    expect(kindForStatus(400)).toBe("validation");
    expect(kindForStatus(500)).toBe("server");
  });

  it("maps a 503 body to unavailable (special-cased in apiErrorFromBody)", () => {
    const err = apiErrorFromBody(503, { error: { code: "not_configured", message: "" } }, null);
    expect(err.kind).toBe("unavailable");
  });
});

describe("apiErrorFromBody", () => {
  it("carries the stable envelope code and a conflict kind for 409", () => {
    const err = apiErrorFromBody(
      409,
      { error: { code: "conflict", message: "Already being processed.", request_id: "req_1" } },
      null,
    );
    expect(err.kind).toBe("conflict");
    expect(err.code).toBe("conflict");
    expect(err.message).toBe("Already being processed.");
    expect(err.requestId).toBe("req_1");
  });

  it("preserves the missing-handoff-config code for a 422", () => {
    const err = apiErrorFromBody(
      422,
      { error: { code: "missing_interview_handoff_config", message: "Add the missing industry and career level to start practice." } },
      null,
    );
    expect(err.code).toBe("missing_interview_handoff_config");
    expect(err.status).toBe(422);
  });

  it("gives a calm conflict userMessage", () => {
    const err = apiErrorFromBody(409, { error: { code: "conflict", message: "" } }, null);
    expect(err.userMessage).toMatch(/already being processed/i);
  });
});

// --- P10B-W9.1: truthful taxonomy -------------------------------------------------------

describe("kindForStatus (W9.1 taxonomy)", () => {
  it("distinguishes each auth-relevant status", () => {
    expect(kindForStatus(401)).toBe("unauthenticated");
    expect(kindForStatus(403)).toBe("forbidden");
    expect(kindForStatus(404)).toBe("notFound");
    expect(kindForStatus(409)).toBe("conflict");
    expect(kindForStatus(422)).toBe("validation");
    expect(kindForStatus(429)).toBe("rateLimited");
  });

  it("classifies 502/503/504 as unavailable and other 5xx as server", () => {
    expect(kindForStatus(502)).toBe("unavailable");
    expect(kindForStatus(503)).toBe("unavailable");
    expect(kindForStatus(504)).toBe("unavailable");
    expect(kindForStatus(500)).toBe("server");
    expect(kindForStatus(599)).toBe("server");
  });
});

describe("unreachableError (offline vs unreachable)", () => {
  it("blames the device only when the browser reports it offline", () => {
    const offline = unreachableError(false);
    expect(offline.kind).toBe("offline");
    expect(offline.userMessage).toMatch(/offline/i);
  });

  it("does NOT blame the user's connection when the device is online", () => {
    const unreachable = unreachableError(true);
    expect(unreachable.kind).toBe("unreachable");
    // Truthful copy: names Ask4Mo, never tells the user to check their internet.
    expect(unreachable.userMessage).toMatch(/ask4mo/i);
    expect(unreachable.userMessage).not.toMatch(/check your (internet|connection)/i);
  });
});

describe("HTTP 500 is a server error, not a network failure", () => {
  it("classifies a received 500 as server with a reference id preserved", () => {
    const err = apiErrorFromBody(
      500,
      { error: { code: "internal_error", message: "An unexpected error occurred.", request_id: "req_9" } },
      "hdr_9",
    );
    expect(err.kind).toBe("server");
    expect(err.requestId).toBe("req_9");
    expect(err.userMessage).toMatch(/ask4mo/i);
    expect(err.userMessage).not.toMatch(/connection/i);
  });

  it("falls back to the header request id when the body has none", () => {
    const err = apiErrorFromBody(500, undefined, "hdr_only");
    expect(err.requestId).toBe("hdr_only");
  });
});

describe("parseRetryAfter", () => {
  it("parses delta-seconds into ms", () => {
    expect(parseRetryAfter("2")).toBe(2000);
    expect(parseRetryAfter("0")).toBe(0);
  });
  it("parses an HTTP-date into a non-negative delay", () => {
    const future = new Date(Date.now() + 5000).toUTCString();
    const ms = parseRetryAfter(future);
    expect(ms).not.toBeNull();
    expect(ms!).toBeGreaterThanOrEqual(0);
  });
  it("returns null for missing/garbage", () => {
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter("soon")).toBeNull();
  });
  it("carries retryAfterMs onto a 429 ApiError", () => {
    const err = apiErrorFromBody(429, { error: { code: "rate_limited", message: "" } }, null, 3000);
    expect(err.kind).toBe("rateLimited");
    expect(err.retryAfterMs).toBe(3000);
  });
});

describe("stateKeyForError maps every kind into the i18n states namespace", () => {
  it("returns states.* keys (localizable source of truth)", () => {
    expect(stateKeyForError("offline")).toBe("states.offline");
    expect(stateKeyForError("unreachable")).toBe("states.serviceUnreachable");
    expect(stateKeyForError("server")).toBe("states.serverError");
    expect(stateKeyForError("unavailable")).toBe("states.serviceUnavailable");
    expect(stateKeyForError("rateLimited")).toBe("states.rateLimited");
    expect(stateKeyForError("unauthenticated")).toBe("states.sessionExpired");
    expect(stateKeyForError("forbidden")).toBe("states.forbidden");
    expect(stateKeyForError("notFound")).toBe("states.notFound");
    expect(stateKeyForError("unknown")).toBe("states.genericError");
  });
});
