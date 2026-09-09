"""Post-Sprint-4 P2 — HITL edit-before-save for approved preparation memory.

The candidate can approve the proposed memory as-is, edit it before saving, or reject
it. An edit is validated (same allowlist/bounds as a normal write) BEFORE the graph
resumes; it can never smuggle arbitrary graph-state. No provider calls.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.human import InvalidHumanDecision, validate_decision
from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService
from src.application.errors import ValidationError
from src.application.memory_service import MemoryApplicationService
from src.persistence import User, init_db, make_engine, make_session_factory
from src.repository import MemoryRepository


# --- unit: validate_decision with an edited memory --------------------------


def _pending(action_id="a1"):
    return {"action_id": action_id, "type": "approve_memory",
            "options": ["approve", "reject"],
            "data": {"category": "recurring_gap", "summary": "orig", "target_role": None}}


def test_edited_memory_accepted_and_normalised():
    out = validate_decision(_pending(), {
        "action_id": "a1", "decision": "approve",
        "memory": {"category": "strength", "summary": "  Edited  ", "target_role": "  PM "}})
    assert out["memory"] == {"category": "strength", "summary": "Edited", "target_role": "PM"}


def test_edited_invalid_category_rejected():
    with pytest.raises(InvalidHumanDecision):
        validate_decision(_pending(), {"action_id": "a1", "decision": "approve",
                                       "memory": {"category": "medical", "summary": "x"}})


def test_edited_overlong_summary_rejected():
    with pytest.raises(InvalidHumanDecision):
        validate_decision(_pending(), {"action_id": "a1", "decision": "approve",
                                       "memory": {"category": "strength", "summary": "x" * 501}})


def test_edited_extra_state_field_rejected():
    # pinned / source_run_id / user_id / arbitrary keys are all rejected.
    for extra in ({"pinned": True}, {"source_run_id": "r"}, {"user_id": 9}, {"foo": 1}):
        with pytest.raises(InvalidHumanDecision):
            validate_decision(_pending(), {"action_id": "a1", "decision": "approve",
                                           "memory": {"category": "strength", "summary": "ok", **extra}})


def test_memory_ignored_on_reject_and_non_memory_actions():
    # A `memory` on a reject is simply not carried through.
    out = validate_decision(_pending(), {"action_id": "a1", "decision": "reject",
                                         "memory": {"category": "strength", "summary": "x"}})
    assert "memory" not in out


# --- service-level: edit-before-save through the graph -----------------------


class _ProposeModel:
    def __init__(self, cat="recurring_gap", summary="Stakeholder comms under pressure", role="PM"):
        self._p = (cat, summary, role)

    def bind_tools(self, s):
        return self

    def invoke(self, messages):
        if not any(isinstance(m, ToolMessage) for m in messages):
            cat, summary, role = self._p
            return AIMessage(content="", tool_calls=[{"name": "ProposePreparationMemory",
                             "args": {"category": cat, "summary": summary, "target_role": role}, "id": "c0"}])
        return AIMessage(content="Approve to remember.")


def _svc():
    engine = make_engine("sqlite://")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        s.add(User(subject="u1", provider="test"))
        s.commit()
    mem = MemoryApplicationService(MemoryRepository(sf))
    svc = AgentApplicationService(model_factory=lambda: _ProposeModel(), career_service=object(),
                                  memory_service=mem)
    return svc, mem


def _propose(svc):
    res = svc.run(AgentRunRequest(goal="remember this", user_id="1"))
    assert res.awaiting_human_input and res.pending_action["type"] == "approve_memory"
    return res


def test_original_approval_saves_original(mem_role="PM"):
    svc, mem = _svc()
    res = _propose(svc)
    svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "approve"})
    saved = mem.list(1)
    assert len(saved) == 1 and saved[0].summary == "Stakeholder comms under pressure"
    assert saved[0].category == "recurring_gap"


def test_edited_approval_saves_edited():
    svc, mem = _svc()
    res = _propose(svc)
    svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "approve",
                                 "memory": {"category": "strength", "summary": "Refined fact", "target_role": "Senior PM"}})
    saved = mem.list(1)
    assert len(saved) == 1 and saved[0].summary == "Refined fact"
    assert saved[0].category == "strength" and saved[0].target_role == "Senior PM"
    assert saved[0].pinned is False  # pinning is a Settings action, never via approval


def test_invalid_edited_category_rejected_before_resume():
    svc, mem = _svc()
    res = _propose(svc)
    with pytest.raises(ValidationError):
        svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "approve",
                                     "memory": {"category": "medical", "summary": "x"}})
    assert mem.list(1) == []  # nothing written; run stays paused
    assert svc.get_run(res.run_id, "1").awaiting_human_input is True


def test_overlong_edited_summary_rejected_before_resume():
    svc, mem = _svc()
    res = _propose(svc)
    with pytest.raises(ValidationError):
        svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "approve",
                                     "memory": {"category": "strength", "summary": "x" * 501}})
    assert mem.list(1) == []


def test_extra_state_field_rejected_before_resume():
    svc, mem = _svc()
    res = _propose(svc)
    with pytest.raises(ValidationError):
        svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "approve",
                                     "memory": {"category": "strength", "summary": "ok", "pinned": True}})
    assert mem.list(1) == []


def test_edited_then_reject_writes_nothing():
    svc, mem = _svc()
    res = _propose(svc)
    svc.resume(res.run_id, "1", {"action_id": res.pending_action["action_id"], "decision": "reject",
                                 "memory": {"category": "strength", "summary": "ignored"}})
    assert mem.list(1) == []


def test_resume_retry_creates_one_memory():
    svc, mem = _svc()
    res = _propose(svc)
    aid = res.pending_action["action_id"]
    svc.resume(res.run_id, "1", {"action_id": aid, "decision": "approve",
                                 "memory": {"category": "strength", "summary": "Once", "target_role": None}})
    # A replayed resume for the already-applied action is a no-op (idempotent).
    from src.application.agent_service import RunNotResumableError
    with pytest.raises(RunNotResumableError):
        svc.resume(res.run_id, "1", {"action_id": aid, "decision": "approve",
                                     "memory": {"category": "strength", "summary": "Once", "target_role": None}})
    assert len(mem.list(1)) == 1
