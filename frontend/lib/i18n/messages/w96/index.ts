// P10B-W9.6 localization fragments aggregator.
//
// Collects the W9.6 translation fragments into one per-locale object keyed by locale code. The
// fragments were authored in parallel, each covering a disjoint slice of the candidate-facing
// product chrome, and each is a plain default export shaped `{ locale: { namespace: { key: value }}}`:
//
//   - prepare   : Prepare / Mo / Agent / Coach surfaces
//   - practice  : Practice / Interview / History / Feedback surfaces
//   - surfaces  : Opportunity / Documents / Company / Workspaces surfaces
//   - legal     : Privacy / Terms / AI transparency / About / Help / Marketing / Trust surfaces
//   - shell     : Shared chrome (progress / memory / home / common / states / nav)
//
// Every fragment is authored with identical keys across all seven supported locales (enforced at
// compile time in each fragment, and re-verified by `tests/i18n.test.tsx`). This module is
// side-effect free; the central catalogue (`lib/i18n/catalog.ts`) deep-merges `w96[locale]` onto
// each base locale catalogue so these keys resolve at runtime, with English fallback.

import type { AppLocale } from "../../locales";
import { SUPPORTED_LOCALE_CODES } from "../../locales";
import prepare from "./prepare";
import practice from "./practice";
import surfaces from "./surfaces";
import legal from "./legal";
import shell from "./shell";

/** A namespace -> key -> string map for one locale. */
type NsMap = Record<string, Record<string, string>>;

/** Each fragment, keyed by locale code (missing namespaces simply do not contribute). */
// Each fragment is authored with its own precise type (some as a typed interface without a string
// index signature); they all share the runtime shape `{ locale: { namespace: { key: value }}}`, so
// they are bridged to the common `Record<string, NsMap>` via `unknown`.
const FRAGMENTS: Array<Record<string, NsMap>> = [
  prepare as unknown as Record<string, NsMap>,
  practice as unknown as Record<string, NsMap>,
  surfaces as unknown as Record<string, NsMap>,
  legal as unknown as Record<string, NsMap>,
  shell as unknown as Record<string, NsMap>,
];

/** Additively merge `source` namespaces/keys into `target` (mutates and returns `target`). */
function mergeNs(target: NsMap, source: NsMap): NsMap {
  for (const [ns, entries] of Object.entries(source)) {
    target[ns] = { ...(target[ns] ?? {}), ...entries };
  }
  return target;
}

/** W9.6 translations by locale code, every fragment deep-merged (en fallback per fragment). */
export const w96 = SUPPORTED_LOCALE_CODES.reduce((acc, locale) => {
  const merged: NsMap = {};
  for (const fragment of FRAGMENTS) {
    const forLocale = (fragment[locale] ?? fragment.en) as NsMap | undefined;
    if (forLocale) mergeNs(merged, forLocale);
  }
  acc[locale] = merged;
  return acc;
}, {} as Record<AppLocale, NsMap>);

/**
 * Additively deep-merge the W9.6 namespaces for a locale onto an existing catalogue object.
 * New namespaces are added; existing namespaces gain the W9.6 keys without dropping any. The
 * inputs are not mutated. Used by the catalogue wiring step in `catalog.ts`.
 */
export function mergeW96Into<T extends Record<string, Record<string, string>>>(
  base: T,
  locale: AppLocale,
): T {
  const fragment = w96[locale] ?? w96.en;
  const out: Record<string, Record<string, string>> = { ...base };
  for (const [ns, entries] of Object.entries(fragment)) {
    out[ns] = { ...(out[ns] ?? {}), ...entries };
  }
  return out as T;
}

export default w96;
