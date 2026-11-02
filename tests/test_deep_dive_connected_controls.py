"""Fail-closed controls for bounded synthetic Deep Dive acceptance evidence."""
from __future__ import annotations

import json
import sqlite3
import stat
from types import SimpleNamespace

import pytest

from scripts.e2e import deep_dive_connected as deep


def report(*, expected=1, unexpected=0, skipped=0, returncode=0, **extra):
    return SimpleNamespace(returncode=returncode, stdout=json.dumps({
        "stats": {"expected": expected, "unexpected": unexpected, "skipped": skipped},
        **extra,
    }))


@pytest.mark.parametrize("phase", ("create", "read"))
def test_complete_typed_browser_facts_are_required(phase):
    assert deep.valid_facts(dict(deep.FACTS[phase]), phase)
    assert len(json.dumps(deep.FACTS[phase]).encode()) <= 2048


@pytest.mark.parametrize("phase", ("create", "read"))
def test_every_missing_wrong_or_coerced_observation_refuses_qualification(phase):
    good = deep.FACTS[phase]
    for field, expected in good.items():
        missing = dict(good)
        del missing[field]
        assert not deep.valid_facts(missing, phase), field
        wrong = not expected if type(expected) is bool else expected + 1
        assert not deep.valid_facts({**good, field: wrong}, phase), field
        coerced = int(expected) if type(expected) is bool else bool(expected)
        assert not deep.valid_facts({**good, field: coerced}, phase), field


@pytest.mark.parametrize("phase", ("create", "read"))
@pytest.mark.parametrize("value", (None, [], 1, True, "SYNTHETIC_PRIVATE_CANARY"))
def test_nonmapping_facts_never_qualify(phase, value):
    assert not deep.valid_facts(value, phase)


@pytest.mark.parametrize("phase", ("create", "read"))
def test_unapproved_payload_field_is_not_retained_as_evidence(phase):
    facts = dict(deep.FACTS[phase], raw_payload="SYNTHETIC_PRIVATE_CANARY")
    assert not deep.valid_facts(facts, phase)


def test_unknown_phase_does_not_accept_either_fact_schema():
    for phase in ("", "other", "SYNTHETIC_PRIVATE_CANARY"):
        assert not deep.valid_facts(deep.FACTS["create"], phase)


@pytest.mark.parametrize("phase", ("create", "read"))
def test_bounded_fact_file_loads_only_exact_schema(tmp_path, phase):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(deep.FACTS[phase]))
    assert deep.load_facts(path, phase) == deep.FACTS[phase]


@pytest.mark.parametrize("content", ("malformed", "null", "[]", "{}", "x" * 2049))
def test_invalid_or_oversized_fact_files_fail_without_canary_disclosure(tmp_path, content):
    path = tmp_path / "facts.json"
    path.write_text(content)
    with pytest.raises(ValueError) as error:
        deep.load_facts(path, "create")
    assert content not in str(error.value)
    assert path.read_text() == content


def test_missing_fact_file_is_a_failure(tmp_path):
    with pytest.raises(ValueError):
        deep.load_facts(tmp_path / "missing.json", "create")


def test_successful_browser_report_can_include_normal_reporter_metadata():
    assert deep.phase_ok(report(errors=[], metadata={"fixture": "synthetic"}))


@pytest.mark.parametrize("kwargs", (
    {"returncode": 1}, {"returncode": -15},
    {"expected": 0}, {"expected": 2}, {"expected": True},
    {"unexpected": 1}, {"unexpected": False},
    {"skipped": 1}, {"skipped": False},
    {"errors": [{"message": "SYNTHETIC_PRIVATE_CANARY"}]},
))
def test_failed_skipped_extra_or_invalid_browser_run_does_not_qualify(kwargs):
    assert not deep.phase_ok(report(**kwargs))


@pytest.mark.parametrize("stdout", (
    "malformed", "null", "[]", "{}", '{"stats": null}', '{"stats": {}}',
    '{"stats": {"expected": 1, "unexpected": 0}}',
    '{"stats": {"expected": 1, "skipped": 0}}',
    '{"stats": {"unexpected": 0, "skipped": 0}}',
))
def test_missing_or_malformed_browser_report_does_not_qualify(stdout):
    assert not deep.phase_ok(SimpleNamespace(returncode=0, stdout=stdout))


def test_model_observations_are_fixed_classifications_and_boolean_facts_only(tmp_path):
    for stage in ("InterviewStrategy", "InterviewQuestion", "BranchQuestion", "AnswerEvaluation"):
        deep.record(tmp_path, stage)
    deep.record(tmp_path, "FinalInterviewReport", report_branch_evidence=True)
    path = tmp_path / "model-stages.jsonl"
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"stage": stage, "report_branch_evidence": stage == "FinalInterviewReport"}
        for stage in ("InterviewStrategy", "InterviewQuestion", "BranchQuestion", "AnswerEvaluation", "FinalInterviewReport")
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_unknown_model_observation_cannot_retain_private_canary(tmp_path):
    canary = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(ValueError) as error:
        deep.record(tmp_path, canary)
    assert canary not in str(error.value)
    assert not (tmp_path / "model-stages.jsonl").exists()


@pytest.mark.parametrize("value", (1, 0, None, "SYNTHETIC_PRIVATE_CANARY", []))
def test_report_boundary_fact_cannot_retain_arbitrary_data(tmp_path, value):
    with pytest.raises(ValueError) as error:
        deep.record(tmp_path, "FinalInterviewReport", report_branch_evidence=value)
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(error.value)
    assert not (tmp_path / "model-stages.jsonl").exists()


def test_branch_evidence_cannot_be_attributed_to_nonreport_stage(tmp_path):
    with pytest.raises(ValueError):
        deep.record(tmp_path, "AnswerEvaluation", report_branch_evidence=True)
    assert not (tmp_path / "model-stages.jsonl").exists()


def test_observation_limit_refuses_append_without_overwriting_existing_events(tmp_path):
    for _ in range(deep.OBSERVATION_LIMIT):
        deep.record(tmp_path, "AnswerEvaluation")
    path = tmp_path / "model-stages.jsonl"
    before = path.read_bytes()
    assert len(before.splitlines()) == 16
    with pytest.raises(ValueError):
        deep.record(tmp_path, "FinalInterviewReport", report_branch_evidence=True)
    assert path.read_bytes() == before


def test_oversized_observation_file_refuses_append(tmp_path):
    path = tmp_path / "model-stages.jsonl"
    path.write_text("x" * 2049)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        deep.record(tmp_path, "InterviewQuestion")
    assert path.read_bytes() == before


def test_failure_projection_retains_no_nested_private_payload_or_raw_source_path():
    canary = "SYNTHETIC_PRIVATE_CANARY"
    value = {
        "stats": {"expected": 0, "unexpected": 1, "skipped": 0},
        "errors": [{"message": canary, "stack": canary}],
        "suites": [{"tests": [{"results": [{"errors": [
            {"message": canary, "location": {"file": f"/private/{canary}/deep-dive.spec.ts", "line": 42}},
            {"message": canary, "location": {"file": "/private/other.spec.ts", "line": 99}},
        ]}]}]}],
    }
    result = deep.safe_failure(SimpleNamespace(stdout=json.dumps(value)))
    assert result == {
        "classification": "browser_assertion_or_execution_failed",
        "counts": {"expected": 0, "unexpected": 1, "skipped": 0},
        "source_lines": [42],
    }
    assert canary not in json.dumps(result)


def test_failure_source_locations_are_deduplicated_and_bounded():
    value = {
        "stats": {"expected": False, "unexpected": "SYNTHETIC_PRIVATE_CANARY", "skipped": None},
        "errors": [{"location": {"file": "deep-dive.spec.ts", "line": line}}
                   for line in (*range(20, 0, -1), 1, 1)],
    }
    result = deep.safe_failure(SimpleNamespace(stdout=json.dumps(value)))
    assert result["source_lines"] == list(range(1, 11))
    assert result["counts"] == {"expected": None, "unexpected": None, "skipped": None}
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(result)


@pytest.mark.parametrize("stdout", ("malformed", "null", "[]", "{}"))
def test_unreadable_failure_report_has_fixed_classification(stdout):
    assert deep.safe_failure(SimpleNamespace(stdout=stdout)) == {"classification": "browser_report_unreadable"}


@pytest.mark.parametrize("main,branch,parent", ((-1, 1, -1), (0, 101, 0), (0, 1, 101), (0, 1, None), (0, "SYNTHETIC_PRIVATE_CANARY", 0)))
def test_invalid_parent_link_metadata_does_not_emit_private_values(tmp_path, main, branch, parent):
    with sqlite3.connect(tmp_path / "journey.db") as db:
        db.execute("CREATE TABLE questions(position, is_deep_dive, parent_position)")
        db.executemany("INSERT INTO questions VALUES(?,?,?)", ((main, 0, None), (branch, 1, parent)))
    assert deep.parent_link_observation(tmp_path) == {}


def test_parent_link_projection_reads_only_bounded_positions(tmp_path):
    with sqlite3.connect(tmp_path / "journey.db") as db:
        db.execute("CREATE TABLE questions(position, is_deep_dive, parent_position)")
        db.executemany("INSERT INTO questions VALUES(?,?,?)", ((1, 0, None), (2, 1, 1)))
    before = (tmp_path / "journey.db").read_bytes()
    assert deep.parent_link_observation(tmp_path) == {"main_position": 1, "branch_position": 2, "branch_parent_position": 1}
    assert (tmp_path / "journey.db").read_bytes() == before
