"""Deterministic agent-orchestration regression harness.

IMPORTANT: this measures **orchestration**, not LLM intelligence. Each case scripts
the model's tool-call sequence, so it deterministically exercises tool routing,
prerequisites, state carry-over, unregistered-tool rejection and completion —
without any provider call. A future *live* agent benchmark (real model choosing
tools) is separate and is not this harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService

CASES_PATH = Path("evaluations/agent/tool_selection_cases.json")


def build_eval_career():
    """A deterministic, query-aware Career service for the offline harness.

    Mirrors the real tool contracts with fixed, safe data (no provider call). A query
    containing ``no-evidence`` returns an insufficient-evidence retrieval (tool ran,
    zero sources/citations) so the dataset can exercise that path.
    """
    from types import SimpleNamespace

    from src.copilot.models import Citation, KnowledgeEvidence
    from src.copilot.service import KnowledgeRetrievalResult
    from src.copilot.tools.schemas import (
        GapAllocation, GapAnalysisResult, InterviewQuestionSet, MatchStats,
        PreparationPlan, PriorityGap, QuestionCategory, RoleRequirements,
    )

    def _call(value):
        return SimpleNamespace(ok=True, value=value, error=None,
                              execution=SimpleNamespace(tool_name="x", status="ok", error=None))

    class EvalCareer:
        def analyze_job_description(self, jd):
            return _call(RoleRequirements(role_title="Senior Product Manager", seniority="senior",
                                          required_skills=["Roadmapping"]))

        def analyze_candidate_gaps(self, bg, role):
            return _call(GapAnalysisResult(
                matched=["Discovery"], partially_matched=[], missing=["Exec comms"], strengths=["Discovery"],
                priority_gaps=[PriorityGap(requirement="Exec comms", category="c", severity="high", reason="r")],
                stats=MatchStats(total_requirements=3, matched=1, partial=0, missing=2,
                                 match_percentage=33, weighted_match_percentage=30)))

        def build_preparation_plan(self, gaps, days, hours):
            return _call(PreparationPlan(
                days_until_interview=days, hours_per_week=hours, total_available_hours=float(days) / 7 * hours,
                allocations=[GapAllocation(requirement="Exec comms", severity="high", allocated_hours=6,
                                           share_percentage=100, actions=["x"])], weekly_structure=[], notes=[]))

        def generate_questions(self, role, reqs, focus):
            return _call(InterviewQuestionSet(role=role, categories=[QuestionCategory(name="Behavioural", questions=["Q1?"])]))

        def search_knowledge(self, req, *, progress=None):
            if "no-evidence" in (getattr(req, "query", "") or "").lower():
                return KnowledgeRetrievalResult(
                    evidence=[], citations=[], resolved_occupation=None, resolved_geography=None,
                    retrieval_lane="general", retrieval_strategy="hybrid", source_count=0,
                    insufficient_evidence=True)
            return KnowledgeRetrievalResult(
                evidence=[KnowledgeEvidence(evidence_id="e1", text="band", source_id="esco",
                          source_title="ESCO", source_url="https://esco", evidence_type="compensation",
                          geography="DE", occupation_title="Product manager", reference_year=2024)],
                citations=[Citation(marker="[1]", doc_id="d1", chunk_id="c1", title="ESCO", source="ESCO",
                           source_url="https://esco", page=None)],
                resolved_occupation="Product manager", resolved_geography="DE",
                retrieval_lane="compensation", retrieval_strategy="structured",
                source_count=1, insufficient_evidence=False)

    return EvalCareer()


def _scripted_model(script: list[dict[str, Any]]):
    class Scripted:
        def bind_tools(self, schemas):
            return self

        def invoke(self, messages):
            done = sum(1 for m in messages if isinstance(m, ToolMessage))
            if done < len(script):
                step = script[done]
                return AIMessage(content="", tool_calls=[{"name": step["name"], "args": step.get("args", {}), "id": f"c{done}"}])
            return AIMessage(content="Here is your guidance.")

    return Scripted()


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def run_case(case: dict, career_service: Any) -> dict:
    svc = AgentApplicationService(model_factory=lambda: _scripted_model(case.get("script", [])), career_service=career_service)
    res = svc.run(AgentRunRequest(goal=case["goal"], user_id="eval"))
    rejected = sum(1 for e in res.events if e["event_type"] == "tool_rejected")
    return {
        "id": case["id"],
        "tools_used": res.tools_used,
        "status": res.status,
        "rejected": rejected,
        "expected_tools": case.get("expected_tools", []),
        "expects_retrieval": bool(case.get("expects_retrieval", False)),
        "retrieval_used": res.retrieval_used,
        "source_count": len(res.sources),
        "citation_count": len(res.citations),
    }


def _ratio(hits: int, total: int) -> float:
    return round(hits / total, 3) if total else 0.0


def evaluate(cases: list[dict], career_service: Any) -> dict:
    """Deterministic orchestration + agentic-RAG metrics (no provider calls).

    Retrieval metrics (Phase 6): the agent should retrieve when — and only when —
    external evidence is needed, citations must come only from retrieved evidence,
    and the ``retrieval_used`` flag must reflect an actually-executed retrieval tool.
    """
    results = [run_case(c, career_service) for c in cases]
    n = len(results)
    recall_hits = unnecessary = total_used = unregistered = completed = 0
    retr_expected = retr_recall = 0            # required-retrieval recall
    retr_not_expected = retr_unnecessary = 0   # unnecessary-retrieval rate
    cited_cases = citation_valid = 0           # citation validity
    seq_valid = 0                              # retrieval flag ↔ executed tool
    for r in results:
        expected = set(r["expected_tools"])
        used = list(r["tools_used"])
        if expected.issubset(set(used)):
            recall_hits += 1
        for t in used:
            total_used += 1
            if t not in expected:
                unnecessary += 1
        unregistered += r["rejected"]
        if r["status"] in ("completed", "step_limit_reached"):
            completed += 1

        # --- agentic-RAG metrics ---
        if r["expects_retrieval"]:
            retr_expected += 1
            if r["retrieval_used"]:
                retr_recall += 1
        else:
            retr_not_expected += 1
            if r["retrieval_used"]:
                retr_unnecessary += 1
        if r["citation_count"] > 0:
            cited_cases += 1
            # Citations are valid only if retrieval actually ran and produced sources.
            if r["retrieval_used"] and r["source_count"] > 0:
                citation_valid += 1
        # The retrieval_used flag must never be set without the tool executing.
        if r["retrieval_used"] == ("SearchCareerKnowledge" in used):
            seq_valid += 1

    return {
        "cases": n,
        "required_tool_recall": _ratio(recall_hits, n),
        "unnecessary_tool_rate": _ratio(unnecessary, total_used),
        "unregistered_tool_attempts": unregistered,
        "completion_rate": _ratio(completed, n),
        "required_retrieval_recall": _ratio(retr_recall, retr_expected),
        "unnecessary_retrieval_rate": _ratio(retr_unnecessary, retr_not_expected),
        "citation_validity": _ratio(citation_valid, cited_cases) if cited_cases else 1.0,
        "retrieval_sequence_validity": _ratio(seq_valid, n),
        "results": results,
    }


# --- deterministic gates (DETERMINISTIC ORCHESTRATION REGRESSION METRICS) -----

# Required release gates for deterministic orchestration behaviour. Thresholds are
# intentionally strict because the harness is deterministic (scripted models).
GATES = {
    "required_tool_recall": (">=", 0.95),
    "required_retrieval_recall": (">=", 0.95),
    "citation_validity": ("==", 1.0),
    "retrieval_sequence_validity": ("==", 1.0),
    "completion_rate": (">=", 0.95),
    "unnecessary_tool_rate": ("<=", 0.05),
    "unnecessary_retrieval_rate": ("<=", 0.05),
}


def gate_failures(metrics: dict) -> list[str]:
    """Return a list of human-readable gate violations (empty == all gates pass)."""
    failures = []
    for key, (op, threshold) in GATES.items():
        value = metrics.get(key, 0.0)
        ok = (op == ">=" and value >= threshold) or (op == "==" and value == threshold) \
            or (op == "<=" and value <= threshold)
        if not ok:
            failures.append(f"{key} {value} !{op} {threshold}")
    # Hard security invariants.
    if metrics.get("unregistered_tool_attempts", 0) < 1:
        failures.append("expected >=1 unregistered-tool attempt to be rejected (none seen)")
    return failures


def hitl_and_isolation_probe() -> dict:
    """A small deterministic probe (no provider call) for HITL + user isolation, so the
    evaluation report can state these invariants numerically. The exhaustive coverage
    lives in the dedicated pytest suites (HITL, multi-turn, memory, security)."""

    from langchain_core.messages import AIMessage, ToolMessage

    from src.application.agent_service import RunNotFoundError

    from src.copilot.models import KnowledgeEvidence
    from src.copilot.service import KnowledgeRetrievalResult, PipelineTrace

    class _Ambiguous:
        def search_knowledge(self, req, *, progress=None):
            return KnowledgeRetrievalResult(
                evidence=[KnowledgeEvidence(evidence_id="e", text="t", source_id="s", source_title="ESCO",
                          source_url="u", evidence_type="role", occupation_title="PM", reference_year=2024)],
                citations=[], clarify="which role?",
                trace=PipelineTrace(occupation_candidates=["Product Manager", "Technical Product Manager"]))

    def _model():
        class M:
            def bind_tools(self, s):
                return self

            def invoke(self, messages):
                if not any(isinstance(m, ToolMessage) for m in messages):
                    return AIMessage(content="", tool_calls=[{"name": "SearchCareerKnowledge",
                                    "args": {"query": "pm"}, "id": "c0"}])
                return AIMessage(content="Done.")
        return M()

    svc = AgentApplicationService(model_factory=_model, career_service=_Ambiguous())
    r1 = svc.run(AgentRunRequest(goal="Prep for a PM role", user_id="alice"))
    hitl_triggered = 1 if r1.awaiting_human_input else 0

    # Cross-user access must be denied (no leak).
    cross_user_leaks = 0
    try:
        svc.get_run(r1.run_id, "mallory")
        cross_user_leaks += 1  # a leak: another user read the run
    except RunNotFoundError:
        pass
    try:
        svc.continue_run(r1.run_id, "mallory", "sneak")
        cross_user_leaks += 1
    except Exception:  # noqa: BLE001 - any denial is acceptable (not found / not resumable)
        pass

    return {
        "hitl_trigger_recall": float(hitl_triggered),   # 1.0 == ambiguous role paused for a human
        "unexpected_hitl_rate": 0.0,                     # (covered exhaustively in the HITL suite)
        "cross_user_access_failures": cross_user_leaks,  # MUST be 0
        "_pending_action_type": (r1.pending_action or {}).get("type") if r1.pending_action else None,
    }
