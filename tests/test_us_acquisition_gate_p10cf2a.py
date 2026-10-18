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


def test_acquisition_blocked_while_dictionary_unverified():
    _, allowed, blockers = gate.evaluate()
    assert not allowed and any(b.startswith("J:") for b in blockers) and any(b.startswith("K:") for b in blockers)


def test_no_hash_is_fabricated():
    m = json.loads((gate.DIR / "acquisition_manifest.json").read_text())
    assert all(f["state"] == "NOT_ACQUIRED" and f["sha256"] is None for f in m["files"])
    assert {f["original_filename"] for f in m["files"]} == gate.AUTHORISED_FILES
