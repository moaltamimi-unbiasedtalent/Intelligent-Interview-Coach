#!/usr/bin/env node
/**
 * P10B-W9.6 — deterministic candidate-facing hardcoded-English scanner.
 *
 * Bounded by design: it scans only candidate-facing frontend dirs, flags (a) visible JSX text
 * literals and (b) a small set of candidate-facing attribute literals (placeholder/aria-label/title/
 * label/description/alt), and ignores code tokens (className/href/id/enum/URLs/ISO codes/symbols).
 * Legitimate exceptions live in an explicit allowlist with reasons. This is the audit AND the guard.
 *
 * Usage: node scripts/scan-i18n.mjs            (prints offenders, exit 1 if any)
 *        node scripts/scan-i18n.mjs --count    (prints just the count)
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

// Resolved lazily in the CLI path only — importing this module (e.g. from a test) must not depend on
// `import.meta.url` being a file URL.
const SCAN_DIRS = ["components", "app"];

// Reviewer/admin surfaces are intentionally English-ops (not candidate-facing) per the i18n standard.
// File-level exceptions (reviewer/diagnostic components that live outside /review but are only rendered
// on the admin-gated Review surface). Reasons are explicit, not mysterious strings.
const ALLOW_FILES = {
  "components/agent/AgentInspector.tsx": "reviewer/diagnostic — rendered only on the platform-admin Review surface (W9.3); English-ops per the i18n standard",
};
const EXCLUDE_PATH = (p) =>
  /\/(review|admin)\//.test(p) ||
  /\/components\/i18n\//.test(p) ||
  p.endsWith(".test.tsx") || p.endsWith(".test.ts") ||
  Object.keys(ALLOW_FILES).some((f) => p.endsWith(f));

const ATTRS = ["placeholder", "aria-label", "title", "label", "description", "alt"];

// Candidate-facing CONTENT keys in object/array literals (not JSX): FAQ/help datasets, card/
// empty-state/nav content maps, comparison tables, tutorial-like definitions. These render to
// candidates as copy, so a string literal assigned to one of them must be localized. This is the
// category that escaped the original (JSX-only) scan — e.g. `{ q: "...", a: "..." }` in HelpCenter.
// Deliberately bounded: it does NOT include structural/technical keys (id, key, href, name, type,
// value, className, testId, slug, icon, variant, role, path, url, code, ...), so class names, routes,
// enum tokens, test IDs and import paths are not flagged.
const CONTENT_KEYS = [
  "title", "subtitle", "heading", "description", "label", "hint", "helper", "placeholder",
  "question", "answer", "q", "a", "body", "message", "summary", "intro", "note", "cta",
  "tooltip", "caption", "empty", "emptyText", "text",
];

// Protected brand invariants (P10B-W9.7): EXACT-match only, reported separately as "approved brand
// invariants" and never counted as offenders. This is deliberately NOT a general English-marketing
// exception: a partial match, different punctuation/case ("Ask more. Be more.", "Ask More, Be More") or
// any other English copy is still flagged. Keep in sync with `BRAND_SLOGAN` in lib/brand.ts
// (tests/brand-slogan-invariant.test.ts asserts equality).
const APPROVED_BRAND_INVARIANTS = new Set(["Ask More. Be More."]);

// Proper nouns / technical tokens that are never translated (substring or exact, case-sensitive).
const ALLOW_SUBSTR = [
  "Ask4Mo", "Mo", "O*NET", "ONET", "ESCO", "ISCO", "SOC", "NOC", "KldB", "RAGAS", "OpenAI",
  "OpenRouter", "LangGraph", "GDPR", "OCR", "CV", "JD", "URL", "ID", "AI",
];
// Exact strings that are acceptable as-is (reasons in the test's allowlist, not here).
const ALLOW_EXACT = new Set([
  "·", "…", "/", "-", "—", "+", "✕", "▾", "📌", "→", "←", "%", "EUR", "USD",
]);

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (p.endsWith(".tsx")) out.push(p);
  }
  return out;
}

// Strip JSX expression containers {…}, comments, and string-literal attribute VALUES we don't scan,
// so that `className="flex ..."` etc. are not treated as visible text.
//
// Also strip Next.js page `metadata` / `generateMetadata` blocks: localizing server-component
// `export const metadata` titles needs a locale-aware `generateMetadata` path and is a documented,
// architecture-bound deferral (P10B-W9.6 §5 / W9.6A §L). They are not rendered candidate chrome, so
// the content-key pass below must not flag their `title:`/`description:` object properties.
function stripNoise(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ") // block comments
    .replace(/\/\/[^\n]*/g, " ") // line comments
    .replace(/export\s+const\s+metadata\b[\s\S]*?\};/g, " ") // export const metadata = {...}; (single- or multi-line)
    .replace(/export\s+async\s+function\s+generateMetadata\b[\s\S]*?\n\}/g, " ") // generateMetadata(){...}
    // schema.org JSON-LD structured data (rendered into <script type="application/ld+json">): this is
    // machine-readable crawler metadata, not candidate-rendered chrome — same deferred category as page
    // metadata. Strip any object literal carrying an "@context" marker.
    .replace(/const\s+\w+\s*=\s*\{[\s\S]*?"@context"[\s\S]*?\n\s*\};/g, " ");
}

function looksEnglish(text) {
  const t = text.trim();
  if (t.length < 2) return false;
  if (ALLOW_EXACT.has(t)) return false;
  if (!/[A-Za-z]/.test(t)) return false; // no letters -> not copy
  // Reject anything bearing code syntax — this removes TS generics (useState<T>(...)), arrow fns,
  // object/JSX fragments and string-literal noise that a byte-level scan can otherwise catch.
  if (/[;={}<>\\`|"]/.test(t)) return false;
  if (t.includes("=>")) return false;
  // Reject inline-ternary / expression fragments that the byte-level JSX-text scan captures between a
  // self-closing tag and the next tag, e.g. `) : error ? (`, `r.url ? (`, `0) out.push(`, `) : step`.
  // None of these shapes can be candidate-facing copy: a close-paren adjacent to a colon (ternary
  // else), a question-mark adjacent to an open-paren (ternary then JSX), a method call `.name(`, or
  // text that begins with `)` / ends with `(` (an expression boundary, never a sentence).
  if (/\)\s*:/.test(t) || /\?\s*\(/.test(t) || /\.\w+\s*\(/.test(t)) return false;
  if (/^\)/.test(t) || /\($/.test(t)) return false;
  if (/\b(const|let|return|null|undefined|useState|useRef|useCallback|function|import|export)\b/.test(t)) return false;
  // Single bare TS type/identifier tokens that slip through as pseudo "text".
  const TYPE_WORDS = new Set(["Promise", "Void", "ReactNode", "AbortSignal", "HTMLElement", "Record", "Partial", "Readonly", "Array", "Map", "Set", "Props", "Ref"]);
  if (!/\s/.test(t) && TYPE_WORDS.has(t)) return false;
  // Must contain a lowercase word of >=2 letters OR a space-separated phrase (real sentences/labels).
  const hasWord = /[A-Za-z][a-z]{1,}/.test(t);
  const hasSpace = /\s/.test(t);
  if (!hasWord && !hasSpace) return false;
  // Skip identifiers / code-ish single tokens (no space, camelCase/snake/kebab, or dotted).
  if (!hasSpace && /^[A-Za-z0-9_.\-/:$]+$/.test(t) && !/^[A-Z][a-z]+$/.test(t)) return false;
  // Skip if the whole string is a single allowlisted proper-noun token.
  if (ALLOW_SUBSTR.some((a) => t === a)) return false;
  return true;
}

/**
 * Pure detection over a SOURCE STRING (exported so a regression test can prove the blind spots are
 * closed without touching the filesystem). Returns [{ kind, text }]. `stripNoise` is applied here.
 */
export function scanAll(rawSrc) {
  const src = stripNoise(rawSrc);
  const hits = [];
  const approved = [];
  const record = (kind, text) => {
    if (APPROVED_BRAND_INVARIANTS.has(text)) approved.push({ kind, text });
    else if (looksEnglish(text)) hits.push({ kind, text });
  };

  // (a) Visible JSX text nodes: text between > and < that is not an expression and not a tag.
  for (const m of src.matchAll(/>\s*([^<>{}\n][^<>{}]*?)\s*</g)) {
    record("jsx-text", m[1].trim());
  }

  // (b) Candidate-facing attribute literals.
  const attrRe = new RegExp(`\\b(${ATTRS.join("|")})\\s*=\\s*"([^"]+)"`, "g");
  for (const m of src.matchAll(attrRe)) {
    record(`attr:${m[1]}`, m[2].trim());
  }

  // (c) Candidate-facing CONTENT in object/array literals: `key: "English"` where key is a known
  // content key (title/q/a/body/...). This catches copy stored OUTSIDE JSX (FAQ/help datasets,
  // content maps, card/empty-state config) that passes (a)/(b) by. Both quote styles; the value
  // must still read as English prose (looksEnglish filters identifiers/keys/code tokens, so a value
  // like "help.gs1q" or "getting-started" is not flagged).
  const keyRe = new RegExp(`(?:^|[\\s,{[(])(${CONTENT_KEYS.join("|")})\\s*:\\s*("(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*')`, "g");
  for (const m of src.matchAll(keyRe)) {
    record(`obj:${m[1]}`, m[2].slice(1, -1).trim()); // strip surrounding quotes
  }
  return { hits, approved };
}

/** Offender hits only (the original API; approved brand invariants are excluded). */
export function scanSource(rawSrc) {
  return scanAll(rawSrc).hits;
}

export { looksEnglish, stripNoise, APPROVED_BRAND_INVARIANTS };

// CLI entrypoint only (guarded so importing this module for tests has no side effects / no exit).
const isCli = process.argv[1] && process.argv[1].replace(/\\/g, "/").endsWith("scripts/scan-i18n.mjs");
if (isCli) {
  const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
  const files = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d))).filter((p) => !EXCLUDE_PATH(p));
  const all = [];
  const approvedAll = [];
  for (const abs of files) {
    const { hits, approved } = scanAll(readFileSync(abs, "utf8"));
    for (const h of hits) all.push({ file: relative(ROOT, abs), ...h });
    for (const h of approved) approvedAll.push({ file: relative(ROOT, abs), ...h });
  }

  if (process.argv.includes("--count")) {
    console.log(all.length);
  } else {
    const byFile = new Map();
    for (const h of all) {
      if (!byFile.has(h.file)) byFile.set(h.file, []);
      byFile.get(h.file).push(h);
    }
    for (const [file, hits] of [...byFile.entries()].sort()) {
      console.log(`\n${file}  (${hits.length})`);
      for (const h of hits) console.log(`  [${h.kind}] ${JSON.stringify(h.text)}`);
    }
    console.log(`\nTOTAL candidate-facing hardcoded-English offenders: ${all.length} in ${byFile.size} files`);
    // Approved brand invariants (exact-match only) are reported separately and never fail the guard.
    console.log(`Approved brand invariants (exact "Ask More. Be More." literals in scanned source): ${approvedAll.length}`);
    for (const h of approvedAll) console.log(`  [${h.kind}] ${h.file}`);
  }
  process.exit(all.length > 0 ? 1 : 0);
}
