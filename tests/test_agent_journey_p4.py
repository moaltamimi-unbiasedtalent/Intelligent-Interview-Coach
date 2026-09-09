"""Post-Sprint-4 P4 — candidate journey + handoff-provenance derivation.

Pure, deterministic derivation from safe agent state (no model call, no private
state). Covers every journey transition and handoff-provenance case, plus the
end-to-end shape through the agent service.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.agent.journey import (
    STAGE_COMPLETE,
    STAGE_IN_PROGRESS,
    STAGE_NOT_STARTED,
    derive_handoff_summary,
    derive_journey,
)
from src.agent.models import AgentRunRequest
from src.application.agent_service import AgentApplicationService


def _reqs(role="Product Manager"):
    return {"role_title": role, "required_skills": ["a"], "technologies": []}


def _gaps(*names):
    return {"priority_gaps": [{"requirement": n, "category": "skill", "severity": "high", "reason": "x"} for n in names]}


def _plan(*names):
    return {"allocations": [{"requirement": n, "severity": "high", "allocated_hours": 2,
                             "share_percentage": 50, "actions": []} for n in names],
            "total_available_hours": 4}


def _questions(n=3):
    return {"categories": [{"questions": [{"question": f"q{i}"} for i in range(n)]}]}


# --- journey stages ----------------------------------------------------------


def test_empty_run_all_not_started():
    j = derive_journey({})
    assert j["understand"]["status"] == STAGE_NOT_STARTED
    assert j["prepare"]["status"] == STAGE_NOT_STARTED
    assert j["practise"]["status"] == STAGE_NOT_STARTED


def test_role_only_is_understand_in_progress():
    j = derive_journey({"target_role": "PM"})
    assert j["understand"]["status"] == STAGE_IN_PROGRESS
    assert j["understand"]["role_known"] is True


def test_jd_analysed_completes_understand():
    j = derive_journey({"target_role": "PM", "requirements": _reqs()})
    assert j["understand"]["status"] == STAGE_COMPLETE
    assert j["understand"]["requirements_known"] is True


def test_retrieval_only_is_understand_in_progress_without_role():
    j = derive_journey({"retrieval_used": True})
    assert j["understand"]["status"] == STAGE_IN_PROGRESS
    assert j["understand"]["evidence_used"] is True


def test_gaps_known_is_prepare_in_progress():
    j = derive_journey({"target_role": "PM", "requirements": _reqs(), "gaps": _gaps("Comms")})
    assert j["prepare"]["status"] == STAGE_IN_PROGRESS
    assert j["prepare"]["gaps_known"] is True


def test_plan_known_completes_prepare():
    j = derive_journey({"requirements": _reqs(), "gaps": _gaps("Comms"), "preparation_plan": _plan("Comms")})
    assert j["prepare"]["status"] == STAGE_COMPLETE
    assert j["prepare"]["plan_known"] is True


def test_questions_known_completes_prepare():
    j = derive_journey({"requirements": _reqs(), "questions": _questions()})
    assert j["prepare"]["status"] == STAGE_COMPLETE
    assert j["prepare"]["questions_known"] is True


def test_handoff_pending_is_practise_in_progress():
    j = derive_journey({"target_role": "PM", "requirements": _reqs(),
                        "pending_action": {"type": "approve_practice_handoff"}})
    assert j["practise"]["status"] == STAGE_IN_PROGRESS


def test_handoff_approved_completes_practise():
    j = derive_journey({"target_role": "PM", "requirements": _reqs(), "handoff_approved": True})
    assert j["practise"]["status"] == STAGE_COMPLETE
    assert j["practise"]["handoff_approved"] is True


def test_journey_exposes_no_raw_state():
    j = derive_journey({"target_role": "PM", "requirements": _reqs(), "gaps": _gaps("Comms")})
    blob = repr(j)
    # Only booleans + statuses — never the raw requirement/gap content.
    assert "required_skills" not in blob and "Comms" not in blob


# --- handoff provenance ------------------------------------------------------


def test_handoff_none_without_role():
    assert derive_handoff_summary({}) is None


def test_confirmed_role_provenance():
    s = derive_handoff_summary({"confirmed_target_role": "Senior PM"})
    assert s["target_role"] == {"value": "Senior PM", "source": "confirmed_role"}


def test_analysed_role_provenance():
    s = derive_handoff_summary({"requirements": _reqs("Data Scientist")})
    assert s["target_role"] == {"value": "Data Scientist", "source": "job_analysis"}


def test_gap_focus_provenance():
    s = derive_handoff_summary({"confirmed_target_role": "PM", "gaps": _gaps("Stakeholder comms", "Metrics")})
    assert {"value": "Stakeholder comms", "source": "gap_analysis"} in s["focus_areas"]
    assert len(s["focus_areas"]) == 2


def test_plan_focus_provenance_when_no_gaps():
    s = derive_handoff_summary({"confirmed_target_role": "PM", "preparation_plan": _plan("Leadership")})
    assert s["focus_areas"] == [{"value": "Leadership", "source": "preparation_plan"}]


def test_generated_question_provenance():
    s = derive_handoff_summary({"confirmed_target_role": "PM", "questions": _questions(5)})
    assert s["question_count"] == 5 and s["question_source"] == "question_generator"


def test_missing_fields_are_omitted_no_fabrication():
    s = derive_handoff_summary({"confirmed_target_role": "PM"})
    assert set(s.keys()) == {"target_role"}  # no focus_areas / question_count invented


# --- end-to-end through the service ------------------------------------------


def test_service_exposes_journey_and_handoff():
    class M:
        def bind_tools(self, s):
            return self

        def invoke(self, messages):
            return AIMessage(content="Here are some tips.")
    svc = AgentApplicationService(model_factory=lambda: M(), career_service=object())
    res = svc.run(AgentRunRequest(goal="tips?", target_role="PM", user_id="u1"))
    assert res.journey["understand"]["status"] in (STAGE_IN_PROGRESS, STAGE_COMPLETE)
    # A role was provided, so a handoff summary exists with truthful provenance.
    assert res.handoff_summary["target_role"]["value"] == "PM"
