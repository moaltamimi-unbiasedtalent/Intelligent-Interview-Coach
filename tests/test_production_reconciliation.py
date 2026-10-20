"""Production roadmap V2.2 backlog reconciliation: machine-checked, offline, read-only against the register."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reconcile_issues", ROOT / "scripts/production/reconcile_issues.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def committed() -> dict:
    return json.loads(R.RECON.read_text(encoding="utf-8"))


def test_the_committed_reconciliation_is_valid_and_fresh():
    doc = committed()
    assert R.validate(doc) == []
    fresh = R.build()
    assert doc["summary"] == fresh["summary"]
    assert {r["id"]: r["disposition"] for r in doc["items"]} == {r["id"]: r["disposition"] for r in fresh["items"]}


def test_every_register_issue_is_accounted_for_with_zero_unmapped():
    raw, reg = R.load_register()
    doc = committed()
    s = doc["summary"]
    assert (s["historical_issues"], s["historical_closed"], s["historical_active"], s["unmapped_issues"]) == (394, 52, 342, 0)
    assert {i["original_id"] for i in reg} <= {r["id"] for r in doc["items"]}
    assert all(r["disposition"] in R.DISPOSITIONS for r in doc["items"])
    # the 72 pending owner decisions and the 52 closed issues keep their kind of disposition
    hist = {r["id"]: r for r in doc["items"] if r["origin"] == "REGISTER"}
    assert sum(1 for i in reg if i["status"] == "PENDING OWNER DECISION") == 72
    assert all(hist[i["original_id"]]["disposition"] == "OWNER DECISION" for i in reg if i["status"] == "PENDING OWNER DECISION")
    assert all(hist[i["original_id"]]["disposition"] == "CLOSE WITH EVIDENCE" and hist[i["original_id"]]["evidence_of_closure"] == i["closure_evidence"] for i in reg if i["status"] == "CLOSED - VERIFIED")


def test_an_active_issue_without_a_valid_disposition_fails_the_check():
    doc = copy.deepcopy(committed())
    victim = next(r for r in doc["items"] if r["origin"] == "REGISTER" and r["current_status"] != "CLOSED - VERIFIED")
    for bad in ("", "MAYBE LATER"):
        victim["disposition"] = bad
        assert R.validate(doc)
    victim["disposition"] = "DEFER TO NAMED RELEASE"
    victim["release"] = "R1.0"                                        # a deferral must name a LATER release
    assert any("named later release" in e for e in R.validate(doc))
    victim["release"] = "R1.1"
    victim["feature_gate"] = ""                                       # and must say which gate keeps the feature off
    assert any("without a feature gate" in e for e in R.validate(doc))


def test_history_cannot_be_rewritten_or_silently_upgraded():
    doc = copy.deepcopy(committed())
    closed = next(r for r in doc["items"] if r["origin"] == "REGISTER" and r["current_status"] == "CLOSED - VERIFIED")
    closed["evidence_of_closure"] = "none yet"
    assert any("closure evidence" in e for e in R.validate(doc))
    doc = copy.deepcopy(committed())
    active = next(r for r in doc["items"] if r["origin"] == "REGISTER" and r["current_status"] == "NOT RUN")
    active["current_status"] = "CLOSED - VERIFIED"
    active["historical"] = dict(active["historical"], status="CLOSED - VERIFIED")
    assert R.validate(doc)


def test_deferrals_rely_on_gates_that_are_really_disabled_and_none_is_unmapped():
    doc = committed()
    for mod, name in R.GATE_CONSTANTS:
        assert getattr(__import__(mod, fromlist=[name]), name) is False
    deferred = [r for r in doc["items"] if r["disposition"] == "DEFER TO NAMED RELEASE"]
    assert deferred and all(r["feature_gate"].strip() and r["release"] in R.DEFER_RELEASES for r in deferred)
    assert all(r["release"] == "R1.0" for r in doc["items"] if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0"))


def test_language_scope_decisions_are_recorded():
    doc = committed()
    ids = {r["id"]: r for r in doc["items"]}
    assert all(f"REQ-LANG-{n:02d}" in ids for n in range(1, 17))
    assert ids["REQ-LANG-14"]["wp"] == "WP-08" and "Russian" in ids["REQ-LANG-14"]["title"]
    assert ids["REQ-LANG-15"]["release"] == "R1.3" and ids["REQ-LANG-15"]["disposition"] == "DEFER TO NAMED RELEASE"
    assert ids["REQ-LANG-07"]["disposition"] == "FIX BEFORE R1.0" and "country" in ids["REQ-LANG-07"]["title"].lower()
    text = (ROOT / "docs/production/MULTILINGUAL_RELEASE_QUALIFICATION.md").read_text(encoding="utf-8")
    for lang in ("English", "German", "Spanish", "Italian", "Portuguese", "French", "Dutch"):
        assert lang in text
    for gate in range(1, 15):
        assert f"LG-{gate:02d}" in text
