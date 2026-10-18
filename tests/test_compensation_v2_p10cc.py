"""P10C-C: Compensation V2 foundation (GKB-5 model, GKB-6 EU, GKB-7 US). FULLY OFFLINE: throwaway SQLite databases and the committed SYNTHETIC fixture corpus (invented sources,
occupations and amounts in synthetic-fixture sources that can never be approved). Nothing here is official data, a real salary or an approval, and nothing is imported by a
candidate-facing path or changes a gate."""

from __future__ import annotations

import ast
import json
import sqlite3
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation.compensation import adapters as AD
from src.knowledge_foundation.compensation.fixtures import CORPUS_PATH, evaluate_cases, load_corpus, load_world
from src.knowledge_foundation.compensation.money import MoneyError, from_units, scale_of, to_units, validate_currency
from src.knowledge_foundation.compensation.policy import POLICY_PATH, PolicyError, PrecedencePolicy, classify_evidence, normalize_country
from src.knowledge_foundation.compensation.record import CompensationRecordV2, record_key_for
from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver, FxProvider, PppProvider
from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved, CompensationStoreV2, build_citation, evidence_status
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.occupation_resolver import MultilingualRequest
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
from src.persistence import CompensationImportBatch, CompensationRecordV2Row, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'c.db'}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def world(sf):
    return load_world(sf)


@pytest.fixture()
def mech(sf):
    """A mechanism sandbox: taxonomies, a graph node per scheme, a synthetic-fixture source and a REAL-origin source (licensing pending). Nothing here is data."""
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("soc", "2018", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{2}-[0-9]{4}")
    reg.register("fx", origin="synthetic_fixture", publisher="Synthetic publisher", dataset_name="Synthetic dataset", precedence_category="national_official_occupation_statistics")
    reg.register("off", origin="official_local", publisher="Synthetic official publisher", dataset_name="Synthetic official dataset", dataset_version="E1",
                 precedence_category="national_official_occupation_statistics", validation_status="unvalidated")
    n = g.add_occupation("Synthetic occupation [synthetic fixture]", [("soc", "2018", "99-0100"), ("isco", "08", "9100")])["occupation_key"]
    return NS(sf=sf, tax=tax, reg=reg, g=g, key=n, store=CompensationStoreV2(sf, reg, g))


def rec(**kw) -> dict:
    base = dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code="99-0100", occupation_level="detailed", country="US", geography_level="national", currency="USD",
                pay_period="annual", pay_basis="gross", measure="median", value="60000", source_ref="fx", source_edition="E1", reference_year=2025)
    base.update(kw)
    return base


def approve(reg: SourceRegistry, sid: str, *, runtime: bool = False) -> None:
    reg.set_licence(sid, licence_id="Synthetic licence", licence_status="verified", attribution_required="yes", redistribution="yes")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion") + (("approved_for_runtime_use",) if runtime else ()):
        reg.transition(sid, step)


# ====================================================================================================================================== money
def test_money_is_exact_and_never_a_float():
    assert to_units("57390.50", 2) == 5739050 and from_units(5739050, 2) == Decimal("57390.50") and scale_of("57390.0") == 0 and scale_of("641.10") == 1 and scale_of(Decimal("0.125")) == 3
    for bad in (0.5, 1.0, True, "abc", "NaN", "Infinity", None, "1,000"):
        with pytest.raises(MoneyError):
            to_units(bad, 2)
    for bad in (0, "0", "-5", Decimal("-0.01")):
        with pytest.raises(MoneyError):
            to_units(bad, 2)                                                         # zero and negative are never a reported amount
    with pytest.raises(MoneyError):
        to_units("1.234", 2)                                                         # never rounded
    with pytest.raises(MoneyError):
        scale_of("1.1234567")
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3") and from_units(None, 2) is None


def test_currency_must_be_an_iso_4217_code():
    for ok in ("USD", "GBP", "EUR", "MXN", "BRL", "CAD", "CHF"):
        assert validate_currency(ok) == ok
    for bad in ("usd", "US", "USDD", "XXX", "ZZZ", "", None, "€"):
        with pytest.raises(MoneyError):
            validate_currency(bad)


def test_amounts_are_stored_as_exact_integers_not_floating_point(mech):
    mech.store.import_records([rec(value="60000.55", lower_value="40000.10", upper_value="90000.99")], source_ref="fx", source_edition="E1", mode="fixture")
    with mech.sf() as s:
        row = s.execute(text("select typeof(value_units), value_units, amount_scale, typeof(lower_units) from compensation_v2_records")).one()
    assert row == ("integer", 6000055, 2, "integer")
    from src.persistence import GraphOccupation
    with mech.sf() as s:
        oid = s.scalar(select(GraphOccupation.id))
    r = mech.store.records_for([oid], "US")[0]
    assert r["value"] == Decimal("60000.55") and isinstance(r["value"], Decimal) and r["lower_value"] == Decimal("40000.10")


# ====================================================================================================================================== record model
def test_the_record_model_forbids_zero_invented_and_inconsistent_values():
    base = dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code="99-0100", country="us", currency="USD", pay_period="annual", source_ref="fx", source_edition="E1", reference_year=2025)
    ok = CompensationRecordV2(value=Decimal("1"), **base)
    assert ok.country == "US" and ok.pay_basis == "unknown" and ok.measure == "unknown"            # unknown is the default, never assumed
    for bad in ({"value": None}, {"value": Decimal("0")}, {"value": Decimal("-1")}, {"value": Decimal("5"), "lower_value": Decimal("6"), "upper_value": Decimal("5")},
                {"value": Decimal("5"), "lower_value": Decimal("1")}, {"value": Decimal("5"), "measure": "percentile"}, {"value": Decimal("5"), "percentile": 10},
                {"value": Decimal("5"), "pay_period": "fortnightly"}, {"value": Decimal("5"), "currency": "usd"}, {"value": Decimal("5"), "reference_year": 1800},
                {"value": Decimal("5"), "unexpected": 1}, {"value": Decimal("5"), "source_edition": " "}):
        with pytest.raises(Exception):
            CompensationRecordV2(**{**base, **bad})
    assert CompensationRecordV2(value_status="suppressed", **base).value is None
    with pytest.raises(Exception):
        CompensationRecordV2(value_status="suppressed", value=Decimal("5"), **base)


def test_original_period_currency_and_basis_travel_with_the_value():
    r = CompensationRecordV2(taxonomy_scheme="uk_soc", taxonomy_edition="2020", native_code="1234", country="GB", currency="GBP", pay_period="weekly", pay_basis="gross", measure="median",
                             value=Decimal("700.50"), source_ref="fx", source_edition="E1", reference_year=2025)
    assert (r.pay_period, r.currency, r.pay_basis, r.measure, r.value, r.scale()) == ("weekly", "GBP", "gross", "median", Decimal("700.50"), 1)


def test_comparability_requires_everything_and_unknowns_are_comparable_with_nothing():
    mk = lambda **kw: CompensationRecordV2(**{**dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code="99-0100", country="US", currency="USD", pay_period="annual", pay_basis="gross",
                                                       measure="median", value=Decimal("5"), source_ref="fx", source_edition="E1", reference_year=2025), **kw})
    a = mk()
    assert a.comparability_key() == mk(source_ref="other").comparability_key()
    for diff in ({"pay_period": "monthly"}, {"currency": "EUR"}, {"pay_basis": "net"}, {"measure": "mean"}, {"reference_year": 2024}, {"region": "X", "geography_level": "regional"}):
        assert a.comparability_key() != mk(**diff).comparability_key(), diff
    assert mk(pay_basis="unknown").comparability_key()[5] is None and mk(measure="unknown").comparability_key()[6] is None


def test_record_keys_are_deterministic_and_value_independent():
    base = dict(taxonomy_scheme="soc", taxonomy_edition="2018", native_code="99-0100", country="US", currency="USD", pay_period="annual", source_ref="fx", source_edition="E1", reference_year=2025,
                measure="median")
    a, b = CompensationRecordV2(value=Decimal("1"), **base), CompensationRecordV2(value=Decimal("2"), **base)
    assert record_key_for(a, 7) == record_key_for(b, 7) != record_key_for(a, 8) and record_key_for(a, 7).startswith("cv2_")


# ====================================================================================================================================== database constraints
def _row(**kw):
    base = dict(record_key="k", occupation_id=1, taxonomy_id=1, native_code="x", country="US", currency="USD", pay_period="annual", pay_basis="gross", measure="median", percentile=0,
                value_status="reported", amount_scale=0, value_units=1, source_ref="s", source_edition="e", reference_year=2025, evidence_class="C1", precedence_category="x", provenance={})
    base.update(kw)
    return CompensationRecordV2Row(**base)


def test_the_database_refuses_invented_zero_and_inconsistent_rows_independently(mech, sf):
    mech.store.import_records([rec()], source_ref="fx", source_edition="E1", mode="fixture")
    with sf() as s:
        oid, tid = s.execute(text("select occupation_id, taxonomy_id from compensation_v2_records")).one()
    cases = [dict(value_units=0), dict(value_units=-5), dict(value_units=None), dict(value_status="suppressed", value_units=5), dict(lower_units=5, upper_units=3), dict(lower_units=5),
             dict(measure="percentile", percentile=0), dict(percentile=50), dict(currency="US"), dict(evidence_class="C4"), dict(pay_period="fortnightly"), dict(source_ref=""),
             dict(source_edition=""), dict(amount_scale=7), dict(reference_year=1800), dict(measure="bogus"), dict(pay_basis="bogus"), dict(qualification_status="bogus")]
    for i, bad in enumerate(cases):
        with sf() as s:
            s.add(_row(record_key=f"bad{i}", occupation_id=oid, taxonomy_id=tid, native_code=f"n{i}", **bad))
            with pytest.raises(IntegrityError):
                s.commit()


def test_the_database_enforces_the_natural_key_and_restricts_deleting_a_linked_occupation(mech, sf):
    from src.persistence import GraphOccupation
    mech.store.import_records([rec()], source_ref="fx", source_edition="E1", mode="fixture")
    with sf() as s:
        oid, tid, key = s.execute(text("select occupation_id, taxonomy_id, record_key from compensation_v2_records")).one()
    with sf() as s:
        s.add(_row(record_key="other-key", occupation_id=oid, taxonomy_id=tid, native_code="99-0100", source_ref="fx", source_edition="E1", reference_year=2025, value_units=5, evidence_class="C1",
                   precedence_category="national_official_occupation_statistics"))
        with pytest.raises(IntegrityError):
            s.commit()
    with sf() as s:
        s.execute(text("PRAGMA foreign_keys=ON"))
        occ = s.get(GraphOccupation, oid)
        s.delete(occ)
        with pytest.raises(IntegrityError):
            s.commit()
    assert key.startswith("cv2_")


# ====================================================================================================================================== policy
def test_the_precedence_policy_is_the_recovered_six_levels_and_has_no_country_overrides():
    p = PrecedencePolicy.load()
    assert [t["category"] for t in p.tiers] == ["national_official_occupation_statistics", "national_public_employment_service", "eurostat_harmonised", "cedefop_intelligence",
                                                  "authorized_secondary", "insufficient_evidence"] and p.version == "p10c-e/1"
    assert p.rank("eurostat_harmonised") == 3 and p.rank("bogus") is None and p.classes_for("eurostat_harmonised") == ("C3",) and p.classes_for("authorized_secondary") == ()
    raw = json.loads(POLICY_PATH.read_text())
    assert raw["country_overrides"].startswith("none") and not any(k.upper() in {"DE", "US", "UK", "GB", "EU"} for k in raw)
    assert p.raw["comparison_modes"] == {"nominal": "supported", "fx_converted": "not_configured", "ppp_adjusted": "not_configured"}


def test_the_policy_validator_rejects_malformed_or_country_specific_policies(tmp_path):
    raw = json.loads(POLICY_PATH.read_text())

    def write(mod):
        d = json.loads(json.dumps(raw))
        mod(d)
        p = tmp_path / "p.json"
        p.write_text(json.dumps(d))
        return p
    for mod in (lambda d: d["tiers"].pop(0), lambda d: d["tiers"][0].__setitem__("rank", 5), lambda d: d["tiers"][0].__setitem__("category", "bogus"),
                lambda d: d["tiers"][0].__setitem__("evidence_classes", ["C9"]), lambda d: d["tiers"][-1].__setitem__("evidence_classes", ["C3"]),
                lambda d: d.__setitem__("country_overrides", {"DE": ["x"]}), lambda d: d.__setitem__("DE", {"x": 1}), lambda d: d.__setitem__("overrides", {})):
        with pytest.raises(PolicyError):
            PrecedencePolicy.load(write(mod))


@pytest.mark.parametrize("cat,level,geo,expected", [
    ("national_official_occupation_statistics", "detailed", "national", "C1"), ("national_official_occupation_statistics", "broad", "national", "C2"),
    ("national_public_employment_service", "detailed", "national", "C1"), ("national_public_employment_service", "broad", "national", "C2"),
    ("national_official_occupation_statistics", "detailed", "regional", "C1"), ("national_public_employment_service", "broad", "regional", "C2"), ("national_official_occupation_statistics", "unknown", "national", None),
    ("eurostat_harmonised", "broad", "national", "C3"), ("eurostat_harmonised", "detailed", "eu_aggregate", "C3"), ("eurostat_harmonised", "unknown", "national", None),
    ("cedefop_intelligence", "detailed", "national", None), ("authorized_secondary", "detailed", "national", None), ("insufficient_evidence", "detailed", "national", None), ("unknown", "detailed", "national", None),
])
def test_evidence_classes_reflect_actual_source_specificity(cat, level, geo, expected):
    assert classify_evidence(PrecedencePolicy.load(), cat, level, geo) == expected


def test_country_labels_are_explicit_codes_never_derived_from_language():
    assert normalize_country("uk") == "GB" and normalize_country("EL") == "GR" and normalize_country(" de ") == "DE" and normalize_country(None) is None and normalize_country("  ") is None
    assert "language" not in normalize_country.__code__.co_varnames and "locale" not in normalize_country.__code__.co_varnames


# ====================================================================================================================================== importer: governance
def test_the_importer_refuses_unregistered_pending_fixture_and_unattributed_sources(mech):
    s = mech.store
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec()], source_ref="nope", source_edition="E1", mode="fixture")
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec(source_ref="off")], source_ref="off", source_edition="E1", mode="production")             # licensing pending
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec()], source_ref="fx", source_edition="E1", mode="production")                                 # a synthetic source can never be imported as production
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec(source_ref="off")], source_ref="off", source_edition="E1", mode="fixture")                    # fixture mode needs a synthetic source
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec()], source_ref="fx", source_edition="E1", mode="bogus")
    assert s.counts() == {"records": 0, "batches": 0}
    mech.reg.register("noattr", origin="official_local", precedence_category="national_official_occupation_statistics")
    approve(mech.reg, "noattr")
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec(source_ref="noattr")], source_ref="noattr", source_edition="E1", mode="production")          # attribution incomplete
    mech.reg.register("noprec", origin="official_local", publisher="P", dataset_name="D")
    approve(mech.reg, "noprec")
    with pytest.raises(CompensationSourceNotApproved):
        s.import_records([rec(source_ref="noprec")], source_ref="noprec", source_edition="E1", mode="production")


def test_a_production_import_needs_approval_a_known_edition_and_a_known_taxonomy_edition(mech):
    s = mech.store
    approve(mech.reg, "off")
    for ed in ("unknown", "current release", ""):
        with pytest.raises(CompensationSourceNotApproved):
            s.import_records([rec(source_ref="off", source_edition=ed or " ")], source_ref="off", source_edition=ed, mode="production")
    rep = s.import_records([rec(source_ref="off", taxonomy_edition="unknown")], source_ref="off", source_edition="E1", mode="production")
    assert rep.added == 0 and rep.rejections == {"taxonomy_edition_unknown": 1}
    ok = s.import_records([rec(source_ref="off")], source_ref="off", source_edition="E1", mode="production", transformation="mechanism test", actor_user_id=9)
    assert ok.added == 1 and ok.mode == "production"
    with mech.sf() as sess:
        b = sess.scalar(select(CompensationImportBatch).where(CompensationImportBatch.source_ref == "off", CompensationImportBatch.records_added == 1))
        assert b.mode == "production" and b.actor_user_id == 9 and b.transformation == "mechanism test"


def test_rows_are_rejected_with_reason_codes_and_nothing_is_repaired(mech):
    rows = [rec(), rec(native_code="99-9999"), rec(currency="usd"), rec(value="0"), rec(source_ref="other"), rec(source_edition="E2"), rec(taxonomy_edition="2099"),
            rec(region="X"), rec(geography_level="regional"), rec(geography_level="regional", region="Y", native_code="99-0100", country="CA"),
            rec(occupation_level="unknown", native_code="99-0100", country="MX"), {"currency": "USD"}, rec(pay_period="bogus")]
    rep = mech.store.import_records(rows, source_ref="fx", source_edition="E1", mode="fixture")
    assert rep.rows == 13 and rep.added == 2 and rep.rejected == 11
    assert rep.rejections["occupation_not_in_graph"] == 1 and rep.rejections["source_mismatch"] == 2 and rep.rejections["taxonomy_edition_not_registered"] == 1
    assert rep.rejections["region_with_national_level"] == 1 and rep.rejections["regional_level_without_region"] == 1 and rep.rejections["evidence_class_undeterminable"] == 1
    assert sum(v for k, v in rep.rejections.items() if k.startswith("schema_invalid")) == 4 and any(k.startswith("schema_invalid:currency") for k in rep.rejections)
    assert mech.store.counts()["records"] == 2                                                                                          # the valid national row and the labelled regional row
    with mech.sf() as s:
        summary = s.scalar(select(CompensationImportBatch.rejection_summary))
    assert all(isinstance(v, int) for v in summary.values()) and "99-9999" not in json.dumps(summary)                                  # reason codes and counts only


def test_secondary_cedefop_and_regional_evidence_cannot_be_classed_and_are_rejected(mech):
    for sid, cat in (("sec", "authorized_secondary"), ("ced", "cedefop_intelligence"), ("insuff", "insufficient_evidence")):
        mech.reg.register(sid, origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category=cat)
        rep = mech.store.import_records([rec(source_ref=sid)], source_ref=sid, source_edition="E1", mode="fixture")
        assert rep.added == 0 and rep.rejections == {"evidence_class_undeterminable": 1}, sid


def test_an_import_is_idempotent_non_destructive_and_never_overwrites(mech):
    a = mech.store.import_records([rec(value="60000")], source_ref="fx", source_edition="E1", mode="fixture")
    again = mech.store.import_records([rec(value="60000")], source_ref="fx", source_edition="E1", mode="fixture")
    assert a.added == 1 and again.already_imported and again.added == 0 and mech.store.counts() == {"records": 1, "batches": 1}
    changed = mech.store.import_records([rec(value="99999")], source_ref="fx", source_edition="E1", mode="fixture")                  # a different value for the same measurement
    assert changed.added == 0 and changed.rejections == {"conflicting_value_for_same_measurement": 1}
    assert mech.store.records_for([1], "US")[0]["value"] == Decimal("60000")                                                           # the original is untouched
    dup = mech.store.import_records([rec(native_code="99-0100", value="60000", reference_year=2024), rec(native_code="99-0100", value="61000", reference_year=2024)], source_ref="fx",
                                    source_edition="E1", mode="fixture")
    assert dup.added == 1 and dup.rejections == {"conflicting_value_for_same_measurement": 1}                                          # an in-batch conflict is never silently resolved


def test_a_failed_import_rolls_back_everything_including_the_batch(mech, monkeypatch):
    calls = {"n": 0}
    real = CompensationStoreV2._insert

    def boom(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("fail mid-import")
        return real(self, *a, **k)
    monkeypatch.setattr(CompensationStoreV2, "_insert", boom)
    with pytest.raises(RuntimeError):
        mech.store.import_records([rec(reference_year=2024), rec(reference_year=2023), rec(reference_year=2022)], source_ref="fx", source_edition="E1", mode="fixture")
    assert mech.store.counts() == {"records": 0, "batches": 0}


def test_concurrent_identical_imports_yield_one_set_of_records(mech):
    gate, out = threading.Barrier(5), []

    def go():
        gate.wait()
        try:
            out.append(mech.store.import_records([rec(), rec(reference_year=2024)], source_ref="fx", source_edition="E1", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert mech.store.counts()["records"] == 2 and mech.store.counts()["batches"] == 1 and sum(1 for r in out if not isinstance(r, str) and r.added == 2) >= 1


def test_suppressed_values_are_stored_as_a_status_never_as_zero(mech):
    mech.store.import_records([rec(value_status="suppressed", value=None)], source_ref="fx", source_edition="E1", mode="fixture")
    r = mech.store.records_for([1], "US")[0]
    assert r["value_status"] == "suppressed" and r["value"] is None and r["lower_value"] is None


def test_qualification_needs_a_named_reviewer_and_a_genuine_source(mech):
    mech.store.import_records([rec()], source_ref="fx", source_edition="E1", mode="fixture")
    key = mech.store.records_for([1], "US")[0]["record_key"]
    with pytest.raises(ValueError):
        mech.store.set_qualification(key, "qualified", actor_user_id=1)                                # a fixture can never be qualified
    with pytest.raises(ValueError):
        mech.store.set_qualification(key, "bogus", actor_user_id=1)
    with pytest.raises(ValueError):
        mech.store.set_qualification("missing", "qualified", actor_user_id=1)
    assert mech.store.set_qualification(key, "engineering_checked", actor_user_id=None)["qualification_status"] == "engineering_checked"


# ====================================================================================================================================== evidence qualification
def test_schema_validity_alone_never_makes_a_record_operational(mech):
    mech.store.import_records([rec()], source_ref="fx", source_edition="E1", mode="fixture")
    r = mech.store.records_for([1], "US")[0]
    st = evidence_status(r, mech.reg)
    assert st["schema_valid"] and st["occupation_linked"] and st["source_identified"] and st["citation_available"]
    assert not st["licence_verified"] and not st["ingestion_approved"] and not st["runtime_approved"] and not st["measurement_qualified"] and not st["operational"]


def test_a_record_is_operational_only_with_runtime_approval_qualification_and_a_citation(mech):
    approve(mech.reg, "off", runtime=True)
    mech.store.import_records([rec(source_ref="off")], source_ref="off", source_edition="E1", mode="production")
    r = mech.store.records_for([1], "US")[0]
    st = evidence_status(r, mech.reg)
    assert st["runtime_approved"] and st["licence_verified"] and st["ingestion_approved"] and not st["measurement_qualified"] and not st["operational"]
    mech.store.set_qualification(r["record_key"], "qualified", actor_user_id=5)
    r = mech.store.records_for([1], "US")[0]
    assert evidence_status(r, mech.reg)["operational"] is True
    assert evidence_status({**r, "value_status": "suppressed"}, mech.reg)["operational"] is False
    assert evidence_status({**r, "evidence_class": "C3"}, mech.reg)["operational"] is False                      # class not presentable for that precedence tier
    assert evidence_status({**r, "publisher": None}, mech.reg)["operational"] is False


def test_the_citation_is_built_only_from_the_stored_measurement_and_its_registered_source(mech):
    mech.store.import_records([rec()], source_ref="fx", source_edition="E1", mode="fixture")
    r = mech.store.records_for([1], "US")[0]
    c = build_citation(r, mech.reg)
    assert c["publisher"] == "Synthetic publisher" and c["dataset"] == "Synthetic dataset" and c["edition"] == "E1" and c["native_code"] == "99-0100" and c["reference_year"] == 2025
    for broken in ({"publisher": None}, {"dataset_name": None}, {"source_edition": ""}, {"source_ref": "unregistered"}, {"publisher": "A different publisher"}, {"reference_year": None}):
        assert build_citation({**r, **broken}, mech.reg) is None, broken


# ====================================================================================================================================== adapters
def test_the_us_adapter_keeps_original_units_and_maps_markers_to_status():
    rows = [{"OCC_CODE": "11-0000", "O_GROUP": "major", "A_MEDIAN": 123456.0, "A_PCT10": 70000.0, "A_PCT90": 200000.0}, {"OCC_CODE": "11-1011", "O_GROUP": "detailed", "A_MEDIAN": "98,765.5",
            "A_PCT10": "*", "A_PCT90": "#"}, {"OCC_CODE": "11-1021", "O_GROUP": "detailed", "A_MEDIAN": "*"}, {"OCC_CODE": "00-0000", "O_GROUP": "total", "A_MEDIAN": 50000},
            {"OCC_CODE": "", "O_GROUP": "detailed", "A_MEDIAN": 1}, {"OCC_CODE": "11-1031", "O_GROUP": "detailed", "A_MEDIAN": "abc"}, {"OCC_CODE": "11-1041", "O_GROUP": "weird", "A_MEDIAN": 70000}]
    recs, rej = AD.oews_records(rows, source_edition="M2025", reference_year=2025)
    by = {r.native_code: r for r in recs}
    assert by["11-0000"].occupation_level == "broad" and by["11-0000"].lower_value == Decimal("70000.0") and by["11-0000"].bounds_semantic == "percentile_10_90"
    assert by["11-1011"].value == Decimal("98765.5") and by["11-1011"].lower_value is None and by["11-1011"].occupation_level == "detailed"
    assert by["11-1021"].value_status == "suppressed" and by["11-1021"].value is None and by["11-1041"].occupation_level == "unknown"
    assert all(r.pay_period == "annual" and r.currency == "USD" and r.pay_basis == "unknown" and r.taxonomy_edition == "unknown" and r.country == "US" for r in recs)     # nothing assumed
    assert dict(rej) == {"aggregate_total_row": 1, "missing_native_code": 1, "malformed_amount": 1}


def test_the_uk_adapter_keeps_gross_weekly_pay_weekly_and_versions_uk_soc():
    recs, rej = AD.ashe_records([{"code": "1234", "description": "x", "median": "700.50"}, {"code": "12", "median": 900.0}, {"code": "", "median": 1}, {"code": "12a", "median": 1}, {"code": "9999", "median": "x"}],
                                source_edition="2025 provisional", reference_year=2025, data_vintage="provisional")
    by = {r.native_code: r for r in recs}
    assert by["1234"].pay_period == "weekly" and by["1234"].currency == "GBP" and by["1234"].pay_basis == "gross" and by["1234"].value == Decimal("700.50") and by["1234"].country == "GB"
    assert by["1234"].occupation_level == "detailed" and by["12"].occupation_level == "broad" and by["9999"].value_status == "suppressed" and by["1234"].taxonomy_edition == "2020"
    assert by["1234"].data_vintage == "provisional" and "NOT annualised" in by["1234"].limitations and dict(rej) == {"invalid_native_code": 2}
    assert not any(r.pay_period == "annual" for r in recs)


def test_the_eu_adapter_assumes_no_eurostat_code_and_never_treats_pps_as_currency():
    rows = [{"geo": "DE", "isco": "2", "unit": "EUR", "indic": "I1", "value": "25.40"}, {"geo": "EL", "isco": "2512", "unit": "NAC", "indic": "I1", "value": 18.5}, {"geo": "PL", "isco": "2", "unit": "NAC", "indic": "I1", "value": 20},
            {"geo": "DE", "isco": "2", "unit": "PPS", "indic": "I1", "value": 20}, {"geo": "DE", "isco": "2", "unit": "EUR", "indic": "I9", "value": 20}, {"geo": "DE", "isco": "2", "unit": "XYZ", "indic": "I1", "value": 20},
            {"geo": "EU27_2020", "isco": "1", "unit": "EUR", "indic": "I1", "value": ":"}, {"geo": "", "isco": "1", "unit": "EUR", "indic": "I1", "value": 1}, {"geo": "FR", "isco": "A", "unit": "EUR", "indic": "I1", "value": 1}]
    kw = dict(source_edition="SES 2022", reference_year=2022, indicator_map={"I1": ("hourly", "mean")}, currency_by_unit={"EUR": "EUR", "NAC": None, "PPS": None}, currency_by_country={"GR": "EUR"})
    recs, rej = AD.eurostat_ses_records(rows, **kw)
    by = {(r.country, r.native_code): r for r in recs}
    assert by[("DE", "2")].currency == "EUR" and by[("DE", "2")].pay_period == "hourly" and by[("DE", "2")].measure == "mean" and by[("DE", "2")].occupation_level == "broad"
    assert by[("GR", "2512")].occupation_level == "detailed" and by[("EU", "1")].geography_level == "eu_aggregate" and by[("EU", "1")].value_status == "suppressed"
    assert dict(rej) == {"currency_unmapped": 1, "unit_not_a_currency": 1, "unsupported_statistic": 1, "unsupported_unit": 1, "missing_geography": 1, "invalid_native_code": 1}
    none, rej2 = AD.eurostat_ses_records(rows[:1], source_edition="x", reference_year=2022, indicator_map={}, currency_by_unit={})
    assert none == [] and dict(rej2) == {"unsupported_statistic": 1}                                                                  # no map, no records: nothing is assumed


def test_the_onet_prefix_links_are_unverified_derived_rules_that_never_carry_evidence(sf):
    tax, g = TaxonomyCatalogue(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("soc", "2018", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{2}-[0-9]{4}")
    tax.ensure("onet_soc", "31.0")
    soc = g.add_occupation("Synthetic SOC node", [("soc", "2018", "99-0200")])["occupation_key"]
    onet = g.add_occupation("Synthetic O*NET node", [("onet_soc", "31.0", "99-0200.01")])["occupation_key"]
    g.add_occupation("Synthetic orphan", [("onet_soc", "31.0", "99-0300.00")])
    assert AD.derive_onet_soc_prefix_links(g, onet_edition="31.0", soc_edition="2018") == {"created": 1, "skipped": 1}
    rel = g.relationships(onet)[0]
    assert rel["to_key"] == soc and rel["basis"] == "derived_rule" and rel["mapping_status"] == "partial" and rel["relationship_type"] == "broader" and "unverified" in rel["limitations"]
    assert AD.derive_onet_soc_prefix_links(g, onet_edition="31.0", soc_edition="2018")["created"] == 1                                # idempotent
    assert AD.derive_onet_soc_prefix_links(g, onet_edition="9", soc_edition="2018") == {"created": 0, "skipped": 0}


# ====================================================================================================================================== resolver
def test_the_synthetic_corpus_is_synthetic_only():
    c = load_corpus()
    assert "SYNTHETIC" in c["note"] and all(s["source_id"].startswith("fx_") for s in c["sources"]) and all(sc["label"].endswith("[synthetic fixture]") for sc in c["scenarios"])
    assert len(c["cases"]) >= 40 and CORPUS_PATH.exists()


def test_every_corpus_case_matches_and_no_value_is_ever_invented(world):
    results = evaluate_cases(world)
    assert [r for r in results if not r["ok"]] == []
    assert not any(r["invented_value"] for r in results) and not any(r["operational"] or r["presentable"] for r in results)             # nothing is operational or presentable
    assert all(rep.rejected == 0 for rep in world.reports.values())
    cats = {r["category"] for r in results}
    for needed in ("us_code", "uk_code", "eu_isco", "conflict", "ambiguity", "missing_market", "unsupported", "c4", "stale", "measurement", "specificity", "crosswalk", "comparison",
                   "geography_independence", "citation", "approval", "precedence", "context"):
        assert needed in cats, needed


def test_the_default_withholds_everything_that_is_not_operational(world):
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US"))
    assert r.outcome is CompensationOutcome.ABSTAIN and r.evidence_class == "C4" and r.value is None and r.abstention_reason == "evidence_exists_but_is_not_operational"
    assert r.withheld == {"not_operational": 1} and r.candidate_presentable is False


def test_c4_is_abstention_never_an_estimate(world):
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job none", title_language="en"), country="DE", require_operational=False))
    assert r.outcome is CompensationOutcome.ABSTAIN and r.evidence_class == "C4" and r.value is None and r.lower_value is None and r.citation is None and r.corroborating == [] and r.conflicts == []


def test_a_resolution_with_a_qualified_runtime_approved_source_is_presentable(mech, sf):
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    approve(mech.reg, "off", runtime=True)
    mech.store.import_records([rec(source_ref="off", lower_value="40000", upper_value="90000", bounds_semantic="percentile_10_90")], source_ref="off", source_edition="E1", mode="production")
    a = AliasStore(sf)
    a.add_alias(mech.key, "operational test title", language="en", language_basis="curated_manual", alias_type="recognized_title")
    res = CompensationResolver(mech.store, OccupationResolver(mech.g, a, registry=mech.reg), mech.g, mech.reg)
    q = CompensationRequest(occupation=MultilingualRequest(title="operational test title", title_language="en"), country="US")
    first = res.resolve(q)
    assert first.outcome is CompensationOutcome.ABSTAIN and first.abstention_reason == "evidence_exists_but_is_not_operational"          # approved source but unqualified measurement
    mech.store.set_qualification(mech.store.records_for([1], "US")[0]["record_key"], "qualified", actor_user_id=4)
    ok = res.resolve(q)
    assert ok.outcome is CompensationOutcome.EVIDENCE and ok.operational and ok.candidate_presentable and ok.value == "60000" and ok.evidence_class == "C1" and ok.citation["edition"] == "E1"
    assert ok.lower_value == "40000" and ok.bounds_semantic == "percentile_10_90" and ok.currency == "USD" and ok.pay_period == "annual" and ok.pay_basis == "gross"


def test_the_public_response_carries_no_registry_secret_or_private_metadata(world):
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US", require_operational=False))
    d = r.to_public_dict()
    assert d["outcome"] == "evidence" and isinstance(d["value"], str) and d["citation"]["publisher"]
    blob = json.dumps(d, default=str).lower()
    for secret in ("licence", "approval_status", "actor_user_id", "batch", "checksum", "provenance", "secret", "api_key", "record_key", "occupation_id"):
        assert secret not in blob, secret
    assert d["candidate_presentable"] is False and d["policy_version"] == "p10c-e/1"


def test_language_never_selects_the_country_and_there_is_no_cross_country_fallback(world):
    fields = set(CompensationRequest.__dataclass_fields__)
    assert not fields & {"language", "locale", "ui_language", "interface_language", "title_language"} and "country" in fields
    for lang, title, country in (("de", "syn stelle uk", "GB"), ("en", "syn job uk_c1", "GB"), ("en", "syn job uk_c1", "US"), ("en", "syn job uk_c1", None)):
        r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title=title, title_language=lang), country=country, require_operational=False))
        expected = {"GB": CompensationOutcome.EVIDENCE, "US": CompensationOutcome.ABSTAIN, None: CompensationOutcome.INSUFFICIENT_CONTEXT}[country]
        assert r.outcome is expected and r.country == country, (lang, country)
        assert (r.value == "700.5") == (country == "GB")                                                    # the same occupation in another country never borrows GB data


def test_comparison_modes_other_than_nominal_are_not_configured_and_no_rate_exists(world):
    for mode in ("fx_converted", "ppp_adjusted"):
        r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US", comparison_mode=mode, require_operational=False))
        assert r.outcome is CompensationOutcome.NOT_CONFIGURED and r.value is None and r.comparison_mode_status == "not_configured"
    for cls in (FxProvider, PppProvider):
        with pytest.raises(NotImplementedError):
            getattr(cls(), "rate" if cls is FxProvider else "factor")("A", "B", 2025) if cls is FxProvider else cls().factor("A", 2025)
    idents, mult = set(), []
    for f in (ROOT / "src/knowledge_foundation/compensation").glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Name):
                idents.add(n.id.lower())
            elif isinstance(n, ast.Attribute):
                idents.add(n.attr.lower())
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                idents.add(n.name.lower())
            elif isinstance(n, ast.arg):
                idents.add(n.arg.lower())
            elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and any(isinstance(x, ast.Constant) and x.value in (12, 52, 260, 2080, 40) for x in (n.left, n.right)):
                mult.append((f.name, n.lineno))
    for token in ("convert_currency", "annualise", "annualize", "annualized", "fx_rate", "exchange_rate", "ppp_factor_value", "forex", "convert_period", "weekly_to_annual"):
        assert token not in idents, token
    assert mult == []                                                                                                  # no period-conversion arithmetic anywhere


def test_broader_fallback_follows_only_verified_broader_relationships_and_is_labelled(world):
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job child", title_language="en"), country="DE", require_operational=False))
    # Owner rule (P10C-F2A-Q): the parent group's statistic is CONTEXT beside an abstention, never the occupation's own value.
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.evidence_class == "C4" and r.abstention_reason == "exact_occupation_measurement_unavailable"
    assert r.occupation_key == world.keys["child"] and len(r.contextual_evidence) == 1
    ctx = r.contextual_evidence[0]
    assert ctx["broader_occupation_key"] == world.keys["grp"] and ctx["broader_occupation_code"] and ctx["broader_occupation_label"] and ctx["evidence_class"] == "C2" and ctx["citation"]
    assert "NOT the requested occupation" in ctx["warning"] and ctx["measure"] and ctx["reference_year"]
    for slug in ("rel_src", "der_src"):
        r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title=f"syn job {slug}", title_language="en"), country="DE", require_operational=False))
        assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None, slug


def test_an_ambiguous_title_never_produces_a_salary(world):
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn engineer", title_language="en"), country="DE", require_operational=False))
    assert r.outcome is CompensationOutcome.AMBIGUOUS and r.value is None and len(r.candidates) == 2 and r.operational is False and r.occupation_key is None


def test_a_broken_citation_withholds_the_value(world):
    with world.sf() as s:
        s.execute(text("update compensation_v2_records set publisher = 'Altered publisher' where source_ref = 'fx_us_stat' and native_code = '99-0001'"))
        s.commit()
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US", require_operational=False))
    assert r.outcome is CompensationOutcome.ABSTAIN and r.value is None and r.abstention_reason == "evidence_withheld_citation_incomplete"


def test_lookups_use_the_index_and_a_bounded_number_of_queries(world):
    counts = {"n": 0}

    @event.listens_for(world.sf.kw["bind"], "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        counts["n"] += 1
    r = world.resolver.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn job us_c1", title_language="en"), country="US", require_operational=False))
    assert r.outcome is CompensationOutcome.EVIDENCE and counts["n"] < 40
    with world.sf() as s:
        plan = " ".join(x[3] for x in s.execute(text("EXPLAIN QUERY PLAN SELECT id FROM compensation_v2_records WHERE occupation_id = 1 AND country = 'US'")))
    assert "ix_comp_v2_lookup" in plan


def test_a_large_multi_country_dataset_resolves_quickly(sf):
    import time
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    reg.register("fxp", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics")
    store = CompensationStoreV2(sf, reg, g)
    n = 300
    keys = [g.add_occupation(f"Synthetic perf {i}", [("isco", "08", f"{i + 1:04d}")])["occupation_key"] for i in range(n)]
    rows = [dict(taxonomy_scheme="isco", taxonomy_edition="08", native_code=f"{i + 1:04d}", occupation_level="detailed", country=c, geography_level="national", currency="EUR", pay_period="annual",
                 pay_basis="gross", measure="median", value=str(30000 + i + j), source_ref="fxp", source_edition="E1", reference_year=2025) for i in range(n) for j, c in enumerate(("DE", "FR", "ES", "IT"))]
    t0 = time.perf_counter()
    rep = store.import_records(rows, source_ref="fxp", source_edition="E1", mode="fixture")
    assert rep.added == n * 4 and time.perf_counter() - t0 < 60
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    res = CompensationResolver(store, OccupationResolver(g, AliasStore(sf)), g, reg)
    t1 = time.perf_counter()
    for i in range(0, n, 10):
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(known_occupation_keys=(keys[i],)), country="FR", require_operational=False))
        assert r.outcome is CompensationOutcome.EVIDENCE and r.value == str(30000 + i + 1)
    assert (time.perf_counter() - t1) * 1000 / 30 < 100


# ====================================================================================================================================== isolation and gates
def test_nothing_in_compensation_v2_is_imported_by_a_runtime_or_candidate_path():
    offenders = []
    for pkg in ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing"):
        for f in (ROOT / pkg).rglob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
                if any(m and (m.startswith("src.knowledge_foundation") or "CompensationRecordV2" in m) for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
    for rel in ("src/copilot/knowledge/compensation.py", "src/copilot/knowledge/retrieval.py", "src/copilot/knowledge/router.py", "src/copilot/knowledge/governed_datasets.py"):
        t = (ROOT / rel).read_text()
        assert "knowledge_foundation" not in t and "compensation_v2" not in t.lower(), rel


def test_compensation_v1_is_unchanged_and_still_filters_exactly_as_before():
    from src.copilot.knowledge.compensation import CompensationRecord, CompensationRepository
    repo = CompensationRepository(":memory:")
    repo.add(CompensationRecord(source_id="s", occupation_code="99-0001", country="US", year=2025, currency="USD", pay_period="annual", value=1.0))
    repo.add(CompensationRecord(source_id="s", occupation_code="99-0002", country="UK", year=2025, currency="GBP", pay_period="weekly", value=2.0))
    assert repo.count() == 2 and [r.currency for r in repo.filter(country="uk")] == ["GBP"] and repo.filter(occupation_code="99-0001")[0].value == 1.0 and set(repo.countries()) == {"US", "UK"}
    from src.copilot import constants
    assert set(constants.COUNTRY_SOURCE_PRIORITY) == {"DE", "US", "UK", "EU"}


def test_all_gates_stay_off_and_no_new_gate_exists():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, g) is False
    import src.knowledge_foundation.compensation as pkg
    assert not [n for n in dir(pkg) if "ENABLED" in n or "ENFORCED" in n]


def test_no_compensation_module_downloads_calls_a_provider_or_reads_a_protected_store():
    banned = {"requests", "httpx", "urllib", "stripe", "openai", "boto3", "aiohttp", "socket", "pandas"}
    for f in (ROOT / "src/knowledge_foundation/compensation").glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & banned, (f.name, mods & banned)
        assert "data/knowledge" not in f.read_text() and "COMPENSATION_DB_PATH" not in f.read_text(), f.name


def test_no_client_input_can_import_approve_or_qualify():
    for f in (ROOT / "src/api").rglob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert "CompensationStoreV2" not in t and "import_records" not in t and "set_qualification" not in t, f


# ====================================================================================================================================== migration 0037
def test_migration_0037_is_additive_reversible_and_matches_the_orm(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    from src import persistence as P
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0038_compensation_concepts"]
    new = ("compensation_v2_records", "compensation_import_batches")
    command.upgrade(cfg, "0036_multilingual_aliases")
    assert not set(new) & set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert set(new) <= set(insp.get_table_names())
    for t in new:
        model = next(m for m in P.Base.metadata.tables.values() if m.name == t)
        assert {c["name"] for c in insp.get_columns(t)} == {c.name for c in model.columns}, t
    assert {u["name"] for u in insp.get_unique_constraints("compensation_v2_records")} == {"uq_comp_v2_record_key", "uq_comp_v2_natural_key"}
    assert {"ix_comp_v2_lookup", "ix_comp_v2_source"} <= {i["name"] for i in insp.get_indexes("compensation_v2_records")}
    assert {f["referred_table"]: f["options"].get("ondelete") for f in insp.get_foreign_keys("compensation_v2_records")} == {"graph_occupations": "RESTRICT", "occupation_taxonomies": "RESTRICT",
                                                                                                                        "compensation_import_batches": "SET NULL"}
    orm = {c.name for c in P.CompensationRecordV2Row.__table__.constraints if getattr(c, "sqltext", None) is not None}
    assert {"ck_cv2_value_not_zero_or_invented", "ck_cv2_percentile", "ck_cv2_bounds", "ck_cv2_evidence_class", "ck_cv2_provenance_present"} <= orm
    command.downgrade(cfg, "0036_multilingual_aliases")
    after = inspect(create_engine(url))
    assert not set(new) & set(after.get_table_names()) and {"graph_occupation_aliases", "language_coverage", "graph_occupations"} <= set(after.get_table_names())
    command.upgrade(cfg, "head")


def test_the_migration_seeds_nothing_and_preserves_earlier_data(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0036_multilingual_aliases")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("insert into graph_occupations (occupation_key, canonical_label, status, legacy_keys, created_at) values ('ask4mo:occ:keep', 'keep', 'active', '[]', '2026-01-01')"))
    command.upgrade(cfg, "head")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from graph_occupations")).scalar() == 1
        for t in ("compensation_v2_records", "compensation_import_batches"):
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    command.downgrade(cfg, "0036_multilingual_aliases")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from graph_occupations")).scalar() == 1


# ====================================================================================================================================== scripts on a clean checkout
def _run(name, *args, cwd):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, cwd=cwd)


def _snap(root):
    return sorted((str(p.relative_to(root)), p.is_dir() or p.stat().st_size) for p in root.rglob("*"))


def test_the_inventory_script_validates_output_before_data_access_and_fails_in_a_controlled_way(tmp_path):
    root = tmp_path / "clean"
    (root / "data").mkdir(parents=True)
    (root / "evaluations").mkdir()
    (root / "alias").symlink_to(root / "data", target_is_directory=True)
    before = _snap(root)
    for target in ("data/x.json", "evaluations/y.json", "data/nested/z.json", "outside/../data/w.json", "alias/v.json", str(root / "data/abs.json")):
        r = _run("gkb5_compensation_inventory.py", "--root", str(root), "--out", target, cwd=root)
        assert r.returncode == 2 and "refusing" in r.stderr and "Traceback" not in r.stderr, (target, r.stderr[-200:])
    r = _run("gkb5_compensation_inventory.py", "--root", str(root), "--out", str(tmp_path / "elsewhere/inv.json"), cwd=root)
    assert r.returncode == 3 and "missing" in r.stderr and "Traceback" not in r.stderr and not (tmp_path / "elsewhere").exists()
    assert _snap(root) == before


def test_the_inventory_script_reads_a_fixture_store_read_only(tmp_path):
    root = tmp_path / "fx"
    (root / "data/knowledge").mkdir(parents=True)
    (root / "src/knowledge_foundation/data").mkdir(parents=True)
    con = sqlite3.connect(root / "data/knowledge/compensation.db")
    con.execute("create table compensation_records (source_id text, occupation_code text, occupation_title text, geography text, country text, region text, industry text, year integer, currency text, "
                "pay_period text, statistic_type text, value real, lower_bound real, upper_bound real, sample_quality text, source_url text)")
    con.execute("insert into compensation_records values ('s','99-0001','','US','US',null,null,2025,'USD','annual','median',1.0,null,null,'final','u')")
    con.commit()
    con.close()
    before = (root / "data/knowledge/compensation.db").read_bytes()
    out = tmp_path / "out/inv.json"
    r = _run("gkb5_compensation_inventory.py", "--root", str(root), "--out", str(out), cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-300:]
    inv = json.loads(out.read_text())
    assert inv["records"] == 1 and inv["per_source"]["s"]["codes_in_xx_xxxx_shape"] == 1 and "pay_basis" in inv["v1_lacks"] and "salary" not in out.read_text().lower().replace("no salary", "")
    assert (root / "data/knowledge/compensation.db").read_bytes() == before


def test_the_committed_inventory_is_metadata_only_and_matches_the_verified_baseline():
    inv = json.loads((ROOT / "docs/capstone/p10/p10c_c/COMPENSATION_INVENTORY.json").read_text())
    assert inv["records"] == 1913 and inv["per_source"]["bls_oews"]["records"] == 1386 and inv["per_source"]["ons_ashe"]["records"] == 527 and "No titles" in inv["note"]
    assert inv["per_source"]["ons_ashe"]["pay_periods"] == ["weekly"] and inv["per_source"]["bls_oews"]["rows_with_title"] == 0 and inv["eurostat_structured_earnings_available_locally"] is False
    assert all(s["approval_status"] in ("licensing_pending", "restricted") for s in inv["registry_state_of_relevant_sources"].values())
    for per in inv["per_source"].values():
        assert not {"value", "values", "median", "title", "titles", "occupation_title"} & set(per)                   # counts and shapes only
        assert all(isinstance(v, (int, list, dict, str)) for v in per.values())


def test_the_committed_corpus_is_stable_json():
    assert json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["schema"] == "compensation_fixture_corpus/1" and len(load_corpus()["scenarios"]) == 28
    assert datetime(2026, 1, 1, tzinfo=timezone.utc).year == 2026


def test_the_benchmark_script_refuses_protected_outputs_before_doing_any_work(tmp_path):
    for target in ("data/bench.json", "evaluations/bench.json"):
        r = _run("bench_compensation_v2.py", "--out", str(ROOT / target), cwd=tmp_path)
        assert r.returncode == 2 and "refusing" in r.stderr and not (ROOT / target).exists()
