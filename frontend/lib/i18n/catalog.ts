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

export const CATALOGS: Record<AppLocale, Catalog> = { en, de, fr, es, it, pt, nl };

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
  const enCat = en as Record<string, Record<string, string>>;
  const value = localeCat[ns]?.[k] ?? enCat[ns]?.[k];
  if (value == null) return String(key); // never render undefined/blank
  return interpolate(value, vars);
}

export { DEFAULT_APP_LOCALE };
export type { Catalog, Messages };
