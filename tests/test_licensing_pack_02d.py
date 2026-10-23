"""02D PR 2: the licensing review pack stays honest and consistent with the repository and with the validator.

Documentation tests only: no network, no approval. They fail if the pack drifts from the manifest, if the record template stops matching the validator,
or if the template could enable a source as committed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src import knowledge_approval as ka
from src.copilot.knowledge import manifest as km

ROOT = Path(__file__).resolve().parent.parent
EXEC = ROOT / "docs" / "production" / "execution"
PACK = (EXEC / "02D_LICENSING_REVIEW_PACK.md").read_text(encoding="utf-8")
TEMPLATE = json.loads((EXEC / "02D_approval_record_template.json").read_text(encoding="utf-8"))


def test_pack_states_plainly_that_nothing_is_approved_and_the_only_evidence_is_the_repository():
    assert "NOTHING IS APPROVED" in PACK
    assert "The only evidence in this pack is the repository" in PACK
    assert "No network call and no web fetch" in PACK
    assert "Nothing in this pack is legal advice" in PACK


def test_register_is_still_empty():
    data, err = ka.load_committed()
    assert err is None and data["records"] == []


def test_inventory_lists_every_manifest_source_exactly_once():
    rows = re.findall(r"^\| ([a-z0-9_]+) \| ", PACK.split("## 2. Inventory", 1)[1].split("### 2.1", 1)[0], re.M)
    ids = [e.source_id for e in km.load_manifest()]
    assert sorted(rows) == sorted(ids) and len(rows) == len(ids)


def test_inventory_licence_cells_match_the_manifest():
    section = PACK.split("## 2. Inventory", 1)[1].split("### 2.1", 1)[0]
    for e in km.load_manifest():
        row = next(line for line in section.splitlines() if line.startswith(f"| {e.source_id} | "))
        assert (e.licence or "NONE RECORDED") in row
        assert ("| yes |" in row) == e.licence_review_required


def test_counts_in_the_pack_match_the_manifest():
    entries = km.load_manifest()
    m = re.search(r"Counts: (\d+) manifest sources\. Of these, (\d+) are flagged `licence_review_required` in the manifest, (\d+) have NO licence string", PACK)
    assert m and int(m.group(1)) == len(entries)
    assert int(m.group(2)) == sum(1 for e in entries if e.licence_review_required)
    assert int(m.group(3)) == sum(1 for e in entries if not (e.licence or "").strip())


def test_all_seven_markets_are_covered_and_no_eu_compensation_is_claimed():
    for name in ("Ireland (IE)", "Germany (DE)", "Spain (ES)", "Italy (IT)", "Portugal (PT)", "France (FR)", "Netherlands (NL)"):
        assert name in PACK
    assert "no national compensation source for any of the seven markets" in PACK
    assert "0 records" in PACK


def test_template_has_exactly_the_validators_fields_and_enables_nothing_as_committed():
    assert set(TEMPLATE) == set(ka._REQUIRED_FIELDS)
    status = ka.validate_record(TEMPLATE)
    assert not status.enabled and status.problems
    reg = ka.resolve({"schema_version": 1, "records": [TEMPLATE]}, ka.MODE_ENFORCED)
    assert reg.empty


def test_template_in_the_pack_is_the_committed_template():
    block = PACK.split("```json", 1)[1].split("```", 1)[0]
    assert json.loads(block) == TEMPLATE


def test_pack_lists_the_validators_vocabulary():
    for token in ka.FEATURES + ka.MARKETS:
        assert token in PACK
    for cls in sorted(ka.ACTIVATABLE_LICENCES):
        assert cls in PACK
    assert str(ka.MAX_APPROVAL_DAYS) in PACK


def test_pack_names_the_us_content_decision_and_does_not_decide_it():
    assert "OD-US-CONTENT" in PACK and "US_GENERAL_INFORMATION_DECIDED" in PACK
    assert ka.US_GENERAL_INFORMATION_DECIDED is False


def test_pack_contains_the_checklist_and_open_questions():
    assert PACK.count("| Q-") >= 16
    assert "## 7. Checklist for the qualified licensing reviewer" in PACK
    assert "Never approve on the strength of this pack alone." in PACK
