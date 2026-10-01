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
// each base locale catalogue so these keys resolve at runtime.

import type { AppLocale } from "../../locales";
import { SUPPORTED_LOCALE_CODES } from "../../locales";
import prepare from "./prepare";
import practice from "./practice";
import surfaces from "./surfaces";
import legal from "./legal";
import shell from "./shell";
import help from "./help"; // P10B-W9.6A — Help Center section/article content
import closure from "./closure"; // P10B-W9.7A — strings found by visual QA (all 8 locales)
import w98 from "../w98"; // P10B-W9.8 — Data & Privacy Center (all 8 locales)
// P10B-W9.7: Russian blocks live beside (not inside) the 7-locale fragment files, each typed against
// its fragment's English shape so missing/extra keys fail `tsc`. `help` carries its own `ru` entry.
import prepareRu from "./ru/prepare";
import practiceRu from "./ru/practice";
import surfacesRu from "./ru/surfaces";
import legalRu from "./ru/legal";
import shellRu from "./ru/shell";

/** A namespace -> key -> string map for one locale. */
type NsMap = Record<string, Record<string, string>>;

/** One fragment: its per-locale blocks, keyed by locale code. */
type Fragment = Record<string, NsMap>;

// Each fragment is authored with its own precise type (some as a typed interface without a string
// index signature); they all share the runtime shape `{ locale: { namespace: { key: value }}}`, so
// they are bridged to the common `Fragment` via `unknown`. Russian is attached per fragment here.
const FRAGMENTS: Array<{ name: string; blocks: Fragment }> = [
  { name: "prepare", blocks: { ...(prepare as unknown as Fragment), ru: prepareRu as unknown as NsMap } },
  { name: "practice", blocks: { ...(practice as unknown as Fragment), ru: practiceRu as unknown as NsMap } },
  { name: "surfaces", blocks: { ...(surfaces as unknown as Fragment), ru: surfacesRu as unknown as NsMap } },
  { name: "legal", blocks: { ...(legal as unknown as Fragment), ru: legalRu as unknown as NsMap } },
  { name: "shell", blocks: { ...(shell as unknown as Fragment), ru: shellRu as unknown as NsMap } },
  { name: "help", blocks: help as unknown as Fragment },
  { name: "closure", blocks: closure as unknown as Fragment },
  { name: "w98", blocks: w98 as unknown as Fragment },
];

/** Additively merge `source` namespaces/keys into `target` (mutates and returns `target`). */
function mergeNs(target: NsMap, source: NsMap): NsMap {
  for (const [ns, entries] of Object.entries(source)) {
    target[ns] = { ...(target[ns] ?? {}), ...entries };
  }
  return target;
}

/**
 * W9.6/W9.7 translations by locale code, every fragment deep-merged. A fragment that lacks a supported
 * locale is a hard error (NOT a silent English fallback): a product locale must be complete.
 */
export const w96 = SUPPORTED_LOCALE_CODES.reduce((acc, locale) => {
  const merged: NsMap = {};
  for (const { name, blocks } of FRAGMENTS) {
    const forLocale = blocks[locale];
    if (!forLocale) throw new Error(`i18n fragment "${name}" has no "${locale}" block`);
    mergeNs(merged, forLocale);
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
  const fragment = w96[locale];
  const out: Record<string, Record<string, string>> = { ...base };
  for (const [ns, entries] of Object.entries(fragment)) {
    out[ns] = { ...(out[ns] ?? {}), ...entries };
  }
  return out as T;
}

export default w96;
