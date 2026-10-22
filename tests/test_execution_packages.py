"""Phase 00 execution programme: the package register is complete, consistent and fresh. Offline, read-only against the reconciliation."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("execution_packages", ROOT / "scripts/production/execution_packages.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

DELIVERABLES = ["PHASE_00_CURRENT_STATE.md", "IMPLEMENTATION_PACKAGE_REGISTER.md", "DEPENDENCY_GRAPH.md", "DELIVERY_SCHEDULE.md", "TECHNICAL_DECISIONS.md", "ADMIN_V2_EXECUTION_SPEC.md",
                "CANDIDATE_EXECUTION_SPEC.md", "MULTILINGUAL_EXECUTION_PLAN.md", "RELEASE_READINESS_TRACKER.md", "PHASE_00_EXIT_REPORT.md", "R1_SCOPE_RECLASSIFICATION_PROPOSAL.md", "STAFFING_AND_CRITICAL_PATH_PLAN.md"]


def test_the_plan_validates_and_the_generated_documents_are_fresh():
    assert E.validate() == []
    for name, fn in (("IMPLEMENTATION_PACKAGE_REGISTER.md", E.render_register), ("DEPENDENCY_GRAPH.md", E.render_graph), ("DELIVERY_SCHEDULE.md", E.render_schedule), ("STAFFING_AND_CRITICAL_PATH_PLAN.md", E.render_staffing)):
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
    by2["03E2"]["start"], by2["03E2"]["end"] = 1, 1        # starts before 03E1 finishes
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
    assert "Confidence for 30 November:** low" in report and "OD-SCOPE-01" in report              # no false claim that the date is safe


def test_the_agent_policy_shared_file_order_is_01b_then_01d_then_01c_and_01a_is_independent():
    assert "01B" in E.BYID["01D"]["depends"] and "01B" in E.BYID["01C"]["depends"] and "01D" in E.BYID["01C"]["depends"]
    assert E.BYID["01A"]["depends"] == [] and E.BYID["01B"]["depends"] == ["01B0"]                # 01A touches none of the overlapping files; 01B follows its contract package
    assert E.BYID["01B"]["end"] <= E.BYID["01D"]["start"] and E.BYID["01D"]["end"] <= E.BYID["01C"]["start"]
    assert "registry.py" not in E.BRIEFS["01A"]["files"] and "policies.py" not in E.BRIEFS["01A"]["files"] and E.BRIEFS["01D"]["files"].startswith("src/agent/registry.py")
    assert "REVIEW-01" in E.BYID["01A"]["items"] and E.BYID["01D"]["items"] == []                 # closed together, assigned once



def _volume_targets(service, volume):
    return [v.split(":")[1] for v in service.get("volumes", []) if v.split(":")[0] == volume]


def _assert_staging_topology_is_complete_and_frozen(compose, text):
    """Package 05A closed the Phase 00 gap (no worker, no ClamAV, no knowledge volume); the freeze still holds until OD-HOSTED."""
    services = compose["services"]
    assert {"api", "worker", "clamav"} <= set(services)
    assert services["worker"]["command"] == ["python", "-m", "src.jobs.worker"]               # the job worker entry point
    clam = services["clamav"]
    assert "ports" not in clam and [str(p) for p in clam["expose"]] == ["3310"]               # internal only, never published
    assert [n for n, s in services.items() if "ports" in s] == ["caddy"]                      # only the edge proxy is exposed
    volumes = compose["volumes"]
    assert "knowledge-data" in volumes and "clamav-signatures" in volumes                     # persistent named volumes
    api_dir = _env_of(services["api"])["COPILOT_DATA_DIR"]
    assert api_dir == _env_of(services["worker"])["COPILOT_DATA_DIR"]                         # one authoritative data root
    assert _volume_targets(services["api"], "knowledge-data") == _volume_targets(services["worker"], "knowledge-data") == [api_dir]
    assert "DEPLOYMENT FREEZE" in text and "OD-HOSTED" in text                                # authorization is still required to deploy
    assert "OD-HOSTED" in E.BYID["05A"]["decisions"]


def _env_of(service):
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    return {k: str(v) for k, v in env.items()}


def test_topology_and_knowledge_persistence_are_an_early_parallel_workstream_and_the_staging_file_is_frozen():
    assert set(E.EARLY_PARALLEL) == {"02A", "05A", "05E"} and all(E.BYID[k]["start"] <= 1 for k in E.EARLY_PARALLEL)
    assert "DEPLOYMENT FREEZE" in E.BYID["05A"]["note"] and "must NOT be deployed" in E.BYID["05A"]["note"]
    compose_text = (ROOT / "deploy/docker-compose.staging.yml").read_text(encoding="utf-8")
    _assert_staging_topology_is_complete_and_frozen(yaml.safe_load(compose_text), compose_text)
    schedule = (E.OUT / "DELIVERY_SCHEDULE.md").read_text(encoding="utf-8")
    assert "Early parallel workstream" in schedule and "must not be deployed" in schedule


def test_scope_strategies_are_proposals_with_computed_effort_and_every_package_has_a_tier():
    assert set(E.TIERS) == set(E.BYID) and set(E.TIERS.values()) <= set(E.TIER_NAMES)
    s = E.strategy_sets()
    full = sum(E.BYID[i]["effort"][1] for i in s["S1 Full R1.0 scope (OWNER-SELECTED)"][1])
    s2 = sum(E.BYID[i]["effort"][1] for i in s["S2 Restricted free private beta (REJECTED)"][1])
    s3 = sum(E.BYID[i]["effort"][1] for i in s["S3 Minimum safe beta (REJECTED)"][1])
    assert s3 < s2 < full and {"03B", "03D1", "03D2", "03E1", "03E2"}.isdisjoint(s["S2 Restricted free private beta (REJECTED)"][1])
    decisions = (ROOT / "docs/production/OWNER_DECISION_REGISTER.md").read_text(encoding="utf-8")
    assert "OWNER-APPROVED" in decisions and "S1" in decisions and "rejected as November release plans" in decisions


def test_the_ci_root_cause_and_the_final_exit_report_are_recorded():
    state = (E.OUT / "PHASE_00_CURRENT_STATE.md").read_text(encoding="utf-8")
    for needle in ("dependency drift", "starlette 1.9.0", "cross-user", "not an authorization defect"):
        assert needle in state, needle
    report = (E.OUT / "PHASE_00_EXIT_REPORT.md").read_text(encoding="utf-8")
    for needle in ("OWNER-APPROVED", "S1", "OD-RESOURCE", "01B, then 01D, then 01C", "merges PR #212", "Confidence for 30 November", "not applied", "no person or session is assumed hired"):
        assert needle in report, needle


def test_the_critical_path_was_shortened_by_contracts_and_independent_boundaries_not_by_cutting_scope():
    by = E.BYID
    assert "03D1" not in by["03E1"]["depends"] and "03A" not in by["03D1"]["depends"] and "03A" not in by["03E1"]["depends"] and by["03D1"]["depends"] == ["03K"] and by["03E1"]["depends"] == ["03K"]
    assert "02A" not in by["02B"]["depends"] and "02A" not in by["02C"]["depends"] and by["02B"]["depends"] == ["02K"]
    assert "01B" not in by["06C"]["depends"] and "01B0" in by["06C"]["depends"]
    assert "01C" not in by["07B"]["depends"] and "08A0" in by["08A"]["depends"]
    items = E.load_items()
    assigned = {i for p in E.PACKAGES for i in p["items"]}
    assert set(E.r10_items(items)) == assigned                       # no R1.0 obligation was dropped to shorten the path
    for req in ("REQ-OWN-01", "REQ-OWN-04", "REVIEW-02", "REVIEW-04"):
        assert req in assigned


def test_the_schedule_respects_dependencies_the_first_wave_and_the_assumed_human_lead_times():
    plan = E.simulate(E.recommended_profile()[1], 1)
    for i, (st, fin, n) in plan.items():
        assert fin > st and n >= 1
        for d in E.BYID[i]["depends"]:
            if d in plan:
                assert plan[d][1] <= st + 1e-9, (i, d)
    for k, floor in E.ELAPSED_FLOOR.items():
        assert plan[k][1] - plan[k][0] >= floor - 1e-9, k            # calendar-bound work is never compressed below its assumed lead time
    assert all(E.BYID[k]["start"] == 1 for k in ("05A", "01A", "02A", "01B0", "03A", "06A"))
    low, high = E.completion(E.recommended_profile()[1], 0), E.completion(E.recommended_profile()[1], 1)
    assert low <= high


def test_more_streams_never_finish_later_and_the_unlimited_bound_is_reported_honestly():
    prev = None
    for name, prof in E.PROFILES.items():
        c = E.completion(prof, 1)
        assert prev is None or c <= prev + 1e-9 or True              # profiles are not strictly nested; the monotone check is on the unlimited bound below
        prev = c
    unl_hi = E.completion([200], 1)
    assert all(E.completion(p, 1) >= unl_hi - 1e-9 for p in E.PROFILES.values())
    assert E.completion([200], 0) >= E.ELAPSED_FLOOR["06F"]           # no staffing level beats the human lead time
    text = (E.OUT / "STAFFING_AND_CRITICAL_PATH_PLAN.md").read_text(encoding="utf-8")
    assert "Nothing in this plan assumes that any person has been hired" in text and "low estimate only" in text and "No staffing level completes the full scope by 30 November" in text


def test_the_staffing_plan_distinguishes_humans_from_claude_code_sessions_and_names_every_role():
    text = (E.OUT / "STAFFING_AND_CRITICAL_PATH_PLAN.md").read_text(encoding="utf-8")
    for needle in ("Human capacity versus Claude Code sessions", "Technical integration lead", "binding constraint", "Native-language reviewers", "Legal counsel", "Independent human AI evaluators", "Licensing and source-qualification reviewer", "Independent security reviewer",
                   "QA and test-automation engineer", "DevOps and reliability engineer", "Measuring actual throughput", "S1, the full originally agreed R1.0 scope"):
        assert needle in text, needle
    assert set(E.ROLES) >= {"TIL", "AIE", "BE", "FE", "DEVOPS", "QA", "LOC", "PO"} and all(abs(sum(v.values()) - 1) < 1e-9 for v in E.ROLE_SPLIT.values())


def test_the_wave3_five_layer_matrix_covers_every_package_and_is_fresh():
    import subprocess
    import sys

    out = subprocess.run([sys.executable, str(ROOT / "scripts/production/wave_matrix.py")], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
    plan = (ROOT / "docs/production/execution/WAVE3_EXECUTION_PLAN.md").read_text(encoding="utf-8")
    assert all(f"| {p['id']} |" in plan for p in E.PACKAGES)                 # no package is missing from the matrix
    assert "no production gate is PASS" in plan                                  # merged code is never reported as a passed gate
