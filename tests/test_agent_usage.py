"""Post-Sprint-4 P1 — safe Agent usage accounting.

Covers the pure aggregation rules (counts, truthful complete/partial, no double
counting, cost) and the end-to-end capture through the agent service. No provider
calls: fake models carry ``usage_metadata`` exactly as LangChain would.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.models import AgentRunRequest
from src.agent.usage import aggregate_usage, usage_from_message
from src.application.agent_service import AgentApplicationService


def _ai(content="", *, tools=None, usage=None):
    kw = {}
    if tools:
        kw["tool_calls"] = tools
    if usage:
        kw["usage_metadata"] = usage
    return AIMessage(content=content, **kw)


# --- pure: message extraction -----------------------------------------------


def test_usage_from_message_reads_tokens():
    e = usage_from_message(_ai("hi", usage={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}))
    assert e["has_usage"] and e["input_tokens"] == 100 and e["total_tokens"] == 120
    assert e["kind"] == "agent" and e["model_calls"] == 1


def test_usage_from_message_missing_is_not_zero():
    e = usage_from_message(_ai("hi"))
    # Counted as a call, but usage is UNKNOWN — never silently 0.
    assert e["model_calls"] == 1 and e["has_usage"] is False
    assert e["total_tokens"] is None


# --- pure: aggregation ------------------------------------------------------


def _agent(inp, out, tot, cost=None):
    return {"source": "agent", "kind": "agent", "model_calls": 1, "model": "m",
            "input_tokens": inp, "output_tokens": out, "total_tokens": tot,
            "reported_cost_usd": cost, "has_usage": tot is not None}


def _tool(name, inp, out, tot):
    return {"source": f"tool:{name}", "kind": "tool", "model_calls": 1, "model": "m",
            "input_tokens": inp, "output_tokens": out, "total_tokens": tot,
            "reported_cost_usd": None, "has_usage": tot is not None}


def test_no_double_counting():
    # One agent turn + JD tool call + question-generator call = exactly 3 model calls.
    u = aggregate_usage([
        _agent(100, 20, 120),
        _tool("AnalyzeJobDescription", 200, 40, 240),
        _tool("GenerateInterviewQuestions", 300, 60, 360),
    ])
    assert u.model_calls == 3
    assert u.agent_model_calls == 1 and u.tool_model_calls == 2
    assert u.total_tokens == 720 and u.input_tokens == 600 and u.output_tokens == 120


def test_complete_when_all_calls_report():
    u = aggregate_usage([_agent(10, 2, 12), _tool("AnalyzeJobDescription", 5, 1, 6)])
    assert u.usage_complete is True and u.missing_usage_sources == []


def test_partial_when_a_tool_call_lacks_usage():
    u = aggregate_usage([_agent(10, 2, 12), _tool("AnalyzeJobDescription", None, None, None)])
    assert u.usage_complete is False
    assert u.missing_usage_sources == ["tool:AnalyzeJobDescription"]
    # Known tokens are still summed; unknown is NOT turned into 0.
    assert u.total_tokens == 12 and u.model_calls == 2


def test_cost_reported_summed_else_none():
    with_cost = aggregate_usage([_agent(10, 2, 12, cost=0.01)])
    assert with_cost.estimated_cost_usd == 0.01
    # A call with tokens but no reported/resolvable cost → cost None (no false precision).
    mixed = aggregate_usage([_agent(10, 2, 12, cost=0.01), _tool("AnalyzeJobDescription", 5, 1, 6)])
    assert mixed.estimated_cost_usd is None


def test_cost_resolver_used_when_reported_absent():
    u = aggregate_usage([_agent(1000, 500, 1500)],
                        cost_resolver=lambda model, i, o: 0.001 * i + 0.002 * o)
    assert u.estimated_cost_usd == round(0.001 * 1000 + 0.002 * 500, 10)


def test_empty_usage_is_not_complete_and_costless():
    u = aggregate_usage([])
    assert u.model_calls == 0 and u.usage_complete is False and u.estimated_cost_usd is None


# --- end-to-end: through the agent service -----------------------------------


class _Career:
    def analyze_job_description(self, jd):
        from types import SimpleNamespace

        from src.copilot.tools.schemas import RoleRequirements
        role = RoleRequirements(role_title="PM", seniority="mid", required_skills=["python"],
                                technologies=[], responsibilities=[], likely_interview_themes=[])
        return SimpleNamespace(ok=True, value=role)


def _outer_model(*, second_usage):
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            if not any(isinstance(m, ToolMessage) for m in messages):
                return _ai(tools=[{"name": "AnalyzeJobDescription",
                                   "args": {"job_description": "Build things. Python needed."},
                                   "id": "c0"}],
                           usage={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})
            return _ai("Done.", usage=second_usage)
    return M()


def test_service_counts_agent_and_tool_calls_without_double_count():
    svc = AgentApplicationService(
        model_factory=lambda: _outer_model(second_usage={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60}),
        career_service=_Career())
    res = svc.run(AgentRunRequest(goal="analyse JD", job_description="Build things. Python needed.", user_id="u1"))
    u = res.usage
    # 2 agent turns + 1 model-backed tool call = 3 (never 4+).
    assert u["agent_model_calls"] == 2 and u["tool_model_calls"] == 1 and u["model_calls"] == 3
    # Outer token usage is real; the fake tool made no real provider call → partial.
    assert u["total_tokens"] == 180
    assert u["usage_complete"] is False
    assert "tool:AnalyzeJobDescription" in u["missing_usage_sources"]


def test_service_usage_contains_no_private_content():
    svc = AgentApplicationService(
        model_factory=lambda: _outer_model(second_usage=None),
        career_service=_Career())
    res = svc.run(AgentRunRequest(goal="analyse JD",
                                  job_description="SECRET-JD-TEXT that must not leak",
                                  candidate_background="SECRET-CV-TEXT", user_id="u1"))
    blob = repr(res.usage)
    assert "SECRET-JD-TEXT" not in blob and "SECRET-CV-TEXT" not in blob
    # Only safe numeric/label fields are present.
    assert set(res.usage) == {
        "agent_model_calls", "tool_model_calls", "model_calls", "input_tokens",
        "output_tokens", "total_tokens", "estimated_cost_usd", "usage_complete",
        "missing_usage_sources"}


def test_service_reports_latency():
    svc = AgentApplicationService(
        model_factory=lambda: _outer_model(second_usage=None), career_service=_Career())
    res = svc.run(AgentRunRequest(goal="analyse JD", job_description="x. Python.", user_id="u1"))
    assert isinstance(res.latency_ms, int) and res.latency_ms >= 0
