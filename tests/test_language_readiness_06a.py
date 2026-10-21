"""06A (REQ-LANG-11, REQ-LANG-13, LG-01, LG-13): per-language readiness records and claim discipline.

Deterministic, 0 paid/live calls. Every active locale has a record for every gate LG-01..LG-14; nothing is PASS without an
evidence reference; no language is production-qualified while a gate is unpassed; and no document or page claims otherwise.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from src.locales import ACTIVE_CANDIDATE_LOCALES

ROOT = Path(__file__).resolve().parent.parent
READINESS = ROOT / "docs/production/execution/language_readiness.json"
GATES = tuple(f"LG-{i:02d}" for i in range(1, 15))
STATES = {"NOT STARTED", "NOT RUN", "ENGINEERING DRAFT", "PASS"}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(READINESS.read_text(encoding="utf-8"))


def test_every_active_locale_has_all_fourteen_gate_records(data):
    assert set(data["languages"]) == set(ACTIVE_CANDIDATE_LOCALES)  # no record for an inactive locale, none missing
    for code in ACTIVE_CANDIDATE_LOCALES:
        gates = data["languages"][code]["gates"]
        assert tuple(gates) == GATES, code
        for g in GATES:
            assert gates[g]["state"] in STATES, (code, g)


def test_nothing_is_pass_without_evidence_and_evidence_paths_exist(data):
    for code, rec in data["languages"].items():
        for g, e in rec["gates"].items():
            if e["state"] == "PASS":
                assert e["evidence"].strip(), (code, g)
                first = e["evidence"].split(";")[0].split(" (")[0].split(":")[0].strip()
                for token in (t.strip() for t in e["evidence"].replace(";", ",").split(",")):
                    path = token.split(" ")[0].split(":")[0]
                    if path.startswith(("docs/", "scripts/", "tests/", "frontend/")):
                        assert (ROOT / path).exists(), (code, g, path)
                assert first
            else:
                assert e["state"] != "PASS"


def test_no_language_is_production_qualified_while_any_gate_is_unpassed(data):
    for code, rec in data["languages"].items():
        unpassed = [g for g, e in rec["gates"].items() if e["state"] != "PASS"]
        assert unpassed, f"{code}: every gate PASS needs a deliberate, evidenced change to this test and record"
        assert rec["production_qualified"] is False and rec["offered_to_real_users"] is False


def test_the_unevidenced_gates_stay_unstarted_not_engineering_draft(data):
    # LG-05/06/08/10/11 need human or live evidence that does not exist; they must never read PASS or ENGINEERING DRAFT.
    for rec in data["languages"].values():
        for g in ("LG-05", "LG-06", "LG-08", "LG-10", "LG-11"):
            assert rec["gates"][g]["state"] == "NOT STARTED"


def test_russian_is_recorded_as_excluded_not_as_a_language_with_gates(data):
    assert "ru" not in data["languages"] and "ru" in data["excluded"]


def test_readiness_validator_flags_a_pass_without_evidence_and_a_premature_qualification(data):
    inv = _load("eval_locale_inventory")
    assert inv.readiness_problems(data) == []
    bad = json.loads(json.dumps(data))
    bad["languages"]["de"]["gates"]["LG-05"] = {"state": "PASS", "evidence": ""}
    assert any("PASS without evidence" in p for p in inv.readiness_problems(bad))
    bad = json.loads(json.dumps(data))
    bad["languages"]["fr"]["production_qualified"] = True
    assert any("production_qualified" in p for p in inv.readiness_problems(bad))
    bad = json.loads(json.dumps(data))
    del bad["languages"]["nl"]["gates"]["LG-09"]
    assert any("missing gate record" in p for p in inv.readiness_problems(bad))


def test_claim_discipline_detector_catches_early_claims_and_allows_negations():
    m = _load("eval_marketing_product_trust")
    assert m.language_qualification_claims("German is production-qualified.")
    assert m.language_qualification_claims("All seven languages are fully supported.")
    assert m.language_qualification_claims("Our interface is natively reviewed in Dutch.")
    assert not m.language_qualification_claims("No language is production-qualified until every gate passes.")
    assert not m.language_qualification_claims("A language is production-qualified only when LG-01 to LG-14 pass.")


def test_no_public_page_or_catalogue_claims_a_language_is_qualified():
    m = _load("eval_marketing_product_trust")
    ok, detail = m.run()["no_language_qualification_claim"]
    assert ok, detail


def test_no_production_document_claims_a_language_is_qualified_early():
    m = _load("eval_marketing_product_trust")
    offenders = {}
    for p in list((ROOT / "docs/production").rglob("*.md")) + [ROOT / "README.md"]:
        found = m.language_qualification_claims(p.read_text(encoding="utf-8"))
        if found:
            offenders[str(p.relative_to(ROOT))] = found
    assert offenders == {}


def test_committed_audit_table_is_current_and_labels_every_language_unqualified():
    audit = (ROOT / "docs/production/execution/evidence/06A_LOCALE_AUDIT.md").read_text(encoding="utf-8")
    assert "No language is production-qualified" in audit
    for code in ACTIVE_CANDIDATE_LOCALES:
        assert f"| {code} |" in audit
    assert "EXCLUDED" in audit and "ru" in audit
    if shutil.which("node") is None:
        pytest.skip("node unavailable: staleness check needs the catalogue helper")
    inv = _load("eval_locale_inventory")
    assert inv.build_markdown() == audit, "stale: run `python scripts/eval_locale_inventory.py --write`"
