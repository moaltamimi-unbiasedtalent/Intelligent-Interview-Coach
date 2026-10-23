import { afterEach, describe, expect, it } from "vitest";

import { ApiError, stateKeyForError, type ApiErrorKind } from "@/lib/api/errors";
import { translate } from "@/lib/i18n/catalog";
import { ACTIVE_CANDIDATE_LOCALES } from "@/lib/i18n/locales";

// 06B: ApiError.userMessage follows the interface language (read from <html lang>), so a failed load never shows English chrome
// in a non-English interface. English stays byte-identical; Russian (excluded) and unknown tags fall back to English.
const KINDS: ApiErrorKind[] = ["offline", "unreachable", "unauthenticated", "forbidden", "notFound", "validation", "conflict", "rateLimited", "server", "unavailable", "unknown"];
const err = (kind: ApiErrorKind) => new ApiError({ kind, status: null, code: kind, message: "x" });

afterEach(() => { document.documentElement.lang = ""; });

describe("ApiError.userMessage follows the interface language (06B)", () => {
  it("English is the original copy and is used when the language is unset, unknown or excluded (ru)", () => {
    for (const lang of ["", "en", "xx", "ru"]) {
      document.documentElement.lang = lang;
      expect(err("server").userMessage).toBe("Ask4Mo hit a problem while processing that request. Please try again.");
    }
  });

  it.each(ACTIVE_CANDIDATE_LOCALES.filter((l) => l !== "en"))("renders the %s catalogue message for every common kind", (loc) => {
    document.documentElement.lang = loc;
    for (const kind of KINDS) {
      const msg = err(kind).userMessage;
      expect(msg).toBe(translate(loc, stateKeyForError(kind)));
      expect(msg.trim().length).toBeGreaterThan(0);
    }
    expect(err("server").userMessage).not.toBe(translate("en", "states.serverError"));
  });

  it("the new prepare.sessionGone message exists, differs from English and is non-empty in every selectable language", () => {
    const en = translate("en", "prepare.sessionGone");
    expect(en).toBe("This preparation session can no longer be resumed.");
    for (const loc of ACTIVE_CANDIDATE_LOCALES.filter((l) => l !== "en")) {
      const v = translate(loc, "prepare.sessionGone");
      expect(v).not.toBe(en);
      expect(v.trim().length).toBeGreaterThan(0);
    }
  });
});
