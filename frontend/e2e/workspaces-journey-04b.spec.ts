import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * 04B Workspaces: the two-person journey in real Chromium, with the backend mocked at the network layer (no server, no paid call).
 * The mock is a small stateful fake of the workspace API that ENFORCES the rules the real backend enforces (membership is the visibility
 * boundary, consent is required, revocation is immediate), so the browser journey proves the UI drives those rules correctly. The
 * authoritative authorization proof is the Python suite (tests/test_workspaces_04b.py, eval_workspace_security.py).
 *
 *  A creates "Team Alpha" and invites B -> B opens the emailed link, sees what it is, accepts -> A shares ONE story with explicit
 *  consent -> B sees only that and can read it -> A stops sharing, B loses access at once -> A removes B -> A deletes the workspace.
 */

type Who = "A" | "B";
const PEOPLE: Record<Who, { id: number; email: string; name: string }> = {
  A: { id: 1, email: "ada@example.com", name: "Ada" },
  B: { id: 2, email: "ben@example.com", name: "Ben" },
};
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const OWNER = { can_rename: true, can_invite: true, can_invite_admin: true, can_remove_members: true, can_change_roles: true, can_transfer: true, can_archive: true, can_restore: false, can_delete: true, can_leave: false, can_share: true };
const MEMBER = { can_rename: false, can_invite: false, can_invite_admin: false, can_remove_members: false, can_change_roles: false, can_transfer: false, can_archive: false, can_restore: false, can_delete: false, can_leave: true, can_share: true };

interface Fake {
  cur: Who;
  ws: { id: number; name: string; status: string; owner: Who } | null;
  members: Array<{ who: Who; role: string }>;
  invite: { id: number; email: string; token: string; status: string } | null;
  grant: { id: number; owner: Who; active: boolean } | null;
  calls: string[];
  detailStatus: number;
}

function fresh(): Fake {
  return { cur: "A", ws: null, members: [], invite: null, grant: null, calls: [], detailStatus: 200 };
}

const maskedEmail = (w: Who) => `${PEOPLE[w].email[0]}***@example.com`;

async function install(page: Page, f: Fake) {
  await page.addInitScript(() => {
    try { window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ }
  });
  const ok = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
  const myRole = () => f.members.find((m) => m.who === f.cur)?.role;
  const wsOut = () => f.ws && ({ id: f.ws.id, name: f.ws.name, status: f.ws.status, owner_user_id: PEOPLE[f.ws.owner].id, member_count: f.members.length, created_at: null });

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
    const method = req.method();
    const body = (() => { try { return req.postDataJSON(); } catch { return {}; } })();
    f.calls.push(`${method} ${path}`);

    if (path === "/capabilities") return ok(route, CAPS);
    if (path === "/auth/me") {
      const p = PEOPLE[f.cur];
      return ok(route, { user_id: p.id, email: p.email, display_name: p.name, platform_role: "user", tier: "basic", status: "active", email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
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
    if (path === "/shares/mine") return ok(route, { shares: f.grant && f.grant.active && f.grant.owner === f.cur && f.ws ? [{ id: f.grant.id, workspace_id: f.ws.id, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, workspace_name: f.ws.name }] : [] });
    if (path === "/shares/with-me") return ok(route, { shares: f.grant && f.grant.active && f.grant.owner !== f.cur && myRole() && f.ws ? [{ id: f.grant.id, workspace_id: f.ws.id, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: maskedEmail(f.grant.owner), workspace_name: f.ws.name }] : [] });
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
      return allowed ? ok(route, { resource_type: "story", resource_id: "5", shared_by_owner: f.cur !== f.grant!.owner, resource: { title: "Led a launch", situation: "We shipped the product on time", competencies: ["Leadership"] } })
        : ok(route, { error: { code: "not_found", message: "Not found." } }, 404);
    }

    if (path === "/workspaces/invitations/preview") {
      if (!f.invite || body.token !== f.invite.token || f.invite.status !== "pending") return ok(route, { error: { code: "conflict", message: "used" } }, 409);
      if (f.invite.email !== PEOPLE[f.cur].email) return ok(route, { error: { code: "forbidden", message: "This invitation was issued to a different email." } }, 403);
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
          members: f.members.map((x) => ({ user_id: PEOPLE[x.who].id, role: x.role, status: "active", joined_at: "2026-10-01T10:00:00Z", label: x.who === f.cur ? PEOPLE[x.who].name : maskedEmail(x.who), is_me: x.who === f.cur, ...(owner || x.who === f.cur ? { email: PEOPLE[x.who].email } : {}) })),
          ...(owner ? { pending_invitations: f.invite && f.invite.status === "pending" ? [{ id: f.invite.id, workspace_id: 7, role: "workspace_member", status: "pending", expires_at: "2099-01-01T00:00:00Z", email: f.invite.email }] : [] } : {}),
          limits: { max_members: 100, max_pending_invitations: 50, invitation_ttl_hours: 72 },
        });
      }
      if (sub === "/shares") return ok(route, { shares: f.grant?.active ? [{ id: f.grant.id, workspace_id: 7, resource_type: "story", resource_id: "5", permission: "view", status: "active", created_at: null, revoked_at: null, shared_by: maskedEmail(f.grant.owner), mine: f.grant.owner === f.cur }] : [] });
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

test("two-person journey: create, invite, accept, share, see only that, revoke, remove, delete", async ({ page }) => {
  const f = fresh();
  await install(page, f);

  // A creates a workspace and opens it
  await page.goto("/workspaces");
  await page.getByLabel(/Workspace name/i).fill("Team Alpha");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.getByRole("link", { name: "Open workspace: Team Alpha" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Team Alpha" })).toBeVisible();

  // A invites B. The note says the mail was handed over, not that it was delivered.
  await page.getByLabel("Email address").fill(PEOPLE.B.email);
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(page.getByText(/handed to the mail provider\. That does not confirm delivery/i)).toBeVisible();
  await expect(page.getByText(PEOPLE.B.email).first()).toBeVisible();                       // pending list

  // B opens the emailed link: sees the workspace and role, nothing is accepted by opening it, then accepts explicitly
  f.cur = "B";
  await page.goto("/workspaces/accept?token=tok-ben-1");
  await expect(page.getByText("Team Alpha")).toBeVisible();
  expect(f.invite?.status).toBe("pending");
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByText("You joined the workspace.")).toBeVisible();
  await page.getByRole("link", { name: "Open the workspace" }).click();
  await expect(page.getByRole("link", { name: "Team Alpha", exact: true })).toBeVisible();
  await expect(page.getByText(/shares nothing automatically/i)).toBeVisible();
  await expect(page.getByText(/Nothing shared yet/i).first()).toBeVisible();                // joining shared nothing

  // A shares ONE story: the button stays disabled until the explicit consent is ticked
  f.cur = "A";
  await page.goto("/workspaces/7");
  await expect(page.getByText(/Nothing is shared in this workspace yet/i)).toBeVisible();
  await expect(page.getByRole("option", { name: "Led a launch" })).toBeAttached();
  await page.getByLabel("Item", { exact: true }).selectOption("5");
  const share = page.getByRole("button", { name: "Share item" });
  await expect(share).toBeDisabled();
  await page.getByRole("checkbox", { name: /every current and future member/i }).check();
  await expect(share).toBeEnabled();
  await share.click();
  await expect(page.getByText("Shared. Members can now view this item.")).toBeVisible();
  expect(f.calls).toContain("POST /shares");

  // B sees that one item and can read it (read only: there is no edit or delete control)
  f.cur = "B";
  await page.goto("/workspaces");
  await expect(page.getByText(/Story #5/)).toBeVisible();
  await page.getByRole("button", { name: /View: Story #5/ }).click();
  await expect(page.getByText("We shipped the product on time")).toBeVisible();
  await expect(page.getByRole("button", { name: /edit|delete/i })).toHaveCount(0);

  // A stops sharing: B's very next view says it is no longer shared
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: /Stop sharing: Story #5/ }).click();
  await expect(page.getByText(/Sharing stopped\. Access ended immediately/)).toBeVisible();
  f.cur = "B";
  await page.goto("/workspaces");
  await expect(page.getByText(/Story #5/)).toHaveCount(0);

  // A removes B (after an explicit, accessible confirmation); B's workspace page is then not available
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: /^Remove: b\*\*\*@example\.com/ }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();              // safe default focus
  await dialog.getByRole("button", { name: "Remove member" }).click();
  await expect(page.getByText("Member removed.")).toBeVisible();
  f.cur = "B";
  await page.goto("/workspaces/7");
  await expect(page.getByText(/not available/i)).toBeVisible();

  // A deletes the workspace: only with the exact name typed
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: "Delete workspace" }).click();
  const del = page.getByRole("alertdialog");
  await del.getByLabel("Type the workspace name to confirm").fill("wrong name");
  await del.getByRole("button", { name: "Delete permanently" }).click();
  expect(f.ws).not.toBeNull();                                                              // refused client side, nothing sent
  await del.getByLabel("Type the workspace name to confirm").fill("Team Alpha");
  await del.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page).toHaveURL(/\/workspaces$/);
  await expect(page.getByText(/You are not in any workspace yet/i)).toBeVisible();
  expect(f.ws).toBeNull();
});

test("invitation page: a used or wrong-address link explains itself and a decline shares nothing", async ({ page }) => {
  const f = fresh();
  f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
  f.members = [{ who: "A", role: "workspace_owner" }];
  f.invite = { id: 11, email: PEOPLE.B.email, token: "tok-ben-1", status: "pending" };
  await install(page, f);

  f.cur = "A";                                                                              // the wrong signed-in account
  await page.goto("/workspaces/accept?token=tok-ben-1");
  await expect(page.getByText(/issued to a different email address/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept invitation" })).toHaveCount(0);

  await page.goto("/workspaces/accept");
  await expect(page.getByText(/invitation link is incomplete/i)).toBeVisible();

  f.cur = "B";
  await page.goto("/workspaces/accept?token=tok-ben-1");
  await page.getByRole("button", { name: "Decline invitation" }).click();
  await expect(page.getByText(/Invitation declined\. Nothing was shared/)).toBeVisible();
  await page.goto("/workspaces/accept?token=tok-ben-1");
  await expect(page.getByText(/expired, was revoked or has already been used/i)).toBeVisible();
});

test("a plain member sees no management controls, and an owner cannot leave without transferring", async ({ page }) => {
  const f = fresh();
  f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
  f.members = [{ who: "A", role: "workspace_owner" }, { who: "B", role: "workspace_member" }];
  await install(page, f);

  f.cur = "B";
  await page.goto("/workspaces/7");
  await expect(page.getByRole("heading", { level: 1, name: "Team Alpha" })).toBeVisible();
  await expect(page.getByText("a***@example.com").first()).toBeVisible();                  // a label, never the owner's full address
  await expect(page.getByText(PEOPLE.A.email)).toHaveCount(0);
  await expect(page.getByLabel("Email address")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Archive workspace|Delete workspace/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Leave" })).toBeVisible();

  f.cur = "A";
  await page.goto("/workspaces/7");
  await expect(page.getByRole("button", { name: "Leave" })).toHaveCount(0);
  await expect(page.getByText(/must transfer ownership before leaving/i)).toBeVisible();
});

test("an unavailable workspace and a server error are shown honestly", async ({ page }) => {
  const f = fresh();
  f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
  f.members = [{ who: "A", role: "workspace_owner" }];
  await install(page, f);
  f.cur = "A";
  f.detailStatus = 404;
  await page.goto("/workspaces/7");
  await expect(page.getByText(/not available/i)).toBeVisible();
  await expect(page.getByRole("link", { name: "All workspaces" })).toBeVisible();
  f.detailStatus = 500;
  await page.goto("/workspaces/7");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("the confirmation dialog traps focus and Escape cancels without changing anything", async ({ page }) => {
  const f = fresh();
  f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
  f.members = [{ who: "A", role: "workspace_owner" }, { who: "B", role: "workspace_member" }];
  await install(page, f);
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: /^Remove: b\*\*\*@example\.com/ }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  expect(f.calls.some((c) => c.includes("/remove"))).toBe(false);
  expect(f.members.length).toBe(2);
});
