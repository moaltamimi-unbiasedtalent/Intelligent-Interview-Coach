#!/usr/bin/env node
// 06F review-pack helper (offline, read-only). Bundles lib/i18n/catalog.ts with esbuild into the OS temp dir, imports the merged
// CATALOGS and prints every string as JSON on stdout: { locale: { "namespace.key": "text", ... } } with keys in sorted order.
// It never writes inside the repository and never calls the network. Same flattening rule as dump-catalog-stats.mjs.
import { build } from "esbuild";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dir = mkdtempSync(path.join(tmpdir(), "a4m-catalog-strings-"));
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
  for (const loc of Object.keys(CATALOGS).sort()) {
    const flat = {};
    const cat = CATALOGS[loc];
    for (const ns of Object.keys(cat).sort()) {
      const body = cat[ns];
      if (body && typeof body === "object") {
        for (const k of Object.keys(body).sort()) if (typeof body[k] === "string") flat[`${ns}.${k}`] = body[k];
      }
    }
    result[loc] = flat;
  }
  process.stdout.write(JSON.stringify(result));
} finally {
  rmSync(dir, { recursive: true, force: true });
}
