import { expect, test, type Page, type TestInfo } from "@playwright/test";

import { WorkspaceDeletionDiagnostics } from "./fixtures/workspaceDeletionDiagnostics";
import { BRAND_SLOGAN } from "../lib/brand";
import { ACTIVE_CANDIDATE_LOCALES, APP_LOCALES, type AppLocale } from "../lib/i18n/locales";
import { T, expectNoEnglishLeak, expectNoOverflow, installSweepMock } from "./fixtures/journey06b";
import {
  PEOPLE, SB_QUESTION, expectAccessibleNames, freshWs, installStoryBankMock, installWorkspaceMock, maskedEmail, type WsFake,
} from "./fixtures/journey06bMocks";

/**
 * 06B (LG-03, LG-09; PG-13 contribution): ONE shared Candidate journey definition, run once per selectable language
 * (en, de, fr, es, it, pt, nl). Mocked network only: no backend, no provider call. Russian is excluded (its dormant specs stay
 * skipped, see 06A_RUSSIAN_TESTS_EXCLUDED.md). Server paths are proven by tests/test_language_journeys_06b.py (real backend).
 * All non-English strings are ENGINEERING translations, not native-reviewed: a passing run is never language approval.
 */
const LOCALES: readonly AppLocale[] = ACTIVE_CANDIDATE_LOCALES;
const otherLocale = (ui: string): AppLocale => LOCALES[(LOCALES.indexOf(ui as AppLocale) + 3) % LOCALES.length];
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const dateIn = (ui: string, iso: string) => new Intl.DateTimeFormat(ui).format(new Date(iso));

// Candidate surfaces of the journey: Home/Opportunity entry, Opportunity, Company research, Prepare/Mo, Practice, History,
// Progress, Documents (Story Bank), Settings, privacy controls, Workspaces, Help.
const SURFACES: Array<{ name: string; path: string }> = [
  { name: "home", path: "/app" },
  { name: "opportunities", path: "/opportunities" },
  { name: "company", path: "/company" },
  { name: "prepare", path: "/prepare" },
  { name: "practice", path: "/practice" },
  { name: "history", path: "/history" },
  { name: "progress", path: "/progress" },
  { name: "documents", path: "/documents" },
  { name: "settings", path: "/settings" },
  { name: "privacy-controls", path: "/account/data" },
  { name: "workspaces", path: "/workspaces" },
  { name: "help", path: "/help" },
];

const CHAT_NO_EVIDENCE = {
  answer: "(model answer text, rendered verbatim)",
  citations: [], sources: [{ title: "O*NET Product manager", source_url: "https://example.org/onet", reference_year: 2024 }],
  tools: [], input_flagged: false, has_evidence: false, preparation_available: false,
};

// ───────────────────────────── shared journey definitions ─────────────────────────────

/** Story Bank: create, evidence, verify, use in Practice with consent, share with consent, revoke, delete, survive reload. */
async function storyBankJourney(page: Page, ui: string) {
  const t = (k: string, v?: Record<string, string | number>) => T(ui, k, v);
  const db = await installStoryBankMock(page, ui);
  await page.goto("/documents");
  await expect(page.getByText(t("storyBank.empty"))).toBeVisible();

  // create (a title is required; nothing is invented)
  await page.getByRole("button", { name: t("storyBank.newStory") }).click();
  await expect(page.getByLabel(t("storyBank.fieldTitle"), { exact: true })).toBeFocused();
  await page.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(page.getByText(t("storyBank.titleRequired"))).toBeVisible();
  await page.getByLabel(t("storyBank.fieldTitle"), { exact: true }).fill("Led the ward migration");
  await page.getByLabel(t("storyBank.fieldSituation"), { exact: true }).fill("The ward moved to a new records system.");
  await page.getByLabel(t("storyBank.fieldTags"), { exact: true }).fill("Leadership, Planning");
  await page.locator("form").getByLabel(t("storyBank.fieldOpportunity"), { exact: true }).selectOption("3");
  await page.getByRole("button", { name: t("common.save"), exact: true }).click();

  const card = page.getByTestId("story-1");
  await expect(card).toContainText("Led the ward migration");
  await expect(card).toContainText(t("documents.stUserCreated"));
  await expect(card).toContainText(t("documents.evNone"));                                   // not verified without evidence
  await expect(card.getByTestId("quality-prompts")).toContainText(t("storyBank.q_action_missing"));
  await expect(card).toContainText(t("storyBank.linkedOpportunity", { title: "Pflegefachkraft bei Acme" }));
  await expectNoEnglishLeak(page, ui, "story bank card");

  // evidence: only a non-rejected document item is offered; the story then shows supporting evidence
  await card.getByRole("button", { name: t("storyBank.linkToggle") }).click();
  await card.getByLabel(t("storyBank.linkDocument"), { exact: true }).selectOption("1");
  const claim = card.getByLabel(t("storyBank.linkClaim"), { exact: true });
  await expect(claim.locator("option", { hasText: "Rejected skill" })).toHaveCount(0);
  await claim.selectOption("11");
  await card.getByRole("button", { name: t("storyBank.linkAction"), exact: true }).click();
  await expect(card).toContainText(t("documents.evVerified"));
  await expect(card.getByTestId("verification-help")).toContainText(t("storyBank.vh_evidence_verified"));

  // verify: a second story only self-confirmed is labelled as the candidate's own statement, never as evidence
  await page.getByRole("button", { name: t("storyBank.newStory") }).click();
  await page.getByLabel(t("storyBank.fieldTitle"), { exact: true }).fill("Calmed a conflict");
  await page.getByLabel(t("storyBank.fieldAction"), { exact: true }).fill("I listened first, then proposed a rota both sides could accept in a short meeting.");
  await page.getByRole("button", { name: t("common.save"), exact: true }).click();
  const card2 = page.getByTestId("story-2");
  await card2.getByRole("button", { name: t("storyBank.confirm") }).click();
  await expect(card2).toContainText(t("storyBank.v_self_confirmed"));
  await expect(card2.getByTestId("verification-help")).toContainText(t("storyBank.vh_self_confirmed"));
  await expect(card2).not.toContainText(t("documents.evVerified"));

  // survive a reload (server state)
  await page.reload();
  await expect(page.getByTestId("story-1")).toContainText(t("documents.evVerified"));
  await expect(page.getByTestId("story-2")).toContainText(t("storyBank.v_self_confirmed"));
  await expect(page.getByTestId("story-count")).toHaveText(t("storyBank.resultsCount", { n: 2 }));
  await expectNoOverflow(page, ui, "story bank list with stories");
  await expectAccessibleNames(page, ui, "story bank list with stories");

  // share with explicit consent, then revoke
  const first = page.getByTestId("story-1");
  await first.getByRole("button", { name: t("storyBank.shareToggle"), exact: true }).click();
  expect(db.grants).toHaveLength(0);                                                          // opening the panel shared nothing
  await first.getByLabel(t("storyBank.shareWorkspace"), { exact: true }).selectOption("4");
  const shareBtn = first.getByRole("button", { name: t("storyBank.shareAction") });
  await expect(shareBtn).toBeDisabled();                                                      // a workspace alone is not consent
  await first.getByRole("checkbox", { name: t("wsMgmt.shareConsent") }).check();
  await shareBtn.click();
  await expect(first).toContainText(t("storyBank.shareSharedWith", { name: "Alpha" }));
  expect(db.shareBodies[0].consent).toBe(true);
  await first.getByRole("button", { name: t("storyBank.shareStop") }).click();
  await expect(first).toContainText(t("storyBank.shareNone"));
  expect(db.grants).toHaveLength(0);

  // use in Practice: chosen one by one, with explicit consent; only ids reach the server; the question is shown verbatim
  await page.goto("/practice");
  await page.getByLabel(t("practice.targetRole")).fill("Registered Nurse");
  await page.getByLabel(t("practice.industry")).fill("healthcare");
  await page.getByRole("checkbox", { name: /Led the ward migration/ }).check();
  const start = page.getByRole("button", { name: t("practice.start") });
  await expect(start).toBeDisabled();                                                         // chosen, not yet consented
  await page.getByRole("checkbox", { name: t("storyBank.pickerConsent") }).check();
  await expect(start).toBeEnabled();
  await expectNoEnglishLeak(page, ui, "practice with stories");
  await start.click();
  await expect(page.getByRole("heading", { name: SB_QUESTION })).toBeVisible();
  const cfg = db.practiceBody?.configuration as Record<string, unknown>;
  expect(cfg.story_ids).toEqual([1]);
  expect(cfg.confirm_story_use).toBe(true);
  expect(JSON.stringify(db.practiceBody)).not.toContain("ward moved to a new records system");

  // delete: asks first and says what goes; afterwards the empty state is honest and survives a reload
  await page.goto("/documents");
  for (const id of [2, 1]) {
    await page.getByTestId(`story-${id}`).getByRole("button", { name: t("storyBank.delete"), exact: true }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText(t("storyBank.deleteBody"));
    await dialog.getByRole("button", { name: t("storyBank.delete"), exact: true }).click();
    await expect(page.getByTestId(`story-${id}`)).toHaveCount(0);
  }
  await expect(page.getByText(t("storyBank.empty"))).toBeVisible();
  await page.reload();
  await expect(page.getByText(t("storyBank.empty"))).toBeVisible();
}

/** Test-only browser response wrapper: retain the real Next router and forward its call unchanged. */
async function observeRealWorkspaceRouter(page: Page) {
  await page.route("**/_next/static/chunks/app/workspaces/**/page-*.js", async route => {
    if (!new URL(route.request().url()).pathname.includes("/%5Bid%5D/") && !new URL(route.request().url()).pathname.includes("/[id]/")) return route.continue();
    const response = await route.fetch();
    const source = await response.text();
    const pattern = /await\s+([\w$]+(?:\.[\w$]+)*)\.workspaces\.remove\(([\w$]+)\.id,([\w$]+)\.trim\(\)\),([\w$]+)\.push\("\/workspaces"\)/g;
    const matches = [...source.matchAll(pattern)];
    if (matches.length !== 1) throw new Error("Expected exactly one observable Workspace delete navigation");
    const transformed = source.replace(pattern, (_match, api, workspace, typed, router) => `await ${api}.workspaces.remove(${workspace}.id,${typed}.trim()),(console.info("ask4mo_router_push_workspaces"),${router}.push("/workspaces"))`);
    await route.fulfill({ response, body: transformed });
  });
}

/** Workspaces: create, invite, verified accept, share with consent, revoke, remove member, delete. */
async function workspaceJourney(page: Page, ui: string, testInfo: TestInfo) {
  const t = (k: string, v?: Record<string, string | number>) => T(ui, k, v);
  const f = freshWs();
  if (ui === "nl" && process.env.ASK4MO_ROUTER_OBSERVE === "1") await observeRealWorkspaceRouter(page);
  await installWorkspaceMock(page, f, ui);
  const storyLabel = `${t("wsMgmt.typeStory")} #5`;

  await page.goto("/workspaces");
  await page.getByLabel(t("workspaces.namePlaceholder")).fill("Team Alpha");
  await page.getByRole("button", { name: t("workspaces.create") }).click();
  await page.getByRole("link", { name: `${t("wsMgmt.openAction")}: Team Alpha` }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Team Alpha" })).toBeVisible();
  await expectNoEnglishLeak(page, ui, "workspace detail (owner)");

  // invite: the note says the mail was handed over, never that it was delivered
  await page.getByLabel(t("wsMgmt.inviteEmail")).fill(PEOPLE.B.email);
  await page.getByRole("button", { name: t("wsMgmt.inviteSend") }).click();
  await expect(page.getByText(t("wsMgmt.inviteSubmitted"))).toBeVisible();

  // verified accept: opening the link accepts nothing; only the explicit button does
  f.cur = "B";
  await page.goto("/workspaces/accept?token=tok-ben-1");
  await expect(page.getByText("Team Alpha")).toBeVisible();
  expect(f.invite?.status).toBe("pending");
  await expectNoEnglishLeak(page, ui, "invitation page");
  await page.getByRole("button", { name: t("wsMgmt.acceptButton") }).click();
  await expect(page.getByText(t("wsMgmt.acceptDone"))).toBeVisible();
  await page.getByRole("link", { name: t("wsMgmt.openWorkspaceAfter") }).click();
  await expect(page.getByRole("link", { name: "Team Alpha", exact: true })).toBeVisible();
  await expect(page.getByText(t("workspaces.privacyNote"))).toBeVisible();
  await expect(page.getByText(t("workspaces.emptyShares")).first()).toBeVisible();            // joining shared nothing

  // share ONE story with explicit consent
  f.cur = "A";
  await page.goto("/workspaces/7");
  await expect(page.getByText(t("wsMgmt.sharedEmpty"))).toBeVisible();
  await page.getByLabel(t("wsMgmt.shareItem"), { exact: true }).selectOption("5");
  const share = page.getByRole("button", { name: t("wsMgmt.shareAction") });
  await expect(share).toBeDisabled();
  await page.getByRole("checkbox", { name: t("wsMgmt.shareConsent") }).check();
  await expect(share).toBeEnabled();
  await share.click();
  await expect(page.getByText(t("wsMgmt.shareDone"))).toBeVisible();
  expect(f.calls).toContain("POST /shares");
  await expectNoOverflow(page, ui, "workspace detail with a shared item");
  await expectAccessibleNames(page, ui, "workspace detail with a shared item");

  // the member sees only that item, read-only, and the owner's user content is not translated
  f.cur = "B";
  await page.goto("/workspaces");
  await expect(page.getByText(storyLabel).first()).toBeVisible();
  await page.getByRole("button", { name: `${t("wsMgmt.viewShared")}: ${storyLabel}` }).click();
  await expect(page.getByText("We shipped the product on time")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(`^(${esc(t("storyBank.edit"))}|${esc(t("storyBank.delete"))})$`, "i") })).toHaveCount(0);

  // revoke: the member loses access at once
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: `${t("wsMgmt.stopSharing")}: ${storyLabel}` }).click();
  await expect(page.getByText(t("wsMgmt.shareStopped"))).toBeVisible();
  f.cur = "B";
  await page.goto("/workspaces");
  await expect(page.getByText(storyLabel)).toHaveCount(0);

  // remove member (accessible, explicit confirmation; safe default focus)
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: `${t("wsMgmt.removeMember")}: ${maskedEmail("B")}` }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: t("common.cancel") })).toBeFocused();
  await dialog.getByRole("button", { name: t("wsMgmt.removeConfirm") }).click();
  await expect(page.getByText(t("wsMgmt.memberRemoved"))).toBeVisible();
  f.cur = "B";
  await page.goto("/workspaces/7");
  await expect(page.getByText(t("wsMgmt.errNotFound"))).toBeVisible();

  // delete: only with the exact name typed
  f.cur = "A";
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: t("wsMgmt.deleteAction") }).click();
  const del = page.getByRole("alertdialog");
  await del.getByLabel(t("wsMgmt.confirmNameLabel")).fill("wrong name");
  await del.getByRole("button", { name: t("wsMgmt.deleteConfirm") }).click();
  expect(f.ws).not.toBeNull();                                                                // refused client side, nothing sent
  await del.getByLabel(t("wsMgmt.confirmNameLabel")).fill("Team Alpha");
  const diag = new WorkspaceDeletionDiagnostics();
  const enabled = ui === "nl";
  const markUrl = () => { const path = new URL(page.url()).pathname; diag.record(path === "/workspaces" ? "url_list" : path === "/workspaces/7" ? "url_detail" : "url_other"); };
  if (enabled) {
    diag.record((await del.getByLabel(t("wsMgmt.confirmNameLabel")).inputValue()).trim() === f.ws?.name ? "confirm_matches" : "confirm_mismatch");
    page.on("request", req => { const path = new URL(req.url()).pathname; if (path === "/api/v1/workspaces/7/delete" && req.method() === "POST") diag.record("delete_request"); else if (path === "/workspaces" && req.headers()["rsc"] === "1") diag.record("route_data_request"); });
    page.on("response", res => { const path = new URL(res.url()).pathname; if (path === "/api/v1/workspaces/7/delete" && res.request().method() === "POST") diag.record(res.status() === 200 && f.ws === null ? "delete_200_fake_absent" : "delete_other"); else if (path === "/workspaces" && res.request().headers()["rsc"] === "1") diag.record(res.status() === 200 ? "route_data_200" : "route_data_other"); });
    page.on("framenavigated", frame => { if (frame === page.mainFrame()) markUrl(); });
    page.on("console", msg => { if (msg.type() === "info" && msg.text() === "ask4mo_router_push_workspaces") diag.record("router_push_invoked"); if (msg.type() === "error") diag.record(/^Failed to load resource: the server responded with a status of [1-5]\d{2}/.test(msg.text()) ? "console_http_error" : "console_other"); });
    page.on("pageerror", () => diag.record("page_error"));
    markUrl();
  }
  try {
    await del.getByRole("button", { name: t("wsMgmt.deleteConfirm") }).click();
    await expect(page).toHaveURL(/\/workspaces$/);
    if (enabled) diag.record("assertion_passed");
  } catch (error) {
    if (enabled) diag.record("assertion_failed");
    throw error;
  } finally {
    if (enabled) {
      markUrl();
      diag.record(await del.isVisible() ? "dialog_visible" : "dialog_hidden");
      diag.record(await page.getByRole("heading", { level: 1, name: "Team Alpha" }).isVisible() ? "detail_visible" : "detail_hidden");
      const evidence = JSON.stringify(diag.snapshot());
      console.log("workspace-deletion-diagnostics " + evidence); // Fixed event labels and bounded timings only.
      await testInfo.attach("workspace-deletion-diagnostics", { body: evidence, contentType: "application/json" });
    }
  }
  await expect(page.getByText(t("workspaces.emptyWorkspaces"))).toBeVisible();
  expect(f.ws).toBeNull();
}

// ───────────────────────────── one run per language ─────────────────────────────

for (const ui of LOCALES) {
  const t = (k: string, v?: Record<string, string | number>) => T(ui, k, v);

  test.describe(`06B journey [${ui}]`, () => {
    for (const s of SURFACES) {
      test(`${s.name}: localised chrome, no English leak, no overflow at 768 and 1280, named controls`, async ({ page }) => {
        await installSweepMock(page, { ui });
        await page.goto(s.path);
        await expect(page.locator("html")).toHaveAttribute("lang", ui);
        await expect(page.locator("main, [role=main]").first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        await expectNoEnglishLeak(page, ui, s.name);
        // the browser's own file-control text (browser language, not ours) must not be visible
        expect(await page.locator("body").innerText(), `${ui} ${s.name}: native file control text`).not.toMatch(/Choose File|No file chosen/);
        await expectAccessibleNames(page, ui, s.name);
        await expectNoOverflow(page, ui, s.name);
        // Review evidence only: git-ignored (frontend/playwright-report/), never committed.
        await page.screenshot({ path: `playwright-report/06b-screens/${ui}-${s.name}.png`, fullPage: true });
      });
    }

    test("the protected slogan is untranslated", async ({ page }) => {
      await installSweepMock(page, { ui });
      await page.goto("/app");
      await expect(page.getByText(BRAND_SLOGAN, { exact: true }).first()).toBeVisible();
      expect(t("common.tagline")).toBe(BRAND_SLOGAN);
    });

    test("onboarding: localised, language choices never touch career geography", async ({ page }) => {
      const patches: Record<string, unknown>[] = [];
      const onboardingCalls: Record<string, unknown>[] = [];
      await installSweepMock(page, { ui, onboarding: true, patches, onboardingCalls });
      await page.goto("/onboarding");
      await expect(page.locator("html")).toHaveAttribute("lang", ui);
      await expect(page.getByRole("heading", { name: t("onboarding.welcomeTitle") })).toBeVisible();
      await expectNoEnglishLeak(page, ui, "onboarding welcome");
      await page.getByRole("button", { name: t("onboarding.getStarted") }).click();
      await expect(page.getByRole("heading", { name: t("onboarding.aboutTitle") })).toBeVisible();
      await page.getByRole("button", { name: t("onboarding.next") }).click();
      await expect(page.getByRole("heading", { name: t("onboarding.careerTitle") })).toBeVisible();
      await page.getByLabel(t("geography.label")).selectOption("fr");                          // an explicit market choice, in any language
      await expectNoEnglishLeak(page, ui, "onboarding career");
      await page.getByRole("button", { name: t("onboarding.next") }).click();
      await page.getByRole("button", { name: t("onboarding.next") }).click();                  // coaching
      await expect(page.getByRole("heading", { name: t("onboarding.languageTitle") })).toBeVisible();
      const conv = otherLocale(ui);
      await page.getByLabel(t("settings.conversationLanguage")).selectOption(conv);
      await expect.poll(() => patches.some((p) => "conversation_language" in p)).toBe(true);
      // language preferences carry ONLY the language field; geography was sent solely by the explicit career step
      for (const p of patches.filter((p) => "conversation_language" in p || "interface_locale" in p)) {
        expect(Object.keys(p)).toHaveLength(1);
      }
      const geoPatches = patches.filter((p) => "career_geography" in p);
      expect(geoPatches.length).toBeGreaterThan(0);
      for (const p of geoPatches) expect(p.career_geography).toBe("fr");
      await expectNoEnglishLeak(page, ui, "onboarding language");
      await page.getByRole("button", { name: t("onboarding.next") }).click();                  // privacy
      await expect(page.getByRole("heading", { name: t("onboarding.privacyTitle") })).toBeVisible();
      await page.getByRole("button", { name: t("onboarding.next") }).click();                  // review
      await expect(page.getByRole("heading", { name: t("onboarding.reviewTitle") })).toBeVisible();
      await expect(page.getByText(t(`geography.fr`), { exact: true })).toBeVisible();
      // languages are shown by their own names, never as raw codes
      await expect(page.getByText(APP_LOCALES.find((l) => l.code === ui)!.nativeLabel, { exact: true }).first()).toBeVisible();
      await expectNoEnglishLeak(page, ui, "onboarding review");
    });

    test("settings: interface and conversation languages are independent and never set geography", async ({ page }) => {
      const patches: Record<string, unknown>[] = [];
      await installSweepMock(page, { ui, geography: "de", patches });
      await page.goto("/settings");
      const conv = otherLocale(ui);
      const iface = page.getByLabel(t("settings.interfaceLanguage"));
      await expect(iface).toHaveValue(ui);
      await page.getByLabel(t("settings.conversationLanguage")).selectOption(conv);
      await expect.poll(() => patches.length).toBeGreaterThan(0);
      expect(patches[0]).toEqual({ conversation_language: conv });
      expect(JSON.stringify(patches)).not.toContain("career_geography");
      await expect(page.locator("html")).toHaveAttribute("lang", ui);                          // chrome did not follow the conversation language
      await expect(page.getByLabel(t("geography.label"))).toHaveValue("de");                  // geography is its own account setting
      await expect(page.getByLabel(t("settings.interfaceLanguage"))).toHaveValue(ui);
    });

    test("language ownership: chrome follows the interface language, Mo-voiced text the conversation language", async ({ page }) => {
      for (const conv of [ui, otherLocale(ui)]) {
        await page.unroute("**/api/v1/**");
        const chatBodies: unknown[] = [];
        await installSweepMock(page, { ui, conv, chat: CHAT_NO_EVIDENCE, chatBodies });
        await page.goto("/prepare");
        await page.getByLabel(t("prepare.askTheCoach")).fill("What should I focus on?");
        await page.getByRole("button", { name: t("prepare.ask"), exact: true }).click();
        await expect(page.getByText(T(conv, "coach.insufficientEvidence"))).toBeVisible();      // Mo note: conversation language
        if (conv !== ui) await expect(page.getByText(t("coach.insufficientEvidence"))).toHaveCount(0);
        await expect(page.getByText(t("prepare.evidenceSourcesOne"))).toBeVisible();            // chrome: interface language
        await page.getByText(t("prepare.evidenceSourcesOne")).click();
        await expect(page.getByRole("link", { name: "O*NET Product manager" })).toHaveAttribute("href", "https://example.org/onet");
        const body = chatBodies[0] as Record<string, unknown>;
        expect(body.conversation_language).toBe(conv);
        expect(body).not.toHaveProperty("interface_locale");
        expect(body).not.toHaveProperty("career_geography");
      }
    });

    test("dates and numbers follow the interface language, not the browser", async ({ page }) => {
      await installSweepMock(page, { ui });
      await page.goto("/history");
      await expect(page.getByText(dateIn(ui, "2026-09-01T10:00:00Z"), { exact: false }).first()).toBeVisible();
      await page.unroute("**/api/v1/**");
      await installSweepMock(page, { ui });
      await page.route("**/api/v1/progress", (route) => route.fulfill({
        status: 200, contentType: "application/json", headers: { "x-request-id": "r" },
        body: JSON.stringify({ interviews_completed: 1, answers_evaluated: 1234, average_practice_score: 72.5, most_common_improvement_area: null, average_answer_seconds: 42, recent_interviews: [{ id: 30, target_role: "Nurse", created_at: "2026-09-01T10:00:00Z" }] }),
      }));
      await page.goto("/progress");
      await expect(page.getByText(`${new Intl.NumberFormat(ui, { maximumFractionDigits: 1 }).format(72.5)}/100`)).toBeVisible();
      await expect(page.getByText(new Intl.NumberFormat(ui).format(1234), { exact: true })).toBeVisible();
      await expect(page.getByText(dateIn(ui, "2026-09-01T10:00:00Z"), { exact: false }).first()).toBeVisible();
    });

    test("error states render localised (server failure on every data surface)", async ({ page }) => {
      for (const path of ["/history", "/progress", "/documents", "/workspaces", "/opportunities"]) {
        await page.unroute("**/api/v1/**");
        await installSweepMock(page, { ui, failAll: true });
        await page.goto(path);
        await expect(page.getByRole("alert").first(), `${ui} ${path}`).toBeVisible();
        await page.waitForLoadState("networkidle");
        await expectNoEnglishLeak(page, ui, `${path} (error state)`);
        await expectAccessibleNames(page, ui, `${path} (error state)`);
      }
    });

    test("keyboard: skip link, language menu and Settings language controls are operable with localised names", async ({ page }) => {
      await installSweepMock(page, { ui });
      await page.goto("/settings");
      await page.keyboard.press("Tab");
      await expect(page.getByRole("link", { name: t("common.skipToContent") })).toBeFocused();
      const menuButton = page.getByTestId("language-menu-button");
      await menuButton.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("menuitemradio")).toHaveCount(7);
      await page.keyboard.press("Escape");
      const iface = page.getByLabel(t("settings.interfaceLanguage"));
      await iface.focus();
      await expect(iface).toBeFocused();
      await expect(page.getByLabel(t("settings.conversationLanguage"))).toBeVisible();
      await expect(page.getByLabel(t("settings.dictationLanguage"))).toBeVisible();
    });

    test("Story Bank journey: create, evidence, verify, use in Practice with consent, share with consent, revoke, delete, survive reload", async ({ page }) => {
      await storyBankJourney(page, ui);
    });

    test("Story Bank: a failed load is explained in the interface language and retryable; the editor is keyboard-operable", async ({ page }) => {
      const db = await installStoryBankMock(page, ui, { failList: true });
      await page.goto("/documents");
      const alert = page.getByRole("alert").filter({ has: page.getByRole("button", { name: t("storyBank.retry") }) });
      await expect(alert).toBeVisible();
      await expect(alert).toContainText(t("states.serverError"));
      db.allow = true;
      await alert.getByRole("button", { name: t("storyBank.retry") }).click();
      await expect(page.getByText(t("storyBank.empty"))).toBeVisible();
      await page.getByRole("button", { name: t("storyBank.newStory") }).focus();
      await page.keyboard.press("Enter");
      await expect(page.getByLabel(t("storyBank.fieldTitle"), { exact: true })).toBeFocused();
      for (const k of ["fieldSituation", "fieldTask", "fieldAction", "fieldResult", "fieldTags"]) {
        await expect(page.getByLabel(t(`storyBank.${k}`), { exact: true })).toBeVisible();
      }
      await expect(page.getByRole("search", { name: t("storyBank.searchRegion") })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("button", { name: t("storyBank.newStory") })).toBeFocused();
      await expectNoOverflow(page, ui, "story editor");
    });

    test("Workspaces journey: create, invite, verified accept, share with consent, revoke, remove member, delete", async ({ page }, testInfo) => {
      await workspaceJourney(page, ui, testInfo);
    });

    test("Workspaces: a missing workspace and a server error are explained in the interface language; dialogs trap focus", async ({ page }) => {
      const f: WsFake = freshWs();
      f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
      f.members = [{ who: "A", role: "workspace_owner" }, { who: "B", role: "workspace_member" }];
      await installWorkspaceMock(page, f, ui);
      f.cur = "A";
      f.detailStatus = 404;
      await page.goto("/workspaces/7");
      await expect(page.getByText(t("wsMgmt.errNotFound"))).toBeVisible();
      await expect(page.getByRole("link", { name: t("wsMgmt.backToList") })).toBeVisible();
      f.detailStatus = 500;
      await page.goto("/workspaces/7");
      await expect(page.getByRole("alert")).toBeVisible();
      await expect(page.getByRole("button", { name: t("states.retry") })).toBeVisible();
      await expectNoEnglishLeak(page, ui, "workspace server error");
      f.detailStatus = 200;
      await page.goto("/workspaces/7");
      await page.getByRole("button", { name: `${t("wsMgmt.removeMember")}: ${maskedEmail("B")}` }).click();
      await expect(page.getByRole("alertdialog")).toBeVisible();
      await expectNoOverflow(page, ui, "workspace dialog");
      await page.keyboard.press("Escape");
      await expect(page.getByRole("alertdialog")).toHaveCount(0);
      expect(f.calls.some((c) => c.includes("/remove"))).toBe(false);
    });
  });
}


test("router minimal: synthetic Workspace delete using real Next router", async ({ page }, testInfo) => {
  test.skip(process.env.ASK4MO_ROUTER_OBSERVE !== "1", "requires isolated router observation build");
  const ui = "nl", t = (k: string) => T(ui, k);
  const f = freshWs();
  f.ws = { id: 7, name: "Team Alpha", status: "active", owner: "A" };
  f.members = [{ who: "A", role: "workspace_owner" }];
  await observeRealWorkspaceRouter(page);
  await installWorkspaceMock(page, f, ui);
  const diag = new WorkspaceDeletionDiagnostics();
  page.on("console", msg => { if (msg.type() === "info" && msg.text() === "ask4mo_router_push_workspaces") diag.record("router_push_invoked"); else if (msg.type() === "error") diag.record("console_other"); });
  page.on("pageerror", () => diag.record("page_error"));
  page.on("request", req => { const path = new URL(req.url()).pathname; if (path === "/api/v1/workspaces/7/delete" && req.method() === "POST") diag.record("delete_request"); else if (path === "/workspaces" && req.headers()["rsc"] === "1") diag.record("route_data_request"); });
  page.on("response", res => { const path = new URL(res.url()).pathname; if (path === "/api/v1/workspaces/7/delete" && res.request().method() === "POST") diag.record(res.status() === 200 && f.ws === null ? "delete_200_fake_absent" : "delete_other"); else if (path === "/workspaces" && res.request().headers()["rsc"] === "1") diag.record(res.status() === 200 ? "route_data_200" : "route_data_other"); });
  const markUrl = () => { const path = new URL(page.url()).pathname; diag.record(path === "/workspaces" ? "url_list" : path === "/workspaces/7" ? "url_detail" : "url_other"); };
  page.on("framenavigated", frame => { if (frame === page.mainFrame()) markUrl(); });
  await page.goto("/workspaces/7");
  await page.getByRole("button", { name: t("wsMgmt.deleteAction") }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByLabel(t("wsMgmt.confirmNameLabel")).fill("Team Alpha");
  diag.record((await dialog.getByLabel(t("wsMgmt.confirmNameLabel")).inputValue()).trim() === f.ws?.name ? "confirm_matches" : "confirm_mismatch");
  const response = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/workspaces/7/delete" && r.request().method() === "POST");
  try {
    await dialog.getByRole("button", { name: t("wsMgmt.deleteConfirm") }).click();
    expect((await response).status()).toBe(200);
    await expect(page).toHaveURL(/\/workspaces$/);
    diag.record("assertion_passed");
    expect(f.ws).toBeNull();
    expect(diag.snapshot().events.some(e => e.event === "router_push_invoked")).toBe(true);
  } catch (error) { diag.record("assertion_failed"); throw error; }
  finally {
    markUrl();
    diag.record(await dialog.isVisible() ? "dialog_visible" : "dialog_hidden");
    diag.record(await page.getByRole("heading", { level: 1, name: "Team Alpha" }).isVisible() ? "detail_visible" : "detail_hidden");
    const evidence = JSON.stringify(diag.snapshot());
    console.log("workspace-router-minimal-diagnostics " + evidence);
    await testInfo.attach("workspace-router-minimal-diagnostics", { body: evidence, contentType: "application/json" });
  }
});
