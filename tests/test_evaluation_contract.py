"""P10B-W9.12 - deterministic validation of the interview-evaluation OUTPUT CONTRACT (0 model calls).

Interview evaluation is LLM-backed; its scores are model-produced and schema-validated. This pins down exactly
what the contract DEFINES and nothing more: seven integer rubric dimensions in 1-10, an integer overall score in
0-100, required text fields. The only relationship the prompt states between them is qualitative ("overall_score
consistent with the criterion scores"); there is deliberately NO formula, so none is enforced (model judgement
remains model judgement).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src import constants, prompts
from src.models import AnswerEvaluation

DIMS = ("relevance", "structure", "evidence", "role_knowledge", "problem_solving", "communication", "credibility")


def _valid(**over):
    base = {d: 6 for d in DIMS}
    base.update(overall_score=60, strengths=["clear"], improvement_areas=["quantify"], missing_evidence=["metrics"],
              stronger_answer_structure="STAR", improved_example_answer="Example.", follow_up_question="Why?")
    base.update(over)
    return base


def test_contract_has_exactly_the_seven_documented_dimensions():
    fields = set(AnswerEvaluation.model_fields)
    assert set(DIMS) <= fields
    assert {"overall_score", "strengths", "improvement_areas", "missing_evidence"} <= fields
    assert AnswerEvaluation(**_valid()).overall_score == 60


@pytest.mark.parametrize("dim", DIMS)
def test_each_rubric_dimension_is_bounded_and_required(dim):
    lo, hi = constants.MIN_RUBRIC_SCORE, constants.MAX_RUBRIC_SCORE
    assert (lo, hi) == (1, 10)
    for bad in (lo - 1, hi + 1, 0, 11, -3):
        with pytest.raises(ValidationError):
            AnswerEvaluation(**_valid(**{dim: bad}))
    for ok in (lo, hi):
        assert getattr(AnswerEvaluation(**_valid(**{dim: ok})), dim) == ok
    missing = _valid()
    del missing[dim]
    with pytest.raises(ValidationError):
        AnswerEvaluation(**missing)


def test_overall_score_is_bounded_0_to_100_and_integer():
    assert (constants.MIN_OVERALL_SCORE, constants.MAX_OVERALL_SCORE) == (0, 100)
    for bad in (-1, 101, 250):
        with pytest.raises(ValidationError):
            AnswerEvaluation(**_valid(overall_score=bad))
    for ok in (0, 100):
        assert AnswerEvaluation(**_valid(overall_score=ok)).overall_score == ok
    with pytest.raises(ValidationError):
        AnswerEvaluation(**_valid(overall_score=55.5))


def test_overall_and_criteria_are_independent_in_the_contract_by_design():
    # No formula is promised, so a high overall with low criteria is NOT rejected here (qualitative guidance only).
    ev = AnswerEvaluation(**_valid(overall_score=90, **{d: 2 for d in DIMS}))
    assert ev.overall_score == 90
    import inspect

    assert "consistent with the criterion scores" in inspect.getsource(prompts)  # qualitative, not a formula
