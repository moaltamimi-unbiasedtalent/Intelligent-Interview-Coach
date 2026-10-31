"""Bounded, synthetic controls for deletion campaign model observations."""
from scripts.e2e.story_deletion_connected import FOREIGN, SELECTED, UNSELECTED, observe, qualifies


def test_observer_requires_both_selected_stories_and_rejects_foreign_context():
    content = (f"[[STORY 7 BEGIN]] {SELECTED} verification: unverified; the candidate's own account [[STORY 7 END]] "
               f"[[STORY 8 BEGIN]] {UNSELECTED} verification: unverified; the candidate's own account [[STORY 8 END]]")
    good = observe([{"content": content}], 7, 8)
    assert qualifies(good)
    assert not qualifies(observe([{"content": content.replace(SELECTED, "absent")}], 7, 8))
    assert not qualifies(observe([{"content": content.replace(UNSELECTED, "absent")}], 7, 8))
    assert not qualifies(observe([{"content": content + FOREIGN}], 7, 8))
    assert not qualifies(observe([{"content": content}], 7, 9))
    assert not qualifies(observe([{"content": content.replace("verification: unverified", "no provenance", 1)}], 7, 8))
    assert not qualifies(observe([{"content": content.replace(SELECTED, "") + SELECTED}], 7, 8))
    assert set(good) == {"selected", "retained", "foreign", "identity", "keep_identity", "selected_provenance", "retained_provenance"}
    assert all(isinstance(value, bool) for value in good.values())
