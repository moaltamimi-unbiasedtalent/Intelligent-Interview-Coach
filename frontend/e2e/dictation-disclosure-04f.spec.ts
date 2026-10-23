import { expect, test, type Page, type Request } from "@playwright/test";

// 04F: browser dictation disclosure and verification, with a MOCKED SpeechRecognition (no microphone,
// no vendor service, no network speech). This is engineering evidence only: it is NOT a live browser
// speech check and NOT a legal review.

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

type Rec = {
  lang: string; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null;
  onresult: ((e: unknown) => void) | null;
};

async function installFakeSpeech(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __recs: unknown[]; __mediaRequested: boolean; SpeechRecognition: unknown };
    w.__recs = [];
    w.__mediaRequested = false;
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onresult: ((e: unknown) => void) | null = null;
      start() { w.__recs.push(this); this.onstart?.(); }
      stop() { this.onend?.(); }
      abort() {}
    }
    w.SpeechRecognition = FakeRecognition;
    const md = navigator.mediaDevices;
    if (md && md.getUserMedia) {
      md.getUserMedia = (() => { w.__mediaRequested = true; return Promise.reject(new Error("blocked in test")); }) as typeof md.getUserMedia;
    }
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

async function fail(page: Page, error: string) {
  await page.evaluate((code) => {
    const recs = (window as unknown as { __recs: Rec[] }).__recs;
    const r = recs[recs.length - 1];
    r.onerror?.({ error: code });
    r.onend?.();
  }, error);
}

test("disclosure is visible before the first microphone use and stays readable", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  await page.goto("/prepare");
  const notice = page.getByTestId("dictation-browser-notice");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("may send your voice to its provider");
  await expect(notice).toContainText("does not store your audio");
  // Nothing has been started or requested at this point.
  expect(await page.evaluate(() => (window as unknown as { __recs: unknown[] }).__recs.length)).toBe(0);
  // The microphone control is described by the disclosure for assistive technology.
  const mic = page.getByRole("button", { name: "Start dictation" });
  await expect(mic).toHaveAccessibleDescription(/may send your voice to its provider/);
  await mic.click();
  await expect(notice).toBeVisible();
  await page.getByRole("button", { name: "Stop dictation" }).click();
  await expect(notice).toBeVisible();
});

test("the selected dictation language is the only locale handed to the engine", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  await page.goto("/prepare");
  await page.getByLabel("Dictation language").selectOption("de-DE");
  await page.getByRole("button", { name: "Start dictation" }).click();
  const lang = await page.evaluate(() => (window as unknown as { __recs: Rec[] }).__recs[0].lang);
  expect(lang).toBe("de-DE");
  // Bounded: exactly the seven speech languages, Russian is not offered.
  const options = await page.getByLabel("Dictation language").locator("option").evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value));
  expect(options).toEqual(["en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL"]);
});

test("permission denied and unsupported-language states show an explicit message and typing still works", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  await page.goto("/prepare");
  const goal = page.getByLabel("What interview are you preparing for?");
  await goal.fill("keep this text");

  await page.getByRole("button", { name: "Start dictation" }).click();
  await fail(page, "not-allowed");
  await expect(page.getByRole("status").filter({ hasText: "Microphone access was blocked" })).toBeVisible();
  await expect(page.getByTestId("dictation-browser-notice")).toBeVisible();

  await page.getByRole("button", { name: "Start dictation" }).click();
  await fail(page, "language-not-supported");
  await expect(page.getByRole("status").filter({ hasText: "can’t recognise speech in the selected dictation language" })).toBeVisible();

  await expect(goal).toHaveValue("keep this text");
  await goal.click();
  await page.keyboard.type(" and more");
  await expect(goal).toHaveValue("keep this text and more");
});

test("dictation sends no audio to Ask4Mo: no media capture, no websocket, no speech upload", async ({ page }) => {
  await installFakeSpeech(page);
  await mock(page);
  const requests: Request[] = [];
  page.on("request", (r) => requests.push(r));
  let sockets = 0;
  page.on("websocket", () => { sockets += 1; });
  await page.goto("/prepare");
  const before = requests.length;
  await page.getByRole("button", { name: "Start dictation" }).click();
  await page.evaluate(() => {
    const r = (window as unknown as { __recs: Rec[] }).__recs[0];
    r.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: "synthetic words only" } }] });
  });
  await page.getByRole("button", { name: "Stop dictation" }).click();
  const during = requests.slice(before);
  // No request issued by the dictation interaction targets a speech endpoint or carries an audio body.
  for (const r of during) {
    expect(r.url()).not.toMatch(/\/speech\/(transcriptions|synthesis)/);
    expect(r.headers()["content-type"] ?? "").not.toMatch(/audio|multipart/);
  }
  expect(sockets).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { __mediaRequested: boolean }).__mediaRequested)).toBe(false);
});
