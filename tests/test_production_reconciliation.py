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
    assert ids["REQ-LANG-14"]["wp"] == "WP-08" and "Russian" in ids["REQ-LANG-14"]["title"] and ids["REQ-LANG-14"]["provenance"] == "EXPLICIT_OWNER_DECISION"
    assert ids["REQ-LANG-16"]["provenance"] == "AWAITING_APPROVAL"      # the market mappings are NOT individually approved
    assert ids["REQ-LANG-15"]["release"] == "R1.3" and ids["REQ-LANG-15"]["disposition"] == "DEFER TO NAMED RELEASE"
    assert ids["REQ-LANG-07"]["disposition"] == "FIX BEFORE R1.0" and "country" in ids["REQ-LANG-07"]["title"].lower()
    text = (ROOT / "docs/production/MULTILINGUAL_RELEASE_QUALIFICATION.md").read_text(encoding="utf-8")
    for lang in ("English", "German", "Spanish", "Italian", "Portuguese", "French", "Dutch"):
        assert lang in text
    for gate in range(1, 15):
        assert f"LG-{gate:02d}" in text


def test_the_five_actual_reviewer_findings_replace_the_demo_findings_which_stay_separate():
    ids = {r["id"]: r for r in committed()["items"]}
    assert not any(i.startswith("RF-") for i in ids)
    for n in range(1, 6):
        rv = ids[f"REVIEW-0{n}"]
        assert rv["origin_class"] == "TURING-REVIEW" and rv["provenance"] == "REVIEWER_FINDING" and rv["disposition"] == "FIX BEFORE R1.0" and len(rv["requirements_list"]) >= 6
        assert ids[f"DEMO-0{n}"]["origin_class"] == "DEMO-OBSERVED"       # engineering-observed, never presented as reviewer findings
    assert len(ids["REVIEW-01"]["requirements_list"]) == 6 and "held-out" in " ".join(ids["REVIEW-01"]["requirements_list"]).lower()
    assert ids["REVIEW-05"]["wp"] == "WP-17" and ids["REVIEW-04"]["priority"] == "P0"


def test_owner_capabilities_are_specified_testable_r1_0_requirements_not_placeholders():
    ids = {r["id"]: r for r in committed()["items"]}
    for n in range(1, 9):
        o = ids[f"REQ-OWN-0{n}"]
        assert o["disposition"] == "FIX BEFORE R1.0" and o["release"] == "R1.0" and o["origin_class"] == "OWNER-REQUIREMENT"
        assert len(o["requirements_list"]) >= 5 and o["required_tests"].strip() and "not in repository" not in o["current_status"].lower()
    assert any("restart" in c.lower() for c in ids["REQ-OWN-06"]["requirements_list"])           # Story Bank acceptance journey
    assert any("revokes" in c.lower() or "revoke" in c.lower() for c in ids["REQ-OWN-07"]["requirements_list"])
    assert len(ids["REQ-OWN-05"]["requirements_list"]) == 9 and any("restore" in c.lower() for c in ids["REQ-OWN-05"]["requirements_list"])


def test_the_agreed_release_train_is_complete_and_russian_is_not_an_automatic_r2_0_commitment():
    doc = committed()
    assert doc["releases"] == ["R1.0", "R1.1", "R1.2", "R1.3", "R1.4", "R1.5", "R1.6", "R1.7", "R2.0"] and set(doc["release_themes"]) == set(doc["releases"])
    for rel in doc["releases"]:
        assert any(r["release"] == rel for r in doc["items"]), rel
    russian = [r for r in doc["items"] if r["rule_id"].startswith("U-RU")]
    assert russian and all(r["disposition"] == "OWNER DECISION" and r["release"] == "UNSCHEDULED" for r in russian)
    assert not any(r["release"] == "R2.0" and "russian" in r["title"].lower() for r in doc["items"])
    assert all(r["release"] != "R1.0" for r in doc["items"] if r["rule_id"] in ("D-COM", "D-SPEECH", "D-INTL", "D-FL"))


def test_academic_only_tasks_are_reclassified_and_not_counted_as_production_work():
    doc = committed()
    ac = [r for r in doc["items"] if r["scope_class"] == "ACADEMIC_ONLY"]
    assert {r["id"] for r in ac} == set(R.ACADEMIC_ONLY) and len(ac) == 6
    assert all(r["disposition"] == "OWNER DECISION" and r["release"] == "UNSCHEDULED" and r["current_status"] == r["historical"]["status"] for r in ac)   # status never rewritten
    assert doc["summary"]["academic_only_items"] == 6


def test_every_item_has_the_required_traceability_fields_and_corrected_deltas_are_explained():
    doc = committed()
    for r in doc["items"]:
        for k in ("id", "origin_class", "description", "wp", "release", "priority", "dependencies", "acceptance_criteria", "test_evidence", "current_status", "owner_role"):
            assert str(r.get(k) or "").strip(), (r["id"], k)
    s = doc["summary"]
    assert s["delta_vs_previous"]["items"] == len(doc["items"]) - s["previous_baseline"]["items"]
    dash = (ROOT / "docs/production/RELEASE_BLOCKER_DASHBOARD.md").read_text(encoding="utf-8")
    assert "Why the numbers moved" in dash and "REQ-OWN-01 to 08" in dash


def test_the_source_of_truth_document_and_fifteen_production_gates_exist():
    src = (ROOT / "docs/production/OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md").read_text(encoding="utf-8")
    for tag in ("[DECISION]", "[CAPABILITY]", "[REVIEWER]", "[PROPOSED]", "[AWAITING]"):
        assert tag in src
    for n in range(1, 6):
        assert f"REVIEW-0{n}" in src
    matrix = (ROOT / "docs/production/PRODUCTION_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    for n in range(1, 16):
        assert f"PG-{n:02d}" in matrix
    assert "386 of 412" in matrix and "FAIL" in matrix                    # the historical coverage gate is preserved
    assert "accepted limitation" in matrix                                # mandatory gates cannot be waived that way


def test_the_owner_scope_decision_s1_is_recorded_and_genuinely_open_decisions_are_retained():
    doc = committed()
    osd = doc["owner_scope_decision"]
    assert osd["selected"] == "S1" and osd["status"] == "OWNER-APPROVED" and set(osd["rejected"]) == {"S2", "S3"} and osd["gates_override_deadline"] is True
    assert "OD-SCOPE-01" in doc["resolved_decisions"] and "OD-SCOPE-01" not in doc["open_decisions"]
    for still_open in ("OD-RESOURCE", "OD-HOSTED", "OD-BUDGET", "OD-GATE-THRESHOLDS", "OD-EMBED", "OD-RECLASS", "OD-US-CONTENT", "OD-PLAN-LIMITS", "OD-LANG-02", "OD-LANG-03", "OD-LANG-04"):
        assert still_open in doc["open_decisions"], still_open
    for resolved in ("OD-ADMIN-NAV", "OD-INVITE", "OD-MALWARE"):
        assert resolved in doc["resolved_decisions"] and resolved not in doc["open_decisions"], resolved
    register = (ROOT / "docs/production/OWNER_DECISION_REGISTER.md").read_text(encoding="utf-8")
    assert "OWNER-APPROVED" in register and "S2 (restricted free private beta) and S3 (minimum safe beta) are rejected" in register


def test_the_reclassification_proposal_stays_unapplied_after_the_sign_off():
    doc = committed()
    assert doc["scope_proposals"]["applied"] is False and doc["summary"]["proposed_reclassification"]["applied"] is False
    by = {r["id"]: r for r in doc["items"]}
    assert all(by[k]["disposition"] == "FIX BEFORE R1.0" and by[k]["release"] == "R1.0" for k in doc["scope_proposals"]["reclassification"])
