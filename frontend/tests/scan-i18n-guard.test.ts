import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM script, no type declarations (it is a build/guard tool, not app code).
import { scanSource, scanAll } from "../scripts/scan-i18n.mjs";

/**
 * P10B-W9.6A — guard regression tests.
 *
 * The original W9.6 scanner inspected only JSX text and JSX attribute literals, so candidate-facing
 * copy stored in object/array literals (the Help Center `SECTIONS` array of `{ q, a }`, content maps,
 * card/empty-state config) escaped detection. These tests prove the blind spot is now closed AND that
 * the detector is still bounded (it does not flag class names, routes, ids, enums, i18n key refs, or
 * machine-readable metadata/JSON-LD).
 *
 * `scanSource` is the scanner's pure detector; these fixtures are strings, never shipped product code.
 */

const kinds = (src: string) => scanSource(src).map((h: { kind: string; text: string }) => h.kind);
const texts = (src: string) => scanSource(src).map((h: { kind: string; text: string }) => h.text);

describe("scan-i18n guard — object-literal candidate content (the W9.6 blind spot)", () => {
  it("detects a Help-style { q, a } FAQ object outside the catalogue (the exact escaped pattern)", () => {
    const fixture = `
      const SECTIONS = [
        { q: "What gets stored", a: "Your completed interview sessions and their reports, private to you." },
      ];
    `;
    const k = kinds(fixture);
    expect(k).toContain("obj:q");
    expect(k).toContain("obj:a");
    expect(texts(fixture)).toContain("What gets stored");
  });

  it("detects English in title/body/description/label/message object properties", () => {
    const fixture = `
      const cards = [
        { title: "Getting started", body: "An AI interview coach that helps you prepare." },
        { description: "Track your practice progress over time.", label: "Open settings" },
        { message: "Something went wrong while loading." },
      ];
    `;
    const k = kinds(fixture);
    expect(k).toContain("obj:title");
    expect(k).toContain("obj:body");
    expect(k).toContain("obj:description");
    expect(k).toContain("obj:label");
    expect(k).toContain("obj:message");
  });

  it("still detects visible JSX text and candidate attribute literals", () => {
    expect(kinds(`<p>Welcome to your workspace</p>`)).toContain("jsx-text");
    expect(kinds(`<img alt="A hand moving a card between workspaces" />`)).toContain("attr:alt");
  });
});

describe("scan-i18n guard — must NOT flag (bounded, no indiscriminate string scanning)", () => {
  it("ignores i18n key references used as object-content values", () => {
    const fixture = `
      const HELP_SECTIONS = [
        { id: "getting-started", titleKey: "help.gsTitle", articles: [ { q: "help.gs1q", a: "help.gs1a" } ] },
      ];
    `;
    expect(scanSource(fixture)).toHaveLength(0);
  });

  it("ignores structural/technical keys and tokens (id, code, href, className, type, value)", () => {
    const fixture = `
      const items = [{ id: "getting-started", code: "en-US", type: "application/ld+json", value: "active" }];
      const a = <div className="flex gap-2 rounded-lg" data-testid="help-root" href="/app/help" />;
      const slug = "reset-password";
    `;
    expect(scanSource(fixture)).toHaveLength(0);
  });

  it("ignores page metadata and schema.org JSON-LD (machine-readable, not candidate chrome)", () => {
    const fixture = `
      export const metadata: Metadata = { title: "Sign in", description: "Sign in to Ask4Mo to continue." };
      const ORG_JSONLD = {
        "@context": "https://schema.org",
        "@type": "Organization",
        description: "Ask4Mo is an interview-preparation workspace for one job.",
      };
    `;
    expect(scanSource(fixture)).toHaveLength(0);
  });

  it("ignores inline-ternary / expression fragments the JSX-text pass captures", () => {
    expect(scanSource(`{cond ? (<A/>) : error ? (<B/>) : (<C/>)}`)).toHaveLength(0);
  });
});

// ─── P10B-W9.7A: the three structural blind spots found by visual QA ───────────────────────────────
describe("scan-i18n guard - W9.7A structural blind spots (string-tuple arrays, HTML entities, mixed text)", () => {
  it("detects the Home feature-block pattern: an array of string tuples rendered via .map", () => {
    const fixture = `
      {[
        ["Prepare with evidence", "Grounded career information and citations when needed."],
        ["Stay in control", "Memory and important handoffs require clear approval."],
      ].map(([title, body]) => (<div key={title}><p>{title}</p><p>{body}</p></div>))}
    `;
    const hits = scanSource(fixture).filter((h: { kind: string }) => h.kind === "array-literal");
    expect(hits.map((h: { text: string }) => h.text)).toEqual(expect.arrayContaining([
      "Prepare with evidence", "Grounded career information and citations when needed.", "Stay in control",
    ]));
  });

  it("detects copy hidden behind an HTML entity (&rsquo; used to trip the ';' code filter)", () => {
    const fixture = `<p className="x">I don&rsquo;t have enough reliable evidence to answer that confidently.</p>`;
    expect(kinds(fixture)).toContain("jsx-text");
  });

  it("detects JSX text MIXED with expressions (text before / after a {value})", () => {
    expect(kinds(`<summary>Career evidence: {n} source{n === 1 ? "" : "s"}</summary>`)).toContain("jsx-text-mixed");
    expect(kinds(`<p>Question {current} of {total}</p>`)).toContain("jsx-text-mixed");
    expect(kinds(`<p>Last updated: {date} · Draft</p>`)).toContain("jsx-text-mixed");
  });

  it("does NOT flag identifier/route/enum arrays, single-word lists, key refs or TS declarations", () => {
    for (const ok of [
      `const A = ["coach", "prep", "practice"];`,
      `const R = ["/app", "/help", "/settings"];`,
      `const S = ["en-US", "de-DE"] as const;`,
      `const K = ["feat1", "feat2", "feat3"] as const;`,
      `interface Section { id: string }`,
      `<p>{t("home.feat1Title")}</p>`,
      `<p>{count} {t("x.y")}</p>`,
      `const cls = cn("flex gap-2", { "a b": true });`,
    ]) {
      expect(scanSource(ok), ok).toHaveLength(0);
    }
  });

  it("the exact protected slogan inside a rendered array is an approved invariant, a variant is not", () => {
    expect(scanAll(`const x = ["Ask More. Be More.", "Title here"];`).approved).toHaveLength(1);
    expect(scanSource(`const x = ["Ask More, Be More", "Title here"];`).length).toBeGreaterThan(0);
  });
});
