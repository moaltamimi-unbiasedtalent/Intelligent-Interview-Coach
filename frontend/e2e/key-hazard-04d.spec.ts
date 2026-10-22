import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { configuredKeyValue } from "./journey/canary";

/**
 * 04D provider-key hazard guard (IR-DEMO-KEY, SEC): the browser must never receive key material.
 *
 * The web server of this suite is built and started with a provider key in its environment (a canary, or the real value if one is exported; see playwright.config.ts). This spec then proves that
 * the configured key VALUE and any key-SHAPED string are absent from (1) every file of the built output (client chunks, server-rendered pages, static assets) and (2) every page and script the running
 * server serves. It also fails if client code ever names a server-side secret variable. The API side of the same guard (every parameterless GET route, as candidate, administrator and anonymous caller,
 * plus the failure paths) is tests/test_provider_failures_04d.py. Nothing here prints a key value.
 */

const KEY = configuredKeyValue();
const KEYSHAPES: Array<[string, RegExp]> = [
  ["OpenRouter-style key", /sk-or-v1-[0-9a-f]{20,}/],
  ["secret-key-style token", /sk-[A-Za-z0-9_-]{24,}/],
  ["Google API key", /AIza[0-9A-Za-z_-]{30,}/],
  ["bearer token literal", /Bearer\s+[A-Za-z0-9._-]{24,}/],
  ["private key block", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
];
// Server-side secret variable NAMES must never appear in a client artefact (a hint of where a key lives is itself a hazard).
const SERVER_SECRET_NAMES = ["OPENROUTER_API_KEY", "COPILOT_EMBEDDING_API_KEY", "SECRET_STORE_MASTER_KEY", "REALTIME_VOICE_API_KEY", "LANGFUSE_SECRET_KEY", "GEMINI_API_KEY", "BREVO_API_KEY"];

function* walk(dir: string): Generator<string> {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (name === "cache" || name === "node_modules") continue;      // the build cache holds compiler inputs, not shipped output
      yield* walk(full);
    } else if (st.size < 8_000_000) {
      yield full;
    }
  }
}

function findings(label: string, text: string): string[] {
  const out: string[] = [];
  if (text.includes(KEY)) out.push(`${label}: the configured key value`);
  for (const [name, re] of KEYSHAPES) if (re.test(text)) out.push(`${label}: ${name}`);
  return out;
}

test("the built output contains no key material and names no server-side secret in client code", async () => {
  const roots = [".next", ".next-journey"].filter((d) => existsSync(join(d, "static")));
  // Against a hosted stack the build is not on this machine: the served-page scan below is then the evidence, and this test says so instead of failing.
  test.skip(roots.length === 0 && process.env.JOURNEY_MODE === "real", "no local build output; the served pages and scripts are scanned instead");
  expect(roots.length, "a production build must exist (the suite builds it before serving)").toBeGreaterThan(0);
  const problems: string[] = [];
  let scanned = 0;
  for (const root of roots) {
    for (const file of walk(root)) {
      if (/\.(png|jpe?g|webp|gif|ico|woff2?|ttf|mp4|webm|map)$/i.test(file)) continue;
      let text = "";
      try { text = readFileSync(file, "utf8"); } catch { continue; }
      scanned += 1;
      problems.push(...findings(file, text));
      // Client artefacts only: static chunks and the client reference manifests. Server bundles may legitimately READ process.env names; they must not CONTAIN a value (checked above).
      if (file.includes(join(root, "static"))) for (const name of SERVER_SECRET_NAMES) if (text.includes(name)) problems.push(`${file}: names ${name} in client code`);
    }
  }
  expect(scanned, "the scan must cover real build output").toBeGreaterThan(20);
  expect(problems).toEqual([]);
});

test("pages and scripts served by the running app contain no key material", async ({ request, baseURL }) => {
  const pages = ["/", "/pricing", "/register", "/sign-in", "/trust", "/ai-transparency", "/help", "/product", "/prepare", "/practice"];
  const scripts = new Set<string>();
  const problems: string[] = [];
  for (const path of pages) {
    const res = await request.get(`${baseURL}${path}`, { maxRedirects: 5 });
    const html = await res.text();
    problems.push(...findings(`GET ${path}`, html));
    for (const m of html.matchAll(/\/_next\/static\/[^"'\s)]+\.js/g)) scripts.add(m[0]);
    // Response headers are a channel too.
    problems.push(...findings(`GET ${path} headers`, JSON.stringify(res.headers())));
  }
  expect(scripts.size, "the served pages must reference client scripts").toBeGreaterThan(3);
  for (const src of [...scripts].slice(0, 80)) {
    const res = await request.get(`${baseURL}${src}`);
    problems.push(...findings(`GET ${src}`, await res.text()));
  }
  expect(problems).toEqual([]);
});

test("the guard itself detects a leak (a planted value and a planted key-shaped string are found)", () => {
  expect(findings("probe", `x ${KEY} y`)).toContain("probe: the configured key value");
  expect(findings("probe", "token sk-or-v1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa here").length).toBeGreaterThan(0);
  expect(findings("probe", "an ordinary sentence about keys and interviews")).toEqual([]);
});
