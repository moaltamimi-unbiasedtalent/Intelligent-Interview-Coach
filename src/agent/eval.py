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
    }


def evaluate(cases: list[dict], career_service: Any) -> dict:
    results = [run_case(c, career_service) for c in cases]
    n = len(results)
    recall_hits = 0
    unnecessary = 0
    total_used = 0
    unregistered = 0
    completed = 0
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
    return {
        "cases": n,
        "required_tool_recall": round(recall_hits / n, 3) if n else 0.0,
        "unnecessary_tool_rate": round(unnecessary / total_used, 3) if total_used else 0.0,
        "unregistered_tool_attempts": unregistered,
        "completion_rate": round(completed / n, 3) if n else 0.0,
        "results": results,
    }
