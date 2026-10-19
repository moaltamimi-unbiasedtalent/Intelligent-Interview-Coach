#!/usr/bin/env python
"""Ask4Mo OFFLINE demonstration journey (deterministic, no provider, no network, no paid call).

Walks ONE synthetic candidate through: Opportunity -> Preparation (Mo, the LangGraph agent) -> Knowledge retrieval and a grounded, cited answer ->
Interview practice -> Feedback. It is the reliable FALLBACK for a demonstration when live provider access is unreliable, and a transparent record of which parts
are REAL, which are MOCKED, and what is DISABLED.

  REAL     : the FastAPI app and its authorization on a throwaway SQLite database; the LangGraph agent, tool registry, allow-list, guards and the
             post-answer grounding policy; the deterministic gap analyser and preparation planner; hybrid retrieval over a SYNTHETIC fixture corpus
             (offline hash embedder); the interview and evaluation services (prompting, schema validation, repair, usage accounting).
  MOCKED   : every LLM reply (a scripted model answers; no provider is contacted).
  DISABLED : live OpenRouter calls, server-side speech, billing and checkout, email delivery, every rollout gate.

Usage:  python scripts/demo_offline_journey.py [--json out.json] [--transcript out.md]
Exit code 0 when every step's checks pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): temp DATABASE_URL, no .env, non-temp engines fail fast. A demonstration must never touch a development store.
import tests.conftest  # noqa: E402,F401

import httpx  # noqa: E402

DATA = ROOT / "evaluations/demo/synthetic_demo_candidate.json"
PASSWORD = "demo-passphrase-synthetic-1"


class _Block:
    """Refuse every request that is not the in-process test transport: the demonstration must be provably offline."""

    def __enter__(self):
        self._sync, self._async = httpx.Client.send, httpx.AsyncClient.send
        orig_s, orig_a = self._sync, self._async

        def guard(request):
            if (request.url.host or "") != "testserver":
                raise RuntimeError(f"offline demonstration attempted a network request to {request.url.host}")

        def s(client, request, **k):
            guard(request)
            return orig_s(client, request, **k)

        async def a(client, request, **k):
            guard(request)
            return await orig_a(client, request, **k)

        httpx.Client.send, httpx.AsyncClient.send = s, a
        return self

    def __exit__(self, *exc):
        httpx.Client.send, httpx.AsyncClient.send = self._sync, self._async


class Journey:
    def __init__(self) -> None:
        self.steps: list[dict] = []
        self.lines: list[str] = []

    def say(self, text: str = "") -> None:
        self.lines.append(text)

    def step(self, number: int, title: str, components: dict[str, str], facts: list[str], checks: dict[str, bool]) -> None:
        self.say(f"## Step {number}: {title}")
        self.say("")
        self.say("| Component | State |")
        self.say("|---|---|")
        for k, v in components.items():
            self.say(f"| {k} | {v} |")
        self.say("")
        for f in facts:
            self.say(f"- {f}")
        self.say("")
        self.say("Checks: " + ", ".join(f"{'PASS' if ok else 'FAIL'} {name}" for name, ok in checks.items()))
        self.say("")
        self.steps.append({"step": number, "title": title, "components": components, "checks": checks})


def _scripted_agent_model(script, final_text):
    from langchain_core.messages import AIMessage, ToolMessage

    class Scripted:
        def bind_tools(self, schemas):
            return self

        def invoke(self, messages):
            done = sum(1 for m in messages if isinstance(m, ToolMessage))
            if done < len(script):
                step = script[done]
                return AIMessage(content="", tool_calls=[{"name": step["name"], "args": step.get("args", {}), "id": f"demo{done}"}])
            return AIMessage(content=final_text)

    return Scripted()


class DemoCareer:
    """The Career application seam for the demo: deterministic tools are the REAL implementations, retrieval is REAL over the synthetic corpus, and only the two
    LLM-backed tools (job analysis, question generation) return fixed structured results (MOCKED)."""

    def __init__(self, world, data) -> None:
        self.world, self.data = world, data

    @staticmethod
    def _ok(value):
        from types import SimpleNamespace

        return SimpleNamespace(ok=True, value=value, error=None, execution=SimpleNamespace(tool_name="demo", status="ok", error=None))

    def analyze_job_description(self, jd):
        from src.copilot.tools.schemas import RoleRequirements

        return self._ok(RoleRequirements(role_title="Data Analyst", seniority="junior", key_responsibilities=["explain findings to non-technical stakeholders", "build weekly dashboards"],
                                         required_skills=["SQL", "basic statistics", "dashboards"], preferred_skills=["Python"], technologies=["SQL"],
                                         likely_interview_themes=["communicating data", "working with stakeholders"]))

    def analyze_candidate_gaps(self, bg, role):
        from src.copilot.tools.gap_analyzer import analyze_gaps
        from src.copilot.tools.schemas import GapAnalyzerArgs

        return self._ok(analyze_gaps(GapAnalyzerArgs(candidate_background=bg, role_requirements=role)))

    def build_preparation_plan(self, gaps, days, hours):
        from src.copilot.tools.prep_planner import build_plan
        from src.copilot.tools.schemas import PrepPlanArgs

        return self._ok(build_plan(PrepPlanArgs(priority_gaps=list(gaps), days_until_interview=int(days), hours_per_week=float(hours))))

    def generate_questions(self, role, reqs, focus):
        from src.copilot.tools.schemas import InterviewQuestionSet, QuestionCategory

        return self._ok(InterviewQuestionSet(role=role, categories=[QuestionCategory(name="Behavioural", questions=[self.data["interview"]["scripted_question"]])]))

    def search_knowledge(self, req, *, progress=None):
        return self.world.service(responder=None).retrieve_evidence(req.query)


def run_journey() -> dict:
    from fastapi.testclient import TestClient

    from src import constants
    from src.agent.models import AgentRunRequest
    from src.application.agent_service import AgentApplicationService
    from src.copilot.knowledge import requalification as Q
    from src.copilot.rag import localized
    from src.copilot.rag.responder import ModelReply
    from src.evaluation_service import EvaluationService
    from src.interview_service import InterviewService
    from src.models import InterviewConfiguration, ModelSettings
    from src.openrouter_client import ChatResult
    from src.pricing_service import PricingService
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register

    data = json.loads(DATA.read_text(encoding="utf-8"))
    J = Journey()
    J.say("# Ask4Mo offline demonstration transcript")
    J.say("")
    J.say("Synthetic candidate, deterministic scripted model, no provider, no network. REAL / MOCKED / DISABLED labels apply to each step.")
    J.say("")
    app, repo, _mail = build_auth_app()
    with TestClient(app) as client:
        # ---------------------------------------------------------------- 1 Opportunity
        email = data["candidate"]["email"]
        assert register(client, email, PASSWORD, data["candidate"]["display_name"]).status_code in (200, 201)
        ck = cookies_for(login_token(client, email, PASSWORD))
        me = client.get("/api/v1/auth/me", cookies=ck).json()
        opp = client.post("/api/v1/opportunities", cookies=ck, json=data["opportunity"])
        listed = client.get("/api/v1/opportunities", cookies=ck).json()
        other = TestClient(app)
        register(other, "other.candidate@example.invalid", PASSWORD)
        ock = cookies_for(login_token(other, "other.candidate@example.invalid", PASSWORD))
        foreign = other.get(f"/api/v1/opportunities/{opp.json()['id']}", cookies=ock)
        J.step(1, "Account and Opportunity", {"FastAPI app, auth, owner-scoped storage": "REAL (throwaway SQLite)", "Email": "MOCKED (in-memory, nothing sent)", "Live provider": "DISABLED"},
               [f"Registered and signed in a synthetic candidate (user id {me['user_id']}); created the Opportunity '{data['opportunity']['target_role']}' at {data['opportunity']['company_name']}.",
                "A second synthetic account asking for that Opportunity receives a not-found answer (ownership isolation)."],
               {"opportunity_created": opp.status_code == 201, "listed_for_owner": len(listed.get("items", listed)) == 1 if isinstance(listed, (list, dict)) else False, "foreign_access_denied": foreign.status_code == 404})
        # ---------------------------------------------------------------- 2 Preparation (Mo)
        corpus = Q.load_corpus()
        with Q.temp_world(corpus) as world:
            career = DemoCareer(world, data)
            script = [{"name": "AnalyzeJobDescription", "args": {"job_description": data["job_description"]}},
                      {"name": "AnalyzeCandidateGaps", "args": {"candidate_background": data["candidate_background"]}},
                      {"name": "BuildPreparationPlan", "args": data["preparation"]},
                      {"name": "SearchCareerKnowledge", "args": {"query": data["knowledge_questions"]["supported"]}}]
            final = ("Here is your preparation outline. Your strongest match is reporting and stakeholder communication; the main gap is Python, so spend your first hours on SQL practice and one "
                     "stakeholder-explanation story. A Data Analyst prepares data, builds dashboards and communicates findings [1].")
            svc = AgentApplicationService(model_factory=lambda: _scripted_agent_model(script, final), career_service=career)
            res = svc.run(AgentRunRequest(goal="Help me prepare for this Data Analyst interview.", job_description=data["job_description"], candidate_background=data["candidate_background"],
                                          user_id="demo-candidate", conversation_language="en"))
            J.step(2, "Preparation with Mo (LangGraph agent, controlled tools, agentic retrieval)",
                   {"LangGraph agent graph, tool allow-list, guards, step bound": "REAL", "Agent LLM": "MOCKED (scripted tool calls and final text)", "Gap analysis and preparation plan": "REAL (deterministic)",
                    "Job analysis, question generation": "MOCKED structured results", "SearchCareerKnowledge retrieval": "REAL over a synthetic fixture corpus (offline hash embedder)", "Human approval": "available; not triggered in this path"},
                   [f"Tools executed in order: {', '.join(res.tools_used)}.", f"Status: {res.status}. Retrieval used: {res.retrieval_used}. Evidence items: {len(res.sources)}; citations: {len(res.citations)}.",
                    f"Mo's answer (after the post-answer grounding policy): \"{res.response}\"", f"Response class (internal): {res.response_class}."],
                   {"tools_in_order": res.tools_used == [s["name"] for s in script], "completed": res.status == "completed", "retrieval_used": bool(res.retrieval_used),
                    "citation_matches_evidence": len(res.citations) >= 1 and "[1]" in res.response})
            # ---------------------------------------------------------------- 3 Knowledge retrieval and grounded answer
            def reply_supported(messages):
                return ModelReply(content=f"{localized.section_headings('en')[0]} A Data Analyst prepares data, builds dashboards and communicates findings [1]. SQL and statistics are core skills [1].")

            ans = world.service(responder=reply_supported).answer(data["knowledge_questions"]["supported"], conversation_language="en")

            def reply_offer(messages):
                return ModelReply(content=localized.insufficient_message("en") + " I can help estimate a salary range for a Data Analyst in Canada if you like.")

            ans2 = world.service(responder=reply_offer).answer(data["knowledge_questions"]["unsupported_geography"], conversation_language="en")
            from src.copilot.security import grounding_policy as GP

            J.step(3, "Knowledge retrieval, citations and the grounding policies",
                   {"Hybrid retrieval, citations, output guards": "REAL (synthetic fixture corpus)", "Answer text": "MOCKED (scripted model reply)", "Grounding policy layer (contextual citations, no unsourced estimates)": "REAL"},
                   [f"Question: \"{data['knowledge_questions']['supported']}\" -> class {ans.trace.response_class}, {len(ans.response.citations)} citation(s) to retrieved evidence.",
                    f"Question: \"{data['knowledge_questions']['unsupported_geography']}\" (no Canadian compensation evidence exists) -> class {ans2.trace.response_class}. The scripted reply offered an unsourced salary estimate; "
                    f"the policy layer removed the offer and added the localized guidance: \"{ans2.response.answer.splitlines()[-1]}\""],
                   {"supported_answer_cited": ans.trace.response_class == "EVIDENCE_BACKED_ANSWER" and len(ans.response.citations) >= 1,
                    "unsupported_is_an_abstention": ans2.trace.response_class.startswith("ABSTENTION"),
                    "no_estimate_offer_survives": not any(GP.offers_unsourced_estimate(s) for _, s in GP._units(ans2.response.answer)) and not GP.money_figures(ans2.response.answer)})
        # ---------------------------------------------------------------- 4 and 5 Interview practice and feedback
        class FakeClient:
            def __init__(self, contents):
                self._c = list(contents)

            def create_chat_completion(self, **kwargs):
                return ChatResult(content=self._c.pop(0), model=kwargs["model"], prompt_tokens=100, completion_tokens=50, total_tokens=150, reported_cost=None, duration_seconds=0.1, request_id="demo")

        iv = data["interview"]
        question_json = json.dumps({"question_id": 1, "question": iv["scripted_question"], "question_type": "behavioural", "competency": "communication", "difficulty": "moderate",
                                    "interviewer_intent": "See whether the candidate can make data meaningful to a non-technical audience.", "expected_answer_elements": ["situation", "action", "result"]})
        eval_json = json.dumps({"overall_score": 74, "relevance": 8, "structure": 7, "evidence": 6, "role_knowledge": 6, "problem_solving": 7, "communication": 8, "credibility": 8,
                                "strengths": ["Chose a concrete situation and adapted the chart to the stakeholder", "Clear action and a stated outcome"],
                                "improvement_areas": ["Quantify the outcome (for example how many weeks the dashboard was used)", "Name the data source and the metric"],
                                "missing_evidence": ["No measured result", "No mention of how accuracy was checked"],
                                "stronger_answer_structure": "Situation, Task, Action, Result, with one number in the Result.",
                                "improved_example_answer": "Example to personalise with your own details: state the metric, the change you made and the measured effect.",
                                "follow_up_question": "What measurable change did the stakeholder's planning show after using the dashboard?"})
        models = [{"id": constants.DEFAULT_MODEL, "pricing": {"prompt": "0.0000006", "completion": "0.0000018"}, "supported_parameters": ["temperature", "max_tokens", "response_format"]}]
        pricing = PricingService(models_fetcher=lambda: models)
        interview = InterviewService(FakeClient([question_json]), pricing)
        evaluation = EvaluationService(FakeClient([eval_json]), pricing)
        cfg = InterviewConfiguration(target_role=iv["target_role"], industry_or_sector=iv["industry_or_sector"], career_level=iv["career_level"], interview_types=iv["interview_types"],
                                     interviewer_persona="neutral", difficulty="moderate", response_detail="standard", number_of_questions=1)
        settings = ModelSettings(model=constants.DEFAULT_MODEL, prompt_technique="rubric_json")
        q, _u = interview.generate_next_question(cfg, settings, current_question_number=1)
        J.step(4, "Interview practice: question generation", {"Interview service (prompting, JSON validation, repair, usage accounting)": "REAL", "Model reply": "MOCKED (scripted)"},
               [f"Question {q.question_id} ({q.question_type}, {q.competency}): \"{q.question}\""], {"question_present": len(q.question) > 15, "question_type_behavioural": q.question_type == "behavioural"})
        ev, usage = evaluation.evaluate_answer(cfg, q.question, iv["synthetic_answer"], settings)
        J.step(5, "Interview feedback", {"Evaluation service (rubric JSON, validation)": "REAL", "Model reply": "MOCKED (scripted)"},
               [f"Overall practice score: {ev.overall_score}/100 (practice feedback only, never a hiring decision).", "Strengths: " + "; ".join(ev.strengths), "To improve: " + "; ".join(ev.improvement_areas), "Missing evidence: " + "; ".join(ev.missing_evidence),
                f"Follow-up question: \"{ev.follow_up_question}\""],
               {"has_follow_up_question": "?" in ev.follow_up_question, "names_missing_evidence": bool(ev.missing_evidence), "usage_recorded": usage is not None})
    ok = all(all(s["checks"].values()) for s in J.steps)
    J.say("## Result")
    J.say("")
    J.say(f"All checks passed: {ok}. No provider was contacted, no network request left the machine, no paid call was made and no real personal data was used.")
    transcript = "\n".join(J.lines) + "\n"
    return {"ok": ok, "steps": J.steps, "transcript": transcript, "transcript_sha256": hashlib.sha256(transcript.encode()).hexdigest()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--transcript")
    a = ap.parse_args(argv)
    with _Block():
        out = run_journey()
    if a.transcript:
        Path(a.transcript).write_text(out["transcript"], encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps({k: v for k, v in out.items() if k != "transcript"}, indent=1), encoding="utf-8")
    print(out["transcript"])
    print(f"transcript sha256: {out['transcript_sha256']}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
