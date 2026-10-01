import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM script, no type declarations (it is a build/guard tool, not app code).
import { scanSource } from "../scripts/scan-i18n.mjs";

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
