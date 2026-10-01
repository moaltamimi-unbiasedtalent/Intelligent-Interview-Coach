/**
 * Catalogue assembly + safe translation (Capstone P3.5).
 *
 * English is the reference; any missing key falls back to English, and a truly unknown
 * key returns the key itself (never `undefined`, a raw object, or a blank) so the UI
 * never renders a broken localisation artifact.
 */

import type { AppLocale } from "./locales";
import { DEFAULT_APP_LOCALE } from "./locales";
import en, { type Catalog, type Messages } from "./messages/en";
import de from "./messages/de";
import fr from "./messages/fr";
import es from "./messages/es";
import it from "./messages/it";
import pt from "./messages/pt";
import nl from "./messages/nl";
import ru from "./messages/ru";
import { mergeW96Into } from "./messages/w96";

// P10B-W9.6: the full-localization fragments are deep-merged onto each base locale catalogue so
// every Ask4Mo-owned candidate-facing string resolves in the selected interface language (with
// English fallback per key). The merge is additive and non-destructive — base keys always win is
// NOT the rule; W9.6 only ADDS namespaces/keys that the base catalogues do not already define, so
// pre-existing keys are untouched. Key parity across all supported locales (eight) is enforced by the fragments
// themselves and re-verified by `tests/i18n.test.tsx`.
export const CATALOGS: Record<AppLocale, Catalog> = {
  en: mergeW96Into(en, "en"),
  de: mergeW96Into(de, "de"),
  fr: mergeW96Into(fr, "fr"),
  es: mergeW96Into(es, "es"),
  it: mergeW96Into(it, "it"),
  pt: mergeW96Into(pt, "pt"),
  nl: mergeW96Into(nl, "nl"),
  ru: mergeW96Into(ru, "ru"),
};

export type Namespace = keyof Messages;
/** A "namespace.key" translation key, typed against the English source. */
export type MessageKey = {
  [N in keyof Messages]: `${N & string}.${keyof Messages[N] & string}`;
}[keyof Messages];

export function getCatalog(locale: AppLocale): Catalog {
  return CATALOGS[locale] ?? en;
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) =>
    name in vars ? String(vars[name]) : `{${name}}`,
  );
}

/** Look up a key in the locale catalogue, falling back to English, then the key. */
export function translate(
  locale: AppLocale,
  key: MessageKey | string,
  vars?: Record<string, string | number>,
): string {
  const [ns, k] = String(key).split(".");
  const localeCat = getCatalog(locale) as Record<string, Record<string, string>>;
  // Fall back to the MERGED English catalogue (CATALOGS.en), so W9.6 namespaces/keys resolve in the
  // fallback path, not just the raw base `en` source.
  const enCat = CATALOGS[DEFAULT_APP_LOCALE] as Record<string, Record<string, string>>;
  const value = localeCat[ns]?.[k] ?? enCat[ns]?.[k];
  if (value == null) return String(key); // never render undefined/blank
  return interpolate(value, vars);
}

export { DEFAULT_APP_LOCALE };
export type { Catalog, Messages };
