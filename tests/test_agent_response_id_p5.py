"""Post-Sprint-4 P5 — stable per-answer response_id for feedback targeting (§8)."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService


class _M:
    def bind_tools(self, s):
        return self

    def invoke(self, messages):
        return AIMessage(content="First answer.")


def test_assistant_answers_carry_a_stable_response_id():
    svc = AgentApplicationService(model_factory=lambda: _M(), career_service=object())
    res = svc.run(AgentRunRequest(goal="hello", user_id="u1"))
    assistant = [m for m in res.conversation if m["role"] == "assistant"]
    assert assistant and assistant[-1]["response_id"] == f"{res.run_id}:1"


def test_response_id_is_absolute_and_stable_across_turns():
    svc = AgentApplicationService(model_factory=lambda: _M(), career_service=object())
    res = svc.run(AgentRunRequest(goal="hello", user_id="u1"))
    first_id = [m for m in res.conversation if m["role"] == "assistant"][-1]["response_id"]
    cont = svc.continue_run(res.run_id, "u1", "and again")
    ids = [m["response_id"] for m in cont.conversation if m["role"] == "assistant"]
    # The first answer keeps its id; the second is a new, distinct absolute id.
    assert first_id in ids and f"{res.run_id}:2" in ids and len(set(ids)) == len(ids)


def test_response_id_is_not_a_content_hash():
    svc = AgentApplicationService(model_factory=lambda: _M(), career_service=object())
    res = svc.run(AgentRunRequest(goal="hello", user_id="u1"))
    rid = [m for m in res.conversation if m["role"] == "assistant"][-1]["response_id"]
    assert rid.startswith(res.run_id + ":") and rid.split(":")[1].isdigit()
