/**
 * Russian (ru) base catalogue - P10B-W9.7 (ENGINEERING translation; native-speaker + legal review
 * pending). Composed from three namespace parts so parity with the English `Catalog` shape is
 * compile-time enforced: a missing OR extra key in any part fails `tsc`. The W9.6/W9.6A fragments
 * (lib/i18n/messages/w96/*, w96/ru/*, w96/help/ru.ts) are merged on top centrally in `catalog.ts`.
 *
 * Interface language only: Russian here does NOT imply Russian dictation/voice (speech capability is a
 * separate list), a Russian labour market, or Russian ESCO/taxonomy content.
 */

import type { Catalog } from "./en";
import a from "./ru-parts/a";
import b from "./ru-parts/b";
import c from "./ru-parts/c";

const ru: Catalog = { ...a, ...b, ...c };

export default ru;
