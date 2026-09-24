/**
 * Centralized, typed locale identifiers (Capstone P3.5 — internationalization).
 *
 * Single source of truth for the seven candidate-product UI languages. It deliberately
 * keeps FOUR DISTINCT concepts apart so they are never conflated:
 *
 *   1. Application locale (UI language)      — this file (`AppLocale`).
 *   2. Dictation recognition locale (BCP-47) — `lib/speech` (`DICTATION_LANGUAGES`).
 *   3. Model/capability profile              — Fast/Balanced/Advanced (`AgentProfile`).
 *   4. Response-detail preference            — Brief/Detailed (`ResponseDetail`).
 *
 * The application locale is never inferred from the dictation locale (or vice versa),
 * and a language choice NEVER changes labour-market geography.
 */

/** The seven supported application UI languages (English is the source language). */
export const APP_LOCALES = [
  { code: "en", label: "English", nativeLabel: "English" },
  { code: "de", label: "German", nativeLabel: "Deutsch" },
  { code: "fr", label: "French", nativeLabel: "Français" },
  { code: "es", label: "Spanish", nativeLabel: "Español" },
  { code: "it", label: "Italian", nativeLabel: "Italiano" },
  { code: "pt", label: "Portuguese", nativeLabel: "Português" },
  { code: "nl", label: "Dutch", nativeLabel: "Nederlands" },
] as const;

export type AppLocale = (typeof APP_LOCALES)[number]["code"];

/** Default/source application locale. Missing translations fall back to this. */
export const DEFAULT_APP_LOCALE: AppLocale = "en";

export const SUPPORTED_LOCALE_CODES: readonly AppLocale[] = APP_LOCALES.map((l) => l.code);

/** Narrow an arbitrary string to a supported AppLocale, else null. */
export function toSupportedLocale(value: string | null | undefined): AppLocale | null {
  if (!value) return null;
  const code = value.toLowerCase().split("-")[0];
  return (SUPPORTED_LOCALE_CODES as readonly string[]).includes(code) ? (code as AppLocale) : null;
}

export function localeLabel(code: AppLocale): string {
  return APP_LOCALES.find((l) => l.code === code)?.label ?? code;
}
