import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// A plain next/link click can start a soft navigation (RSC fetched, 200) that the App Router never commits under CI load; the History row links
// that open a report must therefore use VerifiedLink (lib/navigation/verified.ts), which detects and recovers a dropped navigation.
describe("report-opening links recover a dropped soft navigation", () => {
  for (const f of ["components/interview/HistoryClient.tsx", "components/progress/PracticeProgress.tsx"]) {
    it(`${f} uses VerifiedLink, not next/link`, () => {
      const src = readFileSync(f, "utf8");
      expect(src).toContain('@/components/ui/VerifiedLink');
      expect(src).not.toContain('from "next/link"');
    });
  }
});
