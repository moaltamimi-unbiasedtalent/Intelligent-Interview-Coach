"""Fail-closed, privacy-safe controls for completed-interview deletion evidence."""
from __future__ import annotations

import json
import stat
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts.e2e import history_deletion_connected as deletion

PHASES = ("prepare", "refuse", "delete")
STAGES = ("InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "FinalInterviewReport")


def report(*, expected=1, unexpected=0, skipped=0, returncode=0, **extra):
    return SimpleNamespace(returncode=returncode, stdout=json.dumps({
        "stats": {"expected": expected, "unexpected": unexpected, "skipped": skipped},
        **extra,
    }))


@pytest.mark.parametrize("phase", PHASES)
def test_complete_typed_facts_are_required_for_each_distinct_phase(phase):
    assert deletion.FACTS[phase]
    assert deletion.valid_facts(dict(deletion.FACTS[phase]), phase)
    assert len(json.dumps(deletion.FACTS[phase]).encode()) <= 2048


@pytest.mark.parametrize("phase", PHASES)
def test_missing_incorrect_and_type_coerced_facts_cannot_qualify(phase):
    good = deletion.FACTS[phase]
    for field, expected in good.items():
        missing = dict(good)
        del missing[field]
        assert not deletion.valid_facts(missing, phase), field
        wrong = not expected if type(expected) is bool else expected + 1
        assert not deletion.valid_facts({**good, field: wrong}, phase), field
        coerced = int(expected) if type(expected) is bool else bool(expected)
        assert not deletion.valid_facts({**good, field: coerced}, phase), field


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("value", (None, [], 1, True, "SYNTHETIC_PRIVATE_CANARY"))
def test_nonmapping_facts_never_qualify(phase, value):
    assert not deletion.valid_facts(value, phase)


@pytest.mark.parametrize("phase", PHASES)
def test_unknown_fact_fields_cannot_retain_private_data(phase):
    facts = dict(deletion.FACTS[phase], raw_payload="SYNTHETIC_PRIVATE_CANARY")
    assert not deletion.valid_facts(facts, phase)


def test_unknown_phase_cannot_use_a_different_phase_schema():
    for phase in ("", "other", "SYNTHETIC_PRIVATE_CANARY"):
        assert not deletion.valid_facts(deletion.FACTS["prepare"], phase)


@pytest.mark.parametrize("phase", PHASES)
def test_fact_loader_accepts_only_complete_bounded_phase_evidence(tmp_path, phase):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(deletion.FACTS[phase]))
    assert deletion.load_facts(path, phase) == deletion.FACTS[phase]


@pytest.mark.parametrize("content", ("malformed", "null", "[]", "{}", "x" * 2049))
def test_invalid_oversized_or_incomplete_fact_files_fail_without_disclosing_contents(tmp_path, content):
    path = tmp_path / "facts.json"
    path.write_text(content)
    with pytest.raises(ValueError) as error:
        deletion.load_facts(path, "prepare")
    assert content not in str(error.value)
    assert path.read_text() == content


def test_missing_fact_file_is_a_failure(tmp_path):
    with pytest.raises(ValueError):
        deletion.load_facts(tmp_path / "missing.json", "prepare")


def test_successful_browser_phase_can_include_normal_reporter_metadata():
    assert deletion.phase_ok(report(errors=[], metadata={"fixture": "synthetic"}))


@pytest.mark.parametrize("kwargs", (
    {"returncode": 1}, {"returncode": -15},
    {"expected": 0}, {"expected": 2}, {"expected": True},
    {"unexpected": 1}, {"unexpected": False},
    {"skipped": 1}, {"skipped": False},
    {"errors": [{"message": "SYNTHETIC_PRIVATE_CANARY"}]},
))
def test_failed_skipped_extra_or_invalid_browser_phase_never_qualifies(kwargs):
    assert not deletion.phase_ok(report(**kwargs))


@pytest.mark.parametrize("stdout", (
    "malformed", "null", "[]", "{}", '{"stats": null}', '{"stats": {}}',
    '{"stats": {"expected": 1, "unexpected": 0}}',
    '{"stats": {"expected": 1, "skipped": 0}}',
    '{"stats": {"unexpected": 0, "skipped": 0}}',
))
def test_missing_or_malformed_browser_report_never_qualifies(stdout):
    assert not deletion.phase_ok(SimpleNamespace(returncode=0, stdout=stdout))


def test_model_observations_retain_only_fixed_stage_names(tmp_path):
    for stage in STAGES:
        deletion.record(tmp_path, stage)
    path = tmp_path / "model-stages.jsonl"
    assert [json.loads(line) for line in path.read_text().splitlines()] == [{"stage": stage} for stage in STAGES]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_unknown_model_stage_cannot_disclose_or_retain_canary(tmp_path):
    canary = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(ValueError) as error:
        deletion.record(tmp_path, canary)
    assert canary not in str(error.value)
    assert not (tmp_path / "model-stages.jsonl").exists()


def test_observation_limit_refuses_append_without_altering_existing_evidence(tmp_path):
    for _ in range(deletion.OBSERVATION_LIMIT):
        deletion.record(tmp_path, "AnswerEvaluation")
    path = tmp_path / "model-stages.jsonl"
    before = path.read_bytes()
    assert len(before.splitlines()) == 16
    with pytest.raises(ValueError):
        deletion.record(tmp_path, "FinalInterviewReport")
    assert path.read_bytes() == before


def test_oversized_observation_file_refuses_append(tmp_path):
    path = tmp_path / "model-stages.jsonl"
    path.write_text("x" * 2049)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        deletion.record(tmp_path, "InterviewQuestion")
    assert path.read_bytes() == before


def test_next_observation_cannot_cross_byte_limit_even_below_current_limit(tmp_path):
    path = tmp_path / "model-stages.jsonl"
    path.write_text("x" * 2040)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        deletion.record(tmp_path, "InterviewQuestion")
    assert path.read_bytes() == before


def test_failure_projection_keeps_only_counts_and_local_source_line_numbers():
    canary = "SYNTHETIC_PRIVATE_CANARY"
    value = {
        "stats": {"expected": 0, "unexpected": 1, "skipped": 0},
        "errors": [{"message": canary, "stack": canary}],
        "suites": [{"tests": [{"results": [{"errors": [
            {"message": canary, "location": {"file": f"/private/{canary}/deletion.spec.ts", "line": 42}},
            {"message": canary, "location": {"file": "/private/other.spec.ts", "line": 99}},
        ]}]}]}],
    }
    result = deletion.safe_failure(SimpleNamespace(stdout=json.dumps(value)))
    assert result == {
        "classification": "browser_assertion_or_execution_failed",
        "counts": {"expected": 0, "unexpected": 1, "skipped": 0},
        "source_lines": [42],
    }
    assert canary not in json.dumps(result)


def test_failure_projection_bounds_deduplicated_locations_and_refuses_arbitrary_count_values():
    value = {
        "stats": {"expected": False, "unexpected": "SYNTHETIC_PRIVATE_CANARY", "skipped": None},
        "errors": [{"location": {"file": "deletion.spec.ts", "line": line}}
                   for line in (*range(20, 0, -1), 1, 1)],
    }
    result = deletion.safe_failure(SimpleNamespace(stdout=json.dumps(value)))
    assert result["source_lines"] == list(range(1, 11))
    assert result["counts"] == {"expected": None, "unexpected": None, "skipped": None}
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(result)


@pytest.mark.parametrize("stdout", ("malformed", "null", "[]", "{}"))
def test_unreadable_failure_report_emits_only_fixed_classification(stdout):
    assert deletion.safe_failure(SimpleNamespace(stdout=stdout)) == {"classification": "browser_report_unreadable"}


def deletion_state():
    """Pure synthetic rows; no application database or private inventory access."""
    identity = {"ids": [11, 12, 13], "sessions": ["target-session", "owner-keeper", "foreign-keeper"]}
    before = {
        "interviews": [{"id": iid, "user_id": owner, "source_session_id": sid}
                       for iid, owner, sid in zip(identity["ids"], (7, 7, 8), identity["sessions"])],
        "questions": [{"id": qid, "interview_id": iid} for qid, iid in zip((101, 102, 103), identity["ids"])],
        "answers": [{"id": aid, "question_id": qid} for aid, qid in zip((201, 202, 203), (101, 102, 103))],
        "reports": [{"id": rid, "interview_id": iid} for rid, iid in zip((301, 302, 303), identity["ids"])],
        "interview_sessions": [{"session_id": sid, "user_id": owner}
                               for sid, owner in zip(identity["sessions"], (7, 7, 8))],
        "deletion_audit": [],
    }
    after = {table: deepcopy(rows[1:]) for table, rows in before.items() if table != "deletion_audit"}
    after["deletion_audit"] = [{
        "id": 1, "event_type": "interview.deleted", "actor_user_id": 7,
        "target_type": "interview", "target_id": "11", "result": "success", "context": "{}",
    }]
    return before, after, identity


def test_deletion_delta_requires_selected_cascade_unchanged_sentinels_and_one_metadata_only_audit():
    before, after, identity = deletion_state()
    original_before, original_after = deepcopy(before), deepcopy(after)
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert set(facts) == {
        "target_interview_removed", "selected_questions_removed", "selected_answers_removed",
        "selected_report_removed", "source_session_discarded", "exactly_two_sentinel_records_preserved",
        "one_owner_attributed_deletion_audit", "audit_metadata_only",
    }
    assert all(type(value) is bool and value for value in facts.values())
    assert before == original_before and after == original_after


@pytest.mark.parametrize("section", ("questions", "evaluation", "report"))
def test_fixture_question_evaluation_and_report_cannot_leak_through_audit_metadata(section):
    fixture = json.loads((deletion.ROOT / "frontend/e2e/journey/fixtures.json").read_text())["interview"]
    for content in deletion.fixture_text_canaries(fixture[section]):
        before, after, identity = deletion_state()
        after["deletion_audit"][0]["request_id"] = content
        facts = deletion.deletion_facts(before, after, identity, 7)
        assert facts["audit_metadata_only"] is False
        assert content not in json.dumps(facts)


def test_numeric_scores_do_not_become_timestamp_or_correlation_substring_guards():
    assert deletion.fixture_text_canaries({"score": 74, "schema": "behavioural"}) == []


@pytest.mark.parametrize("table,fact", (
    ("interviews", "target_interview_removed"),
    ("questions", "selected_questions_removed"),
    ("answers", "selected_answers_removed"),
    ("reports", "selected_report_removed"),
    ("interview_sessions", "source_session_discarded"),
))
def test_selected_record_child_or_source_left_behind_never_qualifies(table, fact):
    before, after, identity = deletion_state()
    after[table].insert(0, deepcopy(before[table][0]))
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts[fact] is False
    assert facts["exactly_two_sentinel_records_preserved"] is False
    assert not all(facts.values())


@pytest.mark.parametrize("table", ("interviews", "questions", "answers", "reports", "interview_sessions"))
@pytest.mark.parametrize("index", (0, 1))
def test_any_owner_or_foreign_sentinel_mutation_is_detected_without_emitting_content(table, index):
    before, after, identity = deletion_state()
    after[table][index]["private_canary"] = "SYNTHETIC_PRIVATE_CANARY"
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts["exactly_two_sentinel_records_preserved"] is False
    assert not all(facts.values())
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(facts)


@pytest.mark.parametrize("field,value", (
    ("event_type", "other.event"), ("actor_user_id", 8), ("target_type", "other"),
    ("target_id", "12"), ("result", "failure"),
))
def test_incorrect_audit_attribution_target_or_outcome_never_qualifies(field, value):
    before, after, identity = deletion_state()
    after["deletion_audit"][0][field] = value
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts["one_owner_attributed_deletion_audit"] is False
    assert facts["audit_metadata_only"] is False


@pytest.mark.parametrize("location", ("before", "missing", "duplicate"))
def test_preexisting_missing_or_duplicate_deletion_audit_never_qualifies(location):
    before, after, identity = deletion_state()
    if location == "before":
        before["deletion_audit"] = deepcopy(after["deletion_audit"])
    elif location == "missing":
        after["deletion_audit"] = []
    else:
        after["deletion_audit"].append(deepcopy(after["deletion_audit"][0]))
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts["one_owner_attributed_deletion_audit"] is False
    assert facts["audit_metadata_only"] is False


@pytest.mark.parametrize("context", (
    '{"raw_answer":"SYNTHETIC_PRIVATE_CANARY"}',
    {"raw_answer": "SYNTHETIC_PRIVATE_CANARY"},
))
def test_nonempty_private_audit_context_is_refused_without_disclosure(context):
    before, after, identity = deletion_state()
    after["deletion_audit"][0]["context"] = context
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts["one_owner_attributed_deletion_audit"] is True
    assert facts["audit_metadata_only"] is False
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(facts)


@pytest.mark.parametrize("context", (None, "null", "{}", {}))
def test_empty_semantic_audit_context_accepts_sql_json_null_representation(context):
    before, after, identity = deletion_state()
    after["deletion_audit"][0]["context"] = context
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts and all(facts.values())


@pytest.mark.parametrize("context", ([], "[]", ["SYNTHETIC_PRIVATE_CANARY"], '{"private":"SYNTHETIC_PRIVATE_CANARY"}', "malformed"))
def test_nonempty_wrong_shape_or_malformed_audit_context_never_qualifies(context):
    before, after, identity = deletion_state()
    after["deletion_audit"][0]["context"] = context
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert not facts or not all(facts.values())
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(facts)


@pytest.mark.parametrize("private_value", (*deletion.ROLES, *deletion.ANSWERS, deletion.story.PASSWORD))
def test_known_synthetic_candidate_data_in_other_audit_fields_is_refused(private_value):
    before, after, identity = deletion_state()
    after["deletion_audit"][0]["request_id"] = private_value
    facts = deletion.deletion_facts(before, after, identity, 7)
    assert facts["audit_metadata_only"] is False
    assert private_value not in json.dumps(facts)


@pytest.mark.parametrize("part", ("before", "after", "identity"))
def test_incomplete_deletion_state_cannot_qualify(part):
    before, after, identity = deletion_state()
    if part == "before":
        before = {}
    elif part == "after":
        after = {}
    else:
        identity = {}
    assert deletion.deletion_facts(before, after, identity, 7) == {}
