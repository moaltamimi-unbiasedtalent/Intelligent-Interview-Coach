"""P10C-G final hardening: self-tests of the product-coverage regression guard and of baseline governance. Deterministic; synthetic evaluator output; the committed baselines are only read."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_product_coverage_baseline", ROOT / "scripts/check_product_coverage_baseline.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)
IDS = guard.case_ids()
BASE_FILE = ROOT / "evaluations/product_coverage/baseline_gate_status.json"
DEV = {s: True for s in guard.STORES}
CLEAN = {s: False for s in guard.STORES}


def rows(bad):
    # P10D-R1: the evaluator also emits the source-backed columns; for these synthetic rows the two measurements are identical (the V2 checks are tested in test_p10d_r1_grounding_coverage.py).
    return [{"id": i, "insufficient_ok": "False" if i in bad else "True", "source_backed_ok": "False" if i in bad else "True", "coverage_basis": "none"} for i in IDS]


def summary(bad):
    return guard.parse_results(rows(set(bad)), IDS)


BAD = IDS[:26]


def test_01_identical_results_pass():
    r = guard.compare(summary(BAD), summary(BAD))
    assert r["ok"] and r["regression_status"] == "PASS" and r["regressions"] == [] and r["improvements"] == [] and r["failures"] == []


def test_02_a_genuine_improvement_passes_the_regression_comparison():
    r = guard.compare(summary(BAD[1:]), summary(BAD))
    assert r["ok"] and r["improvements"] == [BAD[0]] and r["regression_status"] == "PASS"


def test_03_one_newly_insufficient_case_fails():
    r = guard.compare(summary(BAD + [IDS[100]]), summary(BAD))
    assert not r["ok"] and r["regressions"] == [IDS[100]] and r["regression_status"] == "FAIL"


def test_04_an_equal_total_with_different_failed_ids_fails():
    now = BAD[1:] + [IDS[100]]                                     # one case resolved, one case regressed: the total is unchanged
    base, cur = summary(BAD), summary(now)
    assert base["sufficient"] == cur["sufficient"]
    r = guard.compare(cur, base)
    assert not r["ok"] and r["regressions"] == [IDS[100]] and r["improvements"] == [BAD[0]]


def test_05_a_lower_sufficient_count_fails():
    r = guard.compare(summary(BAD + IDS[100:103]), summary(BAD))
    assert not r["ok"] and any("lower than the baseline" in f for f in r["failures"])


def test_06_a_changed_denominator_fails():
    with pytest.raises(guard.GuardError):
        guard.parse_results(rows(set(BAD))[:-1], IDS)                                                  # a case silently dropped
    cur = {**summary(BAD), "cases": 411}
    assert not guard.compare(cur, summary(BAD))["ok"] and guard.compare(cur, summary(BAD))["denominator_changed"]
    with pytest.raises(guard.GuardError):
        guard.parse_results(rows(set(BAD)), IDS[:-1] + ["a-different-case"])                          # identifiers changed


def test_07_a_missing_baseline_fails(tmp_path, monkeypatch):
    r = guard.compare(summary(BAD), None)
    assert not r["ok"] and not r["baseline_present"]
    empty = tmp_path / "b.json"
    empty.write_text(json.dumps({"schema": "x", "profiles": {}, "history": []}))
    monkeypatch.setattr(guard, "BASELINE", empty)
    monkeypatch.setattr(guard, "store_report", lambda root=guard.ROOT: CLEAN)
    monkeypatch.setattr(guard, "run_evaluator", lambda: rows(set(BAD)))
    assert guard.main(["--profile", "clean_checkout"]) == 1


def test_08_an_unknown_or_ambiguous_profile_fails_safely():
    with pytest.raises(guard.GuardError):
        guard.resolve_profile("production", DEV)
    with pytest.raises(guard.GuardError):
        guard.resolve_profile("auto", {**CLEAN, "data/knowledge/roles.db": True})                       # one store present, others absent: ambiguous
    assert guard.resolve_profile("auto", DEV) == "developer_local" and guard.resolve_profile("auto", CLEAN) == "clean_checkout"
    assert guard.resolve_profile("clean_checkout", CLEAN) == "clean_checkout"


def test_09_malformed_evaluator_output_fails_safely(monkeypatch):
    good = rows(set(BAD))
    for bad in ([], [{"id": "x"}], [{**good[0], "insufficient_ok": "maybe"}] + good[1:], good + [good[0]], [{"insufficient_ok": "True"}] + good[1:]):
        with pytest.raises(guard.GuardError):
            guard.parse_results(bad, IDS)
    monkeypatch.setattr(guard, "store_report", lambda root=guard.ROOT: CLEAN)
    monkeypatch.setattr(guard, "run_evaluator", lambda: [{"id": "x"}])
    assert guard.main(["--profile", "clean_checkout"]) == 1
    import subprocess

    class P:
        returncode, stderr = 1, "boom"
    monkeypatch.undo()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: P())
    with pytest.raises(guard.GuardError):
        guard.run_evaluator()                                                                          # an evaluator crash is a guard failure, never a pass


def test_10_a_normal_run_cannot_modify_baselines_and_ci_cannot_update(tmp_path, monkeypatch):
    copy = tmp_path / "b.json"
    shutil.copy(BASE_FILE, copy)
    before = copy.read_bytes()
    monkeypatch.setattr(guard, "BASELINE", copy)
    v2copy = tmp_path / "v2.json"
    shutil.copy(guard.BASELINE_V2, v2copy)
    monkeypatch.setattr(guard, "BASELINE_V2", v2copy)
    monkeypatch.setattr(guard, "store_report", lambda root=guard.ROOT: CLEAN)
    cl = json.loads(copy.read_text())["profiles"]["clean_checkout"]
    monkeypatch.setattr(guard, "run_evaluator", lambda: rows(set(cl["insufficient_case_ids"])))
    assert guard.main(["--profile", "clean_checkout"]) == 0 and copy.read_bytes() == before            # normal evaluation is read-only
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert guard.main(["--profile", "clean_checkout", "--update-profile", "--reason", "x"]) == 1 and copy.read_bytes() == before
    with pytest.raises(guard.GuardError):
        guard.plan_update("clean_checkout", summary(BAD), json.loads(copy.read_text()), "x", None, env={"CI": "1"})


def test_11_unauthorised_baseline_weakening_is_rejected(tmp_path):
    data = {"profiles": {"clean_checkout": summary(BAD)}, "history": []}
    weaker = summary(BAD + [IDS[100]])
    with pytest.raises(guard.GuardError):
        guard.plan_update("clean_checkout", weaker, data, "reason", None, env={})                       # no owner authorization
    with pytest.raises(guard.GuardError):
        guard.plan_update("clean_checkout", weaker, data, "reason", "docs/does-not-exist.md", env={})  # not an existing document
    scratch = tmp_path / "authorisation.md"
    scratch.write_text("an untracked file is not an authorization")
    with pytest.raises(guard.GuardError):
        guard.plan_update("clean_checkout", weaker, data, "reason", str(scratch), env={})
    with pytest.raises(guard.GuardError):
        guard.plan_update("clean_checkout", weaker, data, "  ", None, env={})                           # a reason is always required
    tracked = "docs/capstone/p10/P10C_F2A_CAPSTONE_ENGINEERING_CLOSURE.md"
    rec = guard.plan_update("clean_checkout", weaker, data, "reviewed change", tracked, env={})
    assert rec["weakens_baseline"] and rec["added_failures"] == [IDS[100]] and rec["owner_authorization"]["path"] == tracked and len(rec["owner_authorization"]["sha256"]) == 64
    improve = guard.plan_update("clean_checkout", summary(BAD[1:]), data, "fixed a case", None, env={})
    assert not improve["weakens_baseline"] and improve["resolved_failures"] == [BAD[0]] and improve["owner_authorization"] is None
    with pytest.raises(guard.GuardError):
        guard.plan_update("elsewhere", weaker, data, "reason", None, env={})


def test_12_and_13_the_regression_verdict_and_the_gate_are_separate_and_a_pass_never_implies_the_gate():
    r = guard.compare(summary(BAD), summary(BAD))
    assert r["regression_status"] == "PASS" and r["product_coverage_gate"] == "BELOW_GATE" and r["required_sufficient_for_gate"] == 392 and "not a pass" in r["owner_disposition"]
    assert r["status"] == r["product_coverage_gate"]
    few = IDS[:20]
    at = guard.compare(summary(few), summary(few))
    assert at["current"]["sufficient"] == 392 and at["product_coverage_gate"] == "AT_OR_ABOVE_GATE_REPORTED" and "owner review" in at["owner_disposition"]
    rep = guard.report("clean_checkout", CLEAN, summary(BAD), r)
    assert rep["regression_status"] == "PASS" and rep["product_coverage_gate"] == "BELOW_GATE" and "never combined" in rep["note"]
    md = guard.render_md(rep)
    assert "REGRESSION STATUS: PASS" in md and "PRODUCT COVERAGE GATE: BELOW_GATE" in md and "COVERAGE PASSED" not in md.upper() and "95% ACCEPTANCE ACHIEVED" not in md.upper()


def test_14_results_of_different_profiles_cannot_be_combined():
    with pytest.raises(guard.GuardError):
        guard.resolve_profile("clean_checkout", DEV)                                                    # a developer machine cannot be judged against the clean baseline
    with pytest.raises(guard.GuardError):
        guard.resolve_profile("developer_local", CLEAN)
    d = json.loads(BASE_FILE.read_text())["profiles"]
    assert d["developer_local"]["environment_stores"] != d["clean_checkout"]["environment_stores"]
    assert set(d["developer_local"]["insufficient_case_ids"]) != set(d["clean_checkout"]["insufficient_case_ids"])


def test_15_the_committed_baselines_remain_intact():
    d = json.loads(BASE_FILE.read_text())
    assert d["schema"] == "p10c-g-product-coverage-baseline/2" and d["history"] == []                    # no baseline change has been recorded: none was made in this wave
    pinned = {"developer_local": (386, "592a19ac7fc3afb4c5db1be6dedc4753319c7da53e5a2a94c1f3fc1fecde1e73"), "clean_checkout": (258, "0eae6b990b5a2b6ff338360992a1401796e2e11e367cc277169d072158e4ae2c")}
    for name, (n, digest) in pinned.items():
        p = d["profiles"][name]
        assert p["cases"] == 412 and p["sufficient"] == n and p["insufficient"] == 412 - n and len(p["insufficient_case_ids"]) == 412 - n
        assert hashlib.sha256("\n".join(p["insufficient_case_ids"]).encode()).hexdigest() == digest
        assert p["case_ids_sha256"] == guard.ids_digest(IDS) and p["sufficient"] < guard.compare(summary(BAD), None)["required_sufficient_for_gate"]
    assert guard.GATE_PERCENT == 95 and guard.TOTAL == 412 and len(IDS) == 412
