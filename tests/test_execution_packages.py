"""Phase 00 execution programme: the package register is complete, consistent and fresh. Offline, read-only against the reconciliation."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("execution_packages", ROOT / "scripts/production/execution_packages.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

DELIVERABLES = ["PHASE_00_CURRENT_STATE.md", "IMPLEMENTATION_PACKAGE_REGISTER.md", "DEPENDENCY_GRAPH.md", "DELIVERY_SCHEDULE.md", "TECHNICAL_DECISIONS.md", "ADMIN_V2_EXECUTION_SPEC.md",
                "CANDIDATE_EXECUTION_SPEC.md", "MULTILINGUAL_EXECUTION_PLAN.md", "RELEASE_READINESS_TRACKER.md", "PHASE_00_EXIT_REPORT.md", "R1_SCOPE_RECLASSIFICATION_PROPOSAL.md"]


def test_the_plan_validates_and_the_generated_documents_are_fresh():
    assert E.validate() == []
    for name, fn in (("IMPLEMENTATION_PACKAGE_REGISTER.md", E.render_register), ("DEPENDENCY_GRAPH.md", E.render_graph), ("DELIVERY_SCHEDULE.md", E.render_schedule)):
        assert (E.OUT / name).read_text(encoding="utf-8") == fn(), name


def test_every_r1_0_fix_or_verify_item_is_in_exactly_one_package():
    items = E.load_items()
    need = set(E.r10_items(items))
    assigned = [i for p in E.PACKAGES for i in p["items"]]
    assert len(need) == 162 and sorted(assigned) == sorted(need) and len(assigned) == len(set(assigned))


def test_removing_or_duplicating_an_item_fails_the_check(monkeypatch):
    pk = copy.deepcopy(E.PACKAGES)
    victim = next(p for p in pk if p["items"])
    dropped = victim["items"].pop()
    monkeypatch.setattr(E, "PACKAGES", pk)
    monkeypatch.setattr(E, "BYID", {p["id"]: p for p in pk})
    assert any(dropped in e for e in E.validate())
    other = next(p for p in pk if p is not victim and p["items"])
    other["items"].append(dropped)
    victim["items"].append(dropped)
    assert any("several packages" in e or "must be exactly one" in e for e in E.validate())


def test_a_dependency_cycle_or_an_impossible_schedule_is_rejected(monkeypatch):
    pk = copy.deepcopy(E.PACKAGES)
    by = {p["id"]: p for p in pk}
    by["01B"]["depends"] = ["01C"]                          # 01C already depends on 01B: a cycle
    monkeypatch.setattr(E, "PACKAGES", pk)
    monkeypatch.setattr(E, "BYID", by)
    assert any("cycle" in e for e in E.validate())
    pk2 = copy.deepcopy(E.PACKAGES)
    by2 = {p["id"]: p for p in pk2}
    by2["03E"]["start"], by2["03E"]["end"] = 1, 1          # starts before 03D finishes
    monkeypatch.setattr(E, "PACKAGES", pk2)
    monkeypatch.setattr(E, "BYID", by2)
    assert any("before its dependency" in e for e in E.validate())


def test_the_first_five_prs_have_exact_briefs_and_all_required_package_fields_exist():
    for k in ("01A", "01B", "01C", "02A", "03A"):
        b = E.BRIEFS[k]
        assert b["pr1"] and b["files"] and b["out_of_scope"] and b["verification"], k
    for p in E.PACKAGES:
        for f in ("scope", "components", "backend", "frontend", "security", "acceptance", "tests", "pr", "dod"):
            assert str(p[f]).strip(), (p["id"], f)
        assert 0 < p["effort"][0] <= p["effort"][1] and p["track"] in E.TRACKS


def test_the_six_tracks_phases_and_all_deliverables_exist():
    assert set(E.TRACKS) == {"A", "B", "C", "D", "E", "F"} and all(any(p["track"] == t for p in E.PACKAGES) for t in E.TRACKS)
    assert {p["phase"] for p in E.PACKAGES} == set(E.PHASES)
    for name in DELIVERABLES:
        assert (E.OUT / name).is_file() and (E.OUT / name).stat().st_size > 500, name


def test_the_feasibility_figures_are_computed_and_the_critical_path_is_a_real_chain():
    t = E.totals()
    assert t["min_days"] == sum(p["effort"][0] for p in E.PACKAGES) and t["max_days"] >= t["min_days"]
    chain, days = t["cp_max"]
    assert days <= t["max_days"] and all(chain[i] in E.BYID[chain[i + 1]]["depends"] for i in range(len(chain) - 1))
    report = (E.OUT / "PHASE_00_EXIT_REPORT.md").read_text(encoding="utf-8")
    assert "not feasible" in report and "OD-SCOPE-01" in report and "PENDING" in report            # no false claim of readiness


def test_the_agent_policy_shared_file_order_is_01b_then_01d_then_01c_and_01a_is_independent():
    assert "01B" in E.BYID["01D"]["depends"] and "01B" in E.BYID["01C"]["depends"] and "01D" in E.BYID["01C"]["depends"]
    assert E.BYID["01A"]["depends"] == [] and E.BYID["01B"]["depends"] == []                       # 01A touches none of the overlapping files
    assert E.BYID["01B"]["end"] <= E.BYID["01D"]["start"] and E.BYID["01D"]["end"] <= E.BYID["01C"]["start"]
    assert "registry.py" not in E.BRIEFS["01A"]["files"] and "policies.py" not in E.BRIEFS["01A"]["files"] and E.BRIEFS["01D"]["files"].startswith("src/agent/registry.py")
    assert "REVIEW-01" in E.BYID["01A"]["items"] and E.BYID["01D"]["items"] == []                 # closed together, assigned once


def test_topology_and_knowledge_persistence_are_an_early_parallel_workstream_and_the_staging_file_is_frozen():
    assert set(E.EARLY_PARALLEL) == {"02A", "05A", "05E"} and all(E.BYID[k]["start"] <= 1 for k in E.EARLY_PARALLEL)
    assert "DEPLOYMENT FREEZE" in E.BYID["05A"]["note"] and "must NOT be deployed" in E.BYID["05A"]["note"]
    compose = (ROOT / "deploy/docker-compose.staging.yml").read_text(encoding="utf-8")
    assert "worker" not in compose and "clamav" not in compose.lower().replace("clamav_host", "")      # the gap the freeze protects against is real until 05A fixes it
    schedule = (E.OUT / "DELIVERY_SCHEDULE.md").read_text(encoding="utf-8")
    assert "Early parallel workstream" in schedule and "must not be deployed" in schedule


def test_scope_strategies_are_proposals_with_computed_effort_and_every_package_has_a_tier():
    assert set(E.TIERS) == set(E.BYID) and set(E.TIERS.values()) <= set(E.TIER_NAMES)
    s = E.strategy_sets()
    full = sum(E.BYID[i]["effort"][1] for i in s["S1 Full R1.0 scope"][1])
    s2 = sum(E.BYID[i]["effort"][1] for i in s["S2 Restricted free private beta (proposed)"][1])
    s3 = sum(E.BYID[i]["effort"][1] for i in s["S3 Minimum safe beta (capacity-based alternative)"][1])
    assert s3 < s2 < full and {"03B", "03D", "03E"}.isdisjoint(s["S2 Restricted free private beta (proposed)"][1])
    report = (E.OUT / "PHASE_00_EXIT_REPORT.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs/production/OWNER_DECISION_REGISTER.md").read_text(encoding="utf-8")
    assert "NOT owner-approved" in report and "Phase 00 PROPOSES" in decisions and "OD-SCOPE-01" in decisions


def test_the_exit_report_records_the_exact_ci_root_cause_and_the_e8_e10_evidence():
    report = (E.OUT / "PHASE_00_EXIT_REPORT.md").read_text(encoding="utf-8")
    for needle in ("dependency drift", "starlette 1.9.0", "cross_user_isolation", "not an authorization defect", "E8", "E10", "R1_SCOPE_RECLASSIFICATION_PROPOSAL", "01D"):
        assert needle in report, needle
