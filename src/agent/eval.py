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
