import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";

/**
 * P10B-W9.7 - Russian is an interface/conversation language WITHOUT speech support.
 * Real Chromium with the same fake speech engines as e2e/voice.spec.ts (no mic, no audio, no vendor).
 * Proves: for a Russian conversation language Practice does not offer "Listen" (an English voice must
 * never read Cyrillic) nor live voice (the server would coerce the locale to English), the Russian
 * interface chrome is intact, dictation is unchanged (separate, supported-language capability), and
 * the supported languages (English, German) still get playback.
 */

const SID = "sess_ru";
const ru = (k: string) => translate("ru", k);

function account(conversation: string) {
  return {
    user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session",
    capabilities: [], response_detail: "brief", interface_locale: "ru", conversation_language: conversation,
    onboarding_completed: true, onboarding_step: 0,
  };
}
const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true,
  agent_coach_enabled: true, realtime_voice_enabled: true,
};

async function installFakeVoice(page: Page) {
  await page.addInitScript(() => {
    try { window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ }
    class FakeRecognition {
      lang = ""; continuous = false; interimResults = false; maxAlternatives = 1;
      onstart: (() => void) | null = null; onend: (() => void) | null = null;
      onerror: ((e: unknown) => void) | null = null; onresult: ((e: unknown) => void) | null = null;
      start() { this.onstart?.(); }
      stop() { this.onend?.(); }
      abort() {}
    }
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
    const w = window as unknown as { __spoken: string[]; __langs: string[] };
    w.__spoken = []; w.__langs = [];
    class FakeUtterance {
      text: string; lang = ""; voice: unknown = null;
      onstart: (() => void) | null = null; onend: (() => void) | null = null; onerror: (() => void) | null = null;
      onpause: (() => void) | null = null; onresume: (() => void) | null = null;
      constructor(t: string) { this.text = t; }
    }
    Object.defineProperty(window, "SpeechSynthesisUtterance", { value: FakeUtterance, configurable: true, writable: true });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        getVoices: () => [],
        speak: (u: FakeUtterance) => { w.__spoken.push(u.text); w.__langs.push(u.lang); u.onstart?.(); },
        cancel: () => {}, pause: () => {}, resume: () => {},
      },
    });
  });
}

async function mockPractice(page: Page, conversation: string) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (b: unknown, s = 200) =>
      route.fulfill({ status: s, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/auth/me")) return json(account(conversation));
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.match(/\/interviews\/[^/]+$/) && method === "GET")
      return json({
        session_id: SID, state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
        current_question: { question_id: 1, question: "Tell me about a decision you owned.", question_type: "behavioural", competency: "judgement", difficulty: "moderate" },
        report_available: false, last_evaluation: null, target_role: "Senior PM", deep_dive: null,
        error: null, error_recoverable: false, cumulative_cost_usd: 0,
      });
    return json({});
  });
}

test("Russian conversation: Practice offers NO Listen and NO live voice; Russian chrome and dictation intact", async ({ page }) => {
  await installFakeVoice(page);
  await mockPractice(page, "ru");
  await page.goto(`/practice?session=${SID}`);
  await expect(page.getByRole("heading", { name: /Tell me about a decision/ })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  // No playback control and no realtime control for an unsupported speech language.
  await expect(page.getByRole("button", { name: ru("voice.listenQuestion") })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Listen to the question/ })).toHaveCount(0);
  await expect(page.getByTestId("realtime-practice")).toHaveCount(0);
  // Russian answer chrome is present, and dictation (a separate supported-language control) is unchanged.
  await expect(page.getByRole("button", { name: ru("practice.submitAnswer") })).toBeVisible();
  await expect(page.getByRole("button", { name: ru("dictation.start") })).toBeVisible();
  // Nothing was ever spoken.
  const spoken = await page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken);
  expect(spoken).toHaveLength(0);
});

for (const [conv, speechLang] of [["en", "en-US"], ["de", "de-DE"]] as const) {
  test(`${conv} conversation under a Russian interface: Listen and live voice remain available`, async ({ page }) => {
    await installFakeVoice(page);
    await mockPractice(page, conv);
    await page.goto(`/practice?session=${SID}`);
    await expect(page.getByRole("heading", { name: /Tell me about a decision/ })).toBeVisible();
    // Interface is Russian, so the Listen label is the Russian one; playback uses the CONVERSATION locale.
    await page.getByRole("button", { name: ru("voice.listenQuestion") }).click();
    const langs = await page.evaluate(() => (window as unknown as { __langs: string[] }).__langs);
    expect(langs).toContain(speechLang);
    await expect(page.getByTestId("realtime-practice")).toHaveCount(1);
  });
}
