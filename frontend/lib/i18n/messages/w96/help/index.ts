// P10B-W9.6A — Help Center content fragment (all supported locales).
//
// Each locale file is a flat key -> string map of Help section titles and article question/answer
// copy (moved out of components/help/HelpCenter.tsx). This index shapes them into the standard W9.6
// fragment form `{ locale: { help: { ...keys } } }` so the central aggregator (../index.ts) deep-merges
// them into the `help` namespace of every locale catalogue.
//
// Key parity: English is the reference shape. Assigning each locale into `Record<HelpKey, string>`
// (no casts) makes a MISSING key a compile-time error; EXTRA keys are caught by `tests/i18n.test.tsx`.

import en from "./en";
import de from "./de";
import fr from "./fr";
import es from "./es";
import it from "./it";
import pt from "./pt";
import nl from "./nl";
import ru from "./ru";

/** Every Help key, from the English source of record. */
type HelpKey = keyof typeof en;
type HelpMap = Record<HelpKey, string>;

// Compile-time parity guard: each non-English locale must define (at least) every English key as a
// string. A missing key fails `tsc` here; the vitest catalogue test additionally rejects extras.
const deMap: HelpMap = de;
const frMap: HelpMap = fr;
const esMap: HelpMap = es;
const itMap: HelpMap = it;
const ptMap: HelpMap = pt;
const nlMap: HelpMap = nl;
const ruMap: HelpMap = ru;

const help: Record<string, { help: HelpMap }> = {
  en: { help: en },
  de: { help: deMap },
  fr: { help: frMap },
  es: { help: esMap },
  it: { help: itMap },
  pt: { help: ptMap },
  nl: { help: nlMap },
  ru: { help: ruMap },
};

export default help;
