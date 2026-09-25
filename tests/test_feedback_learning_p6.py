"""Feedback learning (Capstone P6/E7): taxonomy + governed improvement lifecycle. Offline."""

from __future__ import annotations

import subprocess
import sys

import pytest

from src.copilot.feedback_intelligence.improvement import (
    ImprovementStatus, LifecycleError, build_improvement_candidates, transition,
)
from src.feedback_taxonomy import FeedbackCategory, normalize_category

_SIGNALS = [
    {"category": "too_verbose", "surface": "agent_answer", "ref": "a1", "rating": "not_helpful"},
    {"category": "too_verbose", "surface": "agent_answer", "ref": "a2", "rating": "not_helpful"},
    {"category": "poor_source", "surface": "agent_answer", "ref": "a3", "rating": "not_helpful"},
    {"category": "poor_source", "surface": "agent_answer", "ref": "a4", "rating": "not_helpful"},
    {"category": "too_verbose", "surface": "final_report", "ref": "a5", "rating": "helpful"},
]


def test_taxonomy_is_bounded_and_falls_back():
    assert len(FeedbackCategory) == 11
    assert normalize_category("nonsense") == "other"
    assert normalize_category("too_brief") == "too_brief"


def test_aggregation_ignores_positive_and_below_threshold():
    cands = build_improvement_candidates(_SIGNALS, min_support=2)
    cats = {c.problem_category.value for c in cands}
    assert cats == {"too_verbose", "poor_source"}
    assert all(c.status is ImprovementStatus.PROPOSED for c in cands)
    assert all(c.support_count >= 2 for c in cands)


def test_candidates_link_to_prompt_lab_and_carry_no_content():
    cands = build_improvement_candidates(_SIGNALS, min_support=2)
    assert all("Prompt Lab" in c.proposed_experiment for c in cands)
    assert all("comment" not in c.model_dump() for c in cands)


def test_full_lifecycle_requires_human_and_blocks_shortcuts():
    c = build_improvement_candidates(_SIGNALS, min_support=2)[0]
    with pytest.raises(LifecycleError):
        transition(c, ImprovementStatus.IMPLEMENTED, actor_id="admin")  # can't skip
    with pytest.raises(LifecycleError):
        transition(c, ImprovementStatus.TRIAGED, actor_id="")           # needs a human
    for to in (ImprovementStatus.TRIAGED, ImprovementStatus.EXPERIMENTING,
               ImprovementStatus.ACCEPTED, ImprovementStatus.IMPLEMENTED):
        c = transition(c, to, actor_id="admin")
    assert c.status is ImprovementStatus.IMPLEMENTED and len(c.history) == 4


def test_feedback_learning_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_feedback_learning.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
