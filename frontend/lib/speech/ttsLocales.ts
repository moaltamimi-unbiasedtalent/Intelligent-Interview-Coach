/**
 * Bounded 7-language speech-OUTPUT (TTS) locale mapping (the product now has 8 interface/conversation
 * languages; Russian is NOT a speech language) + honest availability status
 * (Capstone P7 / E5). The product/conversation language set (en/de/fr/es/it/pt/nl) maps to
 * a bounded BCP-47 speech-synthesis locale. This is SEPARATE from the P3 dictation (STT)
 * locale set and never changes career geography/jurisdiction.
 *
 * Availability is reported honestly per the phase's status vocabulary: we CONFIGURE a
 * locale and DETERMINISTICALLY TEST the mapping, but whether a real voice is installed is
 * BROWSER/PLATFORM-DEPENDENT and live human quality is UNVALIDATED. We never claim parity.
 */

export type ProductLocale = "en" | "de" | "fr" | "es" | "it" | "pt" | "nl";

/** Product/conversation locale → bounded speech-synthesis BCP-47 locale. */
export const TTS_LOCALE: Record<ProductLocale, string> = {
  en: "en-US",
  de: "de-DE",
  fr: "fr-FR",
  es: "es-ES",
  it: "it-IT",
  pt: "pt-PT",
  nl: "nl-NL",
};

export const SUPPORTED_TTS_LOCALES: ProductLocale[] = ["en", "de", "fr", "es", "it", "pt", "nl"];

/**
 * Per-language honest status. `configured`/`deterministicallyTested` are true (we own the
 * mapping + tests); `browserPlatformAvailable` is "depends" because a suitable voice must be
 * installed by the OS/browser; `liveHumanQualityTested` is false (UNVALIDATED — no paid
 * provider, no human review claimed).
 */
export interface TtsLanguageStatus {
  locale: ProductLocale;
  speechLocale: string;
  configured: boolean;
  browserPlatformAvailable: "depends";
  deterministicallyTested: boolean;
  liveHumanQualityTested: boolean;
}

export function ttsLanguageStatus(): TtsLanguageStatus[] {
  return SUPPORTED_TTS_LOCALES.map((locale) => ({
    locale,
    speechLocale: TTS_LOCALE[locale],
    configured: true,
    browserPlatformAvailable: "depends",
    deterministicallyTested: true,
    liveHumanQualityTested: false,
  }));
}

/**
 * True when speech OUTPUT (and realtime voice, which shares this same seven-language set on the
 * backend: `SUPPORTED_REALTIME_LOCALES`) is supported for a conversation language. An unset language
 * means the English default. A product locale outside this set (e.g. Russian, an interface and
 * conversation language since W9.7) must NOT be read aloud with a fallback English voice or start a
 * realtime session that the server would silently coerce to English: callers hide the voice control
 * and the visible text remains the guaranteed path.
 */
export function isSpeechOutputLocale(locale: string | null | undefined): boolean {
  if (!locale) return true;
  const key = locale.slice(0, 2).toLowerCase();
  return (SUPPORTED_TTS_LOCALES as string[]).includes(key);
}

/** Resolve a product/conversation locale to its speech-synthesis locale (safe fallback en-US). */
export function toSpeechLocale(locale: string | null | undefined): string {
  const key = (locale ?? "").slice(0, 2).toLowerCase() as ProductLocale;
  return TTS_LOCALE[key] ?? TTS_LOCALE.en;
}
