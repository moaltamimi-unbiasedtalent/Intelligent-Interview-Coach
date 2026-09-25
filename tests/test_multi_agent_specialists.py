"""Bounded specialists behind Mo (Capstone P5): isolation, no-fabrication, orchestration.

Deterministic — no provider call. Covers the Role/Evidence/Coach specialists, the
owner-scoped evidence boundary, the deterministic router, and specialist orchestration
through the agent service (a scripted model), plus the deterministic eval gate.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.eval import build_eval_career
from src.agent.models import AgentRunRequest
from src.agent.multi_agent_eval import evaluate, gate_failures
from src.agent.registry import career_tool_registry
from src.agent.specialists import (
    SpecialistName,
    is_valid_specialist,
    recommend_specialists,
    run_coaching_specialist,
    run_evidence_specialist,
    run_role_specialist,
)
from src.agent.specialists.router import RoutingContext
from src.agent.specialists.schemas import (
    CoachingInput,
    EvidenceRequest,
    RoleAnalysisInput,
    RoleBrief,
)
from src.application.agent_service import AgentApplicationService, RunNotFoundError


class _FakeEvidence:
    def __init__(self, by_user):
        self._by_user = by_user

    def approved_claims(self, uid):
        return list(self._by_user.get(int(uid), ([], []))[0])

    def evidence_stories(self, uid):
        return list(self._by_user.get(int(uid), ([], []))[1])


def _svc():
    return _FakeEvidence({
        7: ([{"id": 1, "claim_type": "achievement", "display_text": "Cut latency 40%",
              "source_section": "block 1", "review_state": "accepted"},
             {"id": 2, "claim_type": "skill", "display_text": "Roadmapping",
              "source_page": 1, "review_state": "edited"}],
            [{"id": 10, "title": "Leadership win", "situation": "Led 5", "result": "Shipped",
              "status": "source_backed", "evidence_state": "verified", "competencies": ["Leadership"]}]),
        8: ([{"id": 99, "claim_type": "skill", "display_text": "SECRET other user data",
              "source_page": 1, "review_state": "accepted"}], []),
    })


# --- role specialist ---------------------------------------------------------

def test_role_specialist_builds_brief_from_requirements():
    brief = run_role_specialist(RoleAnalysisInput(requirements={
        "role_title": "PM", "seniority": "senior", "required_skills": ["Roadmapping"],
        "technologies": ["SQL"], "key_responsibilities": ["Own roadmap"]}))
    assert brief.role_title == "PM" and brief.source == "requirements"
    assert "Roadmapping" in brief.key_competencies

def test_role_specialist_role_only_and_insufficient():
    assert run_role_specialist(RoleAnalysisInput(target_role="PM")).source == "role_only"
    assert run_role_specialist(RoleAnalysisInput()).source == "insufficient"


# --- evidence specialist: owner-scoped isolation -----------------------------

def test_evidence_is_owner_scoped_and_isolated():
    svc = _svc()
    req = EvidenceRequest(need="roadmapping latency leadership",
                          competencies=["Roadmapping", "Leadership"])
    a = run_evidence_specialist(req, user_id=7, evidence_service=svc)
    b = run_evidence_specialist(req, user_id=8, evidence_service=svc)
    a_ids = {i.id for i in a.items}
    assert 99 not in a_ids                          # never another user's claim
    assert not any("SECRET" in i.text for i in a.items)
    assert {i.id for i in b.items} != a_ids or not a_ids
    assert "Leadership" in a.covered_competencies    # story 10 covers leadership

def test_evidence_no_owner_returns_empty():
    sel = run_evidence_specialist(EvidenceRequest(need="x"), user_id=None, evidence_service=_svc())
    assert sel.items == [] and sel.notes


def test_evidence_excludes_unapproved_and_revoked_via_boundary():
    # The boundary only ever hands the specialist APPROVED claims + verified stories, so a
    # fake returning only those is faithful; assert rejected/revoked never appear because
    # the repository methods (approved_claims / evidence_stories) exclude them (unit-tested
    # in the documents suite). Here we assert the specialist trusts that contract.
    svc = _FakeEvidence({7: ([{"id": 5, "claim_type": "skill", "display_text": "Python",
                               "source_page": 1, "review_state": "accepted"}], [])})
    sel = run_evidence_specialist(EvidenceRequest(need="python"), user_id=7, evidence_service=svc)
    assert [i.id for i in sel.items] == [5]


# --- coaching specialist: no fabrication -------------------------------------

def test_coaching_clarifies_uncovered_never_invents():
    svc = _svc()
    sel = run_evidence_specialist(
        EvidenceRequest(need="roadmapping", competencies=["Roadmapping", "Kubernetes"]),
        user_id=7, evidence_service=svc)
    brief = RoleBrief(role_title="PM", key_competencies=["Roadmapping", "Kubernetes"])
    plan = run_coaching_specialist(CoachingInput(role_brief=brief, evidence=sel))
    assert "Kubernetes" in plan.gaps
    assert any("Kubernetes" in c for c in plan.clarifications)
    valid = {i.id for i in sel.items}
    assert all(set(r.supporting_evidence_ids) <= valid for r in plan.recommendations)

def test_coaching_reasoner_ids_are_server_validated():
    sel = run_evidence_specialist(EvidenceRequest(need="roadmapping"), user_id=7, evidence_service=_svc())
    brief = RoleBrief(role_title="PM", key_competencies=["Roadmapping"])

    def bogus(_req):
        return {"recommendations": [{"recommendation": "x", "supporting_evidence_ids": [1, 777]}],
                "strengths": [], "gaps": [], "clarifications": [], "confidence": "high"}
    plan = run_coaching_specialist(CoachingInput(role_brief=brief, evidence=sel), reasoner=bogus)
    assert all(777 not in r.supporting_evidence_ids for r in plan.recommendations)

def test_coaching_reasoner_failure_falls_back_deterministically():
    sel = run_evidence_specialist(EvidenceRequest(need="roadmapping"), user_id=7, evidence_service=_svc())
    brief = RoleBrief(role_title="PM", key_competencies=["Roadmapping"])

    def boom(_req):
        raise RuntimeError("provider down")
    plan = run_coaching_specialist(CoachingInput(role_brief=brief, evidence=sel), reasoner=boom)
    assert plan.strengths or plan.gaps  # deterministic fallback still produced a plan


# --- router ------------------------------------------------------------------

def test_router_is_valid_bounded_deterministic():
    ctx = RoutingContext(has_requirements=True, has_owner_evidence=True, wants_coaching=True)
    rec = recommend_specialists(ctx)
    assert rec == [SpecialistName.ROLE_OPPORTUNITY, SpecialistName.CANDIDATE_EVIDENCE,
                   SpecialistName.INTERVIEW_STRATEGY]
    assert all(is_valid_specialist(s.value) for s in rec)
    assert recommend_specialists(ctx) == rec  # deterministic

def test_router_skips_evidence_without_owner():
    rec = recommend_specialists(RoutingContext(has_job_description=True, wants_coaching=True))
    assert SpecialistName.CANDIDATE_EVIDENCE not in rec

def test_unknown_specialist_name_is_invalid():
    assert is_valid_specialist("role_opportunity") is True
    assert is_valid_specialist("do_anything") is False


# --- orchestration behind Mo -------------------------------------------------

def _scripted(script):
    def factory():
        class M:
            def bind_tools(self, schemas):
                return self

            def invoke(self, messages):
                done = sum(1 for m in messages if isinstance(m, ToolMessage))
                if done < len(script):
                    s = script[done]
                    return AIMessage(content="", tool_calls=[{"name": s["name"], "args": s.get("args", {}), "id": f"c{done}"}])
                return AIMessage(content="Here is your coaching.")
        return M()
    return factory


def test_specialist_tools_run_behind_mo_and_populate_packet():
    script = [
        {"name": "AnalyzeRoleOpportunity", "args": {"job_description": "Senior PM"}},
        {"name": "FindCandidateEvidence", "args": {"need": "roadmapping", "competencies": ["Roadmapping"]}},
        {"name": "BuildCoachingStrategy", "args": {}},
    ]
    registry = career_tool_registry(build_eval_career(), evidence_service=_svc())
    svc = AgentApplicationService(model_factory=_scripted(script), registry=registry)
    res = svc.run(AgentRunRequest(goal="Coach me", user_id="7"))
    assert res.status == "completed"
    out = res.specialist_outputs
    assert set(out["specialists_used"]) == {"role_opportunity", "candidate_evidence", "interview_strategy"}
    assert out["coaching_plan"] and out["evidence_selection"] and out["role_brief"]
    # Mo never set retrieval_used via a specialist (owned by SearchCareerKnowledge).
    assert res.retrieval_used is False

def test_coaching_tool_requires_role_first():
    script = [{"name": "BuildCoachingStrategy", "args": {}}]
    registry = career_tool_registry(build_eval_career(), evidence_service=_svc())
    svc = AgentApplicationService(model_factory=_scripted(script), registry=registry)
    res = svc.run(AgentRunRequest(goal="coach", user_id="7"))
    # Missing-prerequisite tool error is surfaced safely; the run still completes.
    assert res.status in ("completed", "step_limit_reached")
    assert not res.specialist_outputs.get("coaching_plan")

def test_specialist_run_is_cross_user_isolated():
    script = [{"name": "FindCandidateEvidence", "args": {"need": "roadmapping"}}]
    registry = career_tool_registry(build_eval_career(), evidence_service=_svc())
    svc = AgentApplicationService(model_factory=_scripted(script), registry=registry)
    res = svc.run(AgentRunRequest(goal="find", user_id="7"))
    try:
        svc.get_run(res.run_id, "mallory")
        assert False, "cross-user read must be denied"
    except RunNotFoundError:
        pass


# --- the deterministic gate --------------------------------------------------

def test_multi_agent_eval_gate_passes():
    metrics = evaluate()
    assert gate_failures(metrics) == []
