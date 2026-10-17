"""P10C-A: global knowledge foundation (GKB-0 baseline, GKB-1 source registry and coverage matrix, GKB-2 canonical occupation graph). FULLY OFFLINE: throwaway SQLite databases,
synthetic structural test occupations (never official salary or occupation data), the committed seed files, and tiny synthetic CSV fixtures. No external dataset, provider, Stripe or
network. Nothing here is imported by a candidate-facing path and no rollout or billing gate changes."""

from __future__ import annotations

import ast
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation import baseline as B
from src.knowledge_foundation import coverage as COV
from src.knowledge_foundation import enums as E
from src.knowledge_foundation.graph import ConflictingMapping, GraphError, IdentityConflict, OccupationGraph, occupation_key_for
from src.knowledge_foundation.importers import assess_legacy_store_mappings, read_esco_occupations_csv, read_isco_structure_csv, register_esco_isco
from src.knowledge_foundation.legacy import LegacyCompatibility
from src.knowledge_foundation.registry import RegistryError, SourceRegistry
from src.knowledge_foundation.resolver_contract import GraphResolver, ResolutionOutcome, ResolutionRequest
from src.knowledge_foundation.seed import BASELINE_PATH, build_registry_entries, load_registry_baseline
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue, TaxonomyError, editions_compatible
from src.persistence import GraphOccupationRelationship, GlobalSource, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'kf.db'}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def world(sf):
    tax = TaxonomyCatalogue(sf)
    tax.seed()
    reg = SourceRegistry(sf)
    reg.register("src_a", publisher="Test Publisher", origin="official_local")
    return SimpleNS(sf=sf, tax=tax, reg=reg, g=OccupationGraph(sf))


class SimpleNS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ======================================================================== GKB-1 source registry
def test_a_new_source_starts_discovered_with_unknown_facts_never_approved(world):
    r = world.reg.register("s1")
    assert r["approval_status"] == "discovered" and r["licence_status"] == "unknown" and r["redistribution"] == "unknown" and r["attribution_required"] == "unknown" and r["origin"] == "unknown"
    assert r["publisher"] is None and world.reg.can_ingest("s1") is False and world.reg.can_serve_as_evidence("s1") is False


def test_registering_cannot_create_an_approved_source_or_a_verified_licence(world):
    for bad in ({"approval_status": "approved_for_runtime_use"}, {"approval_status": "approved_for_ingestion"}, {"licence_status": "verified"}, {"origin": "made_up"}, {"evidence_class": "C9"}):
        with pytest.raises(RegistryError):
            world.reg.register("bad", **bad)


def test_the_approval_lifecycle_allows_only_defined_edges_and_every_transition_is_audited(world):
    world.reg.register("s2", origin="official_local", validation_status="unvalidated")
    with pytest.raises(RegistryError):
        world.reg.transition("s2", "approved_for_ingestion")                                   # skipping licensing is not allowed
    world.reg.transition("s2", "licensing_pending", actor_user_id=None, reason="start review")
    with pytest.raises(RegistryError):
        world.reg.transition("s2", "licensing_verified" if False else "approved_for_runtime_use")
    world.reg.transition("s2", "licensing_verified")
    with pytest.raises(RegistryError):
        world.reg.transition("s2", "approved_for_ingestion")                                   # a stated lifecycle step is not a verified licence
    world.reg.set_licence("s2", licence_id="CC BY 4.0", licence_status="verified", attribution_required="yes", redistribution="yes")
    world.reg.transition("s2", "approved_for_ingestion")
    assert world.reg.can_ingest("s2") and not world.reg.can_serve_as_evidence("s2")             # ingestion approval is not runtime approval
    world.reg.transition("s2", "approved_for_runtime_use")
    assert world.reg.can_serve_as_evidence("s2")
    assert [e["to"] for e in world.reg.events("s2")] == ["discovered", "licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use"]


def test_a_licence_cannot_leave_verified_while_the_source_is_approved_and_restricting_revokes_evidence_use(world):
    world.reg.register("s3", origin="official_local", validation_status="unvalidated")
    world.reg.set_licence("s3", licence_id="OGL", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use"):
        if step == "licensing_pending":
            world.reg.transition("s3", step)
        else:
            world.reg.transition("s3", step)
    with pytest.raises(RegistryError):
        world.reg.set_licence("s3", licence_id="OGL", licence_status="unknown")
    world.reg.transition("s3", "restricted", reason="licence question")
    assert world.reg.can_serve_as_evidence("s3") is False and world.reg.can_ingest("s3") is False
    world.reg.set_licence("s3", licence_id="OGL", licence_status="conflicting")


def test_a_synthetic_fixture_can_never_be_approved_at_any_layer(world, sf):
    r = world.reg.register("fx", origin="synthetic_fixture")
    assert r["approval_status"] == "restricted" and world.reg.can_serve_as_evidence("fx") is False
    world.reg.set_licence("fx", licence_id="x", licence_status="verified")
    world.reg.transition("fx", "licensing_pending")
    world.reg.transition("fx", "licensing_verified") if False else None
    with pytest.raises(RegistryError):
        world.reg.transition("fx", "approved_for_ingestion")
    with sf() as s:                                                                               # and the database refuses it independently of the service
        row = s.scalar(select(GlobalSource).where(GlobalSource.source_id == "fx"))
        row.approval_status = "approved_for_runtime_use"
        with pytest.raises(IntegrityError):
            s.commit()


def test_the_database_refuses_an_approval_without_a_verified_licence(sf):
    with sf() as s:
        s.add(GlobalSource(source_id="x", geographies=[], languages=[], provenance={}, approval_status="approved_for_ingestion", licence_status="unknown", origin="official_local"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_re_registration_refreshes_metadata_but_never_changes_approval_or_a_verified_licence(world):
    world.reg.register("s4", origin="official_local", validation_status="unvalidated", dataset_version="1")
    world.reg.set_licence("s4", licence_id="PD", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion"):
        world.reg.transition("s4", step)
    again = world.reg.register("s4", dataset_version="2", licence_id="CHANGED", licence_status="unknown", approval_status="discovered")
    assert again["dataset_version"] == "2" and again["approval_status"] == "approved_for_ingestion" and again["licence_status"] == "verified" and again["licence_id"] == "PD"


def test_runtime_use_needs_a_known_non_fixture_origin_and_a_recorded_validation_status(world):
    world.reg.register("s5", origin="official_local")                                              # validation unknown
    world.reg.set_licence("s5", licence_id="PD", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion"):
        world.reg.transition("s5", step)
    with pytest.raises(RegistryError):
        world.reg.transition("s5", "approved_for_runtime_use")


def test_rejected_and_superseded_are_terminal_and_supersession_names_its_successor(world):
    world.reg.register("old", origin="official_local", validation_status="unvalidated")
    world.reg.register("new")
    with pytest.raises(RegistryError):
        world.reg.supersede("old", by="missing")
    world.reg.set_licence("old", licence_id="PD", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion"):
        world.reg.transition("old", step)
    assert world.reg.supersede("old", by="new")["superseded_by"] == "new"
    with pytest.raises(RegistryError):
        world.reg.transition("old", "licensing_pending")
    world.reg.transition("new", "rejected")
    with pytest.raises(RegistryError):
        world.reg.transition("new", "licensing_pending")


def test_freshness_is_metadata_only_and_unknown_when_not_recorded(world):
    assert world.reg.freshness("src_a") == {"retrieved_at": None, "age_days": None, "freshness": "unknown"}
    world.reg.register("fresh", retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    f = world.reg.freshness("fresh", now=datetime(2026, 1, 11, tzinfo=timezone.utc))
    assert f["age_days"] == 10 and f["freshness"] == "recorded"


def test_the_seed_transform_keeps_unknowns_unknown_and_never_trusts_a_bare_redistribution_flag():
    manifest = {"sources": [{"source_id": "a", "title": "A", "publisher": "P", "authority": "official", "country": "US", "source_type": "compensation_dataset", "language": "en", "licence": None,
                             "redistribution_allowed": True, "licence_review_required": True, "version": "current release", "refresh_frequency": "annual"},
                            {"source_id": "b", "title": "B", "authority": "official", "country": "EU", "source_type": "occupation_taxonomy", "language": "en", "licence": "CC BY 4.0",
                             "licence_notes": "Attribution required.", "redistribution_allowed": True, "version": "v1"},
                            {"source_id": "c", "title": "C", "authority": "industry", "country": "DE", "source_type": "x", "language": "en", "redistribution_allowed": False}]}
    es = {e["source_id"]: e for e in build_registry_entries(manifest, {"sources": []}, {"origins": {"a": ["synthetic_fixture"], "b": ["official_local"]}})}
    assert es["a"]["origin"] == "synthetic_fixture" and es["a"]["approval_status"] == "restricted" and es["a"]["redistribution"] == "unknown" and es["a"]["licence_status"] == "unknown"
    assert es["a"]["provenance"]["conflicts"] == ["redistribution_declared_without_a_stated_licence"] and es["a"]["dataset_version"] == "current release"
    assert es["b"]["licence_status"] == "stated_unverified" and es["b"]["redistribution"] == "yes" and es["b"]["attribution_required"] == "yes" and es["b"]["approval_status"] == "licensing_pending"
    assert es["c"]["redistribution"] == "unknown" and es["c"]["origin"] == "unknown" and es["c"]["precedence_category"] == "unknown" and es["c"]["evidence_class"] is None


def test_the_committed_registry_baseline_loads_idempotently_and_authorizes_nothing(world):
    n = load_registry_baseline(world.reg)
    assert n == 31 and load_registry_baseline(world.reg) == 31
    rows = {r["source_id"]: r for r in world.reg.list()}
    assert len([r for r in rows.values() if r["source_id"] != "src_a"]) == 31
    assert not [r for r in rows.values() if r["approval_status"] in ("approved_for_ingestion", "approved_for_runtime_use")]
    assert not [sid for sid in rows if world.reg.can_ingest(sid) or world.reg.can_serve_as_evidence(sid)]
    assert rows["bls_oews"]["precedence_category"] == "national_official_occupation_statistics" and rows["bls_oews"]["evidence_class"] == "C1" and rows["ons_ashe"]["evidence_class"] is None
    assert rows["bls_oews"]["taxonomy"] == "soc" and rows["ons_ashe"]["taxonomy"] == "uk_soc"
    assert sum(1 for r in rows.values() if r["origin"] == "synthetic_fixture" and r["approval_status"] == "restricted") == 5


def test_the_committed_baseline_has_explicit_licensing_gaps_and_no_invented_licence():
    srcs = json.loads(BASELINE_PATH.read_text())["sources"]
    assert sum(1 for s in srcs if s["licence_status"] == "unknown") == 18 and sum(1 for s in srcs if s["licence_id"]) == 13
    assert sorted({s["licence_id"] for s in srcs if s["licence_id"]}) == ["CC BY 4.0", "CEN standard (commercial)", "Open Government Licence v3.0", "Public domain (U.S. Government work)"]
    assert all(s["licence_status"] == "unknown" for s in srcs if not s["licence_id"])


# ======================================================================== taxonomy editions
def test_the_catalogue_records_statuses_from_evidence_and_never_invents_an_edition(world):
    esco = world.tax.get("esco", "1.2.1")
    assert esco["acquisition_status"] == "available_locally" and world.tax.get("uk_soc", "2020")["acquisition_status"] == "referenced_indirectly"
    for scheme in ("noc", "sinco", "cbo"):
        t = world.tax.editions(scheme)
        assert len(t) == 1 and t[0]["edition"] == "unknown" and t[0]["acquisition_status"] == "identified_externally"
    assert world.tax.get("soc", "unknown")["acquisition_status"] == "referenced_indirectly"
    assert len(json.loads((ROOT / "src/knowledge_foundation/data/taxonomy_catalogue.json").read_text())["taxonomies"]) == 9


def test_seeding_is_idempotent_and_never_silently_relabels_an_existing_row(world):
    world.tax.update("esco", "1.2.1", status="historical")
    world.tax.seed()
    assert world.tax.get("esco", "1.2.1")["status"] == "historical"
    assert len(world.tax.editions("esco")) == 1


def test_editions_are_separate_namespaces_and_unknown_is_compatible_with_nothing(world):
    world.tax.ensure("isco", "88", status="historical", acquisition_status="identified_externally")
    a, b, u1 = world.tax.get("isco", "08"), world.tax.get("isco", "88"), world.tax.ensure("soc", "unknown")
    assert editions_compatible(a, a) and not editions_compatible(a, b) and not editions_compatible(u1, u1)
    assert not editions_compatible(world.tax.get("esco", "1.2.1"), a)
    world.tax.supersede("isco", "88", "08")
    assert world.tax.get("isco", "88")["status"] == "historical" and world.tax.get("isco", "88")["superseded_by_id"] == a["id"]
    with pytest.raises(TaxonomyError):
        world.tax.supersede("isco", "08", "08")
    with pytest.raises(TaxonomyError):
        world.tax.ensure("not_a_scheme")


def test_the_database_refuses_a_duplicate_taxonomy_edition(sf):
    t = TaxonomyCatalogue(sf)
    t.ensure("noc", "2021")
    assert t.ensure("noc", "2021")["id"] == t.get("noc", "2021")["id"]


# ======================================================================== GKB-2 occupation graph
def test_identity_is_independent_of_title_namespace_aware_and_stable(world):
    a = world.g.add_occupation("Software developer", [("isco", "08", "2512")])
    b = world.g.add_occupation("Software developers", [("onet_soc", "31.0", "15-1252.00")])
    again = world.g.add_occupation("Renamed by someone", [("isco", "08", "2512")])
    assert a["occupation_key"] == again["occupation_key"] == occupation_key_for("isco", "08", "2512") and a["canonical_label"] == "Software developer"
    assert a["occupation_key"] != b["occupation_key"] and a["occupation_key"].startswith("ask4mo:occ:")
    assert world.g.counts() == {"occupations": 2, "identifiers": 2, "relationships": 0}


def test_the_same_code_in_different_namespaces_and_editions_never_collides(world):
    world.tax.ensure("isco", "88", status="historical", acquisition_status="identified_externally", code_pattern="[0-9]{1,4}")
    a = world.g.add_occupation("Code 2512 in ISCO-08", [("isco", "08", "2512")])
    b = world.g.add_occupation("Code 2512 in ISCO-88 (synthetic test occupation)", [("isco", "88", "2512")], occupation_key="ask4mo:occ:test-isco88-2512")
    c = world.g.add_occupation("Code 2512 in UK SOC 2020", [("uk_soc", "2020", "2512")])
    assert len({a["occupation_key"], b["occupation_key"], c["occupation_key"]}) == 3
    assert [h["edition"] for h in world.g.find_by_identifier("isco", "2512")] == ["08", "88"]
    assert [h["edition"] for h in world.g.find_by_identifier("isco", "2512", edition="08")] == ["08"]


def test_a_code_held_by_another_occupation_is_an_identity_conflict_and_nothing_is_overwritten(world):
    a = world.g.add_occupation("First", [("isco", "08", "2512")])
    with pytest.raises(IdentityConflict):
        world.g.add_occupation("Second", [("isco", "08", "2512")], occupation_key="ask4mo:occ:someone-else")
    assert world.g.get(a["occupation_key"])["canonical_label"] == "First" and world.g.counts()["occupations"] == 1
    b = world.g.add_occupation("Other", [("isco", "08", "2511")])
    with pytest.raises(IdentityConflict):
        world.g.add_occupation("Joined", [("isco", "08", "2512"), ("isco", "08", "2511")])         # one node cannot swallow two established identities
    assert world.g.counts()["occupations"] == 2 and b["occupation_key"] != a["occupation_key"]


def test_identifiers_must_use_a_registered_edition_and_the_taxonomy_code_format(world):
    with pytest.raises(GraphError):
        world.g.add_occupation("X", [("isco", "1999", "2512")])                                     # unregistered edition
    with pytest.raises(GraphError):
        world.g.add_occupation("X", [("isco", "08", "ABCD")])                                       # not an ISCO code
    with pytest.raises(GraphError):
        world.g.add_occupation("", [("isco", "08", "2512")])
    assert world.g.counts()["occupations"] == 0


def test_duplicate_display_titles_in_different_taxonomies_stay_distinct_nodes(world):
    a = world.g.add_occupation("Accountant", [("isco", "08", "2411")])
    b = world.g.add_occupation("Accountant", [("onet_soc", "31.0", "13-2011.00")])
    assert len(world.g.find_by_label("accountant")) == 2 and a["occupation_key"] != b["occupation_key"]
    assert LegacyCompatibility(world.g).by_title("Accountant")["status"] == "ambiguous"


def test_relationship_vocabulary_is_governed_and_related_is_never_equivalent(world):
    a = world.g.add_occupation("A", [("isco", "08", "2512")])
    b = world.g.add_occupation("B", [("onet_soc", "31.0", "15-1252.00")])
    kw = dict(from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"))
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="similar", basis="curated_manual", mapping_status="unknown", **kw)
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="equivalent", basis="label_similarity", mapping_status="unknown", **kw)
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="equivalent", basis="derived_rule", mapping_status="unknown", limitations="x", **kw)
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", basis="derived_rule", mapping_status="unknown", **kw)       # a derived rule must state its limit
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], a["occupation_key"], relationship_type="related", basis="curated_manual", mapping_status="unknown", from_taxonomy=("isco", "08"), to_taxonomy=("isco", "08"))
    rel = world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", basis="curated_manual", mapping_status="unknown", limitations="curated for test", **kw)
    assert rel["relationship_type"] == "related" and rel["mapping_status"] == "unknown" and rel["qualification_status"] == "unqualified"


def test_verified_needs_a_registered_source_and_a_source_provided_basis(world):
    a = world.g.add_occupation("A", [("isco", "08", "2512")])
    b = world.g.add_occupation("B", [("onet_soc", "31.0", "15-1252.00")])
    kw = dict(relationship_type="broader", from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"))
    for bad in ({"basis": "source_provided", "source_ref": ""}, {"basis": "curated_manual", "source_ref": "src_a"}, {"basis": "source_provided", "source_ref": "not_registered"}):
        with pytest.raises(GraphError):
            world.g.add_relationship(a["occupation_key"], b["occupation_key"], mapping_status="verified", **bad, **kw)
    ok = world.g.add_relationship(a["occupation_key"], b["occupation_key"], mapping_status="verified", basis="source_provided", source_ref="src_a", **kw)
    assert ok["mapping_status"] == "verified" and ok["source_ref"] == "src_a"


def test_endpoints_must_hold_an_identifier_in_the_stated_edition(world):
    a = world.g.add_occupation("A", [("isco", "08", "2512")])
    b = world.g.add_occupation("B", [("onet_soc", "31.0", "15-1252.00")])
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", basis="curated_manual", mapping_status="unknown",
                                 from_taxonomy=("esco", "1.2.1"), to_taxonomy=("onet_soc", "31.0"))
    with pytest.raises(GraphError):
        world.g.add_relationship(a["occupation_key"], "ask4mo:occ:missing", relationship_type="related", basis="curated_manual", mapping_status="unknown",
                                 from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"))


def test_conflicting_statements_are_refused_agreeing_ones_corroborate_and_supersession_keeps_history(world):
    world.reg.register("src_b")
    a = world.g.add_occupation("A", [("isco", "08", "2512")])
    b = world.g.add_occupation("B", [("onet_soc", "31.0", "15-1252.00")])
    kw = dict(from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"), basis="source_provided")
    first = world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="broader", mapping_status="partial", source_ref="src_a", **kw)
    assert world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="broader", mapping_status="partial", source_ref="src_a", **kw) == first      # idempotent
    world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="broader", mapping_status="partial", source_ref="src_b", **kw)                      # corroboration
    with pytest.raises(ConflictingMapping):
        world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="equivalent", mapping_status="verified", source_ref="src_b", **kw)
    assert len(world.g.relationships(a["occupation_key"])) == 2 and world.g.conflicts() == []
    assert world.g.supersede_relationship(a["occupation_key"], b["occupation_key"]) == 2
    assert world.g.relationships(a["occupation_key"]) == [] and len(world.g.relationships(a["occupation_key"], include_superseded=True)) == 2
    corrected = world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="narrower", mapping_status="ambiguous", source_ref="src_b", **kw)
    assert corrected["mapping_status"] == "ambiguous"


def test_the_database_enforces_the_relationship_rules_independently(world, sf):
    a = world.g.add_occupation("A", [("isco", "08", "2512")])
    b = world.g.add_occupation("B", [("onet_soc", "31.0", "15-1252.00")])
    with sf() as s:
        from src.persistence import GraphOccupation, OccupationTaxonomy
        ids = {o.occupation_key: o.id for o in s.scalars(select(GraphOccupation))}
        tax = {(t.scheme, t.edition): t.id for t in s.scalars(select(OccupationTaxonomy))}
        base = dict(from_occupation_id=ids[a["occupation_key"]], to_occupation_id=ids[b["occupation_key"]], from_taxonomy_id=tax[("isco", "08")], to_taxonomy_id=tax[("onet_soc", "31.0")],
                    relationship_type="related", basis="curated_manual")
        for bad in ({"mapping_status": "verified", "source_ref": "x"}, {"mapping_status": "verified", "basis": "source_provided", "source_ref": ""}, {"mapping_status": "bogus"},
                    {"to_occupation_id": ids[a["occupation_key"]], "mapping_status": "unknown"}):
            s.add(GraphOccupationRelationship(**{**base, "mapping_status": "unknown", **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_a_bulk_import_is_all_or_nothing(world):
    def boom(s):
        world.g.add_occupation("One", [("isco", "08", "2512")], _session=s)
        world.g.add_occupation("Two", [("isco", "08", "2511")], _session=s)
        raise RuntimeError("fail mid-import")
    with pytest.raises(RuntimeError):
        world.g.bulk(boom)
    assert world.g.counts() == {"occupations": 0, "identifiers": 0, "relationships": 0}


def test_concurrent_registration_of_the_same_identifier_yields_one_node(world):
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(world.g.add_occupation("Concurrent", [("isco", "08", "2512")])["occupation_key"])
        except (IdentityConflict, GraphError):
            out.append("conflict")
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert world.g.counts()["occupations"] == 1 and set(out) <= {occupation_key_for("isco", "08", "2512"), "conflict", "OperationalError"} and occupation_key_for("isco", "08", "2512") in out


# ======================================================================== resolver contract and legacy compatibility
def _seeded(world):
    world.reg.register("esco", origin="official_local")
    world.g.add_occupation("Data analyst", [("isco", "08", "2511")])
    world.g.add_occupation("Data analyst", [("onet_soc", "31.0", "15-2051.00")])
    world.g.add_occupation("Nurse", [("isco", "08", "2221")])
    return GraphResolver(world.g, COV.CoverageMatrix(world.sf))


def test_resolver_outcomes_cover_resolved_ambiguous_insufficient_unsupported_and_not_found(world):
    COV.CoverageMatrix(world.sf).seed()
    r = _seeded(world)
    assert r.resolve(ResolutionRequest(title="Nurse")).outcome is ResolutionOutcome.RESOLVED
    amb = r.resolve(ResolutionRequest(title="Data Analyst"))
    assert amb.outcome is ResolutionOutcome.AMBIGUOUS and len(amb.candidates) == 2 and "role_context" in amb.context_needed
    assert r.resolve(ResolutionRequest()).outcome is ResolutionOutcome.INSUFFICIENT_CONTEXT
    assert r.resolve(ResolutionRequest(taxonomy_code="2221")).outcome is ResolutionOutcome.INSUFFICIENT_CONTEXT
    assert r.resolve(ResolutionRequest(title="Nurse", country="ZZ")).outcome is ResolutionOutcome.UNSUPPORTED
    assert r.resolve(ResolutionRequest(title="Astronaut")).outcome is ResolutionOutcome.NOT_FOUND
    assert r.resolve(ResolutionRequest(taxonomy_scheme="isco", taxonomy_code="9999")).outcome is ResolutionOutcome.NOT_FOUND
    ok = r.resolve(ResolutionRequest(taxonomy_scheme="isco", taxonomy_code="2221", taxonomy_edition="08", country="DE"))
    assert ok.outcome is ResolutionOutcome.RESOLVED and ok.candidates[0].basis == "identifier_exact"


def test_a_code_in_several_editions_is_ambiguous_until_an_edition_is_given(world):
    world.tax.ensure("isco", "88", status="historical", acquisition_status="identified_externally", code_pattern="[0-9]{1,4}")
    world.g.add_occupation("Synthetic 08 occupation", [("isco", "08", "2512")])
    world.g.add_occupation("Synthetic 88 occupation", [("isco", "88", "2512")], occupation_key="ask4mo:occ:syn88")
    r = GraphResolver(world.g)
    assert r.resolve(ResolutionRequest(taxonomy_scheme="isco", taxonomy_code="2512")).outcome is ResolutionOutcome.AMBIGUOUS
    assert r.resolve(ResolutionRequest(taxonomy_scheme="isco", taxonomy_code="2512", taxonomy_edition="88")).candidates[0].canonical_label == "Synthetic 88 occupation"


def test_only_a_verified_equivalence_joins_same_titled_nodes_never_related_or_broader(world):
    world.reg.register("eq_src")
    a = world.g.add_occupation("Joiner", [("isco", "08", "2512")])
    b = world.g.add_occupation("Joiner", [("onet_soc", "31.0", "15-1252.00")])
    kw = dict(from_taxonomy=("isco", "08"), to_taxonomy=("onet_soc", "31.0"), basis="source_provided", source_ref="eq_src")
    world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", mapping_status="verified", **kw)
    assert GraphResolver(world.g).resolve(ResolutionRequest(title="joiner")).outcome is ResolutionOutcome.AMBIGUOUS
    world.g.supersede_relationship(a["occupation_key"], b["occupation_key"])
    world.g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="equivalent", mapping_status="verified", **kw)
    assert GraphResolver(world.g).resolve(ResolutionRequest(title="joiner")).outcome is ResolutionOutcome.RESOLVED


def test_the_resolver_never_guesses_and_has_no_language_input():
    fields = set(ResolutionRequest.__dataclass_fields__)
    assert not fields & {"language", "locale", "interface_language", "conversation_language", "ui_language"} and "country" in fields
    assert {o.value for o in ResolutionOutcome} == {"resolved", "ambiguous", "insufficient_context", "unsupported", "not_found"}


def test_known_and_legacy_keys_resolve_through_the_graph(world):
    n = world.g.add_occupation("Legacy node", [("isco", "08", "0110")], legacy_keys=["ask4mo:occ:legacy110"])
    r = GraphResolver(world.g)
    assert r.resolve(ResolutionRequest(known_occupation_keys=("ask4mo:occ:legacy110",))).candidates[0].occupation_key == n["occupation_key"]
    assert r.resolve(ResolutionRequest(known_occupation_keys=(n["occupation_key"],))).outcome is ResolutionOutcome.RESOLVED
    assert LegacyCompatibility(world.g).by_legacy_id("ask4mo:occ:legacy110")["status"] == "linked"
    assert LegacyCompatibility(world.g).by_legacy_id("ask4mo:occ:unknown")["status"] == "unresolved"


def test_legacy_native_codes_report_linked_ambiguous_or_unresolved_and_edition_knowledge(world):
    world.tax.ensure("soc", "2018", status="unknown", acquisition_status="unverified", code_pattern="[0-9]{2}-[0-9]{4}")
    world.g.add_occupation("SOC unknown edition", [("soc", "unknown", "15-1252")])
    lc = LegacyCompatibility(world.g)
    hit = lc.by_native_code("soc", "15-1252")
    assert hit["status"] == "linked" and hit["edition_known"] is False and hit["editions"] == ["unknown"]
    world.g.add_occupation("SOC 2018 edition", [("soc", "2018", "15-1252")], occupation_key="ask4mo:occ:syn-soc2018")      # a distinct node for the same code in another edition
    amb = lc.by_native_code("soc", "15-1252")
    assert amb["status"] == "ambiguous" and amb["editions"] == ["2018", "unknown"]                   # never auto-chosen
    assert lc.by_native_code("soc", "99-9999")["status"] == "unresolved"


# ======================================================================== geography coverage
def test_the_default_matrix_is_country_level_and_never_reports_targeted_as_operational():
    m = COV.build_default_matrix()
    rows = {r["code"]: r for r in m["geographies"]}
    assert len(rows) == 47 and sum(1 for r in rows.values() if r["group"] == "eu27") == 27 and {"GB", "IS", "LI", "NO", "CH", "US", "CA", "MX", "BR", "AR", "CL", "CO", "VE"} <= set(rows)
    for r in rows.values():
        assert all(r[d] in E.COVERAGE_LEVELS_ for d in ("taxonomy_level", "crosswalk_level", "compensation_level", "outlook_level"))
        assert "qualified" not in (r["taxonomy_level"], r["crosswalk_level"], r["compensation_level"], r["outlook_level"])
    assert rows["US"]["taxonomy_level"] == "implemented" and rows["US"]["compensation_level"] == "data_available" and rows["US"]["compensation_level"] != "implemented"
    assert rows["CA"]["compensation_level"] == "source_identified" and rows["CA"]["source_languages"] == [] and rows["BR"]["compensation_level"] == "targeted"
    assert rows["CL"]["compensation_level"] == "source_identified" and rows["AR"]["compensation_level"] == "targeted"
    assert E.weakest_level("implemented", "targeted", "data_available") == "targeted" and E.level_rank("bogus") == -1


def test_the_coverage_service_reports_the_weakest_dimension_and_operational_only_when_implemented(world):
    cm = COV.CoverageMatrix(world.sf)
    assert cm.seed() == 47 and cm.seed() == 47
    assert len(cm.all()) == 47
    us, de, br = cm.get("US"), cm.get("DE"), cm.get("BR")
    assert us["overall_level"] == "source_identified" and de["overall_level"] == "targeted" and br["overall_level"] == "targeted"
    assert cm.is_operational("US", "taxonomy_level") and not cm.is_operational("US", "compensation_level") and not cm.is_operational("FR", "taxonomy_level")
    assert not cm.is_operational("US", "bogus") and not cm.is_operational("XX", "taxonomy_level")
    assert cm.summary()["taxonomy_level"]["implemented"] == 2
    with pytest.raises(COV.CoverageError):
        cm.upsert("XX", "Bad", "mars")
    with pytest.raises(COV.CoverageError):
        cm.upsert("XX", "Bad", "us", taxonomy_level="excellent")


def test_coverage_language_support_describes_sources_and_never_implies_a_country(world):
    m = {r["code"]: r for r in COV.build_default_matrix()["geographies"]}
    assert m["DE"]["source_languages"] == ["en", "de"] and m["FR"]["source_languages"] == ["en"] and m["ES"]["source_languages"] == ["en"] and m["MX"]["source_languages"] == []
    # a Russian or German interface locale selects no country: the resolver and the matrix carry no locale input at all
    assert "locale" not in str(COV.CoverageMatrix.get.__code__.co_varnames) and "language" not in str(COV.CoverageMatrix.is_operational.__code__.co_varnames)


# ======================================================================== importers (synthetic fixtures)
ESCO_CSV = """conceptType,conceptUri,iscoGroup,preferredLabel,altLabels,status,code
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa,2512,synthetic software developer,,released,2512.1
Occupation,http://data.europa.eu/esco/occupation/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb,0110,synthetic naval officer,,released,0110.1
Occupation,http://data.europa.eu/esco/occupation/cccccccc-cccc-cccc-cccc-cccccccccccc,9999,synthetic invalid group,,released,9999.1
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa,2512,synthetic software developer,,released,2512.1
Occupation,http://data.europa.eu/esco/occupation/dddddddd-dddd-dddd-dddd-dddddddddddd,2512,synthetic conflicting,,released,2512.9
Occupation,http://data.europa.eu/esco/occupation/dddddddd-dddd-dddd-dddd-dddddddddddd,2511,synthetic conflicting,,released,2512.9
"""
ISCO_CSV = """ISCO_version,major,major_label,sub_major,sub_major_label,minor,minor_label,unit,description
ISCO-08,2,Professionals,25,ICT professionals,251,Software developers,2512,Software developers
ISCO-08,2,Professionals,25,ICT professionals,251,Software developers,2511,Systems analysts
ISCO-08,0,Armed forces,1,Commissioned officers,11,Commissioned officers,110,Commissioned armed forces officers
ISCO-88,2,Old,25,Old,251,Old,2512,Old synthetic
ISCO-58,0,Old,0,Old,0X,Old,0X1,Old synthetic
"""


def _csv_files(tmp_path):
    (tmp_path / "esco.csv").write_text(ESCO_CSV, encoding="utf-8")
    (tmp_path / "isco.csv").write_bytes(ISCO_CSV.encode("cp1252"))
    return tmp_path / "esco.csv", tmp_path / "isco.csv"


def test_the_isco_reader_restores_the_official_code_width_and_ignores_other_versions(tmp_path):
    _, isco = _csv_files(tmp_path)
    codes = read_isco_structure_csv(isco)
    assert set(codes) == {"2", "25", "251", "2512", "2511", "0", "01", "011", "0110"} and codes["0110"] == "Commissioned armed forces officers"
    assert "0X1" not in codes and "0X" not in codes                                                  # ISCO-58 rows never pollute the ISCO-08 authority


def test_the_esco_isco_import_is_verified_only_against_the_official_structure_and_skips_the_rest(world, tmp_path):
    esco_p, isco_p = _csv_files(tmp_path)
    world.reg.register("esco", origin="official_local")
    rows, isco = read_esco_occupations_csv(esco_p), read_isco_structure_csv(isco_p)
    rep = register_esco_isco(world.g, rows, isco)
    assert rep.esco_rows == 6 and rep.esco_nodes == 2 and rep.isco_nodes == 9 and rep.relationships_verified == 2
    assert rep.identical_duplicates == 1 and len(rep.skipped_invalid_isco) == 1 and len(rep.skipped_conflicting_duplicates) == 1
    counts = world.g.counts()
    assert register_esco_isco(world.g, rows, isco).esco_nodes == 2 and world.g.counts() == counts                       # idempotent
    navy = world.g.find_by_identifier("esco", "http://data.europa.eu/esco/occupation/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")[0]
    rel = world.g.relationships(navy["occupation_key"])[0]
    assert rel["relationship_type"] == "broader" and rel["mapping_status"] == "verified" and rel["basis"] == "source_provided" and rel["qualification_status"] == "engineering_checked"
    assert world.g.find_by_identifier("isco", "0110", "08") and not world.g.find_by_identifier("isco", "110")                  # padded code is the identity
    assert world.g.find_by_legacy_key(__import__("src.copilot.knowledge.canonical", fromlist=["x"]).canonical_occupation_id(isco_code="110"))      # legacy stripped identity still resolves
    assert world.g.find_by_legacy_key(__import__("src.copilot.knowledge.canonical", fromlist=["x"]).canonical_occupation_id(esco_uri="2512.1"))   # legacy ESCO identity (derived from the dotted code)


def test_an_unregistered_esco_source_makes_the_whole_import_roll_back(world, tmp_path):
    esco_p, isco_p = _csv_files(tmp_path)
    rows, isco = read_esco_occupations_csv(esco_p), read_isco_structure_csv(isco_p)
    with pytest.raises(GraphError):
        register_esco_isco(world.g, rows, isco, esco_source_ref="not_registered")
    assert world.g.counts() == {"occupations": 0, "identifiers": 0, "relationships": 0}


def test_the_legacy_store_assessment_is_read_only_and_classifies_every_stored_mapping(world, tmp_path):
    from src.copilot.knowledge.canonical import canonical_occupation_id as cid
    esco_p, isco_p = _csv_files(tmp_path)
    rows, isco = read_esco_occupations_csv(esco_p), read_isco_structure_csv(isco_p)
    db = tmp_path / "roles.db"
    con = sqlite3.connect(db)
    con.executescript("create table occupations (occupation_code text, source_id text); create table occupation_mappings (occupation_code text, scheme text, code text, source_id text);")
    con.executemany("insert into occupation_mappings values (?,?,?,?)", [(cid(esco_uri="2512.1"), "isco", "2512", "esco"), (cid(esco_uri="0110.1"), "isco", "110", "esco"),
                                                                       (cid(esco_uri="9999.1"), "isco", "2511", "esco"), ("ask4mo:occ:unknown", "isco", "2512", "esco")])
    con.commit(); con.close()
    before = db.read_bytes()
    out = assess_legacy_store_mappings(db, rows, isco)
    assert (out["exact"], out["leading_zero_lost"], out["mismatch"], out["no_official_row"]) == (1, 1, 1, 1) and out["leading_zero_lost_codes"] == ["110->0110"]
    assert db.read_bytes() == before


# ======================================================================== GKB-0 baseline
def _fixture_data_root(tmp_path):
    root = tmp_path / "repo"
    (root / "data/knowledge").mkdir(parents=True)
    (root / "data/normalized").mkdir(parents=True)
    (root / "data/raw").mkdir()
    (root / "evaluations/product_coverage").mkdir(parents=True)
    raw = root / "data/raw/oesm25.xlsx"
    raw.write_bytes(b"synthetic raw bytes")
    import hashlib
    (root / "data/source_manifest.json").write_text(json.dumps({"sources": [{"source_id": "bls_oews", "source_type": "compensation_dataset", "manual_acquisition_required": False},
                                                                           {"source_id": "esco", "source_type": "occupation_taxonomy"}, {"source_id": "manual_one", "source_type": "x", "manual_acquisition_required": True}]}))
    (root / "data/source_status.json").write_text(json.dumps({"sources": []}))
    (root / "data/knowledge/data_origins.json").write_text(json.dumps({"origins": {"bls_oews": ["official_local"], "esco": ["official_local"]}}))
    (root / "data/normalized/build_metadata.json").write_text(json.dumps({"pipeline_version": "t1", "git_commit": None, "built_at": "2026-01-01T00:00:00Z", "source_versions": {"bls_oews": "M2025", "esco": "current release"},
                                                                          "source_checksums": [{"algorithm": "sha256", "relative_path": "data/raw/oesm25.xlsx", "hash": hashlib.sha256(b"synthetic raw bytes").hexdigest()}]}))
    (root / "data/normalized/canonicalization_report.json").write_text(json.dumps({"pipeline_version": "t1", "record_counts": {"occupations": 1}, "per_source": {}}))
    (root / "evaluations/product_coverage/cases.json").write_text(json.dumps({"cases": [{"id": "x"}]}))
    for n in B.STORES:
        con = sqlite3.connect(root / "data/knowledge" / n)
        con.execute("create table t (a text)")
        con.execute("insert into t values ('x')")
        con.commit(); con.close()
    return root


def test_the_baseline_is_read_only_deterministic_and_content_free(tmp_path):
    root = _fixture_data_root(tmp_path)
    snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    first = B.build_baseline(root)
    second = B.build_baseline(root)
    assert first == second and {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == snapshot          # nothing was written or modified
    assert first["source_manifest"]["count"] == 3 and first["runtime_stores"]["roles.db"]["tables"] == {"t": 1} and first["evaluation_fixtures"]["product_coverage_cases"]["cases"] == 1
    assert "synthetic raw bytes" not in json.dumps(first)


def test_the_reproducibility_verdicts_never_claim_more_than_the_evidence(tmp_path):
    root = _fixture_data_root(tmp_path)
    per = {v["source_id"]: v for v in B.build_baseline(root)["reproducibility"]["per_source"]}
    assert per["bls_oews"]["verdict"] == "reproducible" and per["bls_oews"]["gaps"] == []
    assert per["esco"]["verdict"] == "partially_reproducible" and "no raw checksum recorded" in per["esco"]["gaps"]      # built, but no recorded raw checksum and an unpinned version
    assert per["manual_one"]["verdict"] == "not_reproducible" and "manual acquisition required" in per["manual_one"]["gaps"]
    assert B.reproducibility_verdict("x", built=True, version="current release", checksums=[{"present": True, "match": True}], manual=False)["verdict"] == "partially_reproducible"
    assert B.reproducibility_verdict("x", built=True, version="2025", checksums=[{"present": True, "match": False}], manual=False)["verdict"] == "not_reproducible"
    assert B.reproducibility_verdict("x", built=True, version="2025", checksums=[{"present": False, "match": False}], manual=False)["verdict"] == "not_reproducible"
    assert B.reproducibility_verdict("x", built=True, version="2025", checksums=[], manual=False)["verdict"] == "partially_reproducible"


def test_an_altered_raw_input_is_detected(tmp_path):
    root = _fixture_data_root(tmp_path)
    (root / "data/raw/oesm25.xlsx").write_bytes(b"tampered")
    b = B.build_baseline(root)
    assert b["build"]["verified_present"] == 1 and b["build"]["verified_match"] == 0
    assert {v["source_id"]: v for v in b["reproducibility"]["per_source"]}["bls_oews"]["verdict"] == "not_reproducible"


def test_the_committed_baseline_manifest_is_consistent_with_the_registry_seed():
    base = json.loads((ROOT / "docs/capstone/p10/p10c_a/GKB0_BASELINE_MANIFEST.json").read_text())
    ids = {s["source_id"] for s in json.loads(BASELINE_PATH.read_text())["sources"]}
    assert {v["source_id"] for v in base["reproducibility"]["per_source"]} == ids
    assert base["runtime_stores"]["roles.db"]["tables"]["occupations"] == 8035 and base["runtime_stores"]["roles.db"]["tables"]["occupation_aliases"] == 23579
    assert base["runtime_stores"]["roles.db"]["tables"]["occupation_mappings"] == 3039 and base["runtime_stores"]["compensation.db"]["tables"]["compensation_records"] == 1913
    assert base["build"]["verified_match"] == base["build"]["recorded_raw_checksums"] == 13 and base["vector_store"]["total_chunks"] == 14087 and base["evaluation_fixtures"]["product_coverage_cases"]["cases"] == 412


def _script(*args, cwd):
    import subprocess, sys
    return subprocess.run([sys.executable, str(ROOT / "scripts/gkb0_baseline.py"), *args], capture_output=True, text=True, cwd=cwd)


def _snapshot(root):
    return sorted((str(p.relative_to(root)), p.is_dir() or p.stat().st_size) for p in root.rglob("*"))


def test_the_baseline_script_refuses_protected_outputs_on_a_clean_checkout(tmp_path):
    """A clean checkout has NO local knowledge files: the destination is rejected (exit 2) before any data is read, and nothing is created."""
    root = tmp_path / "clean"
    (root / "data").mkdir(parents=True)
    (root / "evaluations").mkdir()
    (root / "outside").mkdir()
    (root / "alias").symlink_to(root / "data", target_is_directory=True)
    (root / "evalalias").symlink_to(root / "evaluations", target_is_directory=True)
    assert not (root / "data/knowledge/data_origins.json").exists()
    before = _snapshot(root)
    bad = ["data/x.json", "evaluations/x.json", "data/nested/x.json", "evaluations/nested/x.json", "outside/../data/x.json", "outside/../evaluations/y.json", "data/../data/x.json",
           "alias/x.json", "evalalias/nested/x.json", str(root / "data/abs.json"), str(root / "evaluations/abs.json"), str(root / "outside/../data/abs2.json")]
    for target in bad:
        r = _script("--root", str(root), "--out", target, cwd=root)
        assert r.returncode == 2 and "refusing" in r.stderr and "Traceback" not in r.stderr, (target, r.stderr[-300:])
    assert _snapshot(root) == before                                                          # no file or directory created anywhere


def test_the_baseline_script_with_a_permitted_output_and_missing_data_fails_in_a_controlled_way(tmp_path):
    root = tmp_path / "clean"
    (root / "data").mkdir(parents=True)
    r = _script("--root", str(root), "--out", str(tmp_path / "elsewhere/baseline.json"), cwd=root)
    assert r.returncode == 3 and "required local knowledge data is missing" in r.stderr and "Traceback" not in r.stderr
    assert not (tmp_path / "elsewhere").exists() and _snapshot(root) == [("data", True)]     # nothing fabricated, nothing partial written


def test_the_baseline_script_still_works_on_a_fixture_with_a_permitted_output(tmp_path):
    root = _fixture_data_root(tmp_path)
    out = tmp_path / "out/baseline.json"
    r = _script("--root", str(root), "--out", str(out), cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-300:]
    assert json.loads(out.read_text())["source_manifest"]["count"] == 3


# ======================================================================== isolation, gates, migration
def test_the_foundation_is_not_imported_by_any_candidate_facing_or_runtime_module():
    offenders = []
    for pkg in ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents"):
        for f in (ROOT / pkg).rglob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
    for rel in ("src/copilot/knowledge/compensation.py", "src/copilot/knowledge/retrieval.py", "src/copilot/knowledge/router.py"):
        assert "knowledge_foundation" not in (ROOT / rel).read_text()                                    # current salary retrieval is untouched


def test_the_legacy_compensation_retrieval_and_hard_coded_precedence_are_unchanged():
    from src.copilot import constants
    assert constants.COUNTRY_SOURCE_PRIORITY["US"][:3] == ["onet", "bls_ooh", "bls_oews"] and set(constants.COUNTRY_SOURCE_PRIORITY) == {"DE", "US", "UK", "EU"}
    from src.copilot.knowledge.router import detect_country
    assert detect_country("what does a nurse earn in germany") == "DE" and detect_country("was verdient eine pflegekraft") is None          # language never implies a country


def test_all_rollout_and_billing_gates_stay_off_and_no_compensation_v2_exists():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, g) is False
    import src.copilot.knowledge.compensation as comp
    assert not hasattr(comp, "CompensationRecordV2")
    assert not hasattr(__import__("src.persistence", fromlist=["x"]), "CompensationRecordV2")


def test_no_foundation_module_downloads_or_calls_a_provider():
    banned = {"requests", "httpx", "urllib", "urllib.request", "stripe", "openai", "boto3", "aiohttp"}
    for f in (ROOT / "src/knowledge_foundation").glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & banned, (f.name, mods & banned)


def test_migration_0035_is_additive_reversible_and_matches_the_orm(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    from src import persistence as P
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0035_knowledge_foundation"]
    new = ("global_sources", "global_source_events", "occupation_taxonomies", "graph_occupations", "graph_occupation_identifiers", "graph_occupation_relationships", "geography_coverage")
    command.upgrade(cfg, "0034_preparation_packs")
    assert not set(new) & set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert set(new) <= set(insp.get_table_names())
    for t in new:
        model = next(m for m in P.Base.metadata.tables.values() if m.name == t)
        assert {c["name"] for c in insp.get_columns(t)} == {c.name for c in model.columns}, t
    assert any(u["name"] == "uq_graph_identifier" for u in insp.get_unique_constraints("graph_occupation_identifiers"))
    assert any(u["name"] == "uq_occupation_taxonomy" for u in insp.get_unique_constraints("occupation_taxonomies"))
    command.downgrade(cfg, "0034_preparation_packs")
    after = inspect(create_engine(url))
    assert not set(new) & set(after.get_table_names()) and "preparation_packs" in after.get_table_names() and "opportunities" in after.get_table_names()
    command.upgrade(cfg, "head")


def test_the_migration_seeds_nothing(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    with create_engine(url).connect() as c:
        for t in ("global_sources", "occupation_taxonomies", "graph_occupations", "graph_occupation_identifiers", "graph_occupation_relationships", "geography_coverage"):
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
