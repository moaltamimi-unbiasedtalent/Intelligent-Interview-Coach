import { describe, expect, it } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";
// @ts-expect-error - plain ESM guard script (no type declarations).
import { APPROVED_BRAND_INVARIANTS, scanAll } from "../scripts/scan-i18n.mjs";

/**
 * P10B-W9.7 - the protected brand slogan is NEVER translated, transliterated or re-punctuated, in any
 * interface language (current or future). One constant (`lib/brand.ts`) is the source of truth.
 */

describe("protected brand slogan (all locales)", () => {
  it("is exactly the established brand string", () => {
    expect(BRAND_SLOGAN).toBe("Ask More. Be More.");
  });

  it("covers all eight supported locales (so a new locale is checked automatically)", () => {
    expect([...SUPPORTED_LOCALE_CODES]).toEqual(["en", "de", "fr", "es", "it", "pt", "nl", "ru"]);
  });

  for (const code of ["en", "de", "fr", "es", "it", "pt", "nl", "ru"] as const) {
    it(`${code}: the visible tagline resolves to EXACTLY the slogan`, () => {
      expect(translate(code, "common.tagline")).toBe(BRAND_SLOGAN);
      expect(CATALOGS[code].common.tagline).toBe(BRAND_SLOGAN);
    });

    it(`${code}: register subtitle and About text embed the slogan verbatim`, () => {
      expect(translate(code, "auth.registerSubtitle").endsWith(BRAND_SLOGAN)).toBe(true);
      expect(translate(code, "about.lead")).toContain(BRAND_SLOGAN);
    });
  }

  it("every 'ask more' occurrence in any catalogue is exactly the protected phrase (no variants)", () => {
    for (const code of SUPPORTED_LOCALE_CODES) {
      const cat = CATALOGS[code] as unknown as Record<string, Record<string, string>>;
      for (const ns of Object.keys(cat)) {
        for (const [key, value] of Object.entries(cat[ns])) {
          for (const m of value.matchAll(/ask\s+more/gi)) {
            const at = m.index ?? 0;
            expect(
              value.slice(at, at + BRAND_SLOGAN.length),
              `${code} ${ns}.${key} contains a non-exact variant of the slogan`,
            ).toBe(BRAND_SLOGAN);
          }
        }
      }
    }
  });

  it("is never transliterated into Cyrillic (or translated) in the Russian catalogue", () => {
    const cat = CATALOGS.ru as unknown as Record<string, Record<string, string>>;
    for (const ns of Object.keys(cat)) {
      for (const [key, value] of Object.entries(cat[ns])) {
        expect(/аск\s*мор|аск\s*бе\s*мор|спрашивай\s+больше/i.test(value), `ru ${ns}.${key}`).toBe(false);
      }
    }
  });
});

describe("hardcoded-English guard: the slogan is the ONLY approved brand invariant, exact-match only", () => {
  it("the guard's approved set equals the brand constant", () => {
    expect([...APPROVED_BRAND_INVARIANTS]).toEqual([BRAND_SLOGAN]);
  });

  it("an exact slogan literal is reported as an approved invariant, not an offender", () => {
    const r = scanAll(`<p>${BRAND_SLOGAN}</p>`);
    expect(r.hits).toHaveLength(0);
    expect(r.approved).toHaveLength(1);
  });

  it("variants and arbitrary English marketing copy are still offenders", () => {
    for (const bad of [
      "Ask More, Be More",
      "Ask more. Be more.",
      "ASK MORE. BE MORE.",
      "Ask More Be More",
      "Ask More. Be More. Today",
      "Prepare smarter with Ask4Mo today",
    ]) {
      const r = scanAll(`<p>${bad}</p>`);
      expect(r.approved, bad).toHaveLength(0);
      expect(r.hits.length, `"${bad}" must still be flagged`).toBeGreaterThan(0);
    }
  });

  it("applies equally to attribute and object-literal copy (exact slogan only)", () => {
    expect(scanAll(`<img alt="${BRAND_SLOGAN}" />`).approved).toHaveLength(1);
    expect(scanAll(`const x = { title: "${BRAND_SLOGAN}" };`).approved).toHaveLength(1);
    expect(scanAll(`const x = { title: "Ask More, Be More" };`).hits.length).toBeGreaterThan(0);
  });
});
