"""Prompt Lab (Capstone P6/E6): isolation, no auto-promotion, versioning. Offline."""

from __future__ import annotations

import subprocess
import sys

import pytest

from src.application.prompt_lab import (
    EvaluationSet, PromptLabError, PromptLabService, Variant,
)
from src.llm.policy import OPERATION_POLICY


def _svc(tmp_path):
    return PromptLabService(base_dir=tmp_path)


def _experiment(svc):
    es = EvaluationSet(evaluation_set_id="mp", version="1.0", evaluator="model_policy_floors",
                       cases=[{"user_profile": "fast"}, {"user_profile": "advanced"}])
    return svc.create_experiment(
        title="t", hypothesis="h", created_by="admin", evaluation_set=es,
        variants=[Variant(variant_id="base", label="b", is_baseline=True, config={"operation": "orchestration"}),
                  Variant(variant_id="v2", label="v", config={"operation": "final_response"})])


def test_create_requires_exactly_one_baseline(tmp_path):
    svc = _svc(tmp_path)
    es = EvaluationSet(evaluation_set_id="x", version="1", evaluator="model_policy_floors")
    with pytest.raises(PromptLabError):
        svc.create_experiment(title="t", hypothesis="h", created_by="a", evaluation_set=es,
                              variants=[Variant(variant_id="a", label="a", is_baseline=False)])


def test_unknown_evaluator_rejected(tmp_path):
    svc = _svc(tmp_path)
    es = EvaluationSet(evaluation_set_id="x", version="1", evaluator="do_anything")
    with pytest.raises(PromptLabError):
        svc.create_experiment(title="t", hypothesis="h", created_by="a", evaluation_set=es,
                              variants=[Variant(variant_id="a", label="a", is_baseline=True)])


def test_run_is_isolated_and_versioned(tmp_path):
    snapshot = {op.value: p.min_capability.value for op, p in OPERATION_POLICY.items()}
    svc = _svc(tmp_path)
    exp = svc.run_experiment(_experiment(svc).experiment_id)
    assert exp.status.value == "completed" and len(exp.runs) == 2
    assert all(r.production_versions.get("model_policy_version") for r in exp.runs)
    assert all(r.metrics for r in exp.runs)
    # production policy unchanged by the run
    assert {op.value: p.min_capability.value for op, p in OPERATION_POLICY.items()} == snapshot


def test_no_promotion_without_review_and_never_applies(tmp_path):
    svc = _svc(tmp_path)
    exp = svc.run_experiment(_experiment(svc).experiment_id)
    with pytest.raises(PromptLabError):
        svc.record_promotion_decision(exp.experiment_id, decided_by="admin", outcome="recommend_promote")
    svc.add_review(exp.experiment_id, reviewer_id="admin", outcome="approve")
    exp = svc.record_promotion_decision(exp.experiment_id, decided_by="admin",
                                        outcome="recommend_promote", winning_variant_id="v2")
    assert exp.promotion.applied_to_production is False


def test_prompt_lab_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_prompt_lab.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
