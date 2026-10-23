#!/usr/bin/env node
// 05E legal review pack helper (offline, read-only). Bundles lib/i18n/catalog.ts with esbuild into the OS temp dir, imports the merged CATALOGS and prints, as JSON on stdout,
// the FLAT key -> text map of every namespace (or every key matching the optional --prefix filters) for every locale. It never writes inside the repository and never calls the
// network. The Python generator (scripts/legal_review_pack.py) decides which keys belong to which document.
import { build } from "esbuild";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dir = mkdtempSync(path.join(tmpdir(), "a4m-legal-"));
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
  const result = {};
  for (const [loc, cat] of Object.entries(CATALOGS)) {
    const flat = {};
    for (const [ns, body] of Object.entries(cat)) {
      if (body && typeof body === "object") {
        for (const [k, v] of Object.entries(body)) if (typeof v === "string") flat[`${ns}.${k}`] = v;
      }
    }
    result[loc] = flat;
  }
  process.stdout.write(JSON.stringify(result));
} finally {
  rmSync(dir, { recursive: true, force: true });
}
