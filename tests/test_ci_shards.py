"""CI sharding integrity (W12.4F CI hotfix): every test file runs in exactly one shard, the plan is deterministic, a missing or failing shard fails reconciliation, and the workflow
cannot mask a failure. Pure unit tests: no network, no pytest subprocess."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ci_test_shards", ROOT / "scripts" / "ci_test_shards.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
def test_every_test_file_is_in_exactly_one_shard(n):
    assert S.verify(n) == []
    parts = S.plan(n)
    flat = [f for p in parts for f in p]
    assert sorted(flat) == S.discover() and len(flat) == len(set(flat)) and all(parts)


def test_the_plan_is_deterministic_and_reasonably_balanced():
    assert S.plan(4) == S.plan(4)
    w = S.load_weights()
    loads = [sum(w.get(f, 5.0) for f in p) for p in S.plan(4)]
    assert max(loads) <= 1.15 * (sum(loads) / 4)


def test_a_new_test_file_without_a_weight_is_still_assigned(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "load_weights", lambda: {})
    assert S.verify(4) == []


def test_reconcile_accepts_a_complete_green_run_and_rejects_every_gap():
    ok = [{"shard": str(i), "tests": 10, "failures": 0, "errors": 0, "skipped": 1} for i in (1, 2, 3)]
    assert S.reconcile(ok, 3, 30) == []
    assert S.reconcile(ok[:2], 3, 30)                                              # a missing shard
    assert S.reconcile(ok, 3, 31)                                                  # an uncollected test (executed != collected)
    assert S.reconcile(ok, 3, 29)                                                  # a duplicate execution
    bad = [dict(ok[0], failures=1)] + ok[1:]
    assert any("failures" in e for e in S.reconcile(bad, 3, 30))                   # a failing shard
    assert S.reconcile(ok + [dict(ok[0], shard="9")], 3, 40)                       # an unexpected extra shard


def test_summarize_reads_junit_counts(tmp_path):
    x = tmp_path / "j.xml"
    x.write_text('<testsuites><testsuite tests="7" failures="1" errors="0" skipped="2"/></testsuites>', encoding="utf-8")
    assert S.summarize(x, "2") == {"shard": "2", "tests": 7, "failures": 1, "errors": 0, "skipped": 2}
    out = tmp_path / "o.json"
    assert S.main(["summarize", "--junit", str(x), "--shard", "2", "--out", str(out)]) == 0 and json.loads(out.read_text())["tests"] == 7


def test_the_workflow_cannot_mask_a_failure_and_keeps_the_required_check_name():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error" not in text and "|| true" not in text
    wf = yaml.safe_load(text)
    jobs = wf["jobs"]
    assert jobs["python"]["name"] == "Python tests & checks"                       # the stable required-check name
    assert set(jobs["python"]["needs"]) == {"static-guards", "python-tests", "python-evaluators", "python-evaluation-extras"}
    assert jobs["python"]["if"] == "${{ always() }}"
    assert jobs["python-tests"]["needs"] == "static-guards" and jobs["python-evaluators"]["needs"] == "static-guards"
    assert jobs["python-evaluation-extras"]["needs"] == "static-guards"        # the optional-extras job is part of the required aggregate
    assert {"frontend", "legacy-live-component"} <= set(jobs)
    steps = " ".join(str(s.get("run", "")) for s in jobs["python"]["steps"])
    assert "needs.python-tests.result" in steps and "needs.static-guards.result" in steps and "needs.python-evaluators.result" in steps
    assert "needs.python-evaluation-extras.result" in steps


def test_every_evaluator_step_of_the_original_workflow_is_still_present():
    """The set of evaluator and guard commands must never shrink silently (the original workflow had 46 single-line script steps)."""
    import re
    text = WORKFLOW.read_text(encoding="utf-8")
    cmds = set(re.findall(r"python scripts/(eval_[a-z0-9_]+|check_product_coverage_baseline)\.py", text))
    assert len(cmds) >= 45
    for must in ("eval_admin_design", "eval_admin_qualification", "eval_speech_providers", "eval_kb_requalification", "eval_global_corpus", "check_product_coverage_baseline", "eval_release_matrix",
                 "eval_platform_admin", "eval_agent", "eval_restart_recovery"):
        assert must in cmds
