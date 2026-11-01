"""Reject incomplete or forged bounded History qualification evidence."""
import json
from types import SimpleNamespace

from scripts.e2e.history_identity_connected import phase_ok, valid_facts


def test_history_facts_require_all_expected_typed_observations():
    good={"owners":2,"foreign":404,"missing":404,"anonymous":401,"read_only":True,"identity":True,"fresh":True}
    assert valid_facts(good)
    for bad in (None, {}, {**good,"identity":False}, {**good,"read_only":1}, {**good,"foreign":500}, {**good,"extra":"synthetic"}):
        assert not valid_facts(bad)


def test_browser_phase_rejects_skipped_failed_or_missing_results():
    good = {"stats": {"expected": 1, "unexpected": 0, "skipped": 0}}
    assert phase_ok(SimpleNamespace(returncode=0, stdout=json.dumps(good)))
    for code, data in ((1, good), (0, {}), (0, {"stats": {"expected": 0, "unexpected": 0, "skipped": 1}}), (0, {"stats": {"expected": 1, "unexpected": False, "skipped": 0}})):
        assert not phase_ok(SimpleNamespace(returncode=code, stdout=json.dumps(data)))
