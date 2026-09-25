import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { HelpCenter } from "@/components/help/HelpCenter";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

// P7 closure §10: the new Voice Help section is localised via the i18n catalogues (P3.5
// standard), renders in the selected interface language, and never shows a raw key.

const VOICE_HELP_KEYS = [
  "voice.helpTitle", "voice.hListenQ", "voice.hListenA", "voice.hSpeakQ", "voice.hSpeakA",
  "voice.hLangQ", "voice.hLangA", "voice.hPrivacyQ", "voice.hPrivacyA",
  "voice.hUnsupportedQ", "voice.hUnsupportedA",
] as const;

describe("voice help i18n", () => {
  it("has all voice-help keys in all seven catalogues (non-empty, no raw key)", () => {
    for (const code of SUPPORTED_LOCALE_CODES) {
      for (const key of VOICE_HELP_KEYS) {
        const v = translate(code, key);
        expect(v.trim().length).toBeGreaterThan(0);
        expect(v).not.toBe(key); // never the raw key
      }
    }
  });

  it("German + French voice-help titles are actually translated (differ from English)", () => {
    expect(translate("de", "voice.helpTitle")).not.toBe(translate("en", "voice.helpTitle"));
    expect(translate("fr", "voice.helpTitle")).not.toBe(translate("en", "voice.helpTitle"));
    expect(translate("de", "voice.helpTitle")).toContain("Stimme");
  });

  it("renders the German Voice Help section (no raw keys shown)", () => {
    render(
      <I18nProvider initialLocale="de">
        <HelpCenter />
      </I18nProvider>,
    );
    expect(screen.getByText(translate("de", "voice.helpTitle"))).toBeInTheDocument();
    expect(screen.queryByText("voice.helpTitle")).toBeNull();
    expect(screen.queryByText("voice.hListenQ")).toBeNull();
  });

  it("renders the English Voice Help section by default", () => {
    render(
      <I18nProvider initialLocale="en">
        <HelpCenter />
      </I18nProvider>,
    );
    expect(screen.getByText("Voice: listening & speaking")).toBeInTheDocument();
  });
});
