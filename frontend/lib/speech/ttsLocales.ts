/**
 * Bounded 7-language speech-OUTPUT (TTS) locale mapping + honest availability status
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

/** Resolve a product/conversation locale to its speech-synthesis locale (safe fallback en-US). */
export function toSpeechLocale(locale: string | null | undefined): string {
  const key = (locale ?? "").slice(0, 2).toLowerCase() as ProductLocale;
  return TTS_LOCALE[key] ?? TTS_LOCALE.en;
}
