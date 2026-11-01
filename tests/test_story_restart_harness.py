"""The test supervisor refuses false restart evidence and unowned state."""
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.e2e.story_restart_connected import graceful_stop, phase_result, ready, same_snapshot, validate_owned


def test_only_expected_owned_database_can_resume():
    with tempfile.TemporaryDirectory(prefix="ask4mo_restart_") as tmp:
        state = Path(tmp)
        assert validate_owned(state, None, resume=False) == state.resolve()
        with pytest.raises(ValueError):
            validate_owned(state, [1, 1], resume=True)
        db = state / "journey.db"
        db.write_bytes(b"synthetic")
        st = db.stat()
        assert validate_owned(state, [st.st_dev, st.st_ino], resume=True) == state.resolve()
        with pytest.raises(ValueError):
            validate_owned(state, [st.st_dev, st.st_ino + 1], resume=True)
        with pytest.raises(ValueError):
            validate_owned(state, None, resume=False)
        with pytest.raises(ValueError):
            validate_owned(state.parent, [st.st_dev, st.st_ino], resume=True)


def test_failed_stop_or_dead_replacement_cannot_qualify():
    dead = Mock()
    dead.poll.return_value = 1
    with pytest.raises(RuntimeError):
        graceful_stop(dead, 1)
    with pytest.raises(RuntimeError):
        ready(dead, 1, timeout=1)


def test_missing_or_changed_evidence_cannot_qualify():
    assert same_snapshot({"x": [(1,)]}, {"x": [(1,)]})
    assert not same_snapshot({}, {})
    assert not same_snapshot({"x": [(1,)]}, {"x": [(2,)]})
    good = {"stats": {"expected": 1, "unexpected": 0, "skipped": 0}}
    assert phase_result(SimpleNamespace(returncode=0, stdout=json.dumps(good)))
    for status, data in [(1, good), (0, {}), (0, {"stats": {"expected": 0, "unexpected": 0, "skipped": 1}})]:
        assert not phase_result(SimpleNamespace(returncode=status, stdout=json.dumps(data)))


def test_resume_skips_schema_and_seed(monkeypatch, tmp_path):
    from scripts.e2e import journey_stack
    from src.persistence import Base
    create = Mock()
    seed = Mock()
    monkeypatch.setattr(Base.metadata, "create_all", create)
    monkeypatch.setattr(journey_stack, "_issue_invitations", seed)
    journey_stack._prepare_test_database(Mock(), tmp_path, SimpleNamespace(resume_existing=True, invitations=0))
    create.assert_not_called()
    seed.assert_not_called()


def test_post_restart_facts_reject_missing_or_incorrect_results():
    from scripts.e2e.story_restart_connected import valid_after_facts
    facts = {"owner": True, "other": True, "isolation": True, "foreign_read": 404, "foreign_edit": 404, "unchanged": True}
    assert valid_after_facts(facts)
    for wrong in (None, {}, {**facts, "foreign_read": 500}, {**facts, "owner": 1}, {**facts, "extra": "private"}):
        assert not valid_after_facts(wrong)


def test_shutdown_timeout_blocks_qualification():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = subprocess.TimeoutExpired("owned", 10)
    with pytest.raises(RuntimeError, match="did not stop gracefully"):
        graceful_stop(process, 1)


def test_resume_rejects_symlinked_database(tmp_path):
    with tempfile.TemporaryDirectory(prefix="ask4mo_restart_") as tmp:
        outside = tmp_path / "external.db"
        outside.write_bytes(b"synthetic")
        state = Path(tmp)
        (state / "journey.db").symlink_to(outside)
        st = outside.stat()
        with pytest.raises(ValueError):
            validate_owned(state, [st.st_dev, st.st_ino], resume=True)
