import { describe, expect, it } from "vitest";

import { apiErrorFromBody, kindForStatus } from "@/lib/api/errors";

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
