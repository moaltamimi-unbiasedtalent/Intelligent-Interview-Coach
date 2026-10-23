import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * 04B completion: the TWO-STEP ownership transfer in real Chromium, with the backend mocked at the network layer (no server, no paid call, no email).
 * The fake enforces the rules the real backend enforces (a fresh password step-up before proposing, one open transfer, the bound account and the one-time token
 * for accepting, replay refused, exactly one owner), so the journey proves the UI drives them correctly. The authoritative proof is tests/test_ownership_transfer_04b.py.
 * OD-WS-TRANSFER remains an owner decision: this implements the provisional recommended default and does not claim an approval.
 */

type Who = "A" | "B" | "C";
const PEOPLE: Record<Who, { id: number; email: string; name: string }> = {
  A: { id: 1, email: "ada@example.com", name: "Ada" },
  B: { id: 2, email: "ben@example.com", name: "Ben" },
  C: { id: 3, email: "cleo@example.com", name: "Cleo" },
};
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const OWNER = { can_rename: true, can_invite: true, can_invite_admin: true, can_remove_members: true, can_change_roles: true, can_transfer: true, can_archive: true, can_restore: false, can_delete: true, can_leave: false, can_share: true };
const ADMIN = { ...OWNER, can_invite_admin: false, can_change_roles: false, can_transfer: false, can_archive: false, can_delete: false, can_leave: true };
const MEMBER = { can_rename: false, can_invite: false, can_invite_admin: false, can_remove_members: false, can_change_roles: false, can_transfer: false, can_archive: false, can_restore: false, can_delete: false, can_leave: true, can_share: true };

interface Fake {
  cur: Who;
  roles: Record<string, string>;                       // who -> workspace role
  elevated: boolean;
  transfer: { id: number; proposer: Who; recipient: Who; keep: string; token: string; status: string } | null;
  calls: string[];
}

function fresh(): Fake {
  return { cur: "A", roles: { A: "workspace_owner", B: "workspace_member", C: "workspace_member" }, elevated: false, transfer: null, calls: [] };
}

const masked = (w: Who) => `${PEOPLE[w].email[0]}***@example.com`;

async function install(page: Page, f: Fake) {
  await page.addInitScript(() => {
    try { window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ }
  });
  const ok = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
  const err = (route: Route, status: number, code: string, message: string) => ok(route, { error: { code, message, request_id: "r" } }, status);
  const caps = () => (f.roles[f.cur] === "workspace_owner" ? OWNER : f.roles[f.cur] === "workspace_admin" ? ADMIN : MEMBER);
  const view = (t: NonNullable<Fake["transfer"]>) => ({
    id: t.id, workspace_id: 7, status: t.status, viewer_role: f.cur === t.proposer ? "proposer" : "recipient", former_owner_role: t.keep,
    expires_at: "2099-01-01T00:00:00Z", created_at: null, counterpart_label: masked(f.cur === t.proposer ? t.recipient : t.proposer),
  });

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
    if (path === "/stories") return ok(route, { stories: [] });
    if (path === "/history/interviews") return ok(route, { interviews: [] });
    if (path === "/shares/mine" || path === "/shares/with-me" || path === "/workspaces/7/shares") return ok(route, { shares: [] });

    if (path === "/workspaces" && method === "GET") {
      return ok(route, { workspaces: [{ id: 7, name: "Team Alpha", status: "active", owner_user_id: PEOPLE[(Object.keys(f.roles) as Who[]).find((k) => f.roles[k] === "workspace_owner")!].id, member_count: 3, created_at: null, my_role: f.roles[f.cur], capabilities: caps() }], invited: [] });
    }
    if (path === "/workspaces/transfers/mine") {
      const t = f.transfer;
      return ok(route, { transfers: t && t.status === "pending" && (t.proposer === f.cur || t.recipient === f.cur) ? [{ ...view(t), workspace_name: "Team Alpha" }] : [] });
    }
    if (path === "/workspaces/transfers/step-up" && method === "POST") {
      if (body.password !== "correct-horse") return err(route, 403, "step_up_failed", "That password was not accepted.");
      f.elevated = true;
      return ok(route, { elevated: true, elevated_until: "2099-01-01T00:00:00Z", window_seconds: 300, method: "password_reauthentication" });
    }
    if (path === "/workspaces/transfers/preview" && method === "POST") {
      const t = f.transfer;
      if (!t || body.token !== t.token || t.recipient !== f.cur) return err(route, 404, "not_found", "Ownership transfer not found.");
      if (t.status !== "pending") return err(route, 409, "conflict", "This ownership transfer has already been used, cancelled or has expired.");
      return ok(route, { ...view(t), workspace_name: "Team Alpha" });
    }
    if (path === "/workspaces/transfers/accept" && method === "POST") {
      const t = f.transfer;
      if (!t || body.token !== t.token || t.recipient !== f.cur) return err(route, 404, "not_found", "Ownership transfer not found.");
      if (t.status !== "pending") return err(route, 409, "conflict", "This ownership transfer has already been used, cancelled or has expired.");
      t.status = "accepted";
      f.roles[t.recipient] = "workspace_owner";
      f.roles[t.proposer] = t.keep;
      return ok(route, { id: 7, name: "Team Alpha", status: "active", owner_user_id: PEOPLE[t.recipient].id, member_count: 3, created_at: null });
    }
    const dec = path.match(/^\/workspaces\/transfers\/(\d+)\/decline$/);
    if (dec && method === "POST") {
      const t = f.transfer;
      if (!t || t.id !== Number(dec[1]) || t.recipient !== f.cur) return err(route, 404, "not_found", "Ownership transfer not found.");
      if (t.status !== "pending") return err(route, 409, "conflict", "used");
      t.status = "declined";
      return ok(route, { status: "declined" });
    }
    if (path === "/workspaces/7/transfer" && method === "GET") {
      const t = f.transfer;
      return ok(route, { transfer: t && t.status === "pending" && (t.proposer === f.cur || t.recipient === f.cur) ? view(t) : null });
    }
    if (path === "/workspaces/7/transfer" && method === "POST") {
      if (f.roles[f.cur] !== "workspace_owner") return err(route, 403, "forbidden", "Only the workspace owner may propose an ownership transfer.");
      if (!f.elevated) return err(route, 403, "step_up_required", "Confirm your password to continue.");
      if (body.confirm_name !== "Team Alpha") return err(route, 422, "validation_error", "name");
      if (f.transfer && f.transfer.status === "pending") return err(route, 409, "conflict", "open transfer");
      const recipient = (Object.keys(PEOPLE) as Who[]).find((k) => PEOPLE[k].id === body.new_owner_user_id)!;
      f.transfer = { id: 5, proposer: f.cur, recipient, keep: body.former_owner_role, token: "tok-transfer-1", status: "pending" };
      return ok(route, { ...view(f.transfer), email_delivery: "submitted" });
    }
    if (path === "/workspaces/7/transfer/cancel" && method === "POST") {
      const t = f.transfer;
      if (!t || t.status !== "pending" || t.proposer !== f.cur) return err(route, 404, "not_found", "Ownership transfer not found.");
      t.status = "cancelled";
      return ok(route, { status: "cancelled" });
    }
    if (path === "/workspaces/7" && method === "GET") {
      const mine = f.roles[f.cur];
      const manager = mine !== "workspace_member";
      return ok(route, {
        id: 7, name: "Team Alpha", status: "active", owner_user_id: PEOPLE[(Object.keys(f.roles) as Who[]).find((k) => f.roles[k] === "workspace_owner")!].id, member_count: 3, created_at: null, my_role: mine, capabilities: caps(),
        members: (Object.keys(PEOPLE) as Who[]).map((w) => ({ user_id: PEOPLE[w].id, role: f.roles[w], status: "active", joined_at: "2026-10-01T10:00:00Z", label: w === f.cur ? PEOPLE[w].name : masked(w), is_me: w === f.cur, ...(manager || w === f.cur ? { email: PEOPLE[w].email } : {}) })),
        limits: { max_members: 100, max_pending_invitations: 50, invitation_ttl_hours: 72 },
      });
    }
    return ok(route, {});
  });
}

test("owner proposes (name and password), sees it pending, cancels, and nothing about ownership changed", async ({ page }) => {
  const f = fresh();
  await install(page, f);
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: `Transfer ownership: ${masked("B")}` }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog.getByText(/becomes the only owner/i)).toBeVisible();                   // consequences are shown before anything is sent
  await expect(dialog.getByText(/expires after 7 days/i)).toBeVisible();

  // the wrong password is refused with a localized message and nothing is proposed
  await dialog.getByLabel("Type the workspace name to confirm").fill("Team Alpha");
  await dialog.getByLabel("Confirm your password").fill("wrong");
  await dialog.getByRole("button", { name: "Send proposal" }).click();
  await expect(dialog.getByText("That password was not accepted.")).toBeVisible();
  expect(f.transfer).toBeNull();
  expect(await dialog.getByLabel("Confirm your password").inputValue()).toBe("");           // the password does not linger

  await dialog.getByLabel("Confirm your password").fill("correct-horse");
  await dialog.getByRole("radio", { name: "an admin" }).check();
  await dialog.getByRole("button", { name: "Send proposal" }).click();
  await expect(page.getByText(/Proposal created\. The new owner was sent a notice/)).toBeVisible();
  expect(f.transfer?.keep).toBe("workspace_admin");
  const banner = page.getByTestId("transfer-banner-proposer");
  await expect(banner.getByText(/Nothing has changed yet/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Transfer ownership: / })).toHaveCount(0);   // one open transfer at a time
  expect(f.roles.A).toBe("workspace_owner");

  await banner.getByRole("button", { name: "Cancel proposal" }).click();
  await expect(page.getByText("Proposal cancelled. Ownership did not change.")).toBeVisible();
  await expect(page.getByTestId("transfer-banner-proposer")).toHaveCount(0);
  expect(f.roles.A).toBe("workspace_owner");
});

test("recipient sees the banner on both pages, can only accept through the emailed link, and becomes the single owner", async ({ page }) => {
  const f = fresh();
  f.transfer = { id: 5, proposer: "A", recipient: "B", keep: "workspace_admin", token: "tok-transfer-1", status: "pending" };
  await install(page, f);

  f.cur = "B";
  await page.goto("/workspaces");
  const listBanner = page.getByTestId("transfer-banner-recipient");
  await expect(listBanner).toBeVisible();
  await expect(listBanner.getByRole("button", { name: /accept/i })).toHaveCount(0);          // no one-click accept without the emailed link
  await page.goto("/workspaces/7");
  await expect(page.getByTestId("transfer-banner-recipient").getByText(/open the link in the email/i)).toBeVisible();

  // opening the link changes nothing; accepting is explicit
  await page.goto("/workspaces/transfer/accept?token=tok-transfer-1");
  await expect(page.getByText("Team Alpha")).toBeVisible();
  await expect(page.getByText(/You become the only owner/)).toBeVisible();
  expect(f.transfer?.status).toBe("pending");
  await page.getByRole("button", { name: "Accept ownership" }).click();
  await expect(page.getByText("You are now the owner of this workspace.")).toBeVisible();
  expect(f.roles).toEqual({ A: "workspace_admin", B: "workspace_owner", C: "workspace_member" });
  expect(Object.values(f.roles).filter((r) => r === "workspace_owner")).toHaveLength(1);

  // the link cannot be replayed
  await page.goto("/workspaces/transfer/accept?token=tok-transfer-1");
  await expect(page.getByText(/expired, was cancelled or has already been answered/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept ownership" })).toHaveCount(0);

  // the former owner now sees the role they chose and no owner controls
  f.cur = "A";
  await page.goto("/workspaces/7");
  await expect(page.getByRole("button", { name: /^Transfer ownership: / })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete workspace" })).toHaveCount(0);
});

test("a recipient can decline, and a wrong account or a missing link gets a clear explanation", async ({ page }) => {
  const f = fresh();
  f.transfer = { id: 5, proposer: "A", recipient: "B", keep: "workspace_member", token: "tok-transfer-1", status: "pending" };
  await install(page, f);

  f.cur = "C";                                                                               // not the recipient: the same "gone" wording, no hint that a transfer exists
  await page.goto("/workspaces/transfer/accept?token=tok-transfer-1");
  await expect(page.getByText(/expired, was cancelled or has already been answered/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept ownership" })).toHaveCount(0);
  await page.goto("/workspaces/7");
  await expect(page.getByTestId("transfer-banner-recipient")).toHaveCount(0);
  await expect(page.getByTestId("transfer-banner-proposer")).toHaveCount(0);

  await page.goto("/workspaces/transfer/accept");
  await expect(page.getByText(/This link is incomplete/i)).toBeVisible();

  f.cur = "B";
  await page.goto("/workspaces/7");
  await page.getByTestId("transfer-banner-recipient").getByRole("button", { name: "Decline" }).click();
  await expect(page.getByText("Proposal declined. Ownership did not change.")).toBeVisible();
  expect(f.transfer?.status).toBe("declined");
  expect(f.roles.A).toBe("workspace_owner");
});
