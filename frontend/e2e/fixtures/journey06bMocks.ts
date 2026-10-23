import { expect, type Page, type Route } from "@playwright/test";

import { CAPS, account, jsonRoute, quietTutorial } from "./journey06b";

/**
 * 06B mocked-network "servers" for the Story Bank and Workspaces journeys, plus the accessible-name check. Stateful fakes that
 * ENFORCE the rules the real API enforces (consent required, membership is the visibility boundary, revocation is immediate).
 * The authoritative authorization proof stays in the real-backend tests (tests/test_story_bank_04a*.py, tests/test_workspaces_04b.py,
 * tests/test_language_journeys_06b.py). No backend, no provider call.
 */

export async function expectAccessibleNames(page: Page, locale: string, where: string) {
  // Every visible interactive control has a non-empty accessible name (aria-label, aria-labelledby, label, text, alt, title, value).
  const unnamed = await page.evaluate(() => {
    const visible = (el: Element) => {
      const r = (el as HTMLElement).getBoundingClientRect();
      const cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none";
    };
    const nameOf = (el: Element): string => {
      const h = el as HTMLElement & { labels?: NodeListOf<HTMLLabelElement>; value?: string };
      const aria = el.getAttribute("aria-label");
      if (aria?.trim()) return aria.trim();
      const by = el.getAttribute("aria-labelledby");
      if (by) {
        const t = by.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ").trim();
        if (t) return t;
      }
      if (h.labels && h.labels.length) {
        const t = Array.from(h.labels).map((l) => l.textContent ?? "").join(" ").trim();
        if (t) return t;
      }
      const alt = el.querySelector("img[alt]")?.getAttribute("alt");
      const text = ((h.innerText ?? "") || (h.textContent ?? "")).trim();
      return text || (alt ?? "").trim() || (el.getAttribute("title") ?? "").trim()
        || (h.tagName === "INPUT" && ["submit", "button"].includes((el as HTMLInputElement).type) ? (h.value ?? "").trim() : "");
    };
    return Array.from(document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link]"))
      .filter(visible)
      .filter((el) => !nameOf(el))
      .map((el) => el.outerHTML.replace(/class="[^"]*"/, "").slice(0, 260));
  });
  expect(unnamed, `${locale} ${where}: controls without an accessible name`).toEqual([]);
}

// ----- Story Bank -----

export const SB_CLAIMS = [
  { id: 11, document_id: 1, version_id: 1, claim_type: "achievement", text: "Reduced latency", edited_text: null, display_text: "Reduced latency", source_page: null, source_section: "block 2", review_state: "accepted" },
  { id: 12, document_id: 1, version_id: 1, claim_type: "skill", text: "Rejected skill", edited_text: null, display_text: "Rejected skill", source_page: null, source_section: "block 3", review_state: "rejected" },
];

type Story = {
  id: number; title: string; situation: string | null; task: string | null; action: string | null; result: string | null; competencies: string[];
  status: string; opportunity_id: number | null; archived_at: string | null; confirmed_at: string | null; claims: number[]; uses: number;
};

function presentStory(s: Story) {
  const live = s.claims.length > 0;
  const prompts: string[] = [];
  if (!s.action) prompts.push("action_missing");
  if (!s.result) prompts.push("result_missing");
  return {
    id: s.id, title: s.title, situation: s.situation, task: s.task, action: s.action, result: s.result, competencies: s.competencies, status: s.status,
    evidence_state: live ? "verified" : "none", verification: live ? "evidence_verified" : s.confirmed_at ? "self_confirmed" : "unverified",
    evidence_claim_ids: s.claims, evidence_answer_ids: [], opportunity_id: s.opportunity_id, archived_at: s.archived_at, confirmed_at: s.confirmed_at,
    use_count: s.uses, last_used_at: null, quality_prompts: prompts, updated_at: "2026-10-22T00:00:00Z",
  };
}

export const SB_QUESTION = "Q1-ENTSCHEIDUNG-TEST";

export async function installStoryBankMock(page: Page, ui: string, opts: { failList?: boolean } = {}) {
  await quietTutorial(page);
  const db = {
    next: 1, stories: [] as Story[], grants: [] as { id: number; workspace_id: number; resource_id: string }[],
    practiceBody: null as null | Record<string, unknown>, allow: false, shareBodies: [] as Record<string, unknown>[],
  };
  const session = {
    session_id: "sess_story", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
    current_question: { question_id: 1, question: SB_QUESTION, question_type: "behavioural", competency: "judgement", difficulty: "moderate" },
    report_available: false, last_evaluation: null, target_role: "Registered Nurse", deep_dive: null, error: null, error_recoverable: false, cumulative_cost_usd: 0,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^.*\/api\/v1/, "");
    const method = route.request().method();
    const body = () => { try { return route.request().postDataJSON() ?? {}; } catch { return {}; } };
    const json = (b: unknown, status = 200) => jsonRoute(route, b, status);
    const find = (id: string) => db.stories.find((x) => x.id === Number(id));
    if (path === "/auth/me") return json(account(ui, ui));
    if (path === "/capabilities") return json({ ...CAPS, active_candidate_locales: ["en", "de", "fr", "es", "it", "pt", "nl"], default_locale: "en" });
    if (path === "/documents" && method === "GET") return json({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1, updated_at: null }] });
    if (path === "/documents/1" && method === "GET") return json({ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1, versions: [], claims: SB_CLAIMS });
    if (path === "/opportunities" && method === "GET") return json({ opportunities: [{ id: 3, title: "Pflegefachkraft bei Acme", target_role: "Nurse", status: "active" }] });
    if (path === "/workspaces" && method === "GET") return json({ workspaces: [{ id: 4, name: "Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
    if (path === "/shares/mine") {
      return json({ shares: db.grants.map((g) => ({ id: g.id, owner_user_id: 1, workspace_id: g.workspace_id, resource_type: "story", resource_id: g.resource_id, permission: "view", status: "active", created_at: null, revoked_at: null })) });
    }
    if (path === "/shares" && method === "POST") {
      const b = body();
      db.shareBodies.push(b);
      if (b.consent !== true) return json({ error: { code: "validation_error", message: "consent required" } }, 422);
      db.grants.push({ id: 40, workspace_id: Number(b.workspace_id), resource_id: String(b.resource_id) });
      return json({ share_id: 40, status: "active", permission: "view" });
    }
    if (path.match(/^\/shares\/\d+$/) && method === "DELETE") { db.grants = []; return json({ status: "revoked" }); }
    if (path === "/stories" && method === "GET") {
      if (opts.failList && !db.allow) return json({ error: { code: "internal", message: "x" } }, 500);
      return json({ stories: db.stories.filter((s) => !s.archived_at).map(presentStory) });
    }
    if (path === "/stories/tags") return json({ tags: [...new Set(db.stories.flatMap((s) => s.competencies))].sort() });
    if (path === "/stories/search") return json({ stories: db.stories.filter((s) => !s.archived_at).map(presentStory) });
    if (path === "/stories" && method === "POST") {
      const b = body() as Partial<Story>;
      const s: Story = {
        id: db.next++, title: String(b.title), situation: b.situation || null, task: b.task || null, action: b.action || null, result: b.result || null,
        competencies: (b.competencies as string[]) ?? [], status: "user_created", opportunity_id: (b.opportunity_id as number) ?? null,
        archived_at: null, confirmed_at: null, claims: [], uses: 0,
      };
      db.stories.push(s);
      return json(presentStory(s), 201);
    }
    const one = path.match(/^\/stories\/(\d+)(\/[a-z]+(?:\/[a-z]+\/\d+)?)?$/);
    if (one) {
      const s = find(one[1]);
      if (!s) return json({ error: { code: "not_found", message: "Story not found." } }, 404);
      const sub = one[2] ?? "";
      if (sub === "" && method === "GET") return json(presentStory(s));
      if (sub === "" && method === "DELETE") { db.stories = db.stories.filter((x) => x.id !== s.id); db.grants = []; return json({ deleted: true }); }
      if (sub === "/confirm") { s.confirmed_at = method === "POST" ? "2026-10-22T00:00:00Z" : null; return json(presentStory(s)); }
      if (sub === "/evidence" && method === "POST") {
        const b = body() as { kind: string; ref_id: number };
        const claim = SB_CLAIMS.find((c) => c.id === b.ref_id && c.review_state !== "rejected");
        if (b.kind !== "claim" || !claim) return json({ error: { code: "not_found", message: "Story not found." } }, 404);
        if (!s.claims.includes(claim.id)) s.claims.push(claim.id);
        return json(presentStory(s));
      }
    }
    if (path === "/interviews/options") return json({ career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: [] });
    if (path === "/interviews" && method === "POST") {
      db.practiceBody = body() as Record<string, unknown>;
      for (const id of ((db.practiceBody.configuration as Record<string, unknown>)?.story_ids as number[] | undefined) ?? []) { const s = find(String(id)); if (s) s.uses += 1; }
      return json(session);
    }
    if (path === "/interviews" && method === "GET") return json({ sessions: [] });
    if (path.match(/^\/interviews\/[^/]+$/) && method === "GET") return json(session);
    return json({});
  });
  return db;
}

// ----- Workspaces (two people) -----

export type Who = "A" | "B";
export const PEOPLE: Record<Who, { id: number; email: string; name: string }> = {
  A: { id: 1, email: "ada@example.com", name: "Ada" },
  B: { id: 2, email: "ben@example.com", name: "Ben" },
};
const OWNER = { can_rename: true, can_invite: true, can_invite_admin: true, can_remove_members: true, can_change_roles: true, can_transfer: true, can_archive: true, can_restore: false, can_delete: true, can_leave: false, can_share: true };
const MEMBER = { can_rename: false, can_invite: false, can_invite_admin: false, can_remove_members: false, can_change_roles: false, can_transfer: false, can_archive: false, can_restore: false, can_delete: false, can_leave: true, can_share: true };

export interface WsFake {
  cur: Who;
  ws: { id: number; name: string; status: string; owner: Who } | null;
  members: Array<{ who: Who; role: string }>;
  invite: { id: number; email: string; token: string; status: string } | null;
  grant: { id: number; owner: Who; active: boolean } | null;
  calls: string[];
  detailStatus: number;
}

export const freshWs = (): WsFake => ({ cur: "A", ws: null, members: [], invite: null, grant: null, calls: [], detailStatus: 200 });
export const maskedEmail = (w: Who) => `${PEOPLE[w].email[0]}***@example.com`;

export async function installWorkspaceMock(page: Page, f: WsFake, ui: string) {
  await page.addInitScript(() => {
    try {
      for (const id of [1, 2]) window.localStorage.setItem(`ask4mo.tutorial:${id}`, JSON.stringify({ version: 2, dismissedAt: Date.now() }));
    } catch { /* ignore */ }
  });
  const ok = (route: Route, body: unknown, status = 200) => jsonRoute(route, body, status);
  const myRole = () => f.members.find((m) => m.who === f.cur)?.role;
  const wsOut = () => f.ws && ({ id: f.ws.id, name: f.ws.name, status: f.ws.status, owner_user_id: PEOPLE[f.ws.owner].id, member_count: f.members.length, created_at: null });

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
    const method = req.method();
    const body = (() => { try { return req.postDataJSON() ?? {}; } catch { return {}; } })();
    f.calls.push(`${method} ${path}`);

    if (path === "/capabilities") return ok(route, { ...CAPS, active_candidate_locales: ["en", "de", "fr", "es", "it", "pt", "nl"], default_locale: "en" });
    if (path === "/auth/me") {
      const p = PEOPLE[f.cur];
      return ok(route, account(ui, ui, { user_id: p.id, email: p.email, display_name: p.name }));
    }
    if (path === "/stories") return ok(route, { stories: [{ id: 5, title: "Led a launch", competencies: [], status: "user_created", evidence_state: "none", evidence_claim_ids: [] }] });
    if (path === "/history/interviews") return ok(route, { interviews: [] });

    if (path === "/workspaces" && method === "GET") {
      const mine = f.ws && myRole() ? [{ ...wsOut(), my_role: myRole(), capabilities: myRole() === "workspace_owner" ? OWNER : MEMBER }] : [];
      const invited = f.invite && f.invite.status === "pending" && f.invite.email === PEOPLE[f.cur].email && f.ws
        ? [{ id: f.invite.id, workspace_id: f.ws.id, role: "workspace_member", status: "pending", expires_at: "2099-01-01T00:00:00Z", workspace_name: f.ws.name }] : [];
      return ok(route, { workspaces: mine, invited });
    }
    if (path === "/workspaces" && method === "POST") {
      f.ws = { id: 7, name: body.name, status: "active", owner: f.cur };
      f.members = [{ who: f.cur, role: "workspace_owner" }];
      return ok(route, wsOut());
    }
    if (path === "/shares/mine") {
      return ok(route, { shares: f.grant && f.grant.active && f.grant.owner === f.cur && f.ws ? [{ id: f.grant.id, workspace_id: f.ws.id, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, workspace_name: f.ws.name }] : [] });
    }
    if (path === "/shares/with-me") {
      return ok(route, { shares: f.grant && f.grant.active && f.grant.owner !== f.cur && myRole() && f.ws ? [{ id: f.grant.id, workspace_id: f.ws.id, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: maskedEmail(f.grant.owner), workspace_name: f.ws.name }] : [] });
    }
    if (path === "/shares" && method === "POST") {
      if (body.consent !== true) return ok(route, { error: { code: "validation_error", message: "consent" } }, 422);
      f.grant = { id: 31, owner: f.cur, active: true };
      return ok(route, { share_id: 31, status: "active", permission: "view" });
    }
    if (/^\/shares\/\d+$/.test(path) && method === "DELETE") {
      if (f.grant && f.grant.owner === f.cur) f.grant.active = false;
      return ok(route, { status: "revoked" });
    }
    if (path === "/shares/resource/story/5") {
      const allowed = f.grant?.active && f.ws && myRole() && f.members.some((m) => m.who === f.grant!.owner);
      return allowed
        ? ok(route, { resource_type: "story", resource_id: "5", shared_by_owner: f.cur !== f.grant!.owner, resource: { title: "Led a launch", situation: "We shipped the product on time", competencies: ["Leadership"] } })
        : ok(route, { error: { code: "not_found", message: "Not found." } }, 404);
    }

    if (path === "/workspaces/invitations/preview") {
      if (!f.invite || body.token !== f.invite.token || f.invite.status !== "pending") return ok(route, { error: { code: "conflict", message: "used" } }, 409);
      if (f.invite.email !== PEOPLE[f.cur].email) return ok(route, { error: { code: "forbidden", message: "wrong account" } }, 403);
      return ok(route, { invitation_id: f.invite.id, workspace_name: f.ws!.name, role: "workspace_member", expires_at: "2099-01-01T00:00:00Z" });
    }
    if (path === "/workspaces/invitations/accept" || path === "/workspaces/invitations/decline") {
      if (!f.invite || body.token !== f.invite.token || f.invite.status !== "pending") return ok(route, { error: { code: "conflict", message: "used" } }, 409);
      if (path.endsWith("/accept")) { f.members.push({ who: f.cur, role: "workspace_member" }); f.invite.status = "accepted"; return ok(route, wsOut()); }
      f.invite.status = "declined";
      return ok(route, { status: "declined" });
    }

    const m = path.match(/^\/workspaces\/(\d+)(\/.*)?$/);
    if (m) {
      const sub = m[2] ?? "";
      if (!f.ws || !myRole() || f.detailStatus === 404) return ok(route, { error: { code: "not_found", message: "Workspace not found." } }, 404);
      if (f.detailStatus === 500) return ok(route, { error: { code: "server_error", message: "boom" } }, 500);
      const owner = myRole() === "workspace_owner";
      if (sub === "" && method === "GET") {
        return ok(route, {
          ...wsOut(), my_role: myRole(), capabilities: owner ? OWNER : MEMBER,
          members: f.members.map((x) => ({
            user_id: PEOPLE[x.who].id, role: x.role, status: "active", joined_at: "2026-10-01T10:00:00Z",
            label: x.who === f.cur ? PEOPLE[x.who].name : maskedEmail(x.who), is_me: x.who === f.cur,
            ...(owner || x.who === f.cur ? { email: PEOPLE[x.who].email } : {}),
          })),
          ...(owner ? { pending_invitations: f.invite && f.invite.status === "pending" ? [{ id: f.invite.id, workspace_id: 7, role: "workspace_member", status: "pending", expires_at: "2099-01-01T00:00:00Z", email: f.invite.email }] : [] } : {}),
          limits: { max_members: 100, max_pending_invitations: 50, invitation_ttl_hours: 72 },
        });
      }
      if (sub === "/shares") {
        return ok(route, { shares: f.grant?.active ? [{ id: f.grant.id, workspace_id: 7, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: maskedEmail(f.grant.owner), mine: f.grant.owner === f.cur }] : [] });
      }
      if (sub === "/invite") {
        if (!owner) return ok(route, { error: { code: "forbidden", message: "no" } }, 403);
        f.invite = { id: 11, email: body.email, token: "tok-ben-1", status: "pending" };
        return ok(route, { invitation_id: 11, status: "pending", expires_at: "2099-01-01T00:00:00Z", email_delivery: "submitted" });
      }
      const rm = sub.match(/^\/members\/(\d+)\/remove$/);
      if (rm && method === "POST") {
        const target = (Object.keys(PEOPLE) as Who[]).find((k) => PEOPLE[k].id === Number(rm[1]))!;
        f.members = f.members.filter((x) => x.who !== target);
        if (f.grant && f.grant.owner === target) f.grant.active = false;
        return ok(route, { status: "removed", shares_revoked: 0 });
      }
      if (sub === "/delete" && method === "POST") {
        if (body.confirm_name !== f.ws.name) return ok(route, { error: { code: "validation_error", message: "name" } }, 422);
        f.ws = null; f.members = []; f.grant = null; f.invite = null;
        return ok(route, { status: "deleted", members_removed: 2, shares_removed: 0, invitations_removed: 0 });
      }
    }
    return ok(route, {});
  });
}
