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

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
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
function stripNoise(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ") // block comments
    .replace(/\/\/[^\n]*/g, " "); // line comments
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

function scanFile(abs) {
  const rel = relative(ROOT, abs);
  const src = stripNoise(readFileSync(abs, "utf8"));
  const hits = [];

  // (a) Visible JSX text nodes: text between > and < that is not an expression and not a tag.
  for (const m of src.matchAll(/>\s*([^<>{}\n][^<>{}]*?)\s*</g)) {
    const text = m[1].trim();
    if (looksEnglish(text)) hits.push({ kind: "jsx-text", text });
  }

  // (b) Candidate-facing attribute literals.
  const attrRe = new RegExp(`\\b(${ATTRS.join("|")})\\s*=\\s*"([^"]+)"`, "g");
  for (const m of src.matchAll(attrRe)) {
    const text = m[2].trim();
    if (looksEnglish(text)) hits.push({ kind: `attr:${m[1]}`, text });
  }
  return hits.map((h) => ({ file: rel, ...h }));
}

const files = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d))).filter((p) => !EXCLUDE_PATH(p));
const all = files.flatMap(scanFile);

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
}
process.exit(all.length > 0 ? 1 : 0);
