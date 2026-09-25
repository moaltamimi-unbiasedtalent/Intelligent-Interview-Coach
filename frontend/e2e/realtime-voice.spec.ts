import { expect, test, type Page } from "@playwright/test";

// Capstone P7.5 / C1 realtime voice, end-to-end on the REAL Practice page. A deterministic
// fake realtime adapter is injected on window before load (no microphone, no WebRTC, no
// provider, no audio). Proves §33: Start → ready → question spoken → candidate answers →
// transcript updates → barge-in interruption → final transcript committed ONCE → Practice
// advances once → session can end → turn-based fallback remains available. Backend mocked.

const SID = "sess_rt_e2e";
const ACCOUNT = {
  user_id: 1, email: "user@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};
const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true,
  live_interview_enabled: false, agentic_rag: true, agent_memory: true, human_in_the_loop: true,
  agent_coach_enabled: true, realtime_voice_enabled: true,
};
const GRANT = {
  provider: "fake_realtime", model: "gpt-realtime", voice: "alloy", locale: "en",
  client_secret: "ephemeral-fake-e2e", expires_at: Date.now() / 1000 + 60,
  session_id: "rt_fake_e2e", base_url: "https://example.test/v1",
  max_session_seconds: 300, idle_timeout_seconds: 60,
};

async function installFakeRealtime(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as {
      __ask4moRealtimeAdapter: unknown;
      __rtState: string;
      __rtDrive: Record<string, (arg?: string) => void>;
    };
    let handlers: Record<string, (a?: unknown) => void> = {};
    const setState = (s: string) => {
      w.__rtState = s;
      handlers.onState?.(s);
    };
    w.__ask4moRealtimeAdapter = {
      isSupported: () => true,
      createSession: (_grant: unknown, h: Record<string, (a?: unknown) => void>) => {
        handlers = h;
        return {
          async connect() {
            setState("connecting");
            setState("ready");
          },
          interrupt() {
            handlers.onAssistantAudioEnd?.();
            handlers.onInterrupted?.();
            setState("interrupted");
          },
          stopAssistant() {
            handlers.onAssistantAudioEnd?.();
            setState("ready");
          },
          disconnect() {
            setState("ended");
          },
          getState: () => w.__rtState,
        };
      },
    };
    w.__rtDrive = {
      assistantSpeaking: () => {
        handlers.onAssistantAudioStart?.();
        setState("assistant_speaking");
      },
      assistantText: (t?: string) =>
        handlers.onTranscript?.({ role: "assistant", text: t ?? "", isFinal: true }),
      bargeIn: () => {
        handlers.onAssistantAudioEnd?.();
        handlers.onInterrupted?.();
        setState("listening");
      },
      candidateText: (t?: string) =>
        handlers.onTranscript?.({ role: "candidate", text: t ?? "", isFinal: true }),
    };
  });
}

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

async function mockPractice(page: Page, counters: { answers: number; sessions: number }) {
  const store = { current: baseState() };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (b: unknown, s = 200) =>
      route.fulfill({ status: s, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/auth/me")) return json(ACCOUNT);
    if (url.includes("/capabilities")) return json(CAPS);
    if (url.includes("/voice/realtime/session/end")) return json({ status: "ended" });
    if (url.includes("/voice/realtime/session") && method === "POST") {
      counters.sessions += 1;
      return json(GRANT);
    }
    if (url.match(/\/interviews\/[^/]+\/answers$/) && method === "POST") {
      counters.answers += 1;
      store.current = baseState({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL });
      return json(store.current);
    }
    if (url.match(/\/interviews\/[^/]+$/) && method === "GET") return json(store.current);
    if (url.includes("/interviews/options")) return json({ deep_dive_modes: [] });
    return json({});
  });
}

const drive = (page: Page, fn: string, arg?: string) =>
  page.evaluate(
    ([f, a]) => (window as unknown as { __rtDrive: Record<string, (x?: string) => void> }).__rtDrive[f](a),
    [fn, arg] as const,
  );

test("Practice realtime: start → barge-in → commit ONCE → Practice advances once", async ({ page }) => {
  const counters = { answers: 0, sessions: 0 };
  await installFakeRealtime(page);
  await mockPractice(page, counters);
  await page.goto(`/practice?session=${SID}`);

  await expect(page.getByRole("heading", { name: /tell me about a decision/i })).toBeVisible();
  // Turn-based fallback is present from the start (explicit Submit answer button).
  await expect(page.getByRole("button", { name: /submit answer/i })).toBeVisible();

  // Open the realtime disclosure and start the live session explicitly.
  await page.locator("summary", { hasText: "Start live voice" }).click();
  await page.getByTestId("realtime-start").click();
  await expect(page.getByTestId("realtime-status")).toHaveText(/live voice ready/i);
  expect(counters.sessions).toBe(1);

  // Mo speaks the question (transcript shown, not audio-only).
  await drive(page, "assistantSpeaking");
  await drive(page, "assistantText", "Tell me about a hard call.");
  await expect(page.getByTestId("realtime-mo-line")).toContainText("Tell me about a hard call.");
  await expect(page.getByTestId("realtime-status")).toHaveText(/mo is speaking/i);

  // Candidate barges in → Mo is interrupted; then answers.
  await drive(page, "bargeIn");
  await expect(page.getByTestId("realtime-status")).toHaveText(/listening|you interrupted/i);
  await drive(page, "candidateText", "I paused the launch and de-risked it.");
  await expect(page.getByTestId("realtime-you-line")).toContainText("I paused the launch and de-risked it.");

  // Commit ONCE → Practice advances through the durable answer service exactly once. The
  // realtime panel then unmounts (turn advanced) — that IS the deterministic Practice state
  // taking over. Evidence: evaluation rendered + exactly one answer POST.
  await page.getByTestId("realtime-commit").click();
  await expect(page.getByText(/add metrics/i).first()).toBeVisible();
  expect(counters.answers).toBe(1);
});

test("Practice realtime: explicit End returns to turn-based; typing/fallback remain", async ({ page }) => {
  const counters = { answers: 0, sessions: 0 };
  await installFakeRealtime(page);
  await mockPractice(page, counters);
  await page.goto(`/practice?session=${SID}`);

  await page.locator("summary", { hasText: "Start live voice" }).click();
  await page.getByTestId("realtime-start").click();
  await expect(page.getByTestId("realtime-status")).toHaveText(/live voice ready/i);

  // End the live session cleanly WITHOUT committing → no answer submitted, turn-based remains.
  await page.getByTestId("realtime-end").click();
  await expect(page.getByTestId("realtime-status")).toHaveText(/live voice ended/i);
  expect(counters.answers).toBe(0);
  await expect(page.getByRole("button", { name: /submit answer/i })).toBeVisible();
});
