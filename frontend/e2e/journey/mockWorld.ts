import type { Page, Route } from "@playwright/test";

import { FIXTURES, MOCK_INVITATION_PREFIX } from "./env";

/**
 * A small STATEFUL mock of the Ask4Mo API for the 04D journey (mode "mocked": always on in CI, no backend, no provider).
 *
 * Fidelity rule: every response shape below mirrors what the REAL local stack returned when the same journey was driven against it (scripts/e2e/journey_stack.py),
 * and the journey definition cannot tell the two apart. It mirrors the server rules that the journey depends on (single-use invitations, one uniform refusal,
 * onboarding gate, owner-held data), but it is NOT a substitute for the backend tests that prove those rules; it exists to drive the real UI deterministically.
 * Anything the journey does not need answers `{}`, and is recorded in `world.unmocked` so UI drift is visible.
 */

type Json = Record<string, unknown>;

interface Account {
  user_id: number;
  email: string;
  password: string;
  display_name: string | null;
  interface_locale: string;
  conversation_language: string;
  target_role: string;
  career_geography: string;
  coaching_style: string;
  onboarding_completed: boolean;
  onboarding_step: number;
}

export class MockWorld {
  readonly calls: string[] = [];                 // "METHOD /path" of every API call, in order
  readonly unmocked: string[] = [];              // API calls the world answered with `{}`
  readonly consumedInvitations = new Set<string>();
  /** Mutation switch for the suite's own self-check: when true, creating an interview fails like the original Start Interview defect (a bare 503). */
  failInterviewCreate = false;
  /** The AI provider state of this mocked stack. "ok" = offline fixtures answer (mode offline); "down" = a configured provider that fails this time; "not_configured" = a keyless stack. */
  provider: "ok" | "down" | "not_configured" = "ok";
  /** The Idempotency-Key header of every POST /interviews, in order (a retry after a failure must re-send the SAME key). */
  readonly interviewCreateKeys: Array<string | undefined> = [];
  private users = new Map<string, Account>();
  private signedIn: string | null = null;
  private nextUserId = 1;
  private opportunities: Json[] = [];
  private sessions = new Map<string, Json>();
  private history: Json[] = [];
  private reports = new Map<string, Json>();
  private answers = new Map<string, string[]>();
  private runs = new Map<string, Json>();

  // ---- helpers ----------------------------------------------------------------
  private account(): Account | null {
    return this.signedIn ? this.users.get(this.signedIn) ?? null : null;
  }

  private accountJson(a: Account): Json {
    return {
      user_id: a.user_id, email: a.email, display_name: a.display_name, platform_role: "user", tier: "basic", status: "active", email_verified: false, providers: [],
      auth_method: "session", capabilities: ["current_market_research", "standard_history", "standard_model_profiles", "standard_progress"], admin_permissions: [],
      response_detail: "brief", interface_locale: a.interface_locale, conversation_language: a.conversation_language, coaching_style: a.coaching_style,
      career_geography: a.career_geography, target_role: a.target_role, onboarding_completed: a.onboarding_completed, onboarding_step: a.onboarding_step,
    };
  }

  private static err(code: string, message: string) {
    return { error: { code, message, request_id: "req_journey_mock" } };
  }

  private validInvitation(code: unknown): boolean {
    return typeof code === "string" && code.startsWith(MOCK_INVITATION_PREFIX) && !this.consumedInvitations.has(code);
  }

  private questionJson(n: number): Json {
    const qs = FIXTURES.interview.questions;
    return { question_id: n, question: qs[Math.min(n, qs.length) - 1], question_type: "behavioural", competency: "judgement", difficulty: "moderate" };
  }

  private state(s: Json): Json {
    return { ...s };
  }

  // ---- install ----------------------------------------------------------------
  async install(page: Page): Promise<void> {
    await page.route("**/api/v1/**", (route) => this.handle(route));
  }

  private async handle(route: Route): Promise<void> {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, "");
    const method = req.method();
    const body = (() => { try { return (req.postDataJSON() ?? {}) as Json; } catch { return {} as Json; } })();
    this.calls.push(`${method} ${path}`);
    const json = (data: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_journey_mock" }, body: JSON.stringify(data) });
    const me = this.account();

    // ---- public / auth
    if (path === "/capabilities")
      return json({ career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true, agent_memory: true,
        human_in_the_loop: true, agent_coach_enabled: true, realtime_voice_enabled: false, company_research_enabled: true,
        active_candidate_locales: ["en", "de", "fr", "es", "it", "pt", "nl"], default_locale: "en", language_activation_mode: "labelled", qualified_locales: [],
        unqualified_locales: ["en", "de", "fr", "es", "it", "pt", "nl"], no_language_available: false, ...this.capabilityExtras() });
    if (path === "/auth/register" && method === "POST") {
      // The server's rule, uniformly: a missing or unusable invitation is ONE refusal whatever the email.
      if (!this.validInvitation(body.invitation_code)) return json(MockWorld.err("invitation_required", "server english text that must never be shown"), 403);
      const email = String(body.email ?? "").toLowerCase();
      if (!this.users.has(email)) {
        this.consumedInvitations.add(String(body.invitation_code));
        this.users.set(email, {
          user_id: this.nextUserId++, email, password: String(body.password ?? ""), display_name: (body.display_name as string | null) ?? null,
          interface_locale: typeof body.locale === "string" ? body.locale : "en", conversation_language: "en", target_role: "", career_geography: "", coaching_style: "balanced",
          onboarding_completed: false, onboarding_step: 0,
        });
      }
      return json({ message: "If that email can be registered, we've sent a verification link. Please check your inbox, then sign in." }, 201);
    }
    if (path === "/auth/login" && method === "POST") {
      const u = this.users.get(String(body.email ?? "").toLowerCase());
      if (!u || u.password !== body.password) return json(MockWorld.err("invalid_credentials", "Incorrect email or password."), 401);
      this.signedIn = u.email;
      return json({ message: "Signed in." });
    }
    if (path === "/auth/logout") { this.signedIn = null; return json({ message: "Signed out." }); }
    if (path === "/auth/me") return me ? json(this.accountJson(me)) : json(MockWorld.err("unauthorized", "Authentication required."), 401);

    // everything below needs a session
    if (!me) return json(MockWorld.err("unauthorized", "Authentication required."), 401);

    if (path === "/auth/onboarding" && method === "POST") {
      if (typeof body.step === "number") me.onboarding_step = Math.max(me.onboarding_step, body.step);
      if (body.complete) me.onboarding_completed = true;
      return json(this.accountJson(me));
    }
    if (path === "/auth/preferences" && method === "PATCH") {
      for (const k of ["display_name", "target_role", "career_geography", "coaching_style", "interface_locale", "conversation_language"] as const) if (typeof body[k] === "string") (me as unknown as Json)[k] = body[k];
      return json(this.accountJson(me));
    }

    // ---- opportunities (owner-held)
    if (path === "/opportunities" && method === "POST") {
      const id = this.opportunities.length + 1;
      const title = [body.target_role, body.company_name, body.company_location].filter(Boolean).join(" - ");
      const item: Json = { id, title: (body.title as string) || title, target_role: body.target_role, company_name: body.company_name ?? null, company_location: body.company_location ?? null,
        company_country: body.company_country ?? null, company_domain: body.company_domain ?? null, job_description_document_id: null, status: "active", notes: body.notes ?? null,
        created_at: "2026-01-01T00:00:00", updated_at: "2026-01-01T00:00:00", archived_at: null };
      this.opportunities.push(item);
      return json(item, 201);
    }
    if (path === "/opportunities" && method === "GET") return json({ opportunities: this.opportunities });
    const opp = path.match(/^\/opportunities\/(\d+)$/);
    if (opp && method === "GET") {
      const o = this.opportunities.find((it) => it.id === Number(opp[1]));
      return o ? json({ ...o, jd_available: false, interview_ids: [], interview_count: 0 }) : json(MockWorld.err("not_found", "Opportunity not found."), 404);
    }

    // ---- Mo (agent)
    if (path === "/agent/run" && method === "POST") {
      const runId = `run_journey_${this.runs.size + 1}`;
      if (this.provider !== "ok") {
        // The real server answers a failed run with 200, status failed, a stable failure_code and an English fallback message that the UI must NOT show.
        const failed: Json = { run_id: runId, status: "failed", response: "The assistant isn't configured in this environment.", failure_code: this.provider === "down" ? "ai_provider_unavailable" : "ai_not_configured",
          tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false, memory_count: 0, memory_loaded: [], awaiting_human_input: false, pending_action: null,
          handoff_approved: false, events: [], tool_calls: [], warnings: ["The run did not complete successfully."], step_count: 1, turn_step_count: 1,
          conversation: [{ role: "user", content: String(body.goal ?? "") }, { role: "assistant", content: "The assistant isn't configured in this environment." }],
          preparation_context: null, usage: null, profile: "balanced", latency_ms: 5, cache_hits: 0, cache_misses: 0,
          journey: { understand: { status: "not_started" }, prepare: { status: "not_started" }, practise: { status: "not_started" } }, handoff_summary: null };
        this.runs.set(runId, failed);
        return json(failed);
      }
      const run: Json = {
        run_id: runId, status: "completed", response: FIXTURES.mo.reply, tools_used: [], retrieval_used: false, sources: [], citations: [], resolved_occupation: null, resolved_geography: null,
        memory_used: false, memory_count: 0, memory_loaded: [], awaiting_human_input: false, pending_action: null, handoff_approved: false, events: [], tool_calls: [], warnings: [],
        step_count: 1, turn_step_count: 1,
        conversation: [{ role: "user", content: String(body.goal ?? "") }, { role: "assistant", content: FIXTURES.mo.reply, response_id: `${runId}:1` }],
        preparation_context: null, usage: null, profile: "balanced", latency_ms: 30, cache_hits: 0, cache_misses: 0,
        journey: { understand: { status: "not_started", role_known: false, requirements_known: false, evidence_used: false }, prepare: { status: "not_started" }, practise: { status: "not_started" } },
        handoff_summary: null,
      };
      this.runs.set(runId, run);
      return json(run);
    }
    if (path === "/agent/runs" && method === "GET")
      return json({ runs: [...this.runs.values()].reverse().map((r) => ({ run_id: r.run_id, state: r.status === "failed" ? "failed" : "ready", created_at: "2026-01-01T00:00:00", updated_at: "2026-01-01T00:00:00" })), limit: 10 });
    const runGet = path.match(/^\/agent\/runs\/([^/]+)$/);
    if (runGet && method === "GET") { const r = this.runs.get(runGet[1]); return r ? json(r) : json(MockWorld.err("not_found", "Run not found."), 404); }

    // ---- Practice
    if (path === "/interviews/options")
      return json({ career_levels: ["internship", "entry", "junior", "mid", "senior", "lead", "principal", "manager", "director", "executive"],
        interview_types: ["screening", "behavioural", "technical"], difficulty_levels: ["easy", "moderate", "hard"], deep_dive_modes: ["deepen_reasoning", "challenge_assumptions"] });
    if (path === "/interviews" && method === "POST") {
      this.interviewCreateKeys.push(req.headers()["idempotency-key"]);
      if (this.provider === "not_configured") return json(MockWorld.err("ai_not_configured", "AI features are not configured on this Ask4Mo environment, so nothing was started."), 503);
      if (this.provider === "down") return json(MockWorld.err("ai_provider_unavailable", "The AI service could not complete this request right now. Nothing was lost; you can try again."), 503);
      if (this.failInterviewCreate) return json(MockWorld.err("service_unavailable", "No OpenRouter API key is configured."), 503);
      return this.createInterview(body, json);
    }
    if (path === "/interviews" && method === "GET") return json({ sessions: [...this.sessions.values()].filter((s) => s.state !== "REPORT_READY").map((s) => ({ session_id: s.session_id, target_role: s.target_role, state: s.state, question_number: s.question_number, questions_planned: s.questions_planned })) });
    const iv = path.match(/^\/interviews\/([^/]+)(?:\/(answers|next-question|complete|report))?$/);
    if (iv) {
      const [, id, action] = iv;
      const s = this.sessions.get(id);
      if (!s) return json(MockWorld.err("not_found", "Interview not found."), 404);
      if (!action && method === "GET") return json(this.state(s));
      if (action === "answers" && method === "POST") {
        const list = this.answers.get(id) ?? [];
        list.push(String(body.answer ?? ""));
        this.answers.set(id, list);
        s.state = "INTERVIEW_IN_PROGRESS"; s.current_question = null; s.last_evaluation = FIXTURES.interview.evaluation;
        return json(this.state(s));
      }
      if (action === "next-question" && method === "POST") {
        if (Number(s.question_number) < Number(s.questions_planned)) { s.question_number = Number(s.question_number) + 1; s.state = "AWAITING_ANSWER"; s.current_question = this.questionJson(Number(s.question_number)); s.last_evaluation = null; }
        else { s.state = "INTERVIEW_COMPLETE"; s.current_question = null; }
        return json(this.state(s));
      }
      if (action === "complete" && method === "POST") { s.state = "INTERVIEW_COMPLETE"; s.current_question = null; return json(this.state(s)); }
      if (action === "report" && method === "POST") {
        const reportId = this.history.length + 1;
        s.state = "REPORT_READY"; s.report_available = true;
        const saved = { session_id: id, report: FIXTURES.interview.report, saved_report_id: reportId, save_failed: false };
        this.reports.set(id, saved);
        this.history.push({ id: reportId, target_role: s.target_role, mode: null, status: "completed", questions: this.answers.get(id)?.length ?? 0, created_at: "2026-01-01T00:00:00", session: id });
        return json(saved);
      }
      if (action === "report" && method === "GET") { const r = this.reports.get(id); return r ? json(r) : json(MockWorld.err("not_found", "Report not found."), 404); }
    }

    // ---- History and Progress (derived from this candidate's own completed interviews)
    if (path === "/history/interviews" && method === "GET")
      return json({ interviews: this.history.map(({ session: _s, ...row }) => row), access: { restricted: false, window: null, hidden_count: 0 } });
    const hd = path.match(/^\/history\/interviews\/(\d+)$/);
    if (hd && method === "GET") {
      const row = this.history.find((h) => h.id === Number(hd[1]));
      if (!row) return json(MockWorld.err("not_found", "Interview not found."), 404);
      return json({ interview: { id: row.id, configuration: { target_role: row.target_role, industry_or_sector: FIXTURES.interview.industry, career_level: "senior" }, mode: null, status: "completed",
        started_at: null, ended_at: null, created_at: row.created_at, questions: [], report: { report: FIXTURES.interview.report, usage: { total_tokens: 0, requests: 0 }, cost_usd: 0 } } });
    }
    if (path === "/progress" && method === "GET") {
      const answered = [...this.answers.values()].reduce((n, l) => n + l.length, 0);
      return json({ interviews_completed: this.history.length, answers_evaluated: answered, average_practice_score: answered ? FIXTURES.interview.evaluation.overall_score : null,
        most_common_improvement_area: answered ? FIXTURES.interview.evaluation.improvement_areas[0] : null, average_answer_seconds: null,
        recent_interviews: this.history.map(({ session: _s, ...row }) => row), access: { restricted: false, window: null } });
    }

    // ---- benign reads the pages make in the background
    if (path === "/memory") return json({ memories: [] });
    if (path === "/documents") return json({ documents: [] });
    if (path === "/stories") return json({ stories: [] });

    this.unmocked.push(`${method} ${path}`);
    return json({});
  }

  /** The AI provider mode this stack reports: a configured provider that is down is still "live" (configuration, not health); fixtures are "offline". */
  protected capabilityExtras(): Json {
    return { ai_provider_mode: this.provider === "not_configured" ? "not_configured" : this.provider === "down" ? "live" : "offline" };
  }

  private createInterview(body: Json, json: (d: unknown, s?: number) => Promise<void>): Promise<void> {
    const cfg = (body.configuration ?? {}) as Json;
    const id = `sess_journey_${this.sessions.size + 1}`;
    const s: Json = { session_id: id, state: "AWAITING_ANSWER", question_number: 1, questions_planned: Number(cfg.number_of_questions ?? 5), current_question: this.questionJson(1),
      report_available: false, last_evaluation: null, target_role: cfg.target_role ?? null, deep_dive: null, error: null, error_recoverable: false, cumulative_cost_usd: 0 };
    this.sessions.set(id, s);
    return json(this.state(s));
  }
}
