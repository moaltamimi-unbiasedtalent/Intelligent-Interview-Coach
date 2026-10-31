"""Synthetic controls for the private model-boundary observer."""
from scripts.e2e.story_practice_connected import FOREIGN, SELECTED, UNSELECTED, observe, qualifies


def test_observer_rejects_missing_or_forbidden_context():
    good = f"[[STORY 7 BEGIN]] {SELECTED} verification: unverified; the candidate's own account"
    assert qualifies(observe([{"content": good}], 7))
    assert not qualifies(observe([{"content": good.replace(SELECTED, "absent")}], 7))
    assert not qualifies(observe([{"content": good + UNSELECTED}], 7))
    assert not qualifies(observe([{"content": good + FOREIGN}], 7))
    assert not qualifies(observe([{"content": good}], 8))
