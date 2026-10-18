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
    guard_step = ci[ci.index("Product coverage regression guard"):ci.index("Upload P10C-G")]
    assert "ASK4MO_COVERAGE_PROFILE: clean_checkout" in guard_step and "--update-profile" not in ci                       # the clean profile is set explicitly; CI never updates a baseline


# ------------------------------------------------------------------------------------------------------------------------ final hardening: reproducibility
def test_case_identifiers_and_generation_are_stable():
    import hashlib

    corpus = G.load_corpus()
    ids = [c["id"] for c in corpus["cases"]]
    assert len(ids) == len(set(ids)) == 115 and len(corpus["scenarios"]) == 48
    digest = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
    assert digest == "76f264d03a771569ef1fb22b7216590426a6c0f1582e562dd0ed39f50883f603"                                                                         # any added, removed or renamed case is visible in this test's diff
    assert len(G.REQUIRED_TAGS["negative_regression"]) == 14 and sum(len(v) for v in G.REQUIRED_TAGS.values()) == 83 and len(G.GOVERNANCE) == 12


def test_the_suite_does_not_depend_on_the_working_directory_or_local_store_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "nonexistent-data"))
    monkeypatch.setenv("COPILOT_CHROMA_DIR", str(tmp_path / "nonexistent-chroma"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'nope' / 'x.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    r = G.run_all()
    assert r["ok"] and r["corpus"]["passed"] == 115 and not list(tmp_path.glob("*.db")) and not (tmp_path / "nonexistent-data").exists()


def test_no_module_or_fixture_embeds_a_developer_path_or_a_network_address():
    for rel in ("src/knowledge_foundation/global_eval.py", "src/knowledge_foundation/data/global_evaluation_corpus.json", "scripts/eval_global_corpus.py", "scripts/gen_global_evaluation_corpus.py",
                "scripts/check_product_coverage_baseline.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for token in ("/Users/", "/Volumes/", "C:\\\\", "localhost", "127.0.0.1", "api_key", "sk-or-"):
            assert token not in text, (rel, token)
    import ast

    for rel in ("src/knowledge_foundation/global_eval.py", "scripts/eval_global_corpus.py"):
        mods = {a.name.split(".")[0] for n in ast.walk(ast.parse((ROOT / rel).read_text())) if isinstance(n, ast.Import) for a in n.names}
        assert not mods & {"requests", "httpx", "urllib", "socket", "stripe", "openai", "redis", "psycopg", "chromadb"}, rel


def test_every_gate_stays_false_while_the_suite_runs():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    G.run_all()
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    assert [getattr(bp, g) for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED")] == [False] * 6


# ----------------------------------------------------------------------------------------------------------------------- historical artifacts and registry semantics
def test_the_historical_product_coverage_artifacts_are_identified_as_historical_and_preserved():
    import hashlib

    d = ROOT / "evaluations/product_coverage"
    readme = (d / "README.md").read_text(encoding="utf-8")
    for f in ("summary.md", "failures.md"):
        t = (d / f).read_text(encoding="utf-8")
        assert t.startswith("> **HISTORICAL RESULT: NOT THE CURRENT MEASUREMENT.**") and "2026-08-29" in t and "NOT VERIFIED" in t
        body = t.split("\n\n", 1)[1]
        assert hashlib.sha256(body.encode()).hexdigest() in readme                                                 # the original text beneath the banner is byte-for-byte preserved
    assert hashlib.sha256((d / "results.csv").read_bytes()).hexdigest() in readme
    import csv

    rows = list(csv.DictReader((d / "results.csv").open(encoding="utf-8")))
    assert len(rows) == 412 and sum(r["insufficient_ok"] == "False" for r in rows) == 14                          # the historical 14 are intact, not silently refreshed


def test_registry_lifecycle_semantics_match_their_documentation(tmp_path):
    from src.knowledge_foundation.registry import RegistryError, SourceRegistry
    from src.persistence import init_db, make_engine, make_session_factory

    e = make_engine(f"sqlite:///{tmp_path / 'r.db'}")
    init_db(e)
    reg = SourceRegistry(make_session_factory(e))
    reg.register("s", origin="official_local", validation_status="unvalidated")
    reg.transition("s", "licensing_pending")
    reg.transition("s", "licensing_verified")                                                                     # reachable WITHOUT a verified licence (preserved behaviour)
    assert reg.get("s")["licence_status"] != "verified" and not reg.can_ingest("s")
    with pytest.raises(RegistryError):
        reg.transition("s", "approved_for_ingestion")                                                             # the approval boundary needs the licence evidence
    reg.set_licence("s", licence_id="OGL", licence_status="verified")
    reg.transition("s", "approved_for_ingestion")
    assert reg.can_ingest("s") and not reg.can_serve_as_evidence("s")
    reg.transition("s", "approved_for_runtime_use")
    assert reg.can_serve_as_evidence("s")
    doc = (ROOT / "docs/capstone/p10/P10C_G_GLOBAL_EVALUATION_AND_REGRESSION.md").read_text(encoding="utf-8")
    assert "What `licensing_verified` means" in doc and "licence_status" in doc and "approved_for_runtime_use" in doc
    e.dispose()
