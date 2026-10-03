import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "../lib/i18n/locales";

/**
 * P10B-W9.8 - Data & Privacy Center, end to end. Stateful network mock (no backend, no model, no paid or
 * live provider; the account-deletion test only ever touches this mocked, disposable account).
 * Cross-user isolation is proven authoritatively by the backend tests (tests/test_w98_privacy_controls.py);
 * the browser only ever sends ids it received from its own owner-scoped lists, so there is no id-entry
 * surface to tamper with here.
 */

const T = (locale: string, k: string, v?: Record<string, string | number>) => translate(locale as never, k, v);

function account(locale = "en") {
  return {
    user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: locale, conversation_language: "en",
    coaching_style: "balanced", career_geography: "", target_role: "",
    onboarding_completed: true, onboarding_step: 0,
  };
}

type State = {
  opps: Record<string, unknown>[];
  docs: Record<string, unknown>[];
  mems: Record<string, unknown>[];
  ints: Record<string, unknown>[];
  shares: Record<string, unknown>[];
  deleted: boolean;
  calls: string[];
  reqs: Record<string, unknown>[];
  accepted: boolean;
};

function freshState(): State {
  return {
    opps: [{ id: 1, title: "PM at Acme", target_role: "PM", status: "active" }],
    docs: [{ id: 10, category: "cv", title: "My CV", status: "ready", current_version: 1 }],
    mems: [{ id: 20, category: "strength", summary: "Clear storyteller", target_role: null, pinned: false, source_run_id: null, created_at: null, updated_at: null }],
    ints: [{ id: 30, target_role: "Nurse", created_at: "2026-09-01T10:00:00Z", questions: 3 }],
    shares: [{ id: 40, owner_user_id: 1, workspace_id: 5, resource_type: "interview_report", resource_id: "30", permission: "view", status: "active", created_at: null, revoked_at: null }],
    deleted: false,
    calls: [],
    reqs: [],
    accepted: false,
  };
}

async function mock(page: Page, locale = "en", state = freshState()) {
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() }));
    } catch { /* ignore */ }
  });
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, "");
    const method = req.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (method !== "GET") state.calls.push(`${method} ${path}`);

    if (path === "/auth/me") return state.deleted ? json({ error: { code: "unauthenticated", message: "x" } }, 401) : json(account(locale));
    if (path === "/capabilities") return json({ agent_coach_enabled: false, realtime_voice_enabled: false, company_research_enabled: false });
    if (path === "/auth/account/delete" && method === "POST") { state.deleted = true; return json({ message: "deleted" }); }
    if (path === "/privacy/requests" && method === "POST") {
      const body = JSON.parse(req.postData() ?? "{}");
      const created = { public_id: "r".repeat(32), request_type: body.request_type, type_label: "x", status: "submitted", result_category: null, created_at: "2026-10-03T10:00:00", updated_at: null };
      state.reqs.unshift(created);
      return json(created, 201);
    }
    if (path === "/privacy/requests") return json({ items: state.reqs, total: state.reqs.length, page: 1, page_size: 20 });
    const legalDoc = () => ({ code: "terms", title: "Terms of use", path: "/terms", current_version: "baseline-1", effective_at: null, version_is_baseline: true,
      accepted_current: state.accepted, last_acceptance: state.accepted ? { version: "baseline-1", accepted_at: "2026-10-03T10:00:00", source: "settings", is_current: true } : null });
    if (path === "/privacy/legal/terms/accept" && method === "POST") { state.accepted = true; return json({ documents: [legalDoc()] }); }
    if (path === "/privacy/legal") return json({ documents: [legalDoc()] });
    if (path === "/auth/account/export") return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });

    const rm = (arr: Record<string, unknown>[], id: number) => {
      const i = arr.findIndex((x) => x.id === id);
      if (i < 0) return json({ error: { code: "not_found", message: "x" } }, 404);
      arr.splice(i, 1);
      return json({ deleted: true });
    };
    let m: RegExpMatchArray | null;
    if ((m = path.match(/^\/opportunities\/(\d+)$/)) && method === "DELETE") return rm(state.opps, Number(m[1]));
    if ((m = path.match(/^\/opportunities\/(\d+)\/archive$/))) {
      const o = state.opps.find((x) => x.id === Number(m![1]))!;
      o.status = "archived";
      return json(o);
    }
    if (path === "/opportunities") return json({ opportunities: state.opps });
    if ((m = path.match(/^\/documents\/(\d+)$/)) && method === "DELETE") return rm(state.docs, Number(m[1]));
    if (path === "/documents") return json({ documents: state.docs });
    if ((m = path.match(/^\/memory\/(\d+)$/)) && method === "DELETE") return rm(state.mems, Number(m[1]));
    if (path === "/memory") return json({ memories: state.mems });
    if ((m = path.match(/^\/history\/interviews\/(\d+)$/)) && method === "DELETE") return rm(state.ints, Number(m[1]));
    if (path === "/history/interviews") return json({ interviews: state.ints });
    if ((m = path.match(/^\/shares\/(\d+)$/)) && method === "DELETE") { state.shares = state.shares.filter((x) => x.id !== Number(m![1])); return json({ status: "revoked" }); }
    if (path === "/shares/mine") return json({ shares: state.shares });
    if (path === "/workspaces") return json({ workspaces: [{ id: 5, name: "Team Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
    return json({});
  });
  return state;
}

test("core privacy journey: inspect, export, remove one item of each kind, revoke a share", async ({ page }) => {
  const state = await mock(page);
  await page.goto("/account/data");
  await expect(page.getByRole("heading", { level: 1, name: T("en", "dataPrivacy.title") })).toBeVisible();
  await expect(page.getByTestId("dp-count-opps")).toHaveText("1");
  await expect(page.getByTestId("dp-count-ints")).toHaveText("1");

  // Export is a real download link to the owner-scoped endpoint.
  await expect(page.getByTestId("dp-export-link")).toHaveAttribute("href", /\/auth\/account\/export$/);

  // Delete the document: Cancel first (nothing happens), then confirm.
  const delDoc = page.getByRole("button", { name: `${T("en", "dataPrivacy.deleteAction")}: My CV` });
  await delDoc.click();
  await page.getByRole("button", { name: T("en", "common.cancel") }).click();
  await expect(page.getByText("My CV")).toBeVisible();
  expect(state.calls).toEqual([]);
  await delDoc.click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("en", "dataPrivacy.confirmDelete") }).click();
  await expect(page.getByText("My CV")).toHaveCount(0);
  expect(state.calls).toEqual(["DELETE /documents/10"]);

  // Unrelated data remains.
  await expect(page.getByText("Clear storyteller")).toBeVisible();
  await expect(page.getByText("PM at Acme")).toBeVisible();
  await expect(page.getByTestId("dp-count-docs")).toHaveText("0");

  // Memory, interview, archive an Opportunity, revoke the share.
  await page.getByRole("button", { name: `${T("en", "dataPrivacy.deleteAction")}: Clear storyteller` }).click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("en", "dataPrivacy.confirmDelete") }).click();
  await expect(page.getByText("Clear storyteller")).toHaveCount(0);

  await page.getByRole("button", { name: new RegExp(`^${T("en", "dataPrivacy.deleteAction")}: Nurse`) }).click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("en", "dataPrivacy.confirmDelete") }).click();
  await expect(page.getByTestId("dp-count-ints")).toHaveText("0");

  await page.getByRole("button", { name: `${T("en", "dataPrivacy.archiveAction")}: PM at Acme` }).click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("en", "dataPrivacy.confirmArchive") }).click();
  await expect(page.getByTestId("dp-manage-opportunities").getByText(T("en", "dataPrivacy.archivedBadge"))).toHaveCount(1);
  expect(state.opps).toHaveLength(1); // archive keeps it

  await page.getByRole("button", { name: new RegExp(`^${T("en", "dataPrivacy.revokeAction")}:`) }).click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("en", "dataPrivacy.confirmRevoke") }).click();
  await expect(page.getByText(T("en", "dataPrivacy.sharingEmpty"))).toBeVisible();

  // Retention + legal are visible, and the account deletion zone was left untouched.
  await expect(page.getByTestId("dp-retention")).toBeVisible();
  await expect(page.getByTestId("dp-legal")).toContainText(T("en", "dataPrivacy.legalNotAcceptedCurrent"));
  expect(state.calls.some((c) => c.includes("/auth/account/delete"))).toBe(false);
});

test("W10.10: submit a privacy request, see it listed, and record legal acceptance of the current version", async ({ page }) => {
  const state = await mock(page);
  await page.goto("/account/data");
  await expect(page.getByRole("heading", { name: T("en", "dataPrivacy.prTitle") })).toBeVisible();
  await expect(page.getByText(T("en", "dataPrivacy.prListEmpty"))).toBeVisible();
  await page.getByLabel(T("en", "dataPrivacy.prTypeLabel")).selectOption("correction");
  await page.getByLabel(/Details \(optional\)/).fill("Please correct my surname.");
  await page.getByRole("button", { name: T("en", "dataPrivacy.prSubmit") }).click();
  await expect(page.getByRole("status")).toContainText("r".repeat(32));
  await expect(page.getByTestId("dp-privacy-requests").getByText(T("en", "dataPrivacy.prStatusSubmitted"))).toBeVisible();
  expect(state.calls).toEqual(["POST /privacy/requests"]);

  const legal = page.getByTestId("dp-legal-versions");
  await expect(legal.getByText(T("en", "dataPrivacy.legalNotAcceptedCurrent"))).toBeVisible();   // nothing is pre-accepted
  await expect(legal.getByText(T("en", "dataPrivacy.legalEffectiveUnknown"))).toBeVisible();
  await legal.getByRole("button", { name: /Record my acceptance/ }).click();
  await expect(legal.getByText(/You recorded accepting this version on/)).toBeVisible();
  await expect(legal.getByRole("button", { name: /Record my acceptance/ })).toHaveCount(0);
});

test("account deletion: cancel keeps the account; confirm deletes and ends the session", async ({ page }) => {
  const state = await mock(page);
  await page.goto("/account/data");
  await page.getByTestId("dp-delete-account").click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: T("en", "dataPrivacy.accountConfirmKeep") })).toBeFocused();
  await dialog.getByRole("button", { name: T("en", "dataPrivacy.accountConfirmKeep") }).click();
  await expect(dialog).toHaveCount(0);
  expect(state.deleted).toBe(false);

  await page.getByTestId("dp-delete-account").click();
  await page.getByRole("button", { name: T("en", "dataPrivacy.accountConfirmDelete") }).click();
  await page.waitForURL(/\/sign-in/);
  expect(state.deleted).toBe(true);
  // The session no longer provides access: the account page cannot be used.
  await page.goto("/account/data");
  await expect(page.getByTestId("data-privacy-center")).toHaveCount(0);
});

for (const locale of ["de", "ru"]) {
  test(`${locale}: Data & Privacy Center is fully localized (no raw keys, no English title)`, async ({ page }) => {
    await mock(page, locale);
    await page.goto("/account/data");
    await expect(page.getByRole("heading", { level: 1, name: T(locale, "dataPrivacy.title") })).toBeVisible();
    for (const k of ["overviewTitle", "exportTitle", "manageTitle", "sharingTitle", "retentionTitle", "legalTitle", "accountZoneTitle"]) {
      await expect(page.getByRole("heading", { level: 2, name: T(locale, `dataPrivacy.${k}`) })).toBeVisible();
    }
    const body = await page.locator("main").innerText();
    expect(body).not.toMatch(/dataPrivacy\./);
    expect(body).not.toContain(T("en", "dataPrivacy.title"));
  });
}

test("8-locale smoke: stable heading and primary sections render in every locale", async ({ page }) => {
  for (const locale of SUPPORTED_LOCALE_CODES) {
    await mock(page, locale);
    await page.goto("/account/data");
    await expect(page.getByRole("heading", { level: 1, name: T(locale, "dataPrivacy.title") })).toBeVisible();
    for (const id of ["overview", "export", "manage", "sharing", "retention", "legal", "account"]) {
      await expect(page.getByTestId(`dp-${id}`)).toBeVisible();
    }
    expect(await page.locator("main").innerText()).not.toMatch(/dataPrivacy\./);
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("mobile 390px (light and dark): no horizontal scroll, dialog fits, actions reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  for (const locale of ["ru", "de"]) {
    await mock(page, locale);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/data");
      await expect(page.getByTestId("data-privacy-center")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      if (process.env.W98_SHOTS) await page.screenshot({ path: `${process.env.W98_SHOTS}/dp-${locale}-${scheme}.png`, fullPage: true });
      await page.getByTestId("dp-delete-account").click();
      const box = await page.getByRole("alertdialog").boundingBox();
      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(390);
      await expect(page.getByRole("button", { name: T(locale, "dataPrivacy.accountConfirmKeep") })).toBeVisible();
      await page.keyboard.press("Escape");
    }
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});
