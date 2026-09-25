import { expect, test, type Page } from "@playwright/test";

// P7 / E5 voice experience end-to-end on REAL pages. Fake window.SpeechRecognition (STT)
// and window.speechSynthesis (TTS) are injected before load so the production adapters
// drive them — no microphone, no audio, no vendor call. Proves: Listen speaks the VISIBLE
// text, Stop stops, Speak fills the editable transcript, nothing auto-submits, and TTS
// never auto-opens the mic. Backend mocked at the network layer.

const SID = "sess_e2e";
const ACCOUNT = {
  user_id: 1, email: "user@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};
const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true,
  agent_coach_enabled: true,
};

async function installFakeVoice(page: Page) {
  await page.addInitScript(() => {
    // --- fake STT (mirrors the P3 dictation e2e) ---
    class FakeRecognition {
      lang = ""; continuous = false; interimResults = false; maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onresult: ((e: unknown) => void) | null = null;
      start() { (window as unknown as { __fakeRec: FakeRecognition }).__fakeRec = this; this.onstart?.(); }
      stop() { this.onend?.(); }
      abort() {}
    }
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;

    // --- fake TTS ---
    const w = window as unknown as { __spoken: string[]; __cancels: number };
    w.__spoken = [];
    w.__cancels = 0;
    class FakeUtterance {
      text: string; lang = ""; voice: unknown = null;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onpause: (() => void) | null = null;
      onresume: (() => void) | null = null;
      constructor(t: string) { this.text = t; }
    }
    // speechSynthesis is a read-only getter on Window in real browsers, so a plain
    // assignment silently no-ops — define the property instead.
    Object.defineProperty(window, "SpeechSynthesisUtterance", { value: FakeUtterance, configurable: true, writable: true });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        getVoices: () => [],
        speak: (u: FakeUtterance) => { w.__spoken.push(u.text); u.onstart?.(); },
        cancel: () => { w.__cancels += 1; },
        pause: () => {}, resume: () => {},
      },
    });
  });
}

const spoken = (page: Page) => page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken);

function question(id: number) {
  return { question_id: id, question: `Question ${id}: tell me about a decision.`, question_type: "behavioural", competency: "judgement", difficulty: "moderate" };
}
function baseState(over: Record<string, unknown> = {}) {
  return {
    session_id: SID, state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
    current_question: question(1), report_available: false, last_evaluation: null,
    target_role: "Senior PM", deep_dive: null, error: null, error_recoverable: false,
    cumulative_cost_usd: 0, ...over,
  };
}
const EVAL = {
  overall_score: 74, relevance: 7, structure: 7, evidence: 7, role_knowledge: 7,
  problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add metrics"], missing_evidence: [],
  stronger_answer_structure: "STAR.", improved_example_answer: "", follow_up_question: "And then?",
};

async function mockPractice(page: Page) {
  const store = { current: baseState() };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (b: unknown, s = 200) =>
      route.fulfill({ status: s, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/auth/me")) return json(ACCOUNT);
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.match(/\/interviews\/[^/]+\/answers$/) && method === "POST") {
      store.current = baseState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL });
      return json(store.current);
    }
    if (url.match(/\/interviews\/[^/]+$/) && method === "GET") return json(store.current);
    return json({});
  });
}

test("Practice: Listen speaks the question; Speak fills transcript; no auto-submit; explicit Submit", async ({ page }) => {
  await installFakeVoice(page);
  await mockPractice(page);
  await page.goto(`/practice?session=${SID}`);

  // Question renders.
  await expect(page.getByRole("heading", { name: /tell me about a decision/i })).toBeVisible();

  // Listen speaks the VISIBLE question text.
  await page.getByRole("button", { name: /listen to the question/i }).click();
  expect((await spoken(page)).join(" ")).toContain("tell me about a decision");

  // Speak answer via dictation → editable transcript in the answer field, NO auto-submit.
  await page.getByRole("button", { name: "Start dictation" }).click();
  await page.evaluate(() => {
    const r = (window as unknown as { __fakeRec: { onresult: (e: unknown) => void } }).__fakeRec;
    r.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: "I chose the pragmatic option" } }] });
  });
  const answer = page.getByLabel("Your answer");
  await expect(answer).toHaveValue(/I chose the pragmatic option/);
  // Still awaiting an answer (nothing auto-submitted).
  await expect(page.getByRole("heading", { name: /tell me about a decision/i })).toBeVisible();
  // Edit remains possible.
  await answer.click();
  await page.keyboard.type(" after weighing the risks");
  await expect(answer).toHaveValue(/pragmatic option after weighing the risks/);
  // Explicit submit advances to evaluation.
  await page.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByText(/74/)).toBeVisible();
});

async function mockPrepare(page: Page) {
  const run = {
    run_id: "run_e2e", status: "completed", response: "Focus on measurable impact.",
    tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false,
    memory_count: 0, memory_loaded: [], awaiting_human_input: false, pending_action: null,
    handoff_approved: false, events: [], tool_calls: [], warnings: [], step_count: 1, turn_step_count: 1,
    conversation: [
      { role: "user", content: "Prep me for a PM interview" },
      { role: "assistant", content: "Focus on measurable impact.", response_id: "run_e2e:1" },
    ],
    presentation: { answer: "Focus on measurable impact.", details: "", has_details: false, next_step: null },
    preparation_context: null, resolved_occupation: null, resolved_geography: null, cache_hits: 0, cache_misses: 0,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (b: unknown, s = 200) =>
      route.fulfill({ status: s, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/auth/me")) return json(ACCOUNT);
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.match(/\/agent\/run$/) && method === "POST") return json(run);
    if (url.match(/\/agent\/runs\/[^/]+$/) && method === "GET") return json(run);
    return json({});
  });
}

test("Prepare: Mo response can be listened to; TTS does not auto-open the mic", async ({ page }) => {
  await installFakeVoice(page);
  await mockPrepare(page);
  await page.goto("/prepare");

  await page.getByLabel("What interview are you preparing for?").fill("Prep me for a PM interview");
  await page.getByRole("button", { name: "Start preparing" }).click();

  // Mo's response renders, with a Listen control.
  await expect(page.getByText("Focus on measurable impact.")).toBeVisible();
  const listen = page.getByRole("button", { name: /^listen$/i }).first();
  await listen.click();
  expect((await spoken(page)).join(" ")).toContain("Focus on measurable impact");

  // TTS did NOT auto-open the microphone (no active dictation; Start dictation still offered).
  await expect(page.getByRole("button", { name: "Start dictation" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop dictation" })).toHaveCount(0);
});
