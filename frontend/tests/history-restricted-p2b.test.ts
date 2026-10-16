import { describe, expect, it } from "vitest";

import { ApiError, apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

const FORBIDDEN = /premium|upgrade|plan\b|subscri|price|€|\$|buy|purchase|checkout/i;

describe("W12.4D-P2-B: an owned interview outside the history view", () => {
  it("maps history_not_available on a 403 to its own kind and state key (not 'deleted', not a generic forbidden)", () => {
    const err = apiErrorFromBody(403, { error: { code: "history_not_available", message: "m", request_id: "r" } }, "r", null);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe("historyRestricted");
    expect(stateKeyForError(err.kind)).toBe("states.historyRestricted");
    expect(apiErrorFromBody(403, { error: { code: "forbidden", message: "m", request_id: "r" } }, "r", null).kind).toBe("forbidden");
    expect(apiErrorFromBody(404, { error: { code: "not_found", message: "m", request_id: "r" } }, "r", null).kind).toBe("notFound");
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: says the interview is stored, never presents it as deleted, and has no upgrade or checkout wording`, () => {
      const text = translate(locale, "states.historyRestricted");
      expect(text.trim().length).toBeGreaterThan(30);
      expect(text).not.toBe("states.historyRestricted");
      expect(text).not.toMatch(FORBIDDEN);
      if (locale !== "en") expect(text).not.toBe(translate("en", "states.historyRestricted"));
    });
  }

  it("the English fallback states that the interview was not deleted", () => {
    const err = new ApiError({ kind: "historyRestricted", status: 403, code: "history_not_available", message: "x" });
    expect(err.userMessage).toMatch(/not been deleted/i);
    expect(err.userMessage).not.toMatch(FORBIDDEN);
  });
});
