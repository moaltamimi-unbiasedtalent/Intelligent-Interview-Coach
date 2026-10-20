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
                "CANDIDATE_EXECUTION_SPEC.md", "MULTILINGUAL_EXECUTION_PLAN.md", "RELEASE_READINESS_TRACKER.md", "PHASE_00_EXIT_REPORT.md"]


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
    by["01A"]["depends"] = ["01C"]                          # 01C already depends on 01A: a cycle
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
    assert "NOT feasible" in report and "OD-SCOPE-01" in report and "PENDING" in report            # no false claim of readiness
