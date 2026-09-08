"""Sprint 4 Phase 10 — SessionData ⇆ JSON codec round-trip + safety tests.

Every interview state must survive encode → JSON → decode with semantic equality,
so a durable-store reload reconstructs the exact interview. No pickle; malformed or
unsupported payloads fail safely. No provider calls, no disk.
"""

from __future__ import annotations

import json

import pytest

from src.interview.session_codec import (
    SESSION_STATE_SCHEMA_VERSION,
    SessionCodecError,
    decode_session_data,
    encode_session_data,
)
from src.session_manager import SessionData, SessionManager, SessionState
from tests import _interview_factories as f


def _roundtrip(data: SessionData) -> SessionData:
    payload = encode_session_data(data)
    # Must be genuinely JSON-serialisable (no Python objects left behind).
    payload = json.loads(json.dumps(payload))
    return decode_session_data(payload, schema_version=SESSION_STATE_SCHEMA_VERSION)


def _assert_semantic_equal(a: SessionData, b: SessionData) -> None:
    assert encode_session_data(a) == encode_session_data(b)


# --- state builders ----------------------------------------------------------


def _empty() -> SessionData:
    return SessionData()


def _configured() -> SessionData:
    return SessionData(state=SessionState.SETUP, config=f.config(), settings=f.settings())


def _strategy_ready() -> SessionData:
    return SessionData(
        state=SessionState.STRATEGY_READY, config=f.config(), settings=f.settings(),
        strategy=f.strategy(), usage_records=[f.usage()], cumulative_cost_usd=0.001,
        interview_start_time=1000.0, chat_messages=[{"role": "assistant", "content": "hi"}])


def _awaiting() -> SessionData:
    return SessionData(
        state=SessionState.AWAITING_ANSWER, config=f.config(), settings=f.settings(),
        strategy=f.strategy(), questions=[f.question(1)], current_question_number=1)


def _evaluated() -> SessionData:
    return SessionData(
        state=SessionState.INTERVIEW_IN_PROGRESS, config=f.config(), settings=f.settings(),
        strategy=f.strategy(), questions=[f.question(1)], answers=["My answer."],
        evaluations=[f.evaluation()], current_question_number=1,
        usage_records=[f.usage(), f.usage()], cumulative_cost_usd=0.002)


def _multi_question() -> SessionData:
    return SessionData(
        state=SessionState.INTERVIEW_IN_PROGRESS, config=f.config(3), settings=f.settings(),
        strategy=f.strategy(),
        questions=[f.question(1), f.question(2)], answers=["a1", "a2"],
        evaluations=[f.evaluation(60), f.evaluation(80)], current_question_number=2)


def _complete() -> SessionData:
    d = _multi_question()
    d.state = SessionState.INTERVIEW_COMPLETE
    return d


def _report_ready() -> SessionData:
    d = _complete()
    d.state = SessionState.REPORT_READY
    d.report = f.report()
    return d


def _error_state() -> SessionData:
    return SessionData(
        state=SessionState.ERROR, config=f.config(), settings=f.settings(),
        error="A safe controlled error.", previous_state=SessionState.AWAITING_ANSWER,
        questions=[f.question(1)], current_question_number=1)


def _active_deep_dive() -> SessionData:
    d = _evaluated()
    d.branch_active = True
    d.active_branch_id = "branch-1-1"
    d.branch_parent_question_id = 1
    d.branch_mode = "deepen_reasoning"
    d.branch_depth = 1
    d.branch_questions = [f.branch_question(1)]
    d.branch_answers = ["branch answer"]
    d.branch_evaluations = [f.evaluation(75)]
    d.branch_started_at = 1234.5
    d.state = SessionState.BRANCH_AWAITING_ANSWER
    return d


def _archived_deep_dive() -> SessionData:
    d = _evaluated()
    d.branches = [{
        "branch_id": "branch-1-1",
        "parent_question_id": 1,
        "mode": "deepen_reasoning",
        "questions": [f.branch_question(1), f.branch_question(2, depth=2)],
        "answers": ["b-a1", "b-a2"],
        "evaluations": [f.evaluation(70), f.evaluation(72)],
    }]
    return d


def _with_usage_and_metrics() -> SessionData:
    d = _evaluated()
    d.transcription_usage = [f.external_usage()]
    d.voice_metrics = [{"duration_seconds": 30.0, "word_count": 90, "wpm": 180.0}]
    d.visual_metrics = []
    d.usage_records = [f.usage(), f.usage(reported=None, calculated=0.003)]
    return d


def _saved_report_metadata() -> SessionData:
    d = _report_ready()
    d.saved_report_id = 4242
    d.save_failed = False
    d.preferences = {"theme": "dark"}
    return d


ALL_STATES = [
    _empty, _configured, _strategy_ready, _awaiting, _evaluated, _multi_question,
    _complete, _report_ready, _error_state, _active_deep_dive, _archived_deep_dive,
    _with_usage_and_metrics, _saved_report_metadata,
]


@pytest.mark.parametrize("builder", ALL_STATES, ids=[b.__name__ for b in ALL_STATES])
def test_roundtrip_semantic_equality(builder):
    original = builder()
    restored = _roundtrip(original)
    _assert_semantic_equal(original, restored)


def test_roundtrip_preserves_state_and_key_scalars():
    restored = _roundtrip(_evaluated())
    assert restored.state == SessionState.INTERVIEW_IN_PROGRESS
    assert restored.current_question_number == 1
    assert restored.answers == ["My answer."]
    assert restored.cumulative_cost_usd == 0.002
    assert restored.config.target_role == "Registered Nurse"
    assert restored.evaluations[0].overall_score == 70


def test_roundtrip_preserves_archived_branch_nested_models():
    restored = _roundtrip(_archived_deep_dive())
    br = restored.branches[0]
    assert br["mode"] == "deepen_reasoning"
    assert [q.depth for q in br["questions"]] == [1, 2]
    assert [e.overall_score for e in br["evaluations"]] == [70, 72]


def test_roundtrip_preserves_error_recovery_target():
    restored = _roundtrip(_error_state())
    assert restored.state == SessionState.ERROR
    assert restored.previous_state == SessionState.AWAITING_ANSWER


def test_decode_rejects_unsupported_schema_version():
    payload = encode_session_data(_evaluated())
    with pytest.raises(SessionCodecError):
        decode_session_data(payload, schema_version=SESSION_STATE_SCHEMA_VERSION + 1)


def test_decode_rejects_malformed_payload():
    with pytest.raises(SessionCodecError):
        decode_session_data(["not", "a", "dict"], schema_version=SESSION_STATE_SCHEMA_VERSION)


def test_decode_rejects_unknown_state():
    payload = encode_session_data(_empty())
    payload["state"] = "NOT_A_REAL_STATE"
    with pytest.raises(SessionCodecError):
        decode_session_data(payload, schema_version=SESSION_STATE_SCHEMA_VERSION)


def test_decode_rejects_malformed_nested_model():
    payload = encode_session_data(_evaluated())
    payload["evaluations"] = [{"overall_score": "not-an-int-and-missing-fields"}]
    with pytest.raises(SessionCodecError):
        decode_session_data(payload, schema_version=SESSION_STATE_SCHEMA_VERSION)


def test_codec_does_not_leak_private_answer_text_on_failure():
    payload = encode_session_data(_evaluated())
    payload["questions"] = "corrupt"
    try:
        decode_session_data(payload, schema_version=SESSION_STATE_SCHEMA_VERSION)
        raise AssertionError("expected failure")
    except SessionCodecError as exc:
        assert "My answer." not in str(exc)


def test_roundtrip_through_real_sessionmanager_run():
    # Drive a real SessionManager over a dict store to a mid-interview state, then
    # ensure the codec reconstructs an identical SessionData.
    store: dict = {}
    sm = SessionManager(store, clock=lambda: 1000.0)
    sm.start_new_interview(f.config(2), f.settings())
    sm.save_strategy(f.strategy())
    sm.add_question(f.question(1))
    sm.add_candidate_answer("A structured answer.")
    sm.add_evaluation(f.evaluation(66))
    original = sm.data
    restored = _roundtrip(original)
    _assert_semantic_equal(original, restored)
    assert restored.state == SessionState.INTERVIEW_IN_PROGRESS
