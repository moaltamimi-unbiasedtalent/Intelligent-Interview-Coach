import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import postcss from "postcss";
import tailwind from "tailwindcss";
import { describe, expect, it } from "vitest";

import config from "../tailwind.config";

/**
 * TD-W9-01 guard. Colour tokens are CSS variables, which Tailwind cannot parse, so an alpha modifier such as
 * `border-warning/50` used to be silently dropped (no CSS emitted). The token() helper in tailwind.config.ts now
 * makes those utilities valid. This test finds EVERY `<utility>-<token>/<alpha>` in the source and proves Tailwind
 * actually emits CSS for it, so the defect cannot return unnoticed.
 */

const TOKENS = "background|foreground|surface-2|surface|muted|border|accent-foreground|accent|secondary|success|warning|danger";
const UTIL = "bg|text|border|border-[lrtbxy]|ring|outline|from|to|via|divide|placeholder|shadow|fill|stroke|decoration|caret|accent";
const RE = new RegExp(`(?:^|[\\s"'\`:])((?:[a-z-]+:)*(?:${UTIL})-(?:${TOKENS})/(?:\\d{1,3}|\\[[^\\]]+\\]))(?=$|[\\s"'\`])`, "g");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}

const root = join(__dirname, "..");
const classes = new Set<string>();
for (const dir of ["app", "components", "lib"]) {
  for (const file of walk(join(root, dir))) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(RE)) classes.add(m[1]);
  }
}

describe("custom-token opacity utilities emit CSS (TD-W9-01)", () => {
  it("the source uses at least the known alpha utilities (the scan is not vacuous)", () => {
    expect(classes.size).toBeGreaterThanOrEqual(10);
    expect([...classes].some((c) => c.includes("border-warning/50"))).toBe(true);
  });

  it("every alpha-modified token utility found in the source generates a CSS rule", async () => {
    const list = [...classes];
    const result = await postcss([
      tailwind({ ...config, content: [{ raw: list.join(" "), extension: "html" }] } as never),
    ]).process("@tailwind utilities;", { from: undefined });
    const css = result.css;
    const missing = list.filter((c) => {
      const base = c.split(":").pop() as string;
      const escaped = base.replace(/\//g, "\\/");
      return !css.includes(`.${escaped}`) && !css.includes(`.${c.replace(/[:/]/g, (x) => "\\" + x)}`);
    });
    expect(missing, `dead opacity-token utilities (no CSS emitted): ${missing.join(", ")}`).toEqual([]);
  });

  it("unmodified token utilities are unchanged (plain var())", async () => {
    const result = await postcss([
      tailwind({ ...config, content: [{ raw: "bg-surface text-muted border-border", extension: "html" }] } as never),
    ]).process("@tailwind utilities;", { from: undefined });
    expect(result.css).toContain("background-color: var(--surface)");
    expect(result.css).toContain("color: var(--muted)");
    expect(result.css).toContain("border-color: var(--border)");
  });

  it("alpha modifiers mix the same CSS variable with transparency (one colour system)", async () => {
    const result = await postcss([
      tailwind({ ...config, content: [{ raw: "bg-warning/10", extension: "html" }] } as never),
    ]).process("@tailwind utilities;", { from: undefined });
    expect(result.css).toContain("color-mix(in srgb, var(--warning)");
  });
});
