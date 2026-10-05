import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ADMIN_DESTINATIONS, visibleDestinations } from "@/lib/admin/capabilities";
import fixture from "./fixtures/admin-role-permissions.json";

// P10B-W10.14 Admin navigation qualification. The fixture is GENERATED from the backend registry and role presets (tests/_admin_matrix.py); the frontend knows no role names. This proves the
// REAL visibleDestinations() equals the backend-derived expectation for every persona, and that candidates / unknown roles see no Admin navigation. Navigation is UX only: every API is
// authorised again by the server (proved by tests/test_admin_qualification_w10_14.py over real HTTP).

const personas = Object.entries(fixture.personas) as [string, { permissions: string[]; nav: string[] }][];

describe("Admin navigation matrix (permission-derived)", () => {
  it.each(personas)("%s sees exactly the backend-derived destinations", (_name, p) => {
    expect(visibleDestinations(p.permissions).map((d) => d.href)).toEqual(p.nav);
  });

  it("the candidate, an unknown role and an empty permission set see no Admin navigation", () => {
    expect(visibleDestinations(fixture.personas.user.permissions)).toEqual([]);
    expect(visibleDestinations([])).toEqual([]);
    expect(fixture.unknown_role_nav).toEqual([]);
  });

  it("every Admin role holds Overview and no persona is shown a destination it lacks the permission for", () => {
    for (const [name, p] of personas) {
      if (name === "user") continue;
      expect(p.nav).toContain("/admin");
      for (const d of ADMIN_DESTINATIONS) {
        const shown = p.nav.includes(d.href);
        expect(shown).toBe(d.anyOf.some((perm) => p.permissions.includes(perm)));
      }
    }
  });

  it("platform_admin is broad but not universal: it is not shown Billing or Jobs", () => {
    const nav = fixture.personas.platform_admin.nav;
    expect(nav).not.toContain("/admin/billing");
    expect(nav).not.toContain("/admin/jobs");
    expect(fixture.personas.platform_admin.permissions.length).toBe(28);
    expect(fixture.permissions_total).toBe(43);
  });

  it("the destination table references only permissions that exist and uses no role name", () => {
    const src = readFileSync(join(__dirname, "../lib/admin/capabilities.ts"), "utf8");
    expect(src).not.toMatch(/platform_admin|support_operator|billing_admin|knowledge_admin|security_privacy_admin|operations_admin/);
    const all = new Set(personas.flatMap(([, p]) => p.permissions));
    for (const d of ADMIN_DESTINATIONS) for (const perm of d.anyOf) expect(typeof perm).toBe("string");
    expect(all.size).toBeGreaterThan(20);
  });

  it("every /admin page directory has a page, an h1 header and no raw role-name check", () => {
    const base = join(__dirname, "../app/admin");
    const walk = (dir: string): string[] => readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? walk(join(dir, f)) : f === "page.tsx" ? [join(dir, f)] : []));
    const pages = walk(base);
    expect(pages.length).toBeGreaterThanOrEqual(25);
    for (const p of pages) {
      const text = readFileSync(p, "utf8");
      expect(text).toMatch(/PageHeader|<h1/);
      expect(text).not.toMatch(/platform_role\s*===|role\s*===\s*"/);
    }
  });
});
