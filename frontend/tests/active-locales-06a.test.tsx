import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConversationLanguageField } from "@/components/i18n/ConversationLanguageField";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { CATALOGS } from "@/lib/i18n/catalog";
import {
  ACTIVE_CANDIDATE_LOCALES,
  APP_LOCALES,
  SELECTABLE_LOCALES,
  SUPPORTED_LOCALE_CODES,
  toActiveLocale,
  toSupportedLocale,
} from "@/lib/i18n/locales";

/** 06A (REQ-LANG-14, LG-14): the Candidate selectors offer exactly the seven active locales; ru is preserved, not offered. */
describe("06A active Candidate locales", () => {
  it("exposes exactly the seven active locales in a stable order, never Russian", () => {
    expect([...ACTIVE_CANDIDATE_LOCALES]).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
    expect(SELECTABLE_LOCALES.map((l) => l.code)).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
  });

  it("preserves the Russian catalogue and registry entry (code and tests kept)", () => {
    expect(APP_LOCALES.map((l) => l.code)).toContain("ru");
    expect(SUPPORTED_LOCALE_CODES).toContain("ru");
    expect(Object.keys(CATALOGS)).toContain("ru");
  });

  it("falls back to the default for a stored, cookie or browser ru value without rewriting anything", () => {
    expect(toActiveLocale("ru")).toBeNull();
    expect(toActiveLocale("ru-RU")).toBeNull();
    expect(toActiveLocale("de-AT")).toBe("de");
    expect(toSupportedLocale("ru")).toBe("ru"); // catalogue lookups still resolve
  });

  it("the Mo conversation language field offers seven languages, no Russian", () => {
    render(
      <I18nProvider initialLocale="en">
        <ConversationLanguageField value="en" onChange={() => {}} />
      </I18nProvider>,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
  });
});
