"""04F dictation correction-burden harness: arithmetic, validation and evidence-boundary tests (offline; no audio, no provider, no real data)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("dictation_burden", ROOT / "scripts/dictation_burden.py")
db = importlib.util.module_from_spec(_spec)
sys.modules["dictation_burden"] = db
_spec.loader.exec_module(db)


def test_prompt_set_is_the_seven_speech_languages_with_equal_counts_and_no_russian():
    prompts = db.load_prompts()
    assert tuple(prompts) == db.LANGUAGES
    assert "ru-RU" not in prompts
    assert len({len(v) for v in prompts.values()}) == 1 and len(prompts["en-US"]) == 5
    meta = json.loads(db.PROMPTS_PATH.read_text(encoding="utf-8"))
    assert meta["synthetic"] is True
    for lang, items in prompts.items():
        for text in items:
            assert 10 <= len(text.split()) <= 25, (lang, text)
            assert "@" not in text and "—" not in text


def test_the_speech_language_list_matches_the_product_boundary():
    from src.speech.policy import PRODUCT_SPEECH_LANGUAGES
    assert tuple(code.split("-")[0] for code in db.LANGUAGES) == PRODUCT_SPEECH_LANGUAGES


@pytest.mark.parametrize("raw,final,expected", [
    ("a b c", "a b c", (0, 0, 0)),
    ("a b", "a b c", (1, 0, 0)),          # one insertion
    ("a b c", "a c", (0, 1, 0)),          # one deletion
    ("a x c", "a b c", (0, 0, 1)),        # one substitution
    ("", "a b", (2, 0, 0)),
    ("a b", "", (0, 2, 0)),
    ("a b c d", "a x c", (0, 1, 1)),
])
def test_edit_operation_counts(raw, final, expected):
    ops = db.edit_ops(db.normalise(raw), db.normalise(final))
    assert (ops["insertions"], ops["deletions"], ops["substitutions"]) == expected
    assert ops["distance"] == sum(expected)


def test_normalisation_ignores_case_edge_punctuation_and_unicode_form_but_keeps_inner_hyphen():
    assert db.normalise("Hello, World!") == ["hello", "world"]
    assert db.normalise("quatre-vingt-dix, minutes.") == ["quatre-vingt-dix", "minutes"]
    assert db.normalise("Große") == db.normalise("GROßE") == ["grosse"]   # casefold folds the German sharp s
    assert db.normalise("éte") == db.normalise("éte")      # NFC
    assert db.normalise("... !!") == []


def test_burden_is_edits_per_hundred_final_words_and_zero_for_perfect_dictation():
    prompts = db.load_prompts()
    ref = prompts["en-US"][3]
    perfect = db.score_trial({"participant": "T1", "language": "en-US", "browser": "b", "prompt_index": 3, "raw": ref, "final": ref}, prompts)
    assert perfect["correction_burden"] == 0.0 and perfect["residual_errors_vs_prompt"] == 0
    words = len(ref.split())
    one_wrong = ref.replace("quickly", "quietly")
    t = db.score_trial({"participant": "T1", "language": "en-US", "browser": "b", "prompt_index": 3, "raw": one_wrong, "final": ref}, prompts)
    assert t["distance"] == 1 and t["substitutions"] == 1
    assert t["correction_burden"] == round(100 / words, 2)


def test_residual_error_is_reported_when_the_tester_left_a_mismatch():
    prompts = db.load_prompts()
    ref = prompts["en-US"][0]
    t = db.score_trial({"participant": "T1", "language": "en-US", "browser": "b", "prompt_index": 0, "raw": ref.replace("six", "sex"), "final": ref.replace("six", "sex")}, prompts)
    assert t["distance"] == 0 and t["residual_errors_vs_prompt"] == 1


def test_worked_example_is_synthetic_hand_checkable_and_carries_the_banner():
    result = db.score_sheet(db.worked_example())
    assert result["data_origin"] == "synthetic_example"
    assert result["banner"].startswith("NOT A MEASUREMENT CLAIM")
    overall = result["summary"]["overall"]
    # hand count: en#1 = 1 insertion + 1 substitution; en#3 = 0; de#1 = 1 substitution + 1 deletion
    assert (overall["trials"], overall["participants"], overall["edits"]) == (3, 2, 4)
    assert (overall["insertions"], overall["deletions"], overall["substitutions"]) == (1, 1, 2)
    assert overall["pooled_burden_per_100_words"] == round(100 * 4 / overall["final_words"], 2)
    assert result["summary"]["by_language"]["de-DE"]["edits"] == 2
    # no verdict, no threshold and no pass/fail key anywhere in the output
    assert "pass" not in json.dumps(result).lower().replace("passage", "")


def test_template_round_trips_and_a_blank_sheet_scores_as_zero_words_without_crashing():
    sheet = db.blank_sheet("nl-NL", "P01", "Chrome 130")
    assert sheet["data_origin"] == "human_session" and len(sheet["trials"]) == 5
    assert all(t["raw"] == "" and t["final"] == "" for t in sheet["trials"])
    result = db.score_sheet(sheet)
    assert result["summary"]["overall"]["pooled_burden_per_100_words"] is None
    assert all(r["correction_burden"] is None for r in result["trials"])


def _trial(**kw):
    base = {"participant": "P01", "language": "en-US", "browser": "b", "prompt_index": 0, "raw": "a", "final": "a"}
    base.update(kw)
    return {"data_origin": "human_session", "trials": [base]}


@pytest.mark.parametrize("sheet", [
    {"trials": [{}]},                                           # no data_origin
    {"data_origin": "measured", "trials": [{}]},                # unknown origin
    {"data_origin": "human_session", "trials": []},
    _trial(language="ru-RU"),                                   # Russian is not a speech language
    _trial(language="xx-XX"),
    _trial(prompt_index=99),
    _trial(prompt_index=True),
    _trial(participant="someone@example.com"),                  # identifiable code refused
    _trial(participant="Jane Doe"),
    _trial(raw=None),
])
def test_invalid_sheets_fail_closed(sheet):
    with pytest.raises(db.SheetError):
        db.score_sheet(sheet)


def test_cli_example_writes_only_to_the_given_directory_and_template_refuses_an_email_code(tmp_path, capsys):
    assert db.main(["example", "-o", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["results.json", "sheet.json"]
    assert "FAKE data" in capsys.readouterr().out
    assert db.main(["template", "--language", "de-DE", "--participant", "a@b.c", "--browser", "x", "-o", str(tmp_path / "t.json")]) == 2
    assert not (tmp_path / "t.json").exists()
    assert db.main(["score", str(tmp_path / "missing.json")]) == 2
