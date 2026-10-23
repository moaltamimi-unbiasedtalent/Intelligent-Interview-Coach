"""08A0 release evidence pipeline: ledger schema, determinism, staleness, PASS-without-artefact refusal, language-gate rule parity, no-network default,
tracker-contradiction detection and the reconciliation check. Offline: a test that reaches a socket fails."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import re
import socket
import urllib.error
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_evidence_under_test", ROOT / "scripts/production/release_evidence.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
LA = R.LA

TODAY = date.fromisoformat(R.load_ledger()["as_of"])            # the committed ledger's as_of: the committed-data tests never depend on the real clock
GOOD_LINK = "docs/production/execution/evidence/04E_EVIDENCE.md"
TRACKER_TEXT = R.TRACKER.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network access attempted in an offline test")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def ledger() -> dict:
    return copy.deepcopy(R.load_ledger())


def ctx(today: date = TODAY, release_sha: str | None = None) -> "R.Context":
    return R.Context(today=today, release_sha=release_sha)


def tracker_with(gid: str, state: str) -> str:
    return re.sub(rf"(\| {gid} \|[^\n]*?\| )(NOT STARTED|IN PROGRESS|READY FOR REVIEW|PASS[^|]*|FAIL|BLOCKED)( \|)", rf"\g<1>{state}\g<3>", TRACKER_TEXT, count=1)


def ev(**kw) -> dict:
    base = {"kind": "document", "link": GOOD_LINK, "sha": "f5cf7cb4", "date": "2026-10-20", "produced_by": "Alex Example", "produced_by_type": "human"}
    base.update(kw)
    return base


def fails_for(doc: dict, *, tracker: str | None = None, today: date = TODAY, release_sha: str | None = None) -> list[str]:
    return R.check_ledger(doc, ctx(today, release_sha), tracker_text=tracker)[0]


def any_has(fails: list[str], *needles: str) -> bool:
    return any(all(n in f for n in needles) for f in fails)


# ------------------------------------------------------------------------------------------------------------------ schema
def test_the_committed_ledger_is_schema_valid_and_passes_the_whole_check():
    doc = R.load_ledger()
    assert R.schema_problems(doc) == []
    fails, _notes = R.check_ledger(doc, ctx())
    assert fails == []
    assert R.run_check(today=TODAY, out=lambda s: None) == 0


def test_the_ledger_is_seeded_with_the_real_merged_prs_213_to_235():
    doc = R.load_ledger()
    assert sorted(p["number"] for p in doc["pull_requests"]) == list(range(213, 265))
    by = {p["number"]: p for p in doc["pull_requests"]}
    # independent cross-check against the committed Wave 2 dashboard (PR, package, branch, head, merge SHA)
    dash = (R.EXEC / "WAVE2_EXECUTION_DASHBOARD.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| #(\d+) \| [^|]+ \| ([^|]+) \| ([0-9a-f]{7}) \| ([0-9a-f]{7}) \|", dash, re.M)
    assert len(rows) == 13
    for n, branch, head, merge in rows:
        assert by[int(n)]["branch"].strip() == branch.strip()
        assert by[int(n)]["head_sha"].startswith(head) and by[int(n)]["merge_sha"].startswith(merge), n
    assert by[235]["merge_sha"].startswith("f5cf7cb") and by[235]["ci"]["result"] == "not recorded"     # no CI evidence is committed for #235: never invented
    assert all(by[n]["ci"]["result"] == "success" and by[n]["ci"]["source"] for n in range(213, 235))


def test_every_live_human_and_gate_layer_is_recorded_not_run_or_open_and_only_pg11_is_pass():
    doc = R.load_ledger()
    for pid, ent in doc["packages"].items():
        assert ent["layers"]["live_staging"]["state"] in ("NOT RUN", "N/A"), pid
        assert ent["layers"]["human_qualification"]["state"] in ("OPEN", "NONE REQUIRED"), pid
        assert ent["layers"]["gate_acceptance"]["state"] == "NOT ACCEPTED", pid
        assert all(not le["evidence"] for le in ent["layers"].values()), pid
    assert [g for g, e in doc["gates"].items() if e["state"] == "PASS"] == ["PG-11"]
    for code, rec in doc["language_gates"].items():
        assert all(g["state"] != "PASS" for g in rec["gates"].values()), code


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.pop("as_of"), "missing top-level field 'as_of'"),
    (lambda d: d.update(surprise=1), "unknown top-level field"),
    (lambda d: d["pull_requests"][0].update(merge_sha="zzz"), "merge_sha malformed"),
    (lambda d: d["pull_requests"][0].update(extra=1), "unknown field 'extra'"),
    (lambda d: d["pull_requests"].append(copy.deepcopy(d["pull_requests"][0])), "duplicate PR number"),
    (lambda d: d["pull_requests"][0]["ci"].update(result="green"), "ci.result must be one of"),
    (lambda d: d["gates"]["PG-01"].update(state="MAYBE"), "state must be one of"),
    (lambda d: d["gates"].pop("PG-07"), "gates.PG-07: missing"),
    (lambda d: d["gates"].update({"PG-99": copy.deepcopy(d["gates"]["PG-01"])}), "unknown gate"),
    (lambda d: d["packages"]["04A"]["layers"]["live_staging"].update(state="MAYBE"), "state must be one of"),
    (lambda d: d["gates"]["PG-11"]["evidence"][0].update(produced_by_type="script"), "produced_by_type must be one of"),
    (lambda d: d["gates"]["PG-11"]["evidence"][0].update(sha="nothex"), "evidence sha malformed"),
    (lambda d: d["gates"]["PG-11"]["evidence"][0].update(date="22/10/2026"), "evidence date malformed"),
    (lambda d: d["language_gates"]["en"]["gates"].pop("LG-05"), "gates must be exactly"),
    (lambda d: d["language_gates"]["en"]["gates"]["LG-05"].update(state="APPROVED"), "state must be one of"),
    (lambda d: d["policy"].update(gate_evidence_valid_days=0), "must be a positive integer"),
])
def test_schema_rejects_malformed_ledgers(mutate, needle):
    doc = ledger()
    mutate(doc)
    assert any(needle in p for p in R.schema_problems(doc)), R.schema_problems(doc)


def test_the_documented_json_schema_enums_match_the_module_constants():
    s = json.loads(R.SCHEMA_FILE.read_text(encoding="utf-8"))
    d = s["$defs"]
    assert tuple(d["gate"]["properties"]["state"]["enum"]) == R.GATE_STATES
    assert tuple(d["pull_request"]["properties"]["ci"]["properties"]["result"]["enum"]) == R.CI_RESULTS
    assert tuple(d["evidence"]["properties"]["produced_by_type"]["enum"]) == R.PRODUCER_TYPES
    assert tuple(d["evidence"]["properties"]["binding"]["enum"]) == R.BINDINGS
    assert set(d["language"]["properties"]["gates"]["additionalProperties"]["properties"]["state"]["enum"]) == set(LA.STATES)
    assert s["properties"]["schema"]["const"] == R.SCHEMA_ID
    for layer, states in R.LAYER_STATES.items():
        assert states[-1] == R.POSITIVE[layer]


# ------------------------------------------------------------------------------------------------------------------ generator determinism and the acceptance criterion
def test_the_generated_view_and_matrix_inputs_are_deterministic_and_fresh():
    doc = R.load_ledger()
    assert R.render_view(doc) == R.render_view(copy.deepcopy(doc))
    assert R.render_matrix_inputs(doc) == R.render_matrix_inputs(copy.deepcopy(doc))
    assert R.VIEW.read_text(encoding="utf-8") == R.render_view(doc)
    assert R.MATRIX_INPUTS.read_text(encoding="utf-8") == R.render_matrix_inputs(doc)
    assert R.view_problems(doc) == []
    stale = copy.deepcopy(doc)
    stale["pull_requests"][0]["ci"]["checks"] = "99/99"
    assert R.view_problems(stale)


def test_the_view_reuses_package_status_and_wave_matrix_for_all_45_packages_without_duplicating_them():
    doc = R.load_ledger()
    inputs = json.loads(R.render_matrix_inputs(doc))
    assert list(inputs["packages"]) == [p["id"] for p in R.E.PACKAGES] and len(inputs["packages"]) == 45
    r = inputs["packages"]["02K"]
    assert r["engineering"] == R.W.eng_layer("02K") and r["merge_sha"].startswith("657e456") and r["ci"].startswith("PR #215 CI success")
    assert r["live_staging"]["description"] == R.W.LAYERS["02K"][0] and r["gate_acceptance"]["description"] == R.W.LAYERS["02K"][2]
    assert inputs["packages"]["08A"]["engineering"] == "NOT STARTED"
    # the ledger holds no copy of the package text or the layer descriptions
    raw = R.LEDGER.read_text(encoding="utf-8")
    assert R.W.LAYERS["05A"][0] not in raw and R.E.PACKAGE_STATUS["05A"][3] not in raw


def test_evidence_for_a_merged_package_appears_in_the_view_without_manual_copying(monkeypatch):
    status = dict(R.E.PACKAGE_STATUS)
    status["08A0"] = ("MERGED (PR #299, merge abc1234); CI green", "feat/08a0-release-evidence", "def5678", "synthetic")
    monkeypatch.setattr(R.E, "PACKAGE_STATUS", status)
    doc = ledger()
    doc["packages"].pop("08A0", None)  # create an absent-entry fixture even after the real package has merged
    assert any_has(fails_for(doc), "package 08A0", "no ledger entry")          # the checker demands it ...
    added = R.sync_ledger(doc)                                                  # ... and sync derives it from PACKAGE_STATUS alone
    assert added == ["08A0"]
    entry = doc["packages"]["08A0"]
    assert entry["layers"] == R.blank_layers()                                  # NOT RUN / OPEN / NOT ACCEPTED: sync never writes a positive state
    pr = next(p for p in doc["pull_requests"] if p["number"] == 299)
    assert pr["merge_sha"] == "abc1234" and pr["head_sha"] == "def5678" and pr["ci"]["result"] == "not recorded"
    assert not any_has(fails_for(doc), "08A0")
    row = json.loads(R.render_matrix_inputs(doc))["packages"]["08A0"]
    assert row["merge_sha"] == "abc1234" and row["ci"] == "PR #299 CI not recorded"
    assert "| 08A0 | " in R.render_view(doc) and "PR #299" in R.render_view(doc)
    assert R.sync_ledger(doc) == []                                             # idempotent


# ------------------------------------------------------------------------------------------------------------------ staleness
def test_staleness_is_a_deterministic_function_of_date_and_validity():
    d = date(2026, 10, 22)
    assert not R.is_stale(d, 30, date(2026, 11, 21)) and R.is_stale(d, 30, date(2026, 11, 22))
    assert not R.is_stale(d, 30, d)
    assert R.is_stale(d, 1, date(2026, 10, 24)) and not R.is_stale(d, 1, date(2026, 10, 23))


def test_the_committed_pg11_pass_goes_stale_after_its_stated_validity_and_is_fresh_before():
    doc = R.load_ledger()
    assert fails_for(copy.deepcopy(doc), today=date(2026, 11, 21)) == []
    stale = fails_for(copy.deepcopy(doc), today=date(2026, 11, 22))
    assert any_has(stale, "PG-11", "stale")


def test_release_sha_bound_evidence_is_stale_against_a_different_release_sha():
    doc = ledger()
    doc["gates"]["PG-11"]["evidence"][0]["binding"] = "release_sha"
    assert fails_for(doc, release_sha="f5cf7cb4aaaaaaaa") == []                 # prefix match: the same commit
    assert any_has(fails_for(doc, release_sha="1234567890abcdef"), "PG-11", "stale", "release SHA")
    assert fails_for(doc) == []                                                  # no release SHA stated: only the date applies


def test_a_per_evidence_validity_overrides_the_policy():
    doc = ledger()
    doc["gates"]["PG-11"]["evidence"][0]["valid_days"] = 2
    assert any_has(fails_for(doc, today=date(2026, 10, 25)), "PG-11", "stale")


def test_future_dated_evidence_is_refused():
    doc = ledger()
    doc["gates"]["PG-11"]["evidence"][0]["date"] = "2026-12-01"
    assert any_has(fails_for(doc), "PG-11", "in the future")


# ------------------------------------------------------------------------------------------------------------------ PASS needs an artefact link, a producer and agreement with the tracker
def passing_gate(doc: dict, gid: str, **evkw) -> str:
    doc["gates"][gid]["state"] = "PASS"
    doc["gates"][gid]["evidence"] = [ev(**evkw)]
    return tracker_with(gid, "PASS")


def test_pass_without_any_artefact_is_refused():
    doc = ledger()
    tracker = passing_gate(doc, "PG-04")
    doc["gates"]["PG-04"]["evidence"] = []
    assert any_has(fails_for(doc, tracker=tracker), "PG-04", "PASS without an artefact link")


def test_an_empty_link_or_producer_is_refused_by_the_schema():
    doc = ledger()
    passing_gate(doc, "PG-04", link="", produced_by="")
    probs = R.schema_problems(doc)
    assert any("evidence link must be a non-empty string" in p for p in probs) and any("evidence produced_by must be a non-empty string" in p for p in probs)
    assert fails_for(doc)


@pytest.mark.parametrize("link", ["TBD", "docs/does/not/exist.md", "../../etc/passwd", "/etc/passwd", "ftp://example.org/x", "http://insecure.example/x", "none"])
def test_pass_with_an_invalid_or_placeholder_link_is_refused(link):
    doc = ledger()
    tracker = passing_gate(doc, "PG-04", link=link)
    assert any_has(fails_for(doc, tracker=tracker), "PG-04", "valid artefact link"), link


def test_pass_with_a_valid_human_artefact_and_a_matching_tracker_is_not_refused_for_evidence():
    doc = ledger()
    tracker = passing_gate(doc, "PG-04", link="https://example.org/artefact/1")
    assert not any_has(fails_for(doc, tracker=tracker), "PG-04", "artefact"), fails_for(doc, tracker=tracker)


@pytest.mark.parametrize("who", ["Claude", "automation", "TBD", "engineering team", "bot"])
def test_a_human_producer_must_be_a_named_human(who):
    doc = ledger()
    tracker = passing_gate(doc, "PG-04", produced_by=who)
    assert any_has(fails_for(doc, tracker=tracker), "PG-04", "not a named human")


def test_ledger_pass_without_matching_tracker_state_is_a_contradiction():
    doc = ledger()
    passing_gate(doc, "PG-04")
    assert any_has(fails_for(doc), "PG-04", "contradicts tracker state")        # the tracker still says NOT STARTED


def test_tracker_pass_without_ledger_pass_is_a_contradiction():
    doc = ledger()
    assert any_has(fails_for(doc, tracker=tracker_with("PG-04", "PASS")), "PG-04", "contradicts tracker state")


def test_gate_pass_is_refused_while_a_member_package_is_not_merged_or_has_open_layers():
    doc = ledger()
    tracker = passing_gate(doc, "PG-08", link="https://example.org/a")
    f = fails_for(doc, tracker=tracker)
    # 03D2 has now merged. Use the still-unmerged 01C member of PG-12 to
    # retain the independent non-integration refusal, plus the existing layer refusals.
    pending = ledger()
    pending_tracker = passing_gate(pending, "PG-12", link="https://example.org/a")
    assert any_has(fails_for(pending, tracker=pending_tracker), "PG-12", "01C", "not MERGED")
    assert any_has(f, "PG-08", "03A", "live_staging NOT RUN")
    assert any_has(f, "PG-08", "03C", "human_qualification OPEN")


def test_layer_positive_states_need_the_same_evidence_and_a_named_approver():
    doc = ledger()
    lay = doc["packages"]["02K"]["layers"]
    lay["live_staging"]["state"] = "PASS"
    assert any_has(fails_for(doc), "package 02K", "live_staging", "PASS without an artefact link")
    lay["live_staging"]["state"] = "NOT RUN"
    lay["human_qualification"].update(state="COMPLETE", evidence=[ev()], approver="TBD", approved_on="2026-10-21")
    assert any_has(fails_for(doc), "package 02K", "COMPLETE without a named human approver")
    lay["human_qualification"]["approver"] = "Dr Jane Reviewer"
    assert not any_has(fails_for(doc), "package 02K", "human_qualification")
    lay["gate_acceptance"].update(state="ACCEPTED", evidence=[])
    assert any_has(fails_for(doc), "package 02K", "gate_acceptance", "PASS without an artefact link")


def test_a_ledger_live_pass_cannot_contradict_wave_matrix_not_run():
    doc = ledger()
    doc["packages"]["05A"]["layers"]["live_staging"].update(state="PASS", evidence=[ev()])
    assert any_has(fails_for(doc), "05A", "contradicts wave_matrix.LAYERS")


def test_the_tool_never_writes_a_positive_state():
    doc = ledger()
    for pid in list(doc["packages"])[:3]:
        del doc["packages"][pid]
    R.sync_ledger(doc)
    for ent in doc["packages"].values():
        assert all(le["state"] not in R.POSITIVE.values() for le in ent["layers"].values())
    src = (ROOT / "scripts/production/release_evidence.py").read_text(encoding="utf-8")
    assert not re.search(r"\[[\"']state[\"']\]\s*=\s*[\"'](PASS|ACCEPTED|COMPLETE)[\"']", src)


# ------------------------------------------------------------------------------------------------------------------ language-gate rule parity with src/language_activation.py
LOCALE_SHA = "a0d01c8"


def lg_record(**over) -> dict:
    gates = {g: {"state": "PASS", "evidence": GOOD_LINK, "approver": "Maria Native-Reviewer", "approved_on": "2026-10-10", "release_sha": LOCALE_SHA} for g in LA.GATES}
    rec = {"release_sha": LOCALE_SHA, "gates": gates}
    rec.update(over)
    return rec


def gate_problems(rec: dict, today: date = TODAY, days: int = 90) -> list[str]:
    return R.language_problems("de", rec, ctx(today), days)


def test_a_fully_evidenced_language_record_has_no_gate_problems_and_matches_the_activation_validator():
    rec = lg_record()
    assert gate_problems(rec) == []
    status = LA.validate_locale_record("de", {**rec, "production_qualified": True, "offered_to_real_users": True}, today=TODAY)
    assert status.qualified and status.problems == ()


@pytest.mark.parametrize("gate_update,needle", [
    ({"evidence": ""}, "PASS without an evidence reference"),
    ({"evidence": "TBD"}, "PASS without an evidence reference"),
    ({"evidence": "see the thread"}, "PASS without an artefact link"),                  # stricter than the validator (never looser)
    ({"approver": ""}, "named human approver"),
    ({"approver": "TBD"}, "named human approver"),
    ({"approver": "Claude"}, "named human approver"),
    ({"approver": "GitHub Actions"}, "named human approver"),
    ({"approver": "native reviewer"}, "named human approver"),
    ({"approved_on": ""}, "valid approval date"),
    ({"approved_on": "10/10/2026"}, "valid approval date"),
    ({"approved_on": "2027-01-01"}, "in the future"),
    ({"release_sha": ""}, "release SHA"),
    ({"release_sha": "nothex"}, "release SHA"),
    ({"release_sha": "1111111"}, "stale (approved at a different release SHA)"),
    ({"approved_until": "2026-10-01"}, "stale (approved_until has passed)"),
    ({"approved_until": "never"}, "approved_until is not a valid date"),
    ({"approved_on": "2026-01-01"}, "stale (approval dated"),                              # beyond the stated 90-day validity
])
def test_each_language_pass_rule_is_enforced(gate_update, needle):
    rec = lg_record()
    rec["gates"]["LG-05"].update(gate_update)
    assert any(needle in p and "LG-05" in p for p in gate_problems(rec)), gate_problems(rec)


def test_every_gate_level_pass_problem_of_the_activation_validator_is_a_checker_failure():
    mutations = [{"evidence": ""}, {"approver": "TBD"}, {"approved_on": ""}, {"release_sha": ""}, {"release_sha": "1111111"}, {"approved_until": "2026-10-01"}, {"approved_on": "2027-01-01"}]
    for m in mutations:
        rec = lg_record()
        rec["gates"]["LG-09"].update(m)
        ours = " | ".join(gate_problems(rec))
        theirs = LA.validate_locale_record("de", {**rec, "production_qualified": False, "offered_to_real_users": False}, today=TODAY).problems
        for prob in theirs:
            mm = re.match(r"(LG-\d\d): (.*)", prob)
            if mm and not mm.group(2).startswith("state is ") and "claim" not in prob:
                assert prob in ours, (m, prob)


def test_a_non_pass_language_gate_is_not_a_violation_and_a_passed_one_never_escapes_the_rules():
    rec = lg_record()
    for g in rec["gates"].values():
        g.update(state="ENGINEERING DRAFT")
        for k in ("approver", "approved_on", "release_sha"):
            g.pop(k)
    assert gate_problems(rec) == []
    rec["gates"]["LG-03"]["state"] = "PASS"
    assert any("LG-03" in p for p in gate_problems(rec))


def test_ledger_language_pass_is_refused_when_language_readiness_does_not_pass_it_and_when_the_tracker_count_differs():
    doc = ledger()
    doc["language_gates"]["fr"] = {"release_sha": LOCALE_SHA, "gates": {**doc["language_gates"]["fr"]["gates"], "LG-05": {"state": "PASS", "evidence": GOOD_LINK, "approver": "Maria Native-Reviewer", "approved_on": "2026-10-10", "release_sha": LOCALE_SHA}}}
    f = fails_for(doc)
    assert any_has(f, "language fr LG-05", "contradicts language_readiness.json")
    assert any_has(f, "language fr", "tracker says 0 of 14", "ledger has 1")


def test_language_set_must_match_language_readiness():
    doc = ledger()
    del doc["language_gates"]["nl"]
    assert any_has(fails_for(doc), "language nl", "not in the ledger")
    doc = ledger()
    doc["language_gates"]["ru"] = copy.deepcopy(doc["language_gates"]["en"])
    assert any_has(fails_for(doc), "language ru", "not in language_readiness.json")


# ------------------------------------------------------------------------------------------------------------------ tracker and PACKAGE_STATUS contradiction detection
def test_ledger_state_that_differs_from_the_tracker_is_flagged():
    doc = ledger()
    doc["gates"]["PG-01"]["state"] = "IN PROGRESS"                                # tracker: BLOCKED
    assert any_has(fails_for(doc), "PG-01", "ledger state IN PROGRESS contradicts tracker state BLOCKED")


def test_ledger_pr_and_sha_that_differ_from_package_status_are_flagged():
    doc = ledger()
    next(p for p in doc["pull_requests"] if p["number"] == 215)["merge_sha"] = "1" * 40
    assert any_has(fails_for(doc), "package 02K", "merge SHA", "contradicts PACKAGE_STATUS")
    doc = ledger()
    next(p for p in doc["pull_requests"] if p["number"] == 215)["head_sha"] = "2" * 40
    assert any_has(fails_for(doc), "package 02K", "head SHA", "contradicts PACKAGE_STATUS")
    doc = ledger()
    doc["packages"]["02K"]["prs"] = [216]
    assert any_has(fails_for(doc), "package 02K", "PR #215")


def test_a_merged_package_without_a_ledger_entry_and_an_entry_for_an_unmerged_package_are_flagged():
    doc = ledger()
    del doc["packages"]["04B"]
    assert any_has(fails_for(doc), "package 04B", "no ledger entry")
    doc = ledger()
    doc["packages"]["00A"] = copy.deepcopy(doc["packages"]["02K"])
    assert any_has(fails_for(doc), "package 00A", "not record it as MERGED")
    doc["packages"]["08A"] = copy.deepcopy(doc["packages"]["02K"])
    assert any_has(fails_for(doc), "package 08A", "not in PACKAGE_STATUS")


def test_a_missing_acceptance_artefact_file_is_flagged():
    doc = ledger()
    doc["packages"]["02K"]["acceptance"]["artefacts"] = ["docs/production/execution/evidence/NOPE.md"]
    assert any_has(fails_for(doc), "package 02K", "acceptance artefact")


def test_tracker_parsers_read_the_committed_tracker():
    g = R.tracker_gates()
    assert list(g) == list(R.PG_GATES)
    assert g["PG-11"]["state"] == "PASS" and g["PG-01"]["state"] == "BLOCKED" and g["PG-08"]["packages"].startswith("03A")
    assert R.tracker_language_counts() == {c: 0 for c in ("en", "de", "es", "it", "pt", "fr", "nl")}


# ------------------------------------------------------------------------------------------------------------------ reconciliation check
def test_the_reconciliation_check_passes_and_a_failure_fails_the_run(monkeypatch):
    assert R.reconciliation_problems() == []
    monkeypatch.setattr(R, "reconciliation_problems", lambda: ["reconciliation: item X-1 missing"])
    lines: list[str] = []
    assert R.run_check(today=TODAY, out=lines.append) == 1
    assert any("reconciliation: item X-1 missing" in l for l in lines)


# ------------------------------------------------------------------------------------------------------------------ offline default and the opt-in fetch
def test_the_default_path_makes_no_network_call_and_never_touches_the_fetcher():
    def boom(*a, **k):
        raise AssertionError("fetcher called without --fetch")
    assert R.run_check(today=TODAY, out=lambda s: None, fetcher=boom) == 0     # the autouse fixture also forbids any socket
    doc = R.load_ledger()
    R.render_view(doc)
    R.render_matrix_inputs(doc)
    R.sync_ledger(copy.deepcopy(doc))
    src = (ROOT / "scripts/production/release_evidence.py").read_text(encoding="utf-8")
    head = src.split("def _get_json")[0]
    assert "import urllib" not in head and "import requests" not in head and "import socket" not in head    # imports of a client are lazy and confined to --fetch


def test_fetch_is_opt_in_on_the_cli_and_only_for_check():
    assert R.main(["generate", "--fetch"]) == 2
    assert R.main(["sync", "--fetch"]) == 2
    assert R.main(["check", "--today", "not-a-date"]) == 2


class FakeResp:
    def __init__(self, body: dict, headers: dict | None = None):
        self._b = json.dumps(body).encode()
        self.headers = headers or {}

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(url: str, code: int, headers: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "x", headers, io.BytesIO(b"{}"))


def test_fetch_reads_pr_and_check_runs_without_credentials_and_compares_with_the_ledger():
    seen = []
    doc = R.load_ledger()
    led = next(p for p in doc["pull_requests"] if p["number"] == 215)

    def opener(req, timeout=0):
        seen.append(req)
        if "/pulls/" in req.full_url:
            return FakeResp({"merged": True, "merge_commit_sha": led["merge_sha"], "head": {"sha": led["head_sha"]}})
        return FakeResp({"check_runs": [{"conclusion": "success"}] * 12})
    out = R.fetch_pr_status([215], opener=opener)
    assert out[215] == {"merged": True, "merge_sha": led["merge_sha"], "head_sha": led["head_sha"], "checks_total": 12, "checks_success": 12, "all_success": True}
    assert all("authorization" not in {k.lower() for k in r.headers} for r in seen) and all(r.full_url.startswith("https://api.github.com/repos/") for r in seen)
    assert R.compare_fetched(doc, out) == []
    bad = {215: {**out[215], "merge_sha": "9" * 40, "checks_success": 11, "all_success": False}}
    d = R.compare_fetched(doc, bad)
    assert any("merge SHA differs" in x for x in d) and any("11 of 12" in x for x in d)
    assert any("not merged" in x for x in R.compare_fetched(doc, {215: {**out[215], "merged": False}}))


def test_fetch_handles_the_rate_limit_by_waiting_briefly_or_stopping_with_a_partial_result():
    waits: list[float] = []
    calls = {"n": 0}

    def limited_once(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http_error(req.full_url, 403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1030"})
        if "/pulls/" in req.full_url:
            return FakeResp({"merged": True, "merge_commit_sha": "a" * 40, "head": {"sha": "b" * 40}})
        return FakeResp({"check_runs": [{"conclusion": "success"}]})
    out = R.fetch_pr_status([215], opener=limited_once, sleep=waits.append, now=lambda: 1000.0, max_wait=60)
    assert waits == [31.0] and out[215]["merged"] is True                         # reset in 30 s: waited 30 + 1 then continued

    def limited_long(req, timeout=0):
        raise http_error(req.full_url, 429, {"Retry-After": "3600"})
    waits.clear()
    out = R.fetch_pr_status([215, 217], opener=limited_long, sleep=waits.append, now=lambda: 0.0, max_wait=60)
    assert waits == [] and out == {215: {"rate_limited": True, "reset_epoch": None}}      # too long: stop, partial result, no sleep, no second PR attempted
    d = R.compare_fetched(R.load_ledger(), out)
    assert any("rate limit" in x for x in d)


def test_a_non_rate_limit_http_error_is_raised_not_swallowed():
    def nf(req, timeout=0):
        raise http_error(req.full_url, 404, {})
    with pytest.raises(urllib.error.HTTPError):
        R.fetch_pr_status([215], opener=nf)


def test_check_with_fetch_reports_github_discrepancies_as_failures():
    def fetcher(nums):
        return {n: {"merged": True, "merge_sha": "", "head_sha": "", "checks_total": 12, "checks_success": 12, "all_success": True} for n in nums} | {215: {"merged": False, "merge_sha": "", "head_sha": "", "checks_total": 0, "checks_success": 0, "all_success": False}}
    lines: list[str] = []
    assert R.run_check(today=TODAY, fetch=True, fetcher=fetcher, out=lines.append) == 1
    assert any("fetch: PR #215" in l for l in lines)


# ------------------------------------------------------------------------------------------------------------------ CLI wiring
def test_cli_check_and_generate_write_only_the_generated_files(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "VIEW", tmp_path / "view.md")
    monkeypatch.setattr(R, "MATRIX_INPUTS", tmp_path / "inputs.json")
    # the repo-relative printing in generate needs the files under ROOT; point the tmp files through a root-relative shim
    monkeypatch.setattr(R, "ROOT", tmp_path)
    assert R.main(["generate"]) == 0
    assert (tmp_path / "view.md").read_text(encoding="utf-8") == R.render_view(R.load_ledger())
    assert json.loads((tmp_path / "inputs.json").read_text(encoding="utf-8"))["as_of"] == TODAY.isoformat()
