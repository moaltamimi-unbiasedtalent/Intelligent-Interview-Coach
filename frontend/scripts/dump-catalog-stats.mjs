#!/usr/bin/env node
// 06A locale inventory helper (offline, read-only). Bundles lib/i18n/catalog.ts with esbuild into the
// OS temp dir, imports the merged CATALOGS and prints per-locale statistics as JSON on stdout.
// It never writes inside the repository and never calls the network.
import { build } from "esbuild";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dir = mkdtempSync(path.join(tmpdir(), "a4m-catalog-"));
const out = path.join(dir, "catalog.mjs");
try {
  await build({
    entryPoints: [path.join(root, "lib/i18n/catalog.ts")],
    outfile: out,
    bundle: true,
    format: "esm",
    platform: "node",
    logLevel: "silent",
    alias: { "@": root },
  });
  const { CATALOGS } = await import(pathToFileURL(out).href);
  const flat = (cat) => {
    const m = new Map();
    for (const [ns, body] of Object.entries(cat)) {
      if (body && typeof body === "object") for (const [k, v] of Object.entries(body)) if (typeof v === "string") m.set(`${ns}.${k}`, v);
    }
    return m;
  };
  const ph = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((x) => x[1]).sort().join(",");
  const en = flat(CATALOGS.en);
  const legalNs = new Set(["trust", "privacy", "terms", "legal", "aiTransparency", "dataPrivacy"]);
  const result = {};
  for (const [loc, cat] of Object.entries(CATALOGS)) {
    const m = flat(cat);
    const missing = [...en.keys()].filter((k) => !m.has(k));
    const extra = [...m.keys()].filter((k) => !en.has(k));
    const blank = [...m.entries()].filter(([, v]) => v.trim() === "").length;
    const placeholderMismatch = [...m.entries()].filter(([k, v]) => en.has(k) && ph(v) !== ph(en.get(k))).length;
    // Identical-to-English values are possible English leaks (or legitimate brand/tokens); counted, not judged.
    const identicalToEnglish = loc === "en" ? 0 : [...m.entries()].filter(([k, v]) => en.get(k) === v && /[A-Za-z]{4,}/.test(v)).length;
    const legalKeys = [...m.keys()].filter((k) => legalNs.has(k.split(".")[0])).length;
    result[loc] = {
      keys: m.size, namespaces: Object.keys(cat).length, missing_vs_en: missing.length, extra_vs_en: extra.length,
      blank_values: blank, placeholder_mismatches: placeholderMismatch, identical_to_english: identicalToEnglish,
      legal_namespace_keys: legalKeys,
    };
  }
  process.stdout.write(JSON.stringify(result));
} finally {
  rmSync(dir, { recursive: true, force: true });
}
