import { expect, test, type Page } from "@playwright/test";

// P3 / E-dictation end-to-end on a REAL page. A fake window.SpeechRecognition is
// injected before load so the production BrowserSpeechAdapter drives it — no real
// microphone, no network, no vendor call. Proves: mic → editable transcript in the
// field, NO auto-submit, typing still works.

const ACCOUNT = {
  user_id: 1, email: "user@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: ["current_market_research"], response_detail: "brief",
};
const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true,
  agent_coach_enabled: true,
};

async function installFakeSpeech(page: Page) {
  await page.addInitScript(() => {
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onresult: ((e: unknown) => void) | null = null;
      start() {
        (window as unknown as { __fakeRec: FakeRecognition }).__fakeRec = this;
        this.onstart && this.onstart();
      }
      stop() {
        this.onend && this.onend();
      }
      abort() {}
    }
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
  });
}

async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(ACCOUNT);
    if (url.includes("/capabilities")) return json(CAPS);
    return json({});
  });
}

test("Prepare: dictation fills the editable goal field and does NOT auto-submit", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  await page.goto("/prepare");

  // First-message form is shown (no run started).
  const goal = page.getByLabel("What interview are you preparing for?");
  await expect(goal).toBeVisible();

  await page.getByRole("button", { name: "Start dictation" }).click();
  await expect(page.getByRole("button", { name: "Stop dictation" })).toBeVisible();

  // Emit a final recognition result through the injected engine.
  await page.evaluate(() => {
    const r = (window as unknown as { __fakeRec: { onresult: (e: unknown) => void } }).__fakeRec;
    r.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: "prepare me for a PM interview" } }] });
  });

  // The transcript is in the editable field...
  await expect(goal).toHaveValue(/prepare me for a PM interview/);
  // ...and NOTHING was submitted (no run started, still on the form).
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("button", { name: "Start preparing" })).toBeVisible();

  // Typing still works after dictation (append).
  await goal.click();
  await page.keyboard.type(" next week");
  await expect(goal).toHaveValue(/prepare me for a PM interview next week/);
});

test("Prepare: no microphone/getUserMedia is requested by dictation setup", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  await page.addInitScript(() => {
    (window as unknown as { __mediaRequested: boolean }).__mediaRequested = false;
    const md = navigator.mediaDevices;
    if (md && md.getUserMedia) {
      const orig = md.getUserMedia.bind(md);
      md.getUserMedia = ((c?: MediaStreamConstraints) => {
        (window as unknown as { __mediaRequested: boolean }).__mediaRequested = true;
        return orig(c as MediaStreamConstraints);
      }) as typeof md.getUserMedia;
    }
  });
  await page.goto("/prepare");
  await page.getByRole("button", { name: "Start dictation" }).click();
  const requested = await page.evaluate(
    () => (window as unknown as { __mediaRequested: boolean }).__mediaRequested,
  );
  // The Web Speech API manages capture itself; the app never calls getUserMedia.
  expect(requested).toBe(false);
});
