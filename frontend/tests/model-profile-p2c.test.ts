import { describe, expect, it } from "vitest";

import { ApiError, apiErrorFromBody, stateKeyForError } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

const FORBIDDEN = /premium|upgrade|plan\b|subscri|price|€|\$|buy|purchase|checkout|medium/i;

describe("W12.4D-P2-C: an AI model profile that is not available to the account", () => {
  it("maps both stable backend codes to one kind and state key", () => {
    for (const [status, code] of [[403, "model_profile_not_authorized"], [422, "model_profile_not_available"]] as const) {
      const err = apiErrorFromBody(status, { error: { code, message: "m", request_id: "r" } }, "r", null);
      expect(err).toBeInstanceOf(ApiError);
      expect(err.kind).toBe("modelProfileRestricted");
      expect(stateKeyForError(err.kind)).toBe("states.modelProfileNotAvailable");
    }
    expect(apiErrorFromBody(422, { error: { code: "validation_error", message: "m", request_id: "r" } }, "r", null).kind).toBe("validation");
    expect(apiErrorFromBody(403, { error: { code: "forbidden", message: "m", request_id: "r" } }, "r", null).kind).toBe("forbidden");
  });

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: localized, neutral, no price, upgrade or Medium wording`, () => {
      const text = translate(locale, "states.modelProfileNotAvailable");
      expect(text.trim().length).toBeGreaterThan(20);
      expect(text).not.toBe("states.modelProfileNotAvailable");
      expect(text).not.toMatch(FORBIDDEN);
      if (locale !== "en") expect(text).not.toBe(translate("en", "states.modelProfileNotAvailable"));
    });
  }

  it("the English fallback offers the next action without commercial wording", () => {
    const err = new ApiError({ kind: "modelProfileRestricted", status: 403, code: "model_profile_not_authorized", message: "x" });
    expect(err.userMessage).toMatch(/choose another profile/i);
    expect(err.userMessage).not.toMatch(FORBIDDEN);
  });
});
