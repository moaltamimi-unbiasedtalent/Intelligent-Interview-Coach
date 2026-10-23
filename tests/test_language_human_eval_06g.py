"""06G independent human AI evaluation protocol and harness: statistics, agreement, independence, packet, analysis, schema, report and the guarded generation step.

Offline and deterministic. Everything the tests rate, declare or generate is FAKE and lives in tmp_path; no test names a real reviewer, makes a provider call or sets a threshold.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import tests.conftest  # noqa: F401  (test isolation)
from src.language_quality import human_eval as H
from src.language_quality import human_eval_generate as G
from src.language_quality import rating as R

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "language_human_eval.py"
TODAY = date(2026, 10, 22)


def _load_script():
    spec = importlib.util.spec_from_file_location("language_human_eval_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------------------------------------------------------ statistics
def test_t_critical_is_conservative_between_table_rows():
    assert H.t_critical_95(4) == 2.776 and H.t_critical_95(30) == 2.042
    assert H.t_critical_95(35) == H.t_critical_95(30)         # the larger value, so the interval is never too narrow
    assert H.t_critical_95(500) == H.Z95
    with pytest.raises(ValueError):
        H.t_critical_95(0)


def test_mean_interval_known_value_and_small_samples():
    ci = H.mean_ci95([1, 2, 3, 4, 5])
    assert ci["n"] == 5 and ci["mean"] == 3.0 and ci["sd"] == 1.581
    assert ci["low"] == pytest.approx(3 - 2.776 * 1.5811 / math.sqrt(5), abs=0.002) and ci["high"] == pytest.approx(3 + 2.776 * 1.5811 / math.sqrt(5), abs=0.002)
    assert H.mean_ci95([4])["low"] is None and H.mean_ci95([])["mean"] is None


def test_wilson_and_rule_of_three():
    lo, hi = H.wilson_interval95(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=0.001)
    lo, hi = H.wilson_interval95(5, 10)
    assert lo == pytest.approx(0.2366, abs=0.001) and hi == pytest.approx(0.7634, abs=0.001)
    assert H.wilson_interval95(1, 60)[1] == pytest.approx(0.0888, abs=0.002)
    assert H.upper95_if_zero(60) == 0.05 and H.upper95_if_zero(2) == 1.0
    for bad in ((11, 10), (0, 0), (-1, 5)):
        with pytest.raises(ValueError):
            H.wilson_interval95(*bad)


def test_sample_size_formulas():
    assert H.n_for_mean_halfwidth(1.0, 0.4) == 27 and H.n_for_mean_halfwidth(1.0, 0.5) == 18
    assert H.n_per_group_for_difference(1.0, 0.5) == 65                  # 2 * ((1.96 + 0.84) / 0.5) ** 2 = 62.8 per language, plus 2
    assert H.n_for_zero_event_bound(0.05) == 60 and H.n_for_zero_event_bound(0.01) == 300
    for bad in ((0, 1), (1, 0)):
        with pytest.raises(ValueError):
            H.n_for_mean_halfwidth(*bad)
    with pytest.raises(ValueError):
        H.n_for_zero_event_bound(1.5)
    g = H.guidance()
    assert g["achievable"]["60"]["1.0"] == pytest.approx(0.26, abs=0.01) and g["achievable"]["30"]["1.0"] == pytest.approx(0.37, abs=0.01)


def test_guidance_document_and_schema_artefacts_are_current():
    mod = _load_script()
    for path, text in mod.sync_targets().items():
        assert path.read_text(encoding="utf-8") == text, f"stale {path.name}: run scripts/language_human_eval.py sync --write"
    md = mod.GUIDANCE_PATH.read_text(encoding="utf-8")
    assert "PER LANGUAGE" in md and "not thresholds" in md and "OD-GATE-THRESHOLDS" in md


# ------------------------------------------------------------------------------------------------------------------------------------------------ agreement
def test_cohen_kappa_known_values():
    a, b = [1, 1, 0, 0, 1, 1, 0, 0], [1, 0, 0, 0, 1, 1, 1, 0]
    assert H.cohen_kappa(a, b) == 0.5
    assert H.cohen_kappa([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert H.cohen_kappa([1, 1, 1], [1, 1, 1]) is None and H.cohen_kappa([], []) is None
    x, y = [1, 2, 3, 4, 5, 3, 2, 4], [1, 3, 3, 5, 4, 3, 1, 4]
    assert H.cohen_kappa(x, y, weights="quadratic", categories=range(1, 6)) == R.quadratic_weighted_kappa(x, y)
    assert H.cohen_kappa(x, y, weights="linear", categories=range(1, 6)) != H.cohen_kappa(x, y, weights="quadratic", categories=range(1, 6))
    with pytest.raises(ValueError):
        H.cohen_kappa(x, y, weights="cubic")


def test_krippendorff_alpha_matches_the_published_example():
    r1 = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
    r2 = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
    r3 = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
    r4 = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None]
    units = list(zip(r1, r2, r3, r4))
    assert H.krippendorff_alpha(units, "nominal") == pytest.approx(0.743, abs=0.001)
    assert H.krippendorff_alpha(units, "ordinal") == pytest.approx(0.815, abs=0.001)
    assert H.krippendorff_alpha(units, "interval") == pytest.approx(0.849, abs=0.001)


def test_krippendorff_alpha_edge_cases():
    assert H.krippendorff_alpha([[3, 3], [4, 4], [5, 5], [2, 2]], "ordinal") == 1.0
    assert H.krippendorff_alpha([[3, 3], [3, 3]], "ordinal") is None              # no variation: undefined, never 1 or 0
    assert H.krippendorff_alpha([[3, None], [None, 4]], "ordinal") is None        # nothing pairable
    assert H.krippendorff_alpha([[1, 5], [5, 1], [1, 5], [5, 1]], "ordinal") < 0  # systematic disagreement is negative
    with pytest.raises(ValueError):
        H.krippendorff_alpha([[1, 2]], "ratio")
    assert H.alpha_band(None) == "undefined" and "low" in H.alpha_band(0.5) and "good" in H.alpha_band(0.9)


def test_krippendorff_bootstrap_is_seeded_and_brackets_the_estimate():
    import random

    rng = random.Random(7)
    units = []
    for _ in range(60):
        base = rng.choice((2, 3, 4, 5))
        units.append([min(5, max(1, base + rng.choice((-1, 0, 0, 1)))) for _ in range(3)])
    alpha = H.krippendorff_alpha(units, "ordinal")
    lo, hi = H.krippendorff_ci95(units, "ordinal", seed="s")
    assert (lo, hi) == H.krippendorff_ci95(units, "ordinal", seed="s")
    assert lo < alpha < hi and hi - lo > 0.05
    assert H.krippendorff_ci95([[3, 3]] * 5, "ordinal") == (None, None)


# ------------------------------------------------------------------------------------------------------------------------------------------------ independence
def _decl(lang="de", slot="rater_R1", name="Test Reviewer One", **over):
    d = H.declaration_template(lang, slot)
    d.update({"reviewer_name": name, "native_or_fluent_statement": "Synthetic fixture: a native speaker for the test.", "relationships_to_owner_or_product": "NONE", "other_conflicts": "NONE",
              "declaration_date": "2026-10-20", "typed_signature": name, **H.DECLARATION_BOOLEANS})
    d.update(over)
    return d


def test_blank_declaration_is_incomplete_and_never_prefilled():
    t = H.declaration_template("de", "rater_R1")
    assert t["reviewer_name"] == "" and all(t[k] is None for k in H.DECLARATION_BOOLEANS)
    status, problems = H.validate_declaration(t, today=TODAY)
    assert status == "INCOMPLETE" and problems
    assert json.loads(H.DECLARATION_TEMPLATE_FILE.read_text(encoding="utf-8"))["reviewer_name"] == ""


def test_declaration_validation():
    assert H.validate_declaration(_decl(), today=TODAY) == ("ELIGIBLE_FOR_OWNER_APPOINTMENT", [])
    for field in ("is_author_of_reviewed_text", "contributed_to_prompts_or_translations", "compensation_depends_on_outcome", "paid_by_author_or_author_affiliate", "has_financial_interest_in_outcome"):
        assert H.validate_declaration(_decl(**{field: True}), today=TODAY)[0] == "INCOMPLETE"       # a conflict needs an explanation
        status, _ = H.validate_declaration(_decl(**{field: True, "explanation_if_any_flag_differs": "Explained in writing to the owner for the test."}), today=TODAY)
        assert status == "OWNER_DECISION_REQUIRED"                                                  # never auto-accepted, never auto-rejected
    assert H.validate_declaration(_decl(relationships_to_owner_or_product="Colleague of the owner", explanation_if_any_flag_differs="Works with the owner on another project."), today=TODAY)[0] \
        == "OWNER_DECISION_REQUIRED"
    assert H.validate_declaration(_decl(confirms_no_translation_or_ai_tools=False, explanation_if_any_flag_differs="Used a dictionary and said so in writing."), today=TODAY)[0] == "OWNER_DECISION_REQUIRED"
    for bad in (_decl(is_author_of_reviewed_text="false"), _decl(name="Claude"), _decl(typed_signature="Someone Else"), _decl(declaration_date="2099-01-01"), _decl(slot="R1"),
                _decl(lang="ru"), _decl(other_conflicts=""), _decl(native_or_fluent_statement="yes")):
        assert H.validate_declaration(bad, today=TODAY)[0] == "INCOMPLETE", bad


def test_independence_across_raters():
    good = {f"rater_R{i}": _decl(slot=f"rater_R{i}", name=f"Test Reviewer {i}") for i in (1, 2, 3)}
    assert H.check_independence(good, "de", 3, today=TODAY)["ok"]
    dup = {**good, "rater_R3": _decl(slot="rater_R3", name="test reviewer 1")}
    r = H.check_independence(dup, "de", 3, today=TODAY)
    assert not r["ok"] and any("same person" in p for p in r["problems"])
    assert not H.check_independence({k: v for k, v in good.items() if k != "rater_R3"}, "de", 3, today=TODAY)["ok"]
    assert not H.check_independence(good, "fr", 3, today=TODAY)["ok"]                          # declarations for another language
    wrong_slot = {"rater_R1": good["rater_R2"], "rater_R2": good["rater_R1"], "rater_R3": good["rater_R3"]}
    assert not H.check_independence(wrong_slot, "de", 3, today=TODAY)["ok"]
    needs = {**good, "rater_R2": _decl(slot="rater_R2", name="Test Reviewer 2", paid_by_author_or_author_affiliate=True, explanation_if_any_flag_differs="Paid by an affiliate, explained for the test.")}
    r = H.check_independence(needs, "de", 3, today=TODAY)
    assert not r["ok"] and r["needs_owner_decision"] == ["rater_R2"]


# ------------------------------------------------------------------------------------------------------------------------------------------------ sample and packet
def test_extended_bank_adds_roles_without_touching_the_06c_prompts():
    base, ext = R.prompt_items(), H.prompt_items()
    assert len(base) == 210 and len(ext) == 420
    assert {p["prompt_id"] for p in base} < {p["prompt_id"] for p in ext}
    by_id = {p["prompt_id"]: p for p in ext}
    assert all(by_id[p["prompt_id"]]["prompt"] == p["prompt"] for p in base)                  # 06C prompts are byte-identical
    assert len(H.prompt_items(False)) == 210
    per_lang = {lang: sum(1 for p in ext if p["language"] == lang) for lang in H.LANGUAGES}
    assert set(per_lang.values()) == {60}
    ext_bank = H.load_extension()
    assert ext_bank["synthetic"] is True and len(ext_bank["roles"]) == 6
    assert all(role[lang].strip() for role in ext_bank["roles"].values() for lang in H.LANGUAGES)
    assert not (set(ext_bank["roles"]) & set(R.load_bank()["roles"]))


def _packet(tmp_path, *, fake=False, raters=3, seed="t06g"):
    rows = [{"prompt_id": p["prompt_id"], "language": p["language"], "response": G.fake_responder(p)} for p in H.prompt_items()]
    manifest = H.build_evaluation_packet(rows, tmp_path / "packet", seed=seed, raters=raters, fake=fake)
    return tmp_path / "packet", manifest


def test_packet_blinding_and_minimum_raters(tmp_path):
    packet, manifest = _packet(tmp_path)
    assert manifest["package"] == "06G" and manifest["items_per_sheet"] == 70 and manifest["raters_per_language"] == 3 and manifest["extended_roles"] is True
    files = R.reviewer_files(packet)
    assert set(f for f in files if not f.endswith("rating_sheet.csv")) == set(R.REVIEWER_FILES)
    assert sum(f.endswith("rating_sheet.csv") for f in files) == 21 and not any("private" in f or "key" in f for f in files)
    text = "".join((packet / "reviewer" / f).read_text(encoding="utf-8") for f in files)
    for secret in ("expectation", "private/", "key.json", "internal_id", manifest["seed"]):    # (ordinary words such as "control" occur in the languages, and the fake replies carry a task label)
        assert secret not in text, secret
    with pytest.raises(ValueError):
        _packet(tmp_path / "two", raters=2)
    rows = [{"prompt_id": p["prompt_id"], "language": p["language"], "response": "x"} for p in H.prompt_items(False)]
    with pytest.raises(ValueError):                                                              # base-only outputs do not cover the extended bank
        H.build_evaluation_packet(rows, tmp_path / "short", raters=3)


# ------------------------------------------------------------------------------------------------------------------------------------------------ analysis
def _ready(tmp_path, *, declare=True, fake=False):
    packet, _ = _packet(tmp_path, fake=fake)
    ratings, decls = tmp_path / "ratings", tmp_path / "declarations"
    H.fake_correlated_ratings(packet, ratings)
    if declare:
        H.fake_declarations(decls, today=TODAY)
    return packet, ratings, (decls if declare else None)


def test_analysis_status_ladder_and_never_a_pass(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    report = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)
    assert report["approved"] is False and report["approver"] is None and report["release_sha"] is None and report["status"] == "READY_FOR_OWNER_REVIEW"
    for lang, rec in report["languages"].items():
        assert rec["status"] == "READY_FOR_OWNER_REVIEW" and rec["approved"] is False and H.validate_result(rec) == [], lang
        assert rec["sample"]["model_output_items"] == 60 and rec["sample"]["raters_complete"] == 3
        for d in H.DIMENSIONS:
            dim = rec["dimensions"][d]
            assert dim["ci95_low"] < dim["mean"] < dim["ci95_high"]
            ag = rec["agreement"][d]
            assert ag["krippendorff_alpha_ordinal"] is not None and ag["alpha_ci95_low"] <= ag["krippendorff_alpha_ordinal"] <= ag["alpha_ci95_high"]
            assert -1 <= ag["cohen_kappa_weighted_mean"] <= 1
        assert rec["flags"]["unsafe_content"]["n_items"] == 66 and rec["flags"]["unsafe_content"]["upper95_if_zero"] == round(3 / 66, 4) and rec["thresholds"]["adopted"] is False
    assert "PASS" not in json.dumps(report)
    md = H.render_report_md(report)
    assert "PASS" not in md and "PROPOSAL, NOT ADOPTED" in md and "approves nothing" in md

    unverified = H.analyse(packet, ratings, declarations_dir=None)
    assert unverified["status"] == "INCOMPLETE" and all(v["status"] == "REVIEWERS_UNVERIFIED" for v in unverified["languages"].values())
    assert all(r["name"] == H.NOT_NAMED for v in unverified["languages"].values() for r in v["reviewers"].values())


def test_independence_failure_blocks_ready(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    p = decls / "de" / "rater_R3.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["reviewer_name"] = d["typed_signature"] = json.loads((decls / "de" / "rater_R1.json").read_text(encoding="utf-8"))["reviewer_name"]
    p.write_text(json.dumps(d), encoding="utf-8")
    d2 = json.loads((decls / "fr" / "rater_R1.json").read_text(encoding="utf-8"))
    d2["is_author_of_reviewed_text"] = True
    (decls / "fr" / "rater_R1.json").write_text(json.dumps(d2), encoding="utf-8")
    report = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)
    assert report["languages"]["de"]["status"] == "REVIEWERS_NOT_INDEPENDENT" and report["languages"]["fr"]["status"] == "REVIEWERS_NOT_INDEPENDENT"
    assert report["languages"]["es"]["status"] == "READY_FOR_OWNER_REVIEW" and report["status"] == "INCOMPLETE"


def test_missing_sheet_and_invalid_sheet_and_failed_controls(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    (ratings / "it" / "rater_R3" / "rating_sheet.csv").unlink()
    sheet = ratings / "pt" / "rater_R2" / "rating_sheet.csv"
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    rows[0]["clarity"] = "9"
    with sheet.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(R.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    key = json.loads((packet / "private" / "key.json").read_text(encoding="utf-8"))
    sheet = ratings / "nl" / "rater_R1" / "rating_sheet.csv"
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    for row in rows:
        if key[row["sample_id"]]["source"] == "control":
            row.update({d: "3" for d in H.DIMENSIONS})
            row.update({"wrong_language": "", "unsafe_content": ""})
    with sheet.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(R.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    report = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)
    langs = report["languages"]
    assert langs["it"]["status"] == "RATERS_INSUFFICIENT"
    assert langs["pt"]["status"] == "INCOMPLETE" and langs["pt"]["validation_errors"] >= 1
    assert langs["nl"]["status"] == "CONTROLS_FAILED" and langs["nl"]["controls"]["raters_failing"] == ["rater_R1"]
    assert langs["en"]["status"] == "READY_FOR_OWNER_REVIEW"
    for rec in langs.values():
        assert H.validate_result(rec) == []


def test_flags_are_counted_per_item_with_honest_bounds(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    key = json.loads((packet / "private" / "key.json").read_text(encoding="utf-8"))
    sheet = ratings / "es" / "rater_R2" / "rating_sheet.csv"
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    hit = [r for r in rows if key[r["sample_id"]]["source"] == "model_output"][:2]
    for r in hit:
        r["unsafe_content"] = "Y"
    with sheet.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(R.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    f = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)["languages"]["es"]["flags"]["unsafe_content"]
    assert f["items_flagged_by_any_rater"] == 2 and f["upper95_if_zero"] is None and f["wilson95_high"] > f["rate"] > 0 and f["n_items"] == 66


def test_results_schema_rejects_an_approval_or_a_pass(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    rec = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)["languages"]["de"]
    assert H.validate_result(rec) == []
    for mutate in (lambda r: r.update(approved=True), lambda r: r.update(status="PASS"), lambda r: r.update(approver="Someone"), lambda r: r.update(release_sha="a" * 40),
                   lambda r: r["thresholds"].update(adopted=True), lambda r: r.update(extra=1), lambda r: r.pop("sample"), lambda r: r.update(language="ru"),
                   lambda r: r["proposal_comparison"].update(informational_only=False), lambda r: r["limitations"].append(3)):
        bad = json.loads(json.dumps(rec))
        mutate(bad)
        assert H.validate_result(bad), mutate
    bad = json.loads(json.dumps(rec))
    bad["limitations"].append("everything PASSED")
    assert any("PASS" in e for e in H.validate_result(bad))
    assert json.loads(H.SCHEMA_FILE.read_text(encoding="utf-8")) == H.RESULT_SCHEMA


def test_the_report_generator_can_never_emit_pass(tmp_path):
    with pytest.raises(AssertionError):
        H.assert_no_pass("overall PASS")
    with pytest.raises(AssertionError):
        H.assert_no_pass("PASSED")
    H.assert_no_pass("policy adherence and a pass through the data")                  # ordinary lower-case prose is fine
    assert not any(s == "PASS" or "PASS" in s for s in H.STATUSES)
    packet, ratings, decls = _ready(tmp_path)
    report = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)
    report["note"] = "this run is a PASS"
    with pytest.raises(AssertionError):
        H.render_report_md(report)
    p = H.PROPOSED_LEVELS
    assert "PROPOSAL" in p["label"] and report["thresholds"]["adopted"] is False


def test_proposal_comparison_is_informational_and_covers_every_dimension(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    c = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)["languages"]["fr"]["proposal_comparison"]
    assert c["informational_only"] is True and "NOT ADOPTED" in c["label"]
    assert set(c["mean"]) == set(H.DIMENSIONS) == set(c["alpha_ordinal"])
    assert set(c["flag_upper95"]) == set(H.FLAGS)
    assert all(v in ("AT_OR_ABOVE_PROPOSAL", "BELOW_PROPOSAL", "NOT_COMPUTED") for v in c["mean"].values())


# ------------------------------------------------------------------------------------------------------------------------------------------------ guarded generation
def _budget(tmp_path, marker="OD-BUDGET:test-ref-1", stop="5.00"):
    cfg = tmp_path / "budget.json"
    cfg.write_text(json.dumps({"approval_marker": marker, "classes": {"evaluation": {"categories": {"evaluation": {"hard_cap_usd": "10", "stop_usd": stop}}}}}), encoding="utf-8")
    return cfg


class _Guard:
    def __init__(self, result=None):
        self.result, self.calls = result, []

    def guard_paid_script(self, script, **kw):
        self.calls.append((script, kw))
        return self.result


def test_generation_refuses_without_marker_ceiling_config_and_governor(tmp_path):
    cfg = _budget(tmp_path)
    env = {G.MARKER_ENV: "OD-BUDGET:test-ref-1", G.CONFIG_ENV: str(cfg)}
    guard = _Guard()

    def attempt(environ=env, ceiling="2.5", loader=None):
        return G.require_governed_generation(ceiling_usd=ceiling, environ=environ, guard_loader=loader or (lambda: guard))

    assert attempt() == Decimal("2.5") and guard.calls == [("language_human_eval_generate", {"category": "evaluation"})]
    cases = {
        "ci_forbidden": dict(environ={**env, "CI": "true"}),
        "marker_missing": dict(environ={G.CONFIG_ENV: str(cfg)}),
        "marker_missing ": dict(environ={**env, G.MARKER_ENV: "not-a-marker"}),
        "ceiling_missing": dict(ceiling=None),
        "ceiling_missing  ": dict(ceiling="0"),
        "ceiling_missing   ": dict(ceiling="-1"),
        "ceiling_missing    ": dict(ceiling="nan"),
        "ceiling_missing     ": dict(ceiling="lots"),
        "config_missing": dict(environ={G.MARKER_ENV: "OD-BUDGET:test-ref-1"}),
        "config_invalid": dict(environ={**env, G.CONFIG_ENV: str(tmp_path / "absent.json")}),
        "marker_mismatch": dict(environ={**env, G.MARKER_ENV: "OD-BUDGET:other-ref-9"}),
        "ceiling_above_budget": dict(ceiling="5.01"),
        "governor_absent": dict(loader=lambda: (_ for _ in ()).throw(ImportError("no 05C"))),
        "governor_refused": dict(loader=lambda: _Guard(2)),
    }
    for reason, kw in cases.items():
        with pytest.raises(G.GenerationRefused) as e:
            attempt(**kw)
        assert e.value.reason == reason.strip(), reason
        assert "OD-BUDGET:" not in str(e.value) and "test-ref" not in str(e.value)       # a refusal never echoes the marker
    bad = tmp_path / "noeval.json"
    bad.write_text(json.dumps({"approval_marker": "OD-BUDGET:test-ref-1", "classes": {}}), encoding="utf-8")
    with pytest.raises(G.GenerationRefused) as e:
        attempt(environ={**env, G.CONFIG_ENV: str(bad)})
    assert e.value.reason == "config_invalid"


def test_the_governor_is_called_only_after_every_cheaper_check(tmp_path):
    guard = _Guard()
    for env in ({}, {G.MARKER_ENV: "OD-BUDGET:test-ref-1"}, {G.MARKER_ENV: "OD-BUDGET:test-ref-1", G.CONFIG_ENV: str(_budget(tmp_path, marker="OD-BUDGET:zzzz-ref"))}):
        with pytest.raises(G.GenerationRefused):
            G.require_governed_generation(ceiling_usd="1", environ=env, guard_loader=lambda: guard)
    assert guard.calls == []


def test_without_the_05c_governor_in_the_tree_generation_fails_closed(tmp_path):
    cfg = _budget(tmp_path)
    env = {G.MARKER_ENV: "OD-BUDGET:test-ref-1", G.CONFIG_ENV: str(cfg)}
    try:
        import src.llm.budget.script_guard  # noqa: F401
        present = True
    except ImportError:
        present = False
    if present:                                                                              # after 05C merges the real guard decides (no ledger here, so it refuses)
        with pytest.raises(G.GenerationRefused):
            G.require_governed_generation(ceiling_usd="1", environ=env)
    else:
        with pytest.raises(G.GenerationRefused) as e:
            G.require_governed_generation(ceiling_usd="1", environ=env)
        assert e.value.reason == "governor_absent"


def test_generate_outputs_is_bounded_deduplicated_and_resumable(tmp_path):
    prompts = [{"prompt_id": f"en:t:r{i}", "language": "en", "task": "t", "prompt": "p"} for i in range(5)]
    calls: list[str] = []

    def responder(item):
        calls.append(item["prompt_id"])
        return f"reply {item['prompt_id']}"

    out = tmp_path / "o.jsonl"
    with pytest.raises(G.GenerationRefused) as e:
        G.generate_outputs(prompts, responder, max_requests=4, out_path=out)
    assert e.value.reason == "request_cap" and calls == [] and not out.exists()
    G.generate_outputs(prompts[:2], responder, max_requests=2, out_path=out)
    rows = G.generate_outputs(prompts, responder, max_requests=3, out_path=out)               # resumes: the first two are never asked again
    assert calls == [f"en:t:r{i}" for i in range(5)] and len(rows) == 5 and len(out.read_text(encoding="utf-8").splitlines()) == 5
    with pytest.raises(G.GenerationRefused):
        G.generate_outputs(prompts + prompts[:1], responder, max_requests=9)
    n_before = len(calls)
    with pytest.raises(G.GenerationRefused):
        G.generate_outputs([{"prompt_id": "x", "language": "en", "task": "t", "prompt": "p"}], lambda i: "   ", max_requests=1)
    assert len(calls) == n_before
    out.write_text(out.read_text(encoding="utf-8") + json.dumps({"prompt_id": "en:t:r0", "language": "en", "response": "dup"}) + "\n", encoding="utf-8")
    with pytest.raises(G.GenerationRefused):
        G.generate_outputs(prompts, responder, max_requests=9, out_path=out)


def test_a_failing_responder_stops_the_run_without_retrying(tmp_path):
    prompts = [{"prompt_id": f"en:t:r{i}", "language": "en", "task": "t", "prompt": "p"} for i in range(3)]
    seen: list[str] = []

    def responder(item):
        seen.append(item["prompt_id"])
        if item["prompt_id"].endswith("r1"):
            raise RuntimeError("provider failed")
        return "ok"

    out = tmp_path / "o.jsonl"
    with pytest.raises(RuntimeError):
        G.generate_outputs(prompts, responder, max_requests=3, out_path=out)
    assert seen == ["en:t:r0", "en:t:r1"] and len(out.read_text(encoding="utf-8").splitlines()) == 1


def test_live_path_has_one_entry_point_and_the_scripts_hold_no_client():
    gen = (ROOT / "src" / "language_quality" / "human_eval_generate.py").read_text(encoding="utf-8")
    assert gen.count("OpenRouterClient(") == 1 and gen.index("def live_responder") < gen.index("OpenRouterClient(")
    assert "max_retries=0" in gen and "MAX_OUTPUT_TOKENS" in gen
    for path in (SCRIPT, ROOT / "scripts" / "language_review_pack.py", ROOT / "src" / "language_quality" / "human_eval.py", ROOT / "src" / "language_quality" / "review_pack.py"):
        text = path.read_text(encoding="utf-8")
        assert "OpenRouterClient(" not in text and "openai" not in text.lower().replace("openai/", ""), path.name
        assert "httpx" not in text and "requests." not in text and "urllib.request" not in text, path.name
    assert "src.llm.budget" in SCRIPT.read_text(encoding="utf-8")                            # the 05C static script scan requires the governor to be named


def _cli(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_BUDGET") and k != "CI"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT), capture_output=True, text=True, check=False, env=env)


def test_cli_live_generation_refuses_and_writes_nothing(tmp_path):
    out = tmp_path / "outputs.jsonl"
    r = _cli("generate", "--live", "--out", str(out), "--ceiling-usd", "1")
    assert r.returncode == G.REFUSED_EXIT and "REFUSED (marker_missing)" in r.stderr and not out.exists()
    r = _cli("generate", "--live", "--out", str(out), env_extra={G.MARKER_ENV: "OD-BUDGET:test-ref-1"})
    assert r.returncode == G.REFUSED_EXIT and "ceiling_missing" in r.stderr and not out.exists()
    r = _cli("generate", "--live", "--out", str(out), "--ceiling-usd", "1", env_extra={G.MARKER_ENV: "OD-BUDGET:test-ref-1", "CI": "true"})
    assert r.returncode == G.REFUSED_EXIT and "ci_forbidden" in r.stderr
    assert _cli("generate", "--out", str(out)).returncode != 0                                # a mode is required: offline or live


def test_cli_offline_generation_is_labelled_fake(tmp_path):
    out = tmp_path / "outputs.jsonl"
    r = _cli("generate", "--offline", "--out", str(out))
    assert r.returncode == 0 and "FAKE" in r.stdout
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 420 and all("FAKE SELF-TEST" in row["response"] for row in rows) and G.covers_bank(rows)


def test_cli_prompts_and_declaration_template(tmp_path):
    r = _cli("prompts")
    assert r.returncode == 0 and len(r.stdout.strip().splitlines()) == 420
    assert len(_cli("prompts", "--base").stdout.strip().splitlines()) == 210
    t = tmp_path / "d.json"
    assert _cli("declaration-template", "--language", "nl", "--slot", "rater_R2", "--out", str(t)).returncode == 0
    d = json.loads(t.read_text(encoding="utf-8"))
    assert d["language"] == "nl" and d["rater_slot"] == "rater_R2" and d["reviewer_name"] == ""
    r = _cli("validate-declaration", str(t))
    assert r.returncode == 1 and "INCOMPLETE" in r.stdout


def test_cli_sync_check_is_current():
    r = _cli("sync", "--check")
    assert r.returncode == 0 and "06G artefacts current" in r.stdout


# ------------------------------------------------------------------------------------------------------------------------------------------------ end to end
def test_selftest_runs_end_to_end_on_fake_data_only():
    mod = _load_script()
    report = mod.selftest()
    assert report["fake"] is True and report["status"] == "SELFTEST_ONLY" and report["approved"] is False
    assert all(v["status"] == "SELFTEST_ONLY" and v["fake"] for v in report["languages"].values())
    assert all(n.startswith("Selftest Reviewer") for v in report["languages"].values() for n in (r["name"] for r in v["reviewers"].values()))


def test_a_fake_packet_never_becomes_ready(tmp_path):
    packet, ratings, decls = _ready(tmp_path, fake=True)
    report = H.analyse(packet, ratings, declarations_dir=decls, today=TODAY)
    assert report["status"] == "SELFTEST_ONLY" and all(v["status"] == "SELFTEST_ONLY" for v in report["languages"].values())


def test_report_cli_roundtrip_and_files(tmp_path):
    packet, ratings, decls = _ready(tmp_path)
    r = _cli("report", "--packet", str(packet), "--ratings", str(ratings), "--declarations", str(decls), "--out", str(tmp_path / "out"))
    assert r.returncode == 0 and "never an approval" in r.stdout
    data = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    assert data["approved"] is False and "PASS" not in json.dumps(data) and "PASS" not in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert all(not H.validate_result(v) for v in data["languages"].values())
