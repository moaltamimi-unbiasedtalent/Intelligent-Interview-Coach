import { expect, test, type Page } from "@playwright/test";

import { translate } from "../lib/i18n/catalog";

/**
 * Pilot 2 P1 integrated qualification: the smallest deterministic flow proving that the four P2-01..P2-04
 * remediation surfaces coexist on ONE runtime without contradicting each other. Network mocks only (no
 * backend, no model, no paid or live provider). Each surface keeps its own detailed spec
 * (agent-coach, interview, data-privacy); this one proves the seams between them.
 */

const T = (k: string, v?: Record<string, string | number>) => translate("en" as never, k, v);
const SID = "sess_e2e";

const EVAL = {
  overall_score: 74, relevance: 7, structure: 7, evidence: 7, role_knowledge: 7,
  problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add metrics"], missing_evidence: [],
  stronger_answer_structure: "Use STAR-plus-learning.", improved_example_answer: "", follow_up_question: "What did you learn?",
};

const SOURCE = { title: "O*NET Product manager", source_url: "https://example.org/onet", reference_year: 2024, evidence_type: "role" };
const EVIDENCE_EVENT = { event_type: "tool_completed", tool_name: "FindCandidateEvidence", status: "ok", source_count: 3, step: 1 };

type Variant = "external-only" | "candidate-evidence";

function runBody(variant: Variant) {
  return {
    run_id: "run_e2e", status: "completed", response: "Here is your grounded guidance.",
    tools_used: variant === "candidate-evidence" ? ["SearchCareerKnowledge", "FindCandidateEvidence"] : ["SearchCareerKnowledge"],
    retrieval_used: true, sources: [SOURCE], citations: [], memory_used: false, memory_count: 0,
    awaiting_human_input: false, pending_action: null, handoff_approved: false,
    events: variant === "candidate-evidence" ? [EVIDENCE_EVENT] : [],
    tool_calls: [], warnings: [], step_count: 2, turn_step_count: 2,
    conversation: [
      { role: "user", content: "Prep for a Senior PM interview" },
      { role: "assistant", content: "Here is your grounded guidance." },
    ],
    preparation_context: null, resolved_occupation: "Product manager", resolved_geography: null,
  };
}

function question(id: number) {
  return { question_id: id, question: `Question ${id}: tell me about a decision.`, question_type: "behavioural", competency: "judgement", difficulty: "moderate" };
}

function session(over: Record<string, unknown> = {}) {
  return {
    session_id: SID, state: "AWAITING_ANSWER", question_number: 1, questions_planned: 2,
    current_question: question(1), report_available: false, last_evaluation: null,
    target_role: "Senior Product Manager", deep_dive: null, error: null,
    error_recoverable: false, cumulative_cost_usd: 0, ...over,
  };
}

async function mock(page: Page) {
  const state = {
    variant: "external-only" as Variant,
    calls: [] as string[],
    shares: [{ id: 40, owner_user_id: 1, workspace_id: 5, resource_type: "interview_report", resource_id: "30", permission: "view", status: "active", created_at: null, revoked_at: null }] as Record<string, unknown>[],
    deleted: false,
    session: session(),
  };
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

    if (path === "/auth/me")
      return json({
        user_id: 1, email: "u@example.com", display_name: null, platform_role: "user", tier: "basic", status: "active",
        email_verified: true, providers: ["password"], auth_method: "session", capabilities: [], response_detail: "brief",
        interface_locale: "en", conversation_language: "en", coaching_style: "balanced", career_geography: "", target_role: "",
        onboarding_completed: true, onboarding_step: 0,
      });
    if (path === "/capabilities")
      return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false,
        agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: false });

    // Prepare (Agent Coach)
    if (path === "/agent/run") return json(runBody(state.variant));

    // Practice
    if (path === "/interviews/options") return json({ career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: ["deepen_reasoning"] });
    if (/\/interviews\/[^/]+\/answers$/.test(path)) {
      state.session = session({ state: "INTERVIEW_IN_PROGRESS", current_question: null, last_evaluation: EVAL });
      return json(state.session);
    }
    if (/^\/interviews\/[^/]+$/.test(path) && method === "GET") return json(state.session);

    // Data & Privacy
    if (path === "/shares/mine") return json({ shares: state.shares });
    if (/^\/shares\/\d+$/.test(path) && method === "DELETE") { state.shares = []; return json({ status: "revoked" }); }
    if (path === "/workspaces") return json({ workspaces: [{ id: 5, name: "Team Alpha", status: "active", owner_user_id: 1, member_count: 2, created_at: null }], invited: [] });
    if (path === "/opportunities") return json({ opportunities: [{ id: 1, title: "PM at Acme", target_role: "PM", status: "active" }] });
    if (path === "/documents") return json({ documents: [{ id: 10, category: "cv", title: "My CV", status: "ready", current_version: 1 }] });
    if (path === "/memory") return json({ memories: [] });
    if (path === "/history/interviews") return json({ interviews: [] });
    if (path === "/privacy/requests") return json({ items: [], total: 0, page: 1, page_size: 20 });
    if (path === "/privacy/legal") return json({ documents: [] });
    return json({});
  });
  return state;
}

test("Pilot 2 P1 integrated: provenance, answer score and sharing control coexist truthfully on one runtime", async ({ page }) => {
  const state = await mock(page);

  // P2-04 on a Prepare answer that has an external source but NO candidate-evidence selection.
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep for a Senior PM interview");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByText("Here is your grounded guidance.")).toBeVisible();
  await expect(page.getByTestId("ai-provenance")).toContainText("AI-generated");
  const ext = page.getByTestId("external-sources");
  await expect(ext).toContainText("External sources used: 1");
  await ext.locator("summary").click();
  await expect(ext.getByRole("link", { name: /O\*NET Product manager/i })).toBeVisible();
  await expect(ext).not.toContainText(/verified|fact[- ]checked|fully sourced/i);
  // Retrieval alone (retrieval_used, an Opportunity, an approved CV) never implies "Your evidence considered".
  await expect(page.getByTestId("candidate-evidence-provenance")).toHaveCount(0);

  // The same surface when FindCandidateEvidence really returned evidence.
  state.variant = "candidate-evidence";
  await page.goto("/prepare");
  await page.getByLabel("What interview are you preparing for?").fill("Prep for a Senior PM interview");
  await page.getByRole("button", { name: "Start preparing" }).click();
  await expect(page.getByTestId("candidate-evidence-provenance")).toContainText("Your evidence considered");
  await expect(page.getByTestId("ai-provenance")).toContainText("AI-generated");
  await expect(page.getByTestId("external-sources")).toContainText("External sources used: 1");

  // P2-03 in Practice: labelled score, seven dimensions, separate from Practice Readiness.
  await page.goto(`/practice?session=${SID}`);
  await page.getByLabel("Your answer").fill("I prioritised by impact and effort and measured the result.");
  await page.getByRole("button", { name: "Submit answer" }).click();
  const score = page.getByTestId("answer-score");
  await expect(score.getByText("Interview Answer Score", { exact: true })).toBeVisible();
  await expect(score.getByTestId("answer-score-value")).toContainText("74");
  await expect(score.getByTestId("answer-score-value")).toContainText("/ 100");
  await expect(score).toContainText("Practice feedback only, not a hiring decision.");
  await expect(page.getByTestId("rubric-scores").locator("[data-dimension]")).toHaveCount(7);
  // Practice never shows Prepare provenance chrome, and scoring has no provenance claim.
  await expect(page.getByTestId("ai-provenance")).toHaveCount(0);

  // P2-01: the sharing control is immediately reachable and revokes exactly once.
  await page.goto("/account/data");
  const quick = page.getByTestId("dp-quick-sharing");
  await expect(quick).toBeVisible();
  await quick.getByRole("link", { name: T("dataPrivacy.manageSharingQuick") }).click();
  await expect(page).toHaveURL(/\/account\/data#sharing$/);
  const sharing = page.getByTestId("dp-sharing");
  await expect(sharing).toContainText("Team Alpha");
  await sharing.getByRole("button", { name: new RegExp(`^${T("dataPrivacy.revokeAction")}:`) }).click();
  await page.getByTestId("dp-confirm").getByRole("button", { name: T("dataPrivacy.confirmRevoke") }).click();
  await expect(sharing).toContainText(/private by default/i);

  // Exactly one revoke, nothing unrelated deleted, the account is still active, no admin surface touched.
  await page.waitForTimeout(600);
  expect(state.calls.filter((c) => c.startsWith("DELETE"))).toEqual(["DELETE /shares/40"]);
  expect(state.calls.some((c) => c.includes("/admin") || c.includes("/auth/account/delete"))).toBe(false);
  expect(state.deleted).toBe(false);
});
