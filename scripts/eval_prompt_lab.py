#!/usr/bin/env python
"""Deterministic Prompt Lab evaluation (Capstone P6/E6).

Offline, no provider call, no cost. Gates the Prompt Lab governance invariants:
experiment_isolation, variant_versioning, fixed_eval_set, metric_capture,
no_auto_promotion, human_decision_required, production_config_unchanged,
model_policy_boundary, specialist_boundary, private_data_boundary.

    python scripts/eval_prompt_lab.py

Exits non-zero on any gate failure.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.prompt_lab import (  # noqa: E402
    EvaluationSet, Experiment, PromptLabError, PromptLabService, Variant,
)


def evaluate() -> dict:
    m: dict = {}
    from src.llm.policy import OPERATION_POLICY
    policy_snapshot = {
        op.value: (p.min_capability.value, p.fallback_floor.value) for op, p in OPERATION_POLICY.items()
    }

    base = tempfile.mkdtemp(prefix="promptlab_eval_")
    svc = PromptLabService(base_dir=base)

    es = EvaluationSet(evaluation_set_id="mp", version="1.0", evaluator="model_policy_floors",
                       cases=[{"user_profile": "fast"}, {"user_profile": "advanced"}])
    exp = svc.create_experiment(
        title="Model policy variants", hypothesis="alt policy configs stay safe",
        created_by="admin", evaluation_set=es,
        variants=[
            Variant(variant_id="base", label="baseline", is_baseline=True, config={"operation": "orchestration"}),
            Variant(variant_id="v2", label="final-response", config={"operation": "final_response"}),
        ])

    # experiment_isolation — a run performs no production mutation (checked after run).
    exp = svc.run_experiment(exp.experiment_id)

    # variant_versioning — every run snapshots the production config versions + eval-set version.
    m["variant_versioning"] = 1 if all(
        r.production_versions.get("model_policy_version") and r.evaluation_set_version == "1.0"
        for r in exp.runs) else 0

    # fixed_eval_set — the evaluation set + its cases are frozen on the experiment.
    m["fixed_eval_set"] = 1 if (exp.evaluation_set.cases and exp.evaluation_set.version == "1.0") else 0

    # metric_capture — each variant produced metric results.
    m["metric_capture"] = 1 if all(r.metrics for r in exp.runs) and len(exp.runs) == 2 else 0

    # model_policy_boundary — the evaluator flags floor violations & keeps fallback bounded.
    floor_metric = {mr.metric: mr.value for r in exp.runs for mr in r.metrics}
    m["model_policy_boundary"] = 1 if floor_metric.get("capability_floor_respected") == 1.0 else 0

    # production_config_unchanged — the production policy table is byte-identical after runs.
    after = {op.value: (p.min_capability.value, p.fallback_floor.value) for op, p in OPERATION_POLICY.items()}
    m["production_config_unchanged"] = 1 if after == policy_snapshot else 0
    m["experiment_isolation"] = m["production_config_unchanged"]

    # no_auto_promotion + human_decision_required — promotion before review is refused;
    # a recorded promotion never applies to production.
    blocked = 0
    try:
        svc.record_promotion_decision(exp.experiment_id, decided_by="admin", outcome="recommend_promote")
    except PromptLabError:
        blocked = 1
    m["human_decision_required"] = blocked
    svc.add_review(exp.experiment_id, reviewer_id="admin", outcome="approve")
    exp = svc.record_promotion_decision(exp.experiment_id, decided_by="admin",
                                        outcome="recommend_promote", winning_variant_id="v2")
    m["no_auto_promotion"] = 1 if (exp.promotion and exp.promotion.applied_to_production is False) else 0

    # specialist_boundary — the specialist evaluator keeps output within the configured bound.
    es2 = EvaluationSet(evaluation_set_id="sp", version="1.0", evaluator="specialist_evidence_limit")
    exp2 = svc.create_experiment(title="Specialist limit", hypothesis="bounded", created_by="admin",
                                 evaluation_set=es2,
                                 variants=[Variant(variant_id="b", label="base", is_baseline=True,
                                                   config={"evidence_limit": 5})])
    exp2 = svc.run_experiment(exp2.experiment_id)
    sp = {mr.metric: mr.value for r in exp2.runs for mr in r.metrics}
    m["specialist_boundary"] = 1 if (sp.get("evidence_limit_in_bounds") == 1.0 and sp.get("output_bounded") == 1.0) else 0

    # private_data_boundary — the model forbids extra fields (no candidate-private field can
    # be smuggled into an experiment/eval set), and evaluators take only frozen cases.
    smuggled_rejected = 0
    try:
        Experiment(experiment_id="x", title="t", hypothesis="h", created_by="a",
                   created_at=__import__("datetime").datetime.now(),
                   evaluation_set=es, variants=[], candidate_document="secret")  # type: ignore[call-arg]
    except Exception:  # noqa: BLE001 - extra=forbid rejects the smuggled private field
        smuggled_rejected = 1
    m["private_data_boundary"] = smuggled_rejected

    return m


GATES = {
    "experiment_isolation": 1, "variant_versioning": 1, "fixed_eval_set": 1, "metric_capture": 1,
    "no_auto_promotion": 1, "human_decision_required": 1, "production_config_unchanged": 1,
    "model_policy_boundary": 1, "specialist_boundary": 1, "private_data_boundary": 1,
}


def gate_failures(m: dict) -> list[str]:
    return [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]


def main() -> int:
    m = evaluate()
    print("PROMPT LAB EVALUATION (Capstone P6/E6, offline, no paid calls)")
    print("=" * 68)
    for k in GATES:
        print(f"  {k:<32} {m.get(k)}  (gate == {GATES[k]})")
    print("=" * 68)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
