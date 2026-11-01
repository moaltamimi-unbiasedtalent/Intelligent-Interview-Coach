"""Bounded connected privacy evidence must fail closed."""
from scripts.e2e.privacy_request_connected import valid_browser_stats, valid_facts


def test_valid_facts_rejects_missing_extra_or_wrong_types():
    facts = {"submissions": 2, "owner_isolation": True, "reload": True, "fresh_session": True, "refusals": 6, "unchanged": True}
    assert valid_facts(facts)
    assert not valid_facts(None)
    assert not valid_facts({})
    assert not valid_facts({**facts, "unexpected": "synthetic"})
    assert not valid_facts({**facts, "reload": 1})
    assert not valid_facts({**facts, "submissions": True})
    assert not valid_facts({**facts, "refusals": 5})


def test_browser_stats_require_both_tests_to_pass_without_skips():
    assert valid_browser_stats({"expected": 2, "unexpected": 0, "skipped": 0})
    for stats in (None, {}, {"expected": 1, "unexpected": 0, "skipped": 1},
                  {"expected": 2, "unexpected": 1, "skipped": 0},
                  {"expected": 2, "unexpected": False, "skipped": 0}):
        assert not valid_browser_stats(stats)
