import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// App-shell navigation must go through VerifiedLink (soft-navigation loss recovery). Focused guard, not a
// repository-wide scanner: it only names the shell surfaces covered by the W10.1 reliability correction.
const SHELL = [
  "components/ui/Logo.tsx",
  "components/layout/PrimaryNavigation.tsx",
  "components/layout/MobileNavigation.tsx",
  "components/layout/MoreMenu.tsx",
  "components/auth/AccountMenu.tsx",
  "components/admin/AdminShell.tsx",
  "components/admin/CommandCenter.tsx",
  "components/admin/UsersView.tsx",
  "components/admin/UserDetailView.tsx",
  "components/admin/WorkspacesView.tsx",
  "components/admin/WorkspaceDetailView.tsx",
  "components/admin/SupportQueueView.tsx",
  "components/admin/PlansView.tsx",
  "components/admin/IntegrationsView.tsx",
  "components/admin/IntegrationDetailView.tsx",
  "components/admin/PlanDetailView.tsx",
  "components/admin/SupportTicketAdminView.tsx",
  "components/support/SupportHome.tsx",
  "components/support/SupportTicketView.tsx",
  "components/help/HelpPageContent.tsx",
  "app/review/page.tsx",
];

describe("navigation reliability invariant", () => {
  it.each(SHELL)("%s uses VerifiedLink, not raw next/link", (file) => {
    const src = readFileSync(file, "utf8");
    expect(src).toContain('from "@/components/ui/VerifiedLink"');
    expect(src).not.toContain('from "next/link"');
  });

  it("VerifiedLink verifies plain clicks only and never replaces history", () => {
    const src = readFileSync("components/ui/VerifiedLink.tsx", "utf8");
    expect(src).toContain("verifyNavigation");
    expect(src).not.toContain("router.replace");
    const util = readFileSync("lib/navigation/verified.ts", "utf8");
    expect(util).toContain("router.push");
    expect(util).not.toMatch(/router\.replace/);
  });
});
