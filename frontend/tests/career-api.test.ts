import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function mockFetch(impl: () => Promise<Response> | Response) {
  vi.stubGlobal("fetch", vi.fn(impl));
}
function json(body: unknown, init: ResponseInit & { requestId?: string } = {}) {
  const headers = new Headers({ "content-type": "application/json" });
  if (init.requestId) headers.set("x-request-id", init.requestId);
  return new Response(JSON.stringify(body), { status: init.status ?? 200, headers });
}
afterEach(() => vi.unstubAllGlobals());

describe("Career API client", () => {
  it("career.chat returns a typed grounded response", async () => {
    mockFetch(() =>
      json({
        answer: "Focus on executive communication.",
        citations: [], sources: [{ title: "O*NET", source_url: "https://x" }],
        tools: [], input_flagged: false, has_evidence: true, preparation_available: true,
      }),
    );
    const res = await api.career.chat({ question: "What should I focus on?" });
    expect(res.answer).toContain("executive communication");
    expect(res.sources[0].title).toBe("O*NET");
  });

  it("career.chat validation failure becomes a safe 4xx ApiError", async () => {
    mockFetch(() =>
      json({ error: { code: "validation_error", message: "Question is required.", request_id: "r1" } }, { status: 422 }),
    );
    await expect(api.career.chat({ question: "" })).rejects.toMatchObject({ kind: "validation", requestId: "r1" });
  });

  it("configuration error surfaces as unavailable (503)", async () => {
    mockFetch(() =>
      json({ error: { code: "not_configured", message: "No model configured.", request_id: "r2" } }, { status: 503 }),
    );
    try {
      await api.career.chat({ question: "hi" });
    } catch (e) {
      const err = e as ApiError;
      expect(err.kind).toBe("unavailable");
      expect(err.requestId).toBe("r2");
    }
  });

  it("job-analysis returns a typed tool result", async () => {
    mockFetch(() =>
      json({ ok: true, tool_name: "job_description_analyzer", status: "ok", result: { role_title: "PM", required_skills: ["Roadmapping"] }, error: null }),
    );
    const res = await api.career.jobAnalysis({ job_description: "JD" });
    expect(res.ok).toBe(true);
    expect(res.result?.role_title).toBe("PM");
  });

  it("gap-analysis returns match stats", async () => {
    mockFetch(() =>
      json({ ok: true, tool_name: "candidate_gap_analyzer", status: "ok", result: { matched: [], partially_matched: [], missing: ["A"], strengths: ["B"], priority_gaps: [{ requirement: "A", severity: "High" }], stats: { total_requirements: 3, matched: 1, partial: 1, missing: 1, match_percentage: 33, weighted_match_percentage: 30 } }, error: null }),
    );
    const res = await api.career.gapAnalysis({ candidate_background: "CV", role_requirements: { role_title: "PM" } });
    expect(res.result?.stats.match_percentage).toBe(33);
  });

  it("preparation-plan returns allocations", async () => {
    mockFetch(() =>
      json({ ok: true, tool_name: "preparation_plan_calculator", status: "ok", result: { days_until_interview: 14, hours_per_week: 6, total_available_hours: 12, allocations: [{ requirement: "A", allocated_hours: 6, share_percentage: 50 }], weekly_structure: [], notes: [] }, error: null }),
    );
    const res = await api.career.preparationPlan({ priority_gaps: [], days_until_interview: 14, hours_per_week: 6 });
    expect(res.result?.total_available_hours).toBe(12);
  });

  it("questions returns categories", async () => {
    mockFetch(() =>
      json({ ok: true, tool_name: "interview_question_generator", status: "ok", result: { role: "PM", categories: [{ name: "Behavioural", questions: ["Tell me about…"] }] }, error: null }),
    );
    const res = await api.career.questions({ role: "PM", requirements: [], focus: [] });
    expect(res.result?.categories[0].questions.length).toBe(1);
  });

  it("interviews.create returns a session with the target role and question", async () => {
    mockFetch(() =>
      json({ session_id: "s1", state: "AWAITING_ANSWER", question_number: 1, questions_planned: 5, current_question: { question_id: 1, question: "Q1?", question_type: "behavioural", competency: "x", difficulty: "moderate" }, report_available: false, target_role: "PM" }),
    );
    const res = await api.interviews.create({ preparation_context: { target_role: "PM" } });
    expect(res.session_id).toBe("s1");
    expect(res.target_role).toBe("PM");
    expect(res.current_question?.question).toBe("Q1?");
  });

  it("network failure is a safe ApiError with no raw cause", async () => {
    mockFetch(() => { throw new Error("ECONNREFUSED secret-host"); });
    await expect(api.interviews.get("s1")).rejects.toMatchObject({ kind: "network" });
  });
});
