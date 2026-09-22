"""Sprint 4 closure #16 — server-enforced current-market-research capability toggle.

The user can turn bounded current-market research OFF. Enforcement is server-side: the
ResearchCurrentMarket tool is withheld from the model entirely (never offered, never
executed) and the model cannot re-enable it. The other five Career tools and the two
HITL action tools are unaffected. No provider calls.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.agent.models import AgentRunRequest
from src.agent.nodes import make_tools_node
from src.agent.registry import career_tool_registry
from src.application.agent_service import AgentApplicationService

_OTHER_CAREER_TOOLS = (
    "AnalyzeJobDescription", "AnalyzeCandidateGaps", "BuildPreparationPlan",
    "GenerateInterviewQuestions", "SearchCareerKnowledge",
)


def _capturing_model(captured):
    class M:
        def bind_tools(self, schemas):
            captured["schemas"] = [getattr(s, "__name__", str(s)) for s in schemas]
            return self

        def invoke(self, messages):
            return AIMessage(content="tips: use STAR.")

    return M()


def test_current_market_research_available_by_default():
    captured: dict = {}
    svc = AgentApplicationService(model_factory=lambda: _capturing_model(captured), career_service=object())
    svc.run(AgentRunRequest(goal="tips?", user_id="u1"))
    assert "ResearchCurrentMarket" in captured["schemas"]  # default: available
    for t in _OTHER_CAREER_TOOLS:
        assert t in captured["schemas"]


def test_toggle_off_withholds_only_research_tool():
    captured: dict = {}
    svc = AgentApplicationService(model_factory=lambda: _capturing_model(captured), career_service=object())
    svc.run(AgentRunRequest(goal="tips?", user_id="u1", enable_current_market_research=False))
    # The model never even sees the disabled tool ...
    assert "ResearchCurrentMarket" not in captured["schemas"]
    # ... while every other career + HITL tool remains available.
    for t in _OTHER_CAREER_TOOLS + ("ProposePreparationMemory", "RequestPracticeHandoff"):
        assert t in captured["schemas"]


def test_toggle_persists_across_a_continued_turn():
    captured: dict = {}
    svc = AgentApplicationService(model_factory=lambda: _capturing_model(captured), career_service=object())
    res = svc.run(AgentRunRequest(goal="tips?", user_id="u1", enable_current_market_research=False))
    svc.continue_run(res.run_id, "u1", "and more?")
    assert "ResearchCurrentMarket" not in captured["schemas"]  # choice survives the turn


def test_tools_node_rejects_disabled_tool_defense_in_depth():
    """Even if the model somehow names a withheld tool, the tools node refuses to run it."""
    node = make_tools_node(career_tool_registry(object()))
    msg = AIMessage(content="", tool_calls=[{"name": "ResearchCurrentMarket", "id": "c1", "args": {}}])
    out = node({"messages": [msg], "disabled_tools": ["ResearchCurrentMarket"]})
    assert any(h["tool"] == "ResearchCurrentMarket" and h["status"] == "rejected"
               for h in out["tool_history"])
