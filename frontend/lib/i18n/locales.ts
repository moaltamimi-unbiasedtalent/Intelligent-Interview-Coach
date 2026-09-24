/**
 * Centralized, typed locale identifiers (Capstone P3 — internationalization readiness).
 *
 * This file ONLY declares identifiers so later work has a single, typed source of
 * truth. P3 does **not** implement whole-application translation, and nothing here is
 * wired into rendering yet. It deliberately keeps four DISTINCT concepts apart so a
 * future i18n phase does not have to untangle them:
 *
 *   1. Application locale (UI language)      — this file (`AppLocale`), NOT yet applied.
 *   2. Dictation recognition locale (BCP-47) — `lib/speech` (`DICTATION_LANGUAGES`).
 *   3. Model/capability profile              — Fast/Balanced/Advanced (`AgentProfile`).
 *   4. Response-detail preference            — Brief/Detailed (`ResponseDetail`).
 *
 * The application locale must never be inferred from the dictation locale (or vice
 * versa); each is chosen explicitly by the user in its own control.
 */

/** Target application UI languages for the future Internationalization phase. */
export const APP_LOCALES = [
  { code: "en", label: "English" },
  { code: "de", label: "German" },
  { code: "fr", label: "French" },
  { code: "es", label: "Spanish" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "nl", label: "Dutch" },
] as const;

export type AppLocale = (typeof APP_LOCALES)[number]["code"];

/** The default application locale until the i18n phase adds real selection. */
export const DEFAULT_APP_LOCALE: AppLocale = "en";
