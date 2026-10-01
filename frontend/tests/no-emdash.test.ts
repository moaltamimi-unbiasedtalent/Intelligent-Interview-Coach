import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// P10B Wave 1: customer-facing Ask4Mo-authored copy must not contain the em dash "—"
// (founder brand rule — prefer "-" or a natural rewrite). This is a deterministic guard to
// prevent new customer-facing em dashes from creeping in. It scans the i18n catalogues and the
// customer-facing marketing/legal pages. It does NOT scan code comments, tests, docs, or
// domain/source content.

const ROOT = join(__dirname, "..");
const LOCALES = ["en", "de", "fr", "es", "it", "pt", "nl", "ru"];

// Russian (W9.7) is composed from part files; scan every part so a dash cannot hide in one.
const RU_PART_FILES = [
  "lib/i18n/messages/ru-parts/a.ts",
  "lib/i18n/messages/ru-parts/b.ts",
  "lib/i18n/messages/ru-parts/c.ts",
  "lib/i18n/messages/w96/ru/prepare.ts",
  "lib/i18n/messages/w96/ru/practice.ts",
  "lib/i18n/messages/w96/ru/surfaces.ts",
  "lib/i18n/messages/w96/ru/shell.ts",
  "lib/i18n/messages/w96/ru/legal.ts",
  "lib/i18n/messages/w96/help/ru.ts",
  "lib/i18n/messages/w96/closure.ts", // W9.7A fragment (all locales; same dash rule)
];

const CUSTOMER_FILES = [
  ...LOCALES.map((l) => `lib/i18n/messages/${l}.ts`),
  ...RU_PART_FILES,
  "components/marketing/MarketingShell.tsx",
  "components/marketing/MarketingHome.tsx",
  "components/marketing/ProductContent.tsx",
  "components/marketing/PricingContent.tsx",
  "components/marketing/TrustContent.tsx",
  "app/about/page.tsx",
  "app/privacy/page.tsx",
  "app/terms/page.tsx",
  "app/ai-transparency/page.tsx",
];

describe("no em dash in customer-facing copy (P10B Wave 1)", () => {
  for (const rel of CUSTOMER_FILES) {
    it(`${rel} contains no em dash`, () => {
      const path = join(ROOT, rel);
      if (!existsSync(path)) return; // tolerate optional files
      const text = readFileSync(path, "utf8");
      const idx = text.indexOf("—"); // em dash
      const where = idx >= 0 ? text.slice(Math.max(0, idx - 40), idx + 40) : "";
      expect(idx, `em dash found in ${rel}: …${where}…`).toBe(-1);
    });
  }

  // The Russian catalogue also avoids the en dash (the standard Russian dash is replaced by a colon,
  // comma or parentheses per the W9.7 translation standard).
  for (const rel of ["lib/i18n/messages/ru.ts", ...RU_PART_FILES]) {
    it(`${rel} contains no en dash`, () => {
      const path = join(ROOT, rel);
      if (!existsSync(path)) return;
      expect(readFileSync(path, "utf8").includes("–")).toBe(false);
    });
  }
});
