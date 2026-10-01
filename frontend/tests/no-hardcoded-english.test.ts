import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// P10B-W9.6 — machine-checkable guard against future candidate-facing hardcoded English.
// Delegates to the bounded scanner (scripts/scan-i18n.mjs), which scans only candidate-facing
// frontend dirs, flags visible JSX text + a small set of candidate-facing attribute literals, and
// honours an explicit reviewed allowlist (reviewer/diagnostic files, proper nouns, symbols). A new
// hardcoded candidate-facing English string fails this test.

const ROOT = join(__dirname, "..");

describe("candidate-facing hardcoded-English guard", () => {
  it("reports zero unexplained candidate-facing English offenders", () => {
    let count = 0;
    let report = "";
    try {
      const out = execFileSync("node", ["scripts/scan-i18n.mjs", "--count"], { cwd: ROOT, encoding: "utf8" });
      count = Number(out.trim());
    } catch (e: unknown) {
      // The scanner exits non-zero when offenders exist; capture its full report for the failure.
      const err = e as { status?: number; stdout?: string };
      count = typeof err.status === "number" ? err.status : -1;
      try {
        report = execFileSync("node", ["scripts/scan-i18n.mjs"], { cwd: ROOT, encoding: "utf8" });
      } catch (e2: unknown) {
        report = (e2 as { stdout?: string }).stdout ?? "";
      }
      // Re-derive the count from the report's total line (the --count path above threw).
      const m = report.match(/TOTAL candidate-facing hardcoded-English offenders:\s*(\d+)/);
      if (m) count = Number(m[1]);
    }
    expect(count, `Hardcoded candidate-facing English found:\n${report}`).toBe(0);
  });
});
