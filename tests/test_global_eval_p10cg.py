"""P10C-G: the global evaluation corpus, the governance and negative-regression suite, the product-coverage regression guard and the CI wiring. Offline; throwaway SQLite stores; synthetic data only."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

from src.knowledge_foundation import global_eval as G

ROOT = Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def result():
    return G.run_all()


def test_the_whole_global_suite_passes(result):
    assert result["ok"], {"integrity": result["fixture_integrity_errors"], "cases": [c["id"] for c in result["corpus"]["cases"] if not c["ok"]], "gov": [g["id"] for g in result["governance"] if not g["ok"]],
                          "missing": result["matrix"]["missing_tags"], "failing": result["matrix"]["failing_tags"]}
    assert result["corpus"]["total"] == len(G.load_corpus()["cases"]) >= 100 and result["corpus"]["passed"] == result["corpus"]["total"]


def test_every_required_tag_is_exercised_and_passing(result):
    m = result["matrix"]
    assert m["missing_tags"] == [] and m["failing_tags"] == [] and m["exercised"] == m["required_tags"]
    assert set(m["by_group"]) == set(G.REQUIRED_TAGS) and all(v["required"] == v["exercised"] for v in m["by_group"].values())


def test_all_eight_jurisdictions_have_the_full_positive_and_negative_set(result):
    assert set(result["matrix"]["jurisdictions"]) == set(G.JURISDICTIONS) == {"US", "GB", "DE", "FR", "CA", "MX", "BR", "CL"}
    for key, row in result["matrix"]["jurisdictions"].items():
        assert set(row) == set(G.PER_JURISDICTION_CASES) and all(v is True for v in row.values()), key


def test_the_corpus_is_synthetic_and_nothing_becomes_evidence(result):
    c = result["corpus"]
    assert c["fixture_sources_only"] and c["no_source_can_serve_as_evidence"] and c["import_rejections"] == {} and c["invented_values"] == 0 and c["presentable_or_operational"] == 0
    corpus = G.load_corpus()
    assert "SYNTHETIC" in corpus["note"] and all(x["evidence_origin"] == "SYNTHETIC" for x in corpus["cases"])
    assert all(x["qualification_state"] == "SOURCE_QUALIFICATION_PENDING" for x in corpus["cases"] if x.get("internal") is False)


def test_the_evaluator_can_fail_and_a_wrong_expectation_is_caught(result):
    assert result["corpus"]["meta_check_rejects_a_wrong_expectation"] is True
    corpus = copy.deepcopy(G.load_corpus())
    victim = next(c for c in corpus["cases"] if c["id"] == "us-exact-code")
    victim["expect"]["value"] = "1"
    r = G.run_corpus(corpus)
    assert r["passed"] == r["total"] - 1 and [c["id"] for c in r["cases"] if not c["ok"]] == ["us-exact-code"]


def test_fixture_integrity_rules_reject_a_broken_corpus():
    corpus = copy.deepcopy(G.load_corpus())
    corpus["cases"].append(copy.deepcopy(corpus["cases"][0]))                      # duplicate id
    corpus["cases"][1]["evidence_origin"] = "OFFICIAL"                              # not labelled synthetic
    corpus["cases"][2]["scenario"] = "nope"
    errs = G.validate_corpus(corpus)
    assert any("duplicate case ids" in e for e in errs) and any("not labelled synthetic" in e for e in errs) and any("unknown scenario" in e for e in errs)
    bare = copy.deepcopy(G.load_corpus())
    bare["cases"] = [c for c in bare["cases"] if c["id"] != "mx-wrong-edition"]
    assert any("jurisdiction MX: missing case wrong-edition" in e for e in G.validate_corpus(bare))


def test_a_missing_required_tag_fails_the_matrix():
    corpus = G.load_corpus()
    cres = G.run_corpus(corpus)
    cres["cases"] = [c for c in cres["cases"] if "occupation:ambiguous_title" not in c["tags"]]
    m = G.coverage_matrix(corpus, cres, G.run_governance())
    assert "occupation:ambiguous_title" in m["missing_tags"]


def test_every_governance_check_passes_individually_and_says_what_it_did(result):
    assert len(result["governance"]) >= 12
    for g in result["governance"]:
        assert g["ok"] and g["detail"] and g["tags"], g["id"]


def test_the_registry_lifecycle_flags_follow_the_actual_state_names(result):
    ladder = next(g for g in result["governance"] if g["id"] == "g-lifecycle-ladder")
    for name in ("discovered", "licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use", "restricted"):
        assert name in ladder["detail"]


def test_a_crashing_governance_check_is_a_failing_check(monkeypatch):
    def boom(make):
        raise RuntimeError("synthetic crash")
    monkeypatch.setattr(G, "GOVERNANCE", [("g-crash", ["negative:fabricated_mapping"], boom)])
    out = G.run_governance()
    assert out[0]["ok"] is False and "RuntimeError" in out[0]["detail"]


def test_runs_are_deterministic_and_dispose_of_their_temporary_stores(result):
    tmp = Path(tempfile.gettempdir())
    before = {p.name for p in tmp.glob("p10cg_*")}
    again = G.run_all()
    assert again["determinism_hash"] == result["determinism_hash"]
    assert {p.name for p in tmp.glob("p10cg_*")} <= before                          # nothing it created is left behind


def test_the_corpus_generator_output_is_committed():
    gen = _script("gen_global_evaluation_corpus")
    assert gen.main(["--check"]) == 0


def test_the_cli_runner_writes_machine_readable_results_and_refuses_protected_paths(tmp_path):
    mod = _script("eval_global_corpus")
    out = tmp_path / "r.json"
    assert mod.main(["--repeat", "2", "--json", str(out)]) == 0
    d = json.loads(out.read_text())
    assert d["schema"] == "p10c-g-results/1" and d["ok"] and d["deterministic_across_runs"] and d["claims"] == {"product_ready": False, "human_qualified": False, "source_qualified_globally": False,
                                                                                                                    "runtime_approved": False, "product_coverage_gate_passed": False}
    assert set(d["existing_evaluators"]) == set(mod.EXISTING) and all(not v["failed"] for v in d["existing_evaluators"].values())
    with pytest.raises(SystemExit):
        mod.main(["--json", str(ROOT / "data" / "x.json")])
    with pytest.raises(SystemExit):
        mod.main(["--json", str(ROOT / "evaluations" / "x.json")])


# ----------------------------------------------------------------------------------------------------------------------------- product coverage guard
def test_the_product_coverage_guard_fails_on_regression_and_never_reports_a_pass():
    guard = _script("check_product_coverage_baseline")
    base = {"cases": 412, "sufficient": 386, "insufficient": 26, "insufficient_case_ids": [f"c{i}" for i in range(26)]}
    same = guard.compare(dict(base), base)
    assert same["ok"] and same["status"] == "BELOW_GATE" and same["required_sufficient_for_gate"] == 392 and "not a pass" in same["owner_disposition"]
    worse = guard.compare({"cases": 412, "sufficient": 385, "insufficient": 27, "insufficient_case_ids": base["insufficient_case_ids"] + ["new"]}, base)
    assert not worse["ok"] and worse["regressions"] == ["new"]
    better = guard.compare({"cases": 412, "sufficient": 387, "insufficient": 25, "insufficient_case_ids": base["insufficient_case_ids"][1:]}, base)
    assert better["ok"] and better["improvements"] == ["c0"] and better["status"] == "BELOW_GATE"                     # an improvement is reported, never silently accepted as a pass
    shrunk = guard.compare({"cases": 411, "sufficient": 386, "insufficient": 25, "insufficient_case_ids": base["insufficient_case_ids"][1:]}, base)
    assert not shrunk["ok"] and shrunk["denominator_changed"]
    assert not guard.compare(dict(base), None)["ok"]                                                                    # no baseline for the environment: fail, do not guess


def test_the_committed_product_baselines_are_honest():
    d = json.loads((ROOT / "evaluations/product_coverage/baseline_gate_status.json").read_text())
    assert set(d["profiles"]) == {"developer_local", "clean_checkout"}
    assert d["profiles"]["developer_local"]["sufficient"] == 386 and d["profiles"]["clean_checkout"]["sufficient"] == 258
    assert all(p["cases"] == 412 and p["sufficient"] < 392 for p in d["profiles"].values())                              # both below the unchanged 95% gate (392)
    assert "NOT passes" in d["note"]


# --------------------------------------------------------------------------------------------------------------------------------------------- CI wiring
def test_ci_runs_the_corpus_and_the_guard_without_secrets_and_without_softening_failures():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "scripts/eval_global_corpus.py" in ci and "scripts/check_product_coverage_baseline.py" in ci
    seg = ci[ci.index("Global evaluation corpus"):ci.index("Secret scan")]
    assert "continue-on-error" not in seg and "secrets." not in seg and "|| true" not in seg and "RUNNER_TEMP" in seg and "upload-artifact" in seg
    assert ci.index("scripts/eval_global_corpus.py") < ci.index("Working tree must be clean")
