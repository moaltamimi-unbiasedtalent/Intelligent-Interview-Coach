"""P10C-F2B: UK Package 2 preparation. No UK file is acquired (Package 2 is not authorised): these tests cover the unacquired-manifest gate, the ASHE suppression record and its guard, the weekly-pay
integrity of the existing adapter and the read-only UK V1 baseline. Synthetic data and throwaway SQLite databases only."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.knowledge_foundation import ashe_suppression as S
from src.knowledge_foundation.compensation import adapters as AD
from src.knowledge_foundation.compensation.record import CompensationRecordV2
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
from src.persistence import init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
F2B = ROOT / "docs/capstone/p10/p10c_f2b"
_spec = importlib.util.spec_from_file_location("p10c_f2a_gate_f2b", ROOT / "scripts/p10c_f2a_acquisition_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# ------------------------------------------------------------------------------------------------------------------------------------------ package gate
def test_package_2_is_unacquired_unauthorised_and_blocked():
    errs, allowed, blockers = gate.evaluate(F2B)
    assert errs == [] and allowed is False
    assert any(b.startswith("B:") for b in blockers) and any(b.startswith("J:") for b in blockers)
    m = json.loads((F2B / "acquisition_manifest.json").read_text())
    assert m["package_authorization"]["status"] == "APPROVAL_PENDING" and m["package_authorization"]["reference"] is None and m["owner_authorization_ref"] is None
    assert all(f["state"] == "NOT_ACQUIRED" and f["sha256"] is None and f["acquired_at"] is None and f["storage_location"] is None for f in m["files"])
    assert all(f["ingestion_state"] == "NOT_INGESTED" and f["runtime_approval"] == "NOT_APPROVED" and f["qualification_status"] == "NOT_QUALIFIED" for f in m["files"])
    assert {f["original_filename"] for f in m["files"]} == set(m["authorised_files"]) and len(m["files"]) == 3
    assert all(f["official_url"].startswith("https://www.ons.gov.uk/") for f in m["files"])


def test_an_acquired_file_in_an_unauthorised_package_is_refused(tmp_path):
    m = json.loads((F2B / "acquisition_manifest.json").read_text())
    m["files"][0].update(state="ACQUIRED", sha256="a" * 64, acquired_at="2026-10-18T00:00:00Z", size_bytes=1, http_status=200, storage_location="/tmp/x")
    (tmp_path / "acquisition_manifest.json").write_text(json.dumps(m))
    (tmp_path / "source_verification.json").write_text((F2B / "source_verification.json").read_text())
    errs, _, _ = gate.evaluate(tmp_path)
    assert any("authorization is not APPROVED" in e for e in errs)


def test_the_us_package_gate_is_unchanged():
    errs, allowed, _ = gate.evaluate()
    assert errs == [] and allowed is True


def test_unverified_facts_are_marked_and_the_edition_is_not_forced_to_soc_2020():
    v = json.loads((F2B / "source_verification.json").read_text())
    pre = {p["id"]: p for p in v["preconditions"]}
    assert pre["D"]["status"] == "PARTIAL" and pre["J"]["status"] == "NOT_MET" and pre["K"]["status"] == "PARTIAL"
    m = json.loads((F2B / "acquisition_manifest.json").read_text())
    t14 = next(f for f in m["files"] if f["file_id"] == "uk_ashe_table14_2025_provisional")
    assert t14["taxonomy_edition"] == "NOT_CONFIRMED"
    assert any(f["status"] == "INFERENCE" for f in v["verified_facts"])                  # the V1 structure hint is labelled an inference, never a verification


# --------------------------------------------------------------------------------------------------------------------------------------- suppression record
def test_the_suppression_record_matches_the_ons_notice():
    r = S.rules()
    assert r["correction_date"] == "2025-12-19" and r["occupation_codes"] == ["33", "331", "3312"] and r["tables"] == ["2", "3", "14", "15", "20"]
    assert set(r["geographies"]) == {"UK", "London", "South East", "East"} and r["pay_periods_affected"] == ["annual"] and "weekly" in r["pay_periods_not_affected_by_this_notice"]
    assert r["verification_status"] == "PARTIALLY_VERIFIED" and r["unverified"]


@pytest.mark.parametrize("code,period,geo,table,expected", [("3312", "annual", "UK", None, True), ("3312", "annual", None, "14", True), ("33", "annual", "London", "2", True), ("331", "annual", "South East", "15", True),
                                                            ("3312", "weekly", "UK", "14", False), ("3312", "hourly", "UK", None, False), ("3311", "annual", "UK", None, False),
                                                            ("3312", "annual", "North West", None, False), ("3312", "annual", "UK", "12", False), ("3312", "annual", "south-east", None, True)])
def test_suppression_scope(code, period, geo, table, expected):
    assert S.is_suppressed(code, pay_period=period, geography=geo, table=table) is expected


def _rec(code, period="annual", region=None, status="reported", **prov):
    return CompensationRecordV2(taxonomy_scheme="uk_soc", taxonomy_edition="2020", native_code=code, occupation_level="detailed" if len(code) == 4 else "broad", country="GB", region=region,
                                geography_level="regional" if region else "national", currency="GBP", pay_period=period, pay_basis="gross", measure="median", value_status=status,
                                value=Decimal("40000") if status == "reported" else None, source_ref="ons_ashe", source_edition="2025 provisional", reference_year=2025, provenance=prov)


def test_the_guard_refuses_to_restore_suppressed_measurements_and_allows_the_rest():
    assert S.violates(_rec("3312")) and S.violates(_rec("33", region="London")) and S.violates(_rec("331", table="14"))
    assert not S.violates(_rec("3312", period="weekly")) and not S.violates(_rec("3311")) and not S.violates(_rec("3312", status="suppressed"))
    assert not S.violates(_rec("3312", table="12"))
    with pytest.raises(S.SuppressionViolation):
        S.assert_respected([_rec("3311"), _rec("3312")])
    S.assert_respected([_rec("3311"), _rec("3312", status="suppressed"), _rec("3312", period="weekly")])


@pytest.fixture()
def uk_store(tmp_path):
    e = make_engine(f"sqlite:///{tmp_path / 'uk.db'}")
    init_db(e)
    sf = make_session_factory(e)
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("uk_soc", "2020", status="current", acquisition_status="available_locally", code_pattern="[0-9]{1,4}")
    reg.register("ons_ashe", origin="authorised_manual", publisher="Synthetic official publisher", dataset_name="Synthetic ASHE-like dataset", dataset_version="2025 provisional",
                 precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    reg.transition("ons_ashe", "licensing_pending")
    reg.set_licence("ons_ashe", licence_id="syn", licence_status="verified")
    reg.transition("ons_ashe", "licensing_verified")
    reg.transition("ons_ashe", "approved_for_ingestion")
    for code in ("3311", "3312", "33"):
        g.add_occupation(f"syn uk {code}", [("uk_soc", "2020", code)])
    return CompensationStoreV2(sf, reg, g)


def test_the_store_rejects_a_restored_suppressed_cell_but_keeps_weekly_pay(uk_store):
    rows = [_rec("3312"), _rec("3312", period="weekly"), _rec("3311"), _rec("33", region="London")]
    rep = uk_store.import_records(rows, source_ref="ons_ashe", source_edition="2025 provisional", mode="production")
    assert rep.rejections == {"publisher_suppressed_measurement_must_stay_missing": 2} and rep.added == 2
    keys = {(r["native_code"], r["pay_period"]) for r in uk_store.records_for([1, 2, 3], "GB")}
    assert keys == {("3312", "weekly"), ("3311", "annual")}                             # nothing in the notice's scope was stored as annual pay


# ------------------------------------------------------------------------------------------------------------------------------------------ weekly integrity
def test_weekly_pay_stays_weekly_and_is_never_annualised():
    rows = [{"code": "2136", "median": "1100.5"}, {"code": "9", "median": "x"}]
    recs, rej = AD.ashe_records(rows, source_edition="2025 provisional", reference_year=2025, uk_soc_edition="2020")
    assert {r.pay_period for r in recs} == {"weekly"} and recs[0].value == Decimal("1100.5") and recs[0].currency == "GBP" and recs[0].pay_basis == "gross"
    assert all(r.value is None for r in recs if r.value_status != "reported") and not any(r.pay_period == "annual" for r in recs)
    assert recs[1].value_status == "suppressed" and recs[1].value is None


# ------------------------------------------------------------------------------------------------------------------------------------------- V1 baseline
def test_the_committed_uk_v1_baseline_is_metadata_only():
    b = json.loads((F2B / "uk_v1_baseline.json").read_text())
    assert b["records"] == 527 and b["rows_without_occupation_code"] == 1 and b["code_length_distribution"] == {"1": 9, "2": 26, "3": 103, "4": 388}
    assert b["pay_periods"] == ["weekly"] and b["statistics"] == ["median"] and b["store_modified_by_this_run"] is False
    assert b["rows_with_title"] == 0 and not any(k in b for k in ("values", "titles", "titles_sample", "pay_values"))          # counts only: no title and no pay value is carried


@pytest.mark.skipif(not (ROOT / "data/knowledge/compensation.db").exists(), reason="local V1 store not present in this environment")
def test_the_baseline_reproduces_from_the_local_v1_store():
    spec = importlib.util.spec_from_file_location("p10c_f2b_v1_baseline", ROOT / "scripts/p10c_f2b_v1_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    db = ROOT / "data/knowledge/compensation.db"
    before = (db.stat().st_size, db.stat().st_mtime_ns)
    live = json.loads(json.dumps(mod.baseline(db)))
    committed = json.loads((F2B / "uk_v1_baseline.json").read_text())
    assert {k: v for k, v in live.items() if k != "store_modified_by_this_run"} == {k: v for k, v in committed.items() if k != "store_modified_by_this_run"}
    assert before == (db.stat().st_size, db.stat().st_mtime_ns)
