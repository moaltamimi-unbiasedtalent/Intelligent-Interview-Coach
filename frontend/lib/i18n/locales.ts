/**
 * Centralized, typed locale identifiers (Capstone P3.5 — internationalization).
 *
 * Single source of truth for the CATALOGUE locales (eight, Russian added in W9.7 and preserved) and, below, the seven ACTIVE Candidate languages (06A). It deliberately
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

/**
 * The eight CATALOGUE locales (English is the source language). Russian (W9.7) is PRESERVED here so its
 * catalogue, tests and message lookups keep working, but it is EXCLUDED from R1.0 Candidate selection
 * (06A, REQ-LANG-14): never render a selector from this list; use `SELECTABLE_LOCALES`.
 */
export const APP_LOCALES = [
  { code: "en", label: "English", nativeLabel: "English" },
  { code: "de", label: "German", nativeLabel: "Deutsch" },
  { code: "fr", label: "French", nativeLabel: "Français" },
  { code: "es", label: "Spanish", nativeLabel: "Español" },
  { code: "it", label: "Italian", nativeLabel: "Italiano" },
  { code: "pt", label: "Portuguese", nativeLabel: "Português" },
  { code: "nl", label: "Dutch", nativeLabel: "Nederlands" },
  { code: "ru", label: "Russian", nativeLabel: "Русский" },
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

/**
 * Locales a Candidate may SELECT or start new work in (06A, REQ-LANG-14). Mirrors the server-defined
 * `ACTIVE_CANDIDATE_LOCALES` in `src/locales.py` (also served by GET /capabilities); a backend test asserts the
 * two stay equal. Listing a language here is NOT a qualification claim: see docs/production/execution/language_readiness.json.
 */
export const ACTIVE_CANDIDATE_LOCALES: readonly AppLocale[] = ["en", "de", "fr", "es", "it", "pt", "nl"];

/** The locales every Candidate language selector offers (no Russian). */
export const SELECTABLE_LOCALES = APP_LOCALES.filter((l) => (ACTIVE_CANDIDATE_LOCALES as readonly string[]).includes(l.code));

export function isActiveLocale(code: string | null | undefined): code is AppLocale {
  return !!code && (ACTIVE_CANDIDATE_LOCALES as readonly string[]).includes(code);
}

/**
 * Like `toSupportedLocale`, but a stored/detected locale that is not active (a legacy `ru` preference, a Russian
 * browser or cookie) resolves to null so callers fall back to the default interface language. Display-only: it
 * never rewrites the stored preference and never touches career geography.
 */
export function toActiveLocale(value: string | null | undefined): AppLocale | null {
  const supported = toSupportedLocale(value);
  return supported && isActiveLocale(supported) ? supported : null;
}
