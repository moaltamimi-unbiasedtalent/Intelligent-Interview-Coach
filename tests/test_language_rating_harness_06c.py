"""06C (LG-04, LG-05): blinded native-reader rating protocol and harness, end to end on FAKE outputs and FAKE raters. Offline, deterministic, no model call.

The harness is an evidence package for a named human approver. These tests prove the package works, is blinded, is complete, and can never approve anything.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
from pathlib import Path

import pytest

from src.language_quality import rating as R

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("language_rating_harness", ROOT / "scripts" / "language_rating_harness.py")
CLI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CLI)


def _neutral_outputs():
    """Real-looking, label-free replies so the blinding scan is meaningful (the fake generator's replies carry a task label by design)."""
    return [{"prompt_id": p["prompt_id"], "language": p["language"], "response": f"Antwort {i}: bitte bereite dich vor."} for i, p in enumerate(R.prompt_items())]


@pytest.fixture()
def packet(tmp_path):
    out = tmp_path / "packet"
    manifest = R.build_packet(_neutral_outputs(), out, seed="unit-seed", raters=2, fake=False)
    return out, manifest


def _complete(packet_dir, tmp_path, name="ratings"):
    ratings = tmp_path / name
    R.fake_ratings(packet_dir, ratings)
    return ratings


def _rows(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(R.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)


# ================================================================================================================================ the plan
def test_the_sampling_plan_matches_what_the_bank_and_the_sheets_actually_contain(packet):
    out, manifest = packet
    plan = R.SAMPLING_PLAN
    assert plan["languages"] == list(R.LANGUAGES) == ["en", "de", "fr", "es", "it", "pt", "nl"]
    prompts = R.prompt_items()
    assert len(prompts) == len(R.LANGUAGES) * plan["model_output_samples_per_language"] == 210
    assert plan["model_output_samples_per_language"] + plan["policy_sentence_samples_per_language"] + plan["control_items_per_sheet"] == plan["items_per_rater_sheet"] == manifest["items_per_sheet"]
    for lang in R.LANGUAGES:
        mine = [p for p in prompts if p["language"] == lang]
        assert len({(p["task"], p["role"]) for p in mine}) == len(mine) == 30                # every task x every role exactly once per language
        for r in (1, 2):
            assert len(_rows(out / "reviewer" / lang / f"rater_R{r}" / "rating_sheet.csv")) == 40
    assert plan["independent_raters_per_language_minimum"] == 2 and manifest["raters_per_language"] == 2


def test_the_prompt_bank_is_synthetic_and_language_complete():
    bank = R.load_bank()
    assert bank["synthetic"] is True and set(bank["languages"]) == set(R.LANGUAGES)
    text = json.dumps(bank, ensure_ascii=False)
    assert not re.search(r"@|https?://|\d{5,}", text)                                       # no address, link or long number: nothing resembling real data
    assert len(bank["roles"]) == 6 and len(bank["tasks"]) == 5
    for task in bank["tasks"].values():
        assert set(task["template"]) == set(R.LANGUAGES) and all("{role}" in t for t in task["template"].values())
    for role in bank["roles"].values():
        assert set(role) == set(R.LANGUAGES)
    assert all("Canada" in bank["tasks"]["mo_abstention"]["template"][l] or "Kanada" in bank["tasks"]["mo_abstention"]["template"][l] or "Canad" in bank["tasks"]["mo_abstention"]["template"][l]
               for l in R.LANGUAGES)                                                       # a fixed neutral country for every language: language never implies geography


def test_the_rubric_has_the_four_required_dimensions_with_anchors():
    assert R.DIMENSIONS == ("clarity", "correctness", "tone", "policy_adherence") and R.SCALE == (1, 5)
    md = R.render_rubric_md()
    for dim in R.DIMENSIONS:
        assert dim.replace("_", " ").capitalize() in md and set(R.ANCHORS[dim]) == {1, 3, 5}
    assert "wrong_language" in md and "unsafe_content" in md


# ============================================================================================================================ what a reviewer gets
def test_a_reviewer_receives_exactly_two_documents_and_one_sheet_per_language_and_rater(packet):
    out, _ = packet
    expected = sorted(["README.txt", "RUBRIC.md"] + [f"{l}/rater_R{r}/rating_sheet.csv" for l in R.LANGUAGES for r in (1, 2)])
    assert R.reviewer_files(out) == expected
    assert set(R.REVIEWER_FILES) == {"README.txt", "RUBRIC.md"}
    for sheet in (out / "reviewer").rglob("rating_sheet.csv"):
        with sheet.open(encoding="utf-8", newline="") as fh:
            assert next(csv.reader(fh)) == list(R.SHEET_COLUMNS)


def test_the_reviewer_files_are_blinded_nothing_private_or_leading_is_in_them(packet):
    out, manifest = packet
    forbidden = [manifest["seed"], "private", "key.json", "control", "mo_abstention", "mo_grounded", "injection_probe", "interview_feedback", "interview_question", "policy_sentence",
                 "expected", "expectation", "LG-0", "gpt", "openrouter", "claude", "balanced", "advanced", "profile", "prompt version", "model_output", "fabricated_figure", "policy_violation"]
    for path in (out / "reviewer").rglob("*"):
        if path.is_file():
            body = path.read_text(encoding="utf-8")
            for needle in forbidden:
                assert not re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", body, re.I), f"{path.name} leaks {needle!r}"      # whole words: "gecontroleerd" is Dutch, not a leak
    for sheet in (out / "reviewer").rglob("rating_sheet.csv"):
        for row in _rows(sheet):
            assert re.fullmatch(r"S[0-9A-F]{10}", row["sample_id"]) and row["item_kind"] in ("assistant reply", "interview question", "interview feedback", "system notice")
            assert all(row[c] == "" for c in R.DIMENSIONS + R.FLAGS + ("comment",))


def test_sample_ids_are_opaque_stable_per_language_and_the_order_differs_per_rater(packet):
    out, _ = packet
    for lang in R.LANGUAGES:
        a = [r["sample_id"] for r in _rows(out / "reviewer" / lang / "rater_R1" / "rating_sheet.csv")]
        b = [r["sample_id"] for r in _rows(out / "reviewer" / lang / "rater_R2" / "rating_sheet.csv")]
        assert sorted(a) == sorted(b) and len(set(a)) == 40                                 # both raters rate the same 40 items ...
        assert a != b                                                                       # ... in an independent order
    ids = [r["sample_id"] for l in R.LANGUAGES for r in _rows(out / "reviewer" / l / "rater_R1" / "rating_sheet.csv")]
    assert len(set(ids)) == len(ids) == 280


def test_the_same_seed_reproduces_the_packet_and_a_different_seed_changes_every_id(tmp_path):
    outputs = _neutral_outputs()
    a = R.build_packet(outputs, tmp_path / "a", seed="s1")
    b = R.build_packet(outputs, tmp_path / "b", seed="s1")
    c = R.build_packet(outputs, tmp_path / "c", seed="s2")
    assert a["sheets_sha256"] == b["sheets_sha256"] and a["sheets_sha256"] != c["sheets_sha256"]
    ids = lambda p: {r["sample_id"] for r in _rows(p / "reviewer" / "de" / "rater_R1" / "rating_sheet.csv")}  # noqa: E731
    assert not ids(tmp_path / "a") & ids(tmp_path / "c")


def test_the_private_key_maps_every_sample_and_stays_out_of_the_reviewer_folder(packet):
    out, _ = packet
    key = json.loads((out / "private" / "key.json").read_text(encoding="utf-8"))
    assert len(key) == 280
    by_source = {}
    for meta in key.values():
        by_source[meta["source"]] = by_source.get(meta["source"], 0) + 1
    assert by_source == {"model_output": 210, "policy_sentence": 42, "control": 28}
    assert not any("private" in f for f in R.reviewer_files(out))


def test_policy_sentences_in_the_sheets_are_the_current_localized_text(packet):
    from src.copilot.rag import localized

    out, _ = packet
    rows = _rows(out / "reviewer" / "fr" / "rater_R1" / "rating_sheet.csv")
    texts = {r["response"] for r in rows}
    assert localized.INSUFFICIENT["fr"] in texts and localized.COMPENSATION_GUIDANCE["fr"] in texts and localized.UNRETRIEVED_LIMITATION["fr"] in texts


def test_model_text_that_looks_like_a_spreadsheet_formula_is_neutralised(tmp_path):
    outputs = _neutral_outputs()
    outputs[0]["response"] = "=HYPERLINK(\"http://example.invalid\",\"x\")"
    outputs[1]["response"] = "+1+1"
    out = tmp_path / "p"
    R.build_packet(outputs, out, seed="f")
    cells = {r["response"] for l in R.LANGUAGES for r in _rows(out / "reviewer" / l / "rater_R1" / "rating_sheet.csv")}
    assert "'=HYPERLINK(\"http://example.invalid\",\"x\")" in cells and "'+1+1" in cells
    assert not any(c[:1] in "=+@" for c in cells)


@pytest.mark.parametrize("mutate,message", [
    (lambda o: o[1:], "missing"), (lambda o: o + [{"prompt_id": "xx:unknown:role", "language": "xx", "response": "x"}], "unknown"),
    (lambda o: [{**o[0], "response": "  "}] + o[1:], "without prompt_id or response"), (lambda o: o + [o[0]], "duplicate"),
])
def test_the_packet_refuses_incomplete_unknown_empty_or_duplicate_outputs(tmp_path, mutate, message):
    with pytest.raises(ValueError, match=message):
        R.build_packet(mutate(_neutral_outputs()), tmp_path / "p", seed="x")


def test_fewer_than_two_raters_is_refused(tmp_path):
    with pytest.raises(ValueError):
        R.build_packet(_neutral_outputs(), tmp_path / "p", raters=1)


# ============================================================================================================================ aggregation
def test_aggregation_runs_end_to_end_and_reports_agreement_controls_and_flags(packet, tmp_path):
    out, _ = packet
    summary = R.aggregate(out, _complete(out, tmp_path))
    assert summary["status"] == "READY_FOR_HUMAN_REVIEW" and not summary["fake"]
    assert set(summary["languages"]) == set(R.LANGUAGES)
    for lang, v in summary["languages"].items():
        assert v["status"] == "READY_FOR_HUMAN_REVIEW" and v["raters_complete"] == 2 and v["items_rated"] == 36 and v["controls_per_sheet"] == 4
        assert set(v["dimensions"]) == set(R.DIMENSIONS) and v["dimensions"]["clarity"]["n_ratings"] == 72
        assert set(v["by_task"]) == {"mo_grounded", "mo_abstention", "interview_question", "interview_feedback", "injection_probe", "policy_sentence"}
        assert set(v["agreement"]) == set(R.DIMENSIONS) and v["agreement"]["tone"]["pairs"] == 1
        assert v["raters_failing_controls"] == [] and set(v["flag_rates"]) == set(R.FLAGS)
    assert "READY_FOR_HUMAN_REVIEW" in R.render_summary_md(summary)


def test_the_aggregate_never_approves_anything_and_says_what_is_missing(packet, tmp_path):
    out, _ = packet
    summary = R.aggregate(out, _complete(out, tmp_path))
    assert summary["approved"] is False and summary["approver"] is None and summary["approved_on"] is None and summary["release_sha"] is None
    assert "OD-GATE-THRESHOLDS" in summary["thresholds"] and set(summary["gate_ids"]) == {"LG-04", "LG-05"}
    assert all(v == "NOT NAMED (OD-LANG-03)" for v in summary["reviewers"].values())
    named = R.aggregate(out, tmp_path / "ratings", reviewers={"de": "Reviewer Name"})
    assert named["reviewers"]["de"] == "Reviewer Name" and named["approved"] is False and named["reviewers"]["fr"].startswith("NOT NAMED")
    assert "never approves" in summary["note"].lower()


def test_fake_data_can_only_ever_report_selftest(tmp_path):
    out = tmp_path / "p"
    R.build_packet(R.fake_outputs(), out, seed="x", fake=True)
    summary = R.aggregate(out, _complete(out, tmp_path))
    assert summary["fake"] and summary["status"] == "SELFTEST_ONLY" and (out / "reviewer" / "README.txt").read_text(encoding="utf-8").startswith("FAKE SELF-TEST PACKET")


def test_an_inattentive_rater_is_caught_by_the_controls(packet, tmp_path):
    out, _ = packet
    ratings = _complete(out, tmp_path)
    key = json.loads((out / "private" / "key.json").read_text(encoding="utf-8"))
    sheet = ratings / "de" / "rater_R2" / "rating_sheet.csv"
    rows = _rows(sheet)
    for row in rows:
        if key[row["sample_id"]]["source"] == "control" and key[row["sample_id"]]["control"] != "good":
            for dim in R.DIMENSIONS:
                row[dim] = "5"                                                              # praises every flawed control
            row["unsafe_content"] = row["wrong_language"] = "N"
    _write(sheet, rows)
    v = R.aggregate(out, ratings)["languages"]["de"]
    assert v["status"] == "CONTROLS_FAILED" and v["raters_failing_controls"] == ["rater_R2"] and v["controls_failed_by_rater"]["rater_R1"] == 0


def test_incomplete_invalid_or_foreign_sheets_make_the_language_incomplete_and_never_pass(packet, tmp_path):
    out, _ = packet
    ratings = _complete(out, tmp_path)
    s = ratings / "es" / "rater_R1" / "rating_sheet.csv"
    rows = _rows(s)
    rows[0]["clarity"] = ""                                                                 # blank rating
    rows[1]["tone"] = "9"                                                                   # out of scale
    rows[2]["unsafe_content"] = "maybe"                                                     # bad flag
    rows[3]["sample_id"] = "S0000000000"                                                    # foreign id
    _write(s, rows)
    (ratings / "it" / "rater_R2" / "rating_sheet.csv").unlink()                             # a rater never returned a sheet
    summary = R.aggregate(out, ratings)
    es, it = summary["languages"]["es"], summary["languages"]["it"]
    assert es["status"] == "INCOMPLETE" and es["error_count"] >= 4
    assert it["status"] == "RATERS_INSUFFICIENT" and it["raters_complete"] == 1
    assert summary["status"] == "INCOMPLETE"


def test_a_sheet_with_changed_columns_is_rejected(packet, tmp_path):
    out, _ = packet
    ratings = _complete(out, tmp_path)
    s = ratings / "nl" / "rater_R1" / "rating_sheet.csv"
    s.write_text(s.read_text(encoding="utf-8").replace("policy_adherence", "policy"), encoding="utf-8")
    v = R.aggregate(out, ratings)["languages"]["nl"]
    assert v["status"] == "INCOMPLETE" and any("columns differ" in e for e in v["errors"])


def test_quadratic_weighted_kappa_behaves_like_kappa():
    assert R.quadratic_weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0
    assert R.quadratic_weighted_kappa([1, 1, 5, 5], [5, 5, 1, 1]) < 0
    assert R.quadratic_weighted_kappa([3, 3, 3], [3, 3, 3]) is None                          # constant raters: undefined, never reported as perfect
    assert 0 < R.quadratic_weighted_kappa([1, 2, 3, 4, 5, 3], [2, 2, 3, 5, 5, 3]) < 1
    assert R.quadratic_weighted_kappa([], []) is None


# =================================================================================================================================== CLI
def test_the_selftest_passes_and_writes_nothing_into_the_repository(tmp_path):
    before = {p for p in (ROOT / "scripts").iterdir()}
    summary = CLI.selftest()
    assert summary["status"] == "SELFTEST_ONLY" and summary["approved"] is False
    assert {p for p in (ROOT / "scripts").iterdir()} == before
    assert CLI.main(["selftest"]) == 0


def test_the_cli_runs_sample_prompts_and_aggregate_end_to_end(tmp_path, capsys):
    assert CLI.main(["prompts"]) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(lines) == 210 and set(lines[0]) == {"prompt_id", "language", "prompt"}
    outputs = tmp_path / "outputs.jsonl"
    outputs.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in _neutral_outputs()), encoding="utf-8")
    packet = tmp_path / "packet"
    assert CLI.main(["sample", "--outputs", str(outputs), "--out", str(packet), "--seed", "cli"]) == 0
    ratings = _complete(packet, tmp_path)
    names = tmp_path / "names.json"
    names.write_text(json.dumps({"de": "Reviewer Name"}), encoding="utf-8")
    assert CLI.main(["aggregate", "--packet", str(packet), "--ratings", str(ratings), "--out", str(tmp_path / "res"), "--reviewers", str(names)]) == 0
    summary = json.loads((tmp_path / "res" / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "READY_FOR_HUMAN_REVIEW" and summary["approved"] is False and summary["reviewers"]["de"] == "Reviewer Name"
    assert (tmp_path / "res" / "summary.md").exists()


def test_the_cli_sample_needs_exactly_one_source(tmp_path):
    with pytest.raises(SystemExit):
        CLI.main(["sample", "--out", str(tmp_path / "x")])
    with pytest.raises(SystemExit):
        CLI.main(["sample", "--fake", "--outputs", str(tmp_path / "o.jsonl"), "--out", str(tmp_path / "x")])


# ===================================================================================================================== no way to spend money
def test_the_harness_has_no_provider_network_or_credential_code_path():
    for rel in ("src/language_quality/rating.py", "src/language_quality/inventory.py", "src/language_quality/invariance.py", "scripts/language_rating_harness.py",
                "scripts/eval_language_ai_behaviour.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", text, flags=re.S)
        assert not re.search(r"^\s*(import|from)\s+(httpx|requests|openai|urllib\.request|socket|aiohttp|langchain\w*|src\.openrouter_client|src\.llm)\b", code, re.M), rel
        assert not re.search(r"OPENROUTER_API_KEY|OPENAI_API_KEY|os\.environ|getenv", code), rel
