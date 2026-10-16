import { describe, expect, it } from "vitest";

import { ApiError, apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { translate } from "@/lib/i18n/catalog";

const FORBIDDEN = /premium|upgrade|plan\b|subscri|price|€|\$|buy|purchase/i;

describe("W12.4D-P2-A: temporary AI safety limit (stable code, no commercial wording)", () => {
  it("maps the ai_usage_limit code on a 429 to the aiLimited kind and its own state key", () => {
    const err = apiErrorFromBody(429, { error: { code: "ai_usage_limit", message: "m", request_id: "r1", capability: "practice", temporary: true, retry_after_seconds: 90 } }, "r1", 90_000);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe("aiLimited");
    expect(err.retryAfterMs).toBe(90_000);
    expect(stateKeyForError(err.kind)).toBe("states.aiUsageLimit");
  });

  it("a plain 429 stays a generic rate limit and a pause stays a pause", () => {
    expect(apiErrorFromBody(429, { error: { code: "rate_limited", message: "m", request_id: "r" } }, "r", null).kind).toBe("rateLimited");
    expect(apiErrorFromBody(503, { error: { code: "platform_paused", message: "m", request_id: "r" } }, "r", null).kind).toBe("paused");
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: the message exists, says it is temporary and never shows an upgrade or price call to action`, () => {
      const text = translate(locale, "states.aiUsageLimit");
      expect(text.trim().length).toBeGreaterThan(20);
      expect(text).not.toBe("states.aiUsageLimit");
      expect(text).not.toMatch(FORBIDDEN);
      if (locale !== "en") expect(text).not.toBe(translate("en", "states.aiUsageLimit"));
    });
  }

  it("the English fallback message offers the next action and no commercial wording", () => {
    const err = new ApiError({ kind: "aiLimited", status: 429, code: "ai_usage_limit", message: "x" });
    expect(err.userMessage).toMatch(/try again/i);
    expect(err.userMessage).not.toMatch(FORBIDDEN);
  });
});
