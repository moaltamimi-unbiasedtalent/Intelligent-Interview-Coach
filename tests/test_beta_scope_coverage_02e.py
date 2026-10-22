"""02E: the frozen beta-scope coverage measure beside the preserved historical gate. Offline; reads committed files only."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.copilot.evaluation import beta_scope_coverage as B

ROOT = Path(__file__).resolve().parents[1]


def _register(tmp_path, features=(), markets=(), sources=()):
    p = tmp_path / "register.json"
    p.write_text(json.dumps({"enabled_features": list(features), "approved_markets": list(markets),
                             "qualified_sources": [{"source_id": s, "market": m} for s, m in sources]}), encoding="utf-8")
    return B.load_register(p)


# ------------------------------------------------------------------ frozen dataset
def test_case_set_is_frozen_reproducible_and_complete():
    cases, digest = B.load_cases()
    assert digest == B.FROZEN_CASES_SHA256
    assert B._canonical(B.generate_candidate_cases()) == B.CASES_PATH.read_bytes()      # the committed file is exactly the generator's output
    assert len(cases) == len(B.FEATURES) * len(B.MARKETS) * len(B.OCCUPATIONS) == 108
    assert {c.market for c in cases} == set(B.MARKETS) and {c.feature for c in cases} == set(B.FEATURES)


def test_a_modified_case_set_is_refused(tmp_path):
    p = tmp_path / "cases.json"
    p.write_bytes(B.CASES_PATH.read_bytes().replace(b"Accountant", b"Plumber", 1))
    with pytest.raises(B.CoverageDatasetError):
        B.load_cases(p, expected_sha256=B.FROZEN_CASES_SHA256)
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(B.CoverageDatasetError):
        B.load_cases(p, expected_sha256=None)
    with pytest.raises(B.CoverageDatasetError):
        B.load_cases(tmp_path / "missing.json", expected_sha256=None)


# ------------------------------------------------------------------ today: nothing is approved
def test_the_committed_register_approves_nothing_and_the_measure_says_so():
    reg = B.load_register()
    assert reg.empty and reg.problems == ()
    rep = B.report_both()
    beta = rep["beta_scope"]
    assert (beta["verdict"], beta["in_scope_cases"], beta["denominator"]) == ("NO_APPROVED_SCOPE", 0, 0)
    assert beta["percent"] is None and beta["sufficient"] is None          # not 0%, not 100%
    assert "not a pass" in beta["statement"] and beta["threshold"] is None
    assert rep["pg_05_claimed"] is False


def test_missing_or_malformed_register_is_empty_with_a_problem_never_assumed_approved(tmp_path):
    assert B.load_register(tmp_path / "none.json").problems == ("register_missing",)
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    r = B.load_register(bad)
    assert r.empty and r.problems == ("register_malformed",)
    r2 = _register(tmp_path, features=["compensation"], markets=["DE"], sources=[("kldb", "UK")])   # source qualified for a market that is not approved
    assert r2.empty and "qualified_source_for_unapproved_market" in r2.problems
    assert _register(tmp_path, features=["nope"], markets=["DE"], sources=[("kldb", "DE")]).problems == ("unknown_feature_in_register",)


# ------------------------------------------------------------------ the scope rule: enabled x approved x qualified
def test_scope_is_the_intersection_of_feature_market_and_a_qualified_source(tmp_path):
    cases, digest = B.load_cases()
    reg = _register(tmp_path, features=["compensation", "licence"], markets=["DE", "UK"], sources=[("ba_entgeltatlas", "DE"), ("ons_ashe", "UK")])
    out = B.beta_scope_measure(reg, cases, digest)
    # 2 features x 2 markets x 2 occupations, each cell has a qualified source in the case's source family
    assert out["in_scope_cases"] == 8 and out["verdict"] == "NOT_EVALUATED" and out["percent"] is None
    only_de = _register(tmp_path, features=["compensation"], markets=["DE", "UK"], sources=[("ba_entgeltatlas", "DE")])
    assert B.beta_scope_measure(only_de, cases, digest)["in_scope_cases"] == 2          # UK approved but no UK source qualified
    wrong_source = _register(tmp_path, features=["compensation"], markets=["DE"], sources=[("onet", "DE")])
    assert B.beta_scope_measure(wrong_source, cases, digest)["in_scope_cases"] == 0     # a US source never qualifies a German case
    no_feature = _register(tmp_path, features=[], markets=["DE"], sources=[("kldb", "DE")])
    assert B.beta_scope_measure(no_feature, cases, digest)["verdict"] == "NO_APPROVED_SCOPE"


def test_percentage_is_reported_only_with_outcomes_for_every_in_scope_case_and_never_a_pass(tmp_path):
    cases, digest = B.load_cases()
    reg = _register(tmp_path, features=["compensation"], markets=["DE"], sources=[("kldb", "DE")])
    scope = [c.case_id for c in cases if c.feature == "compensation" and c.market == "DE"]
    assert len(scope) == 2
    partial = B.beta_scope_measure(reg, cases, digest, {scope[0]: True})
    assert partial["verdict"] == "NOT_EVALUATED" and partial["percent"] is None
    full = B.beta_scope_measure(reg, cases, digest, {scope[0]: True, scope[1]: False, "unrelated": True})
    assert (full["sufficient"], full["denominator"], full["percent"]) == (1, 2, 50.0)
    assert full["verdict"] == "REPORTED_NO_THRESHOLD" and full["threshold"] is None       # no threshold exists: never PASS


# ------------------------------------------------------------------ historical record preserved, reported together
def test_historical_measure_is_read_from_the_record_and_unchanged():
    h = B.historical_measure()
    dev, clean = h["profiles"]["developer_local"], h["profiles"]["clean_checkout"]
    assert (dev["sufficient"], dev["cases"], dev["required_for_gate"], dev["verdict"]) == (386, 412, 392, "FAIL")
    assert (clean["sufficient"], clean["cases"], clean["required_for_gate"], clean["verdict"]) == (258, 412, 392, "FAIL")
    assert h["unchanged"] is True and h["threshold_percent"] == 95


def test_historical_verdict_is_derived_from_the_recorded_counts_not_hard_coded(tmp_path):
    rec = json.loads(B.HISTORICAL_BASELINE_PATH.read_text(encoding="utf-8"))
    rec["profiles"]["developer_local"]["sufficient"] = 392
    p = tmp_path / "b.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    assert B.historical_measure(p)["profiles"]["developer_local"]["verdict"] == "AT_OR_ABOVE_GATE_REPORTED"
    rec["profiles"]["developer_local"]["cases"] = 400          # a changed denominator is never a pass
    p.write_text(json.dumps(rec), encoding="utf-8")
    assert B.historical_measure(p)["profiles"]["developer_local"]["verdict"] == "FAIL"
    with pytest.raises(B.CoverageDatasetError):
        B.historical_measure(tmp_path / "missing.json")


def test_both_measures_are_always_reported_together(tmp_path):
    for reg in (B.load_register(), _register(tmp_path, features=["compensation"], markets=["DE"], sources=[("kldb", "DE")])):
        rep = B.report_both(register=reg)
        assert set(rep) >= {"historical_gate", "beta_scope", "reporting_rule"}
        assert rep["historical_gate"]["profiles"] and rep["beta_scope"]["measure_id"] == B.MEASURE_ID
        assert "never called the original gate" in rep["reporting_rule"]
    # the signature offers no way to ask for one measure only
    import inspect
    assert not {"only", "historical_only", "beta_only", "include_historical"} & set(inspect.signature(B.report_both).parameters)


def test_the_evaluator_script_prints_both_measures_and_exits_zero():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "eval_beta_scope_coverage.py")], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr
    text = out.stdout
    assert "HISTORICAL GATE" in text and "BETA-SCOPE MEASURE" in text
    assert "386 of 412" in text and "required 392" in text and "FAIL" in text
    assert "NO_APPROVED_SCOPE" in text and "PG-05 is NOT claimed met" in text


def test_the_evaluator_checks_catch_a_report_missing_a_measure_or_a_changed_record():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import eval_beta_scope_coverage as E
    finally:
        sys.path.pop(0)
    good = B.report_both()
    assert E.check(good) == []
    assert E.check({"beta_scope": good["beta_scope"]}) == ["both_measures_not_reported_together"]
    changed = json.loads(json.dumps(good))
    changed["historical_gate"]["profiles"]["developer_local"]["sufficient"] = 392
    assert "historical_record_changed:developer_local" in E.check(changed)
    claimed = json.loads(json.dumps(good))
    claimed["pg_05_claimed"] = True
    assert "pg_05_claimed" in E.check(claimed)
    bad_empty = json.loads(json.dumps(good))
    bad_empty["beta_scope"]["percent"] = 100.0
    assert "empty_scope_reports_a_figure" in E.check(bad_empty)


def test_the_historical_evaluators_are_untouched():
    """The historical evaluator semantics must not be edited by 02E (a content check of the two historical scripts against origin/main is done in CI review;
    here: they do not import or reference the beta-scope module)."""
    for name in ("check_product_coverage_baseline.py", "eval_product_coverage.py"):
        assert "beta_scope" not in (ROOT / "scripts" / name).read_text(encoding="utf-8")
