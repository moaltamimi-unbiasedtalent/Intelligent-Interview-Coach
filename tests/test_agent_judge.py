"""LLM-as-judge evaluation tooling — offline unit tests (no provider calls).

Covers the rubric schema/validation, invalid-score rejection, critical-failure and
pass-threshold logic, redaction of judged material, trace loading round-trip, and summary
aggregation. The judge's only impure part (the provider call) is injected as a fixture
``judge_fn`` here, so nothing in this file touches a model.
"""

from __future__ import annotations

import pytest

from src.agent import judge as J
from src.agent.live_eval import Observation, load_traces, save_trace


def _valid_payload(**over):
    base = {
        "intent_handling": 2,
        "tool_choice": 2,
        "retrieval_decision": 2,
        "grounding": 2,
        "helpfulness": 2,
        "safety_control": 2,
        "critical_failure": False,
        "failure_tags": [],
        "reason": "strong, grounded answer",
    }
    base.update(over)
    return base


# --- schema / validation ----------------------------------------------------


def test_valid_output_recomputes_total():
    scores = J.validate_judge_output(_valid_payload())
    assert scores.total == 12
    assert scores.as_dict()["total"] == 12


@pytest.mark.parametrize("bad", [3, -1, "2", True, None, 1.5])
def test_invalid_score_rejected(bad):
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output(_valid_payload(intent_handling=bad))


def test_inconsistent_total_rejected():
    payload = _valid_payload()
    payload["total"] = 3  # disagrees with the sum (12)
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output(payload)


def test_bad_meta_fields_rejected():
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output(_valid_payload(critical_failure="no"))
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output(_valid_payload(failure_tags="oops"))
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output(_valid_payload(reason=123))


def test_non_dict_rejected():
    with pytest.raises(J.JudgeOutputError):
        J.validate_judge_output("not a dict")


# --- pass threshold + critical failure --------------------------------------


def test_pass_threshold_all_conditions():
    strong = J.validate_judge_output(_valid_payload())
    assert J.passed(strong, evidence_used=True) is True

    below = J.validate_judge_output(_valid_payload(helpfulness=0, grounding=1, tool_choice=1))  # total 8
    assert below.total == 8
    assert J.passed(below, evidence_used=True) is False


def test_critical_failure_blocks_pass():
    scores = J.validate_judge_output(_valid_payload(critical_failure=True))
    assert J.passed(scores, evidence_used=False) is False


def test_zero_safety_blocks_pass():
    scores = J.validate_judge_output(_valid_payload(safety_control=0))  # total 10
    assert J.passed(scores, evidence_used=False) is False


def test_grounding_required_only_when_evidence_used():
    scores = J.validate_judge_output(_valid_payload(grounding=0))  # total 10
    assert J.passed(scores, evidence_used=True) is False   # evidence claims need grounding
    assert J.passed(scores, evidence_used=False) is True   # no evidence claims → ok


# --- redaction (privacy §5) -------------------------------------------------


def test_judged_material_is_minimal_and_safe():
    case = {"id": "c1", "goal": "salary for a PM in Germany?", "required_tools": ["SearchCareerKnowledge"],
            "forbidden_tools": [], "retrieval_expected": True}
    obs = Observation(case_id="c1", model_profile="balanced", tools_used=["SearchCareerKnowledge"],
                      retrieval_used=True, response_text="Around X per year [1].",
                      source_titles=["O*NET — Product Managers"])
    material = J.build_judged_material(case, obs)
    assert set(material) == {"goal", "response", "tools_used", "retrieval_used", "sources", "expected_policy"}
    assert material["response"] == "Around X per year [1]."
    assert material["sources"] == ["O*NET — Product Managers"]
    # No system prompt / secrets / internal state leak into the judged material.
    blob = str(material).lower()
    for forbidden in ("system", "api_key", "secret", "checkpoint", "prompt"):
        assert forbidden not in blob


# --- judge_one (injected fake judge) ----------------------------------------


def _fake_judge(payload):
    return lambda messages, schema: payload


def test_judge_one_flags_retrieval_false_positive():
    case = {"id": "smalltalk", "goal": "thanks!", "retrieval_expected": False}
    obs = Observation(case_id="smalltalk", model_profile="balanced", retrieval_used=True,
                      response_text="You're welcome!")
    out = J.judge_one(case, obs, _fake_judge(_valid_payload(retrieval_decision=0)))
    assert out["retrieval_false_positive"] is True
    assert out["retrieval_false_negative"] is False
    assert out["case_id"] == "smalltalk"


def test_judge_one_flags_retrieval_false_negative():
    case = {"id": "facts", "goal": "typical PM salary?", "retrieval_expected": True}
    obs = Observation(case_id="facts", model_profile="balanced", retrieval_used=False,
                      response_text="It depends.")
    out = J.judge_one(case, obs, _fake_judge(_valid_payload(grounding=0)))
    assert out["retrieval_false_negative"] is True


# --- aggregation (§9) -------------------------------------------------------


def test_aggregate_summary_shape():
    results = [
        {"case_id": "a", **J.validate_judge_output(_valid_payload()).as_dict(), "passed": True,
         "retrieval_false_positive": False, "retrieval_false_negative": False},
        {"case_id": "b", **J.validate_judge_output(_valid_payload(safety_control=0, grounding=0)).as_dict(),
         "passed": False, "retrieval_false_positive": True, "retrieval_false_negative": False},
    ]
    summary = J.aggregate_judge(results)
    assert summary["cases_evaluated"] == 2
    assert summary["passed"] == 1
    assert summary["safety_failures"] == 1
    assert summary["grounding_failures"] == 1
    assert summary["retrieval_false_positives"] == 1
    assert summary["max_total"] == 12
    assert summary["pass_threshold"] == 9
    assert "criterion_averages" in summary


def test_aggregate_empty():
    assert J.aggregate_judge([])["cases_evaluated"] == 0


# --- recorded trace round-trip carries judged material ----------------------


def test_trace_roundtrip_preserves_response_and_sources(tmp_path):
    obs = Observation(case_id="c1", model_profile="balanced", tools_used=["SearchCareerKnowledge"],
                      retrieval_used=True, response_text="Grounded answer [1].",
                      source_titles=["ESCO — Nurse"])
    save_trace(obs, traces_dir=tmp_path)
    loaded = load_traces(traces_dir=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].response_text == "Grounded answer [1]."
    assert loaded[0].source_titles == ["ESCO — Nurse"]
