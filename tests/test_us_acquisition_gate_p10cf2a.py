"""P10C-F2A: the acquisition records are consistent and acquisition stays blocked until every precondition is met."""
import importlib.util
import json
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts/p10c_f2a_acquisition_gate.py"
_s = importlib.util.spec_from_file_location("p10c_f2a_gate", _p)
gate = importlib.util.module_from_spec(_s)
_s.loader.exec_module(gate)


def test_records_consistent():
    errs, _, _ = gate.evaluate()
    assert errs == []


def test_ingestion_blocked_until_registry_lifecycle_and_every_precondition_met():
    _, allowed, blockers = gate.evaluate()
    assert not allowed and any(b.startswith("L:") for b in blockers)
    assert not any(b.startswith(("J:", "K:", "M:")) for b in blockers)


def test_acquired_files_have_real_hashes_and_stay_unqualified():
    m = json.loads((gate.DIR / "acquisition_manifest.json").read_text())
    assert {f["original_filename"] for f in m["files"]} == gate.AUTHORISED_FILES
    for f in m["files"]:
        assert f["state"] == "ACQUIRED" and len(f["sha256"]) == 64 and f["http_status"] == 200
        assert f["ingestion_state"] == "NOT_INGESTED" and f["qualification_status"] == "NOT_QUALIFIED" and f["runtime_approval"] == "NOT_APPROVED"
        assert gate.REPO not in Path(f["storage_location"]).parents


def test_hashes_match_staged_files_when_present():
    m = json.loads((gate.DIR / "acquisition_manifest.json").read_text())
    if all(Path(f["storage_location"]).exists() for f in m["files"]):
        assert gate.verify_hashes() == []


def test_data_dictionary_has_no_unknown_field_and_no_top_code_marker_claim():
    d = json.loads((gate.DIR / "data_dictionary_validation.json").read_text())
    assert all(f["status"] in {"VERIFIED", "PARTIALLY_VERIFIED", "NOT_VERIFIED"} for f in d["fields"])
    assert {s["symbol"] for s in d["symbols"]} == {"*", "**", "#", "~"}
    assert d["aggregation_rules"]["o_group_counts"]["detailed"] == 830 and d["aggregation_rules"]["duplicate_codes"]["count"] == 7
