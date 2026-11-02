"""Negative controls for bounded, synthetic Mo Stop connected evidence."""
from __future__ import annotations

import json
import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.e2e import mo_stop_connected as stop


def report(*, expected=1, unexpected=0, skipped=0, returncode=0, **extra):
    return SimpleNamespace(returncode=returncode, stdout=json.dumps({
        "stats": {"expected": expected, "unexpected": unexpected, "skipped": skipped},
        **extra,
    }))


def test_complete_browser_facts_are_required():
    assert stop.valid_facts(dict(stop.FACTS))
    assert len(json.dumps(stop.FACTS).encode()) <= 2048


@pytest.mark.parametrize("field", tuple(stop.FACTS))
def test_missing_observation_never_qualifies(field):
    facts = dict(stop.FACTS)
    del facts[field]
    assert not stop.valid_facts(facts)


@pytest.mark.parametrize("field", tuple(stop.FACTS))
def test_wrong_observation_never_qualifies(field):
    facts = dict(stop.FACTS)
    expected = facts[field]
    facts[field] = not expected if type(expected) is bool else expected + 1
    assert not stop.valid_facts(facts)


@pytest.mark.parametrize("field", tuple(stop.FACTS))
def test_type_coercion_never_hides_invalid_observation(field):
    facts = dict(stop.FACTS)
    facts[field] = int(facts[field]) if type(facts[field]) is bool else bool(facts[field])
    assert not stop.valid_facts(facts)


@pytest.mark.parametrize("value", (None, [], 1, True, "synthetic"))
def test_facts_require_a_mapping(value):
    assert not stop.valid_facts(value)


def test_unapproved_evidence_field_is_rejected():
    facts = dict(stop.FACTS, raw_payload="SYNTHETIC_PRIVATE_CANARY")
    assert not stop.valid_facts(facts)


def test_successful_phase_retains_reporter_metadata():
    assert stop.phase_ok(report(errors=[], metadata={"fixture": "synthetic"}))


@pytest.mark.parametrize("kwargs", (
    {"returncode": 1},
    {"returncode": -15},
    {"expected": 0},
    {"expected": 2},
    {"expected": True},
    {"unexpected": 1},
    {"unexpected": False},
    {"skipped": 1},
    {"skipped": False},
    {"errors": [{"message": "synthetic setup failure"}]},
))
def test_failed_skipped_extra_or_invalid_phase_never_qualifies(kwargs):
    assert not stop.phase_ok(report(**kwargs))


@pytest.mark.parametrize("stdout", (
    "malformed",
    "null",
    "[]",
    "{}",
    '{"stats": null}',
    '{"stats": {}}',
    '{"stats": {"expected": 1, "unexpected": 0}}',
    '{"stats": {"expected": 1, "skipped": 0}}',
    '{"stats": {"unexpected": 0, "skipped": 0}}',
))
def test_missing_or_malformed_phase_report_never_qualifies(stdout):
    assert not stop.phase_ok(SimpleNamespace(returncode=0, stdout=stdout))


def test_call_observation_retains_only_fixed_allowlisted_kind(tmp_path):
    for kind in ("model_entered", "model_returned", "tool_dispatch_attempt"):
        stop.record(tmp_path, kind)
    target = tmp_path / "calls.jsonl"
    assert [json.loads(line) for line in target.read_text().splitlines()] == [
        {"kind": "model_entered"},
        {"kind": "model_returned"},
        {"kind": "tool_dispatch_attempt"},
    ]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_unapproved_call_observation_fails_without_retaining_canary(tmp_path):
    canary = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(ValueError) as error:
        stop.record(tmp_path, canary)
    assert canary not in str(error.value)
    assert not (tmp_path / "calls.jsonl").exists()


def test_fixture_can_return_tool_proposal_then_normal_completion_without_cancellation():
    model = stop.ControlledModel(hold=False)
    assert model.bind_tools([]) is model
    proposal = model.invoke([])
    completion = model.invoke([])
    assert model.calls == 2
    assert len(proposal.tool_calls) == 1
    assert completion.tool_calls == []
    assert completion.content == stop.LATE_ANSWER
    for message in (proposal, completion):
        assert message.usage_metadata == {"input_tokens": 5, "output_tokens": 4, "total_tokens": 9}
        assert "cost" not in message.response_metadata


def test_fixture_barrier_requires_explicit_release_after_entry_marker(tmp_path, monkeypatch):
    fifo = tmp_path / "barrier-release"
    os.mkfifo(fifo, 0o600)
    marker = tmp_path / "barrier-entered.json"
    entered = threading.Event()
    original = Path.chmod

    def observe_chmod(path, mode, **kwargs):
        result = original(path, mode, **kwargs)
        if path == marker:
            entered.set()
        return result

    monkeypatch.setattr(Path, "chmod", observe_chmod)
    model = stop.ControlledModel(state=tmp_path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(model.invoke, [])
        assert entered.wait(5), "fixture did not reach its private barrier"
        assert json.loads(marker.read_text()) == {"entered": True}
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
        assert not future.done()
        assert [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()] == [{"kind": "model_entered"}]
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        try:
            assert os.write(fd, b"release") == 7
        finally:
            os.close(fd)
        message = future.result(timeout=5)
    assert message.content == stop.LATE_ANSWER
    assert model.calls == 1
    assert [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()] == [
        {"kind": "model_entered"}, {"kind": "model_returned"},
    ]


def test_observation_retention_limit_refuses_next_event_without_append(tmp_path):
    for _ in range(stop.OBSERVATION_LIMIT):
        stop.record(tmp_path, "model_entered")
    target = tmp_path / "calls.jsonl"
    before = target.read_bytes()
    assert len(before.splitlines()) == 16
    with pytest.raises(ValueError, match="bounded observation limit exceeded"):
        stop.record(tmp_path, "model_returned")
    assert target.read_bytes() == before


def test_oversized_observation_file_refuses_append(tmp_path):
    target = tmp_path / "calls.jsonl"
    target.write_text("x" * 2049)
    before = target.read_bytes()
    with pytest.raises(ValueError, match="bounded observation limit exceeded"):
        stop.record(tmp_path, "model_entered")
    assert target.read_bytes() == before
