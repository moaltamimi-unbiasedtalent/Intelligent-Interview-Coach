"""P10C-B: multilingual occupation aliases (GKB-3), multilingual ESCO adapter contract (GKB-4), deterministic internal resolver (GKB-13). FULLY OFFLINE: throwaway SQLite databases and
the committed SYNTHETIC fixture corpus (codes 99xx, synthetic-fixture sources, test-string aliases). Nothing here is official terminology, an official mapping or salary evidence, and
nothing is imported by a candidate-facing path or changes a gate."""

from __future__ import annotations

import ast
import json
import sqlite3
import time
import tracemalloc
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.copilot.knowledge.canonical import canonical_occupation_id as cid
from src.knowledge_foundation import normalize as N
from src.knowledge_foundation.aliases import AliasError, AliasStore
from src.knowledge_foundation.codes import isco_padding_candidates, restore_isco_zero_padding
from src.knowledge_foundation.coverage import CoverageMatrix
from src.knowledge_foundation.esco_adapter import (SourceNotApproved, EscoLabelRow, import_esco_labels, import_legacy_aliases, language_from_filename, plan_esco_labels,
                                                    read_esco_labels_csv, read_legacy_aliases)
from src.knowledge_foundation.fixtures import CORPUS_PATH, evaluate_cases, load_corpus, load_into
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.importers import assess_legacy_store_mappings, read_esco_occupations_csv, read_isco_structure_csv, register_esco_isco
from src.knowledge_foundation.language_coverage import LanguageCoverageError, LanguageCoverageService
from src.knowledge_foundation.legacy import LegacyIdentityAdapter
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver, ResolutionOutcome
from src.knowledge_foundation.qualification import qualify_relationship, summarize_qualification
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
from src.persistence import GraphOccupationAlias, init_db, make_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture()
def sf(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'kf.db'}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture()
def w(sf):
    tax = TaxonomyCatalogue(sf)
    tax.seed()
    reg = SourceRegistry(sf)
    reg.register("fx", origin="synthetic_fixture")
    reg.register("off", origin="official_local")
    reg.register("unk")                                                      # origin unknown
    g, a = OccupationGraph(sf), AliasStore(sf)
    n1 = g.add_occupation("Synthetic occupation one", [("isco", "08", "9901")])
    n2 = g.add_occupation("Synthetic occupation two", [("isco", "08", "9902")])
    return NS(sf=sf, tax=tax, reg=reg, g=g, a=a, k1=n1["occupation_key"], k2=n2["occupation_key"])


@pytest.fixture()
def corpus_world(sf):
    keys = load_into(sf)
    cm, lc = CoverageMatrix(sf), LanguageCoverageService(sf)
    cm.seed()
    lc.seed()
    reg, g, a = SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    return NS(sf=sf, keys=keys, cm=cm, lc=lc, reg=reg, g=g, a=a, r=OccupationResolver(g, a, coverage=cm, language_coverage=lc, registry=reg))


# ====================================================================================================================================== normalization
@pytest.mark.parametrize("raw,expected", [
    ("  Software-Entwickler/in ", "software entwickler in"), ("C++ Developer", "c++ developer"), ("C# developer", "c# developer"), (".NET Developer", ".net developer"),
    ("Node.js", "node.js"), ("Sr. Engineer", "sr engineer"), ("R&D Manager", "r&d manager"), ("Straße", "strasse"), ("ÉCOLE Primaire", "école primaire"),
    ("Инженер-механик", "инженер механик"), ("Ёж", "ёж"), ("ＡＢＣ", "abc"), ("Año", "año"),
])
def test_normalization_rules(raw, expected):
    assert N.normalize_label(raw) == expected and N.normalize_label(N.normalize_label(raw)) == expected                       # idempotent


def test_normalization_collisions_distinct_occupations_are_not_merged():
    n = N.normalize_label
    assert len({n("C"), n("C++"), n("C#")}) == 3 and n("año") != n("ano") and n("майор") != n("маиор")                       # й is not folded to и
    assert N.fold_label(n("Año")) == N.fold_label(n("Ano")) == "ano"                                                         # the tolerant key does fold Latin diacritics
    assert N.fold_label(n("майор")) == "майор" and N.fold_label(n("Ёж")) == "ёж"                                              # Cyrillic is never folded
    assert n("Softwareentwickler") != n("Software Entwickler")                                                               # no compound splitting
    assert n("Pfleger/in") != n("Pfleger") and n("QA") == "qa"                                                               # no gender or abbreviation expansion
    assert N.normalize_label("--") == "" and N.normalize_label("") == ""


def test_the_original_text_is_never_replaced_and_keys_are_versioned(w):
    r = w.a.add_alias(w.k1, "  Ärztin/Arzt  ", language="de", language_basis="curated_manual", alias_type="recognized_title")
    assert r["alias_text"] == "Ärztin/Arzt" and r["normalized_text"] == "ärztin arzt" and r["folded_text"] == "arztin arzt" and r["normalization_version"] == N.NORMALIZATION_VERSION
    assert r["script"] == "Latn" and N.detect_script("Инженер") == "Cyrl" and N.detect_script("123") is None and N.detect_script("abc абв") == "Zzzz"


def test_language_tags_are_independent_of_the_ui_locale_list():
    assert N.normalize_language_tag("DE_ch") == "de-ch" and N.normalize_language_tag(None) == "und" and N.normalize_language_tag("pl") == "pl" and N.normalize_language_tag("zh-Hans") == "zh-Hans"
    with pytest.raises(ValueError):
        N.normalize_language_tag("not a language!")


# ====================================================================================================================================== alias model
def test_a_new_alias_has_unknown_language_and_is_unqualified(w):
    r = w.a.add_alias(w.k1, "Some label")
    assert r["language"] == "und" and r["language_basis"] == "unknown" and r["qualification_status"] == "unqualified" and r["alias_type"] == "unknown" and r["evidence_eligible_origin"] is False


def test_language_is_never_guessed(w):
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", language="en")                                             # a known language must state its basis
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", language_basis="source_declared", source_ref="off")        # a basis needs a language
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", language="en", language_basis="source_declared")           # a source-based basis needs a source
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", language="en", language_basis="fixture_declared", source_ref="off")      # fixture-declared needs a synthetic source
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", language="!!", language_basis="curated_manual")
    for lang in ("pl", "zh-Hans", "ru"):                                                    # any language is representable, not only the eight UI locales
        assert w.a.add_alias(w.k1, f"label {lang}", language=lang, language_basis="curated_manual")["language"] == lang


def test_an_official_alias_needs_a_registered_source_with_a_known_origin(w):
    for bad in ("", "not_registered", "unk"):
        with pytest.raises(AliasError):
            w.a.add_alias(w.k1, "Official one", language="en", language_basis="curated_manual", alias_type="official_preferred", source_ref=bad)
    ok = w.a.add_alias(w.k1, "Official one", language="en", language_basis="source_declared", alias_type="official_preferred", source_ref="off")
    assert ok["alias_type"] == "official_preferred" and ok["qualification_status"] == "unqualified"        # official type is not qualification


def test_a_synthetic_fixture_alias_is_stored_but_never_evidence_eligible(w):
    r = w.a.add_alias(w.k1, "Fixture label", language="en", language_basis="fixture_declared", alias_type="official_preferred", source_ref="fx")
    assert r["source_origin"] == "synthetic_fixture" and r["evidence_eligible_origin"] is False
    with pytest.raises(AliasError):
        w.a.set_qualification(r["id"], "qualified", actor_user_id=1)                        # a fixture can never be qualified


def test_the_database_enforces_alias_rules_independently(w, sf):
    from src.persistence import GraphOccupation
    with sf() as s:
        oid = s.scalar(select(GraphOccupation.id).limit(1))
        base = dict(occupation_id=oid, alias_text="x", normalized_text="x", folded_text="x", normalization_version="n1", context_terms=[], provenance={})
        for bad in ({"language": "en", "language_basis": "unknown"}, {"language": "und", "language_basis": "source_declared"},
                    {"alias_type": "official_preferred", "source_ref": ""}, {"alias_type": "made_up"}, {"qualification_status": "bogus"}):
            s.add(GraphOccupationAlias(**{**base, **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_uniqueness_never_forces_distinct_occupations_to_merge(w):
    w.a.add_alias(w.k1, "Developer", language="en", language_basis="curated_manual", alias_type="recognized_title")
    w.a.add_alias(w.k2, "Developer", language="en", language_basis="curated_manual", alias_type="recognized_title")           # shared alias is legal
    w.a.add_alias(w.k1, "Programmer", language="en", language_basis="curated_manual", alias_type="recognized_title")          # several aliases, one language
    again = w.a.add_alias(w.k1, "developer", language="en", language_basis="curated_manual", alias_type="recognized_title")  # idempotent on the normalized key
    assert again["alias_text"] == "Developer" and w.a.counts()["aliases"] == 3
    w.a.add_alias(w.k1, "Developer", language="de", language_basis="curated_manual", alias_type="recognized_title")           # same text, other language: separate row
    w.a.add_alias(w.k1, "Developer", language="en", language_basis="curated_manual", alias_type="recognized_title", taxonomy=("isco", "08"))     # other edition: separate row
    assert w.a.counts()["aliases"] == 5 and w.a.counts()["by_language"] == {"de": 1, "en": 4}
    assert w.a.shared_aliases() == [{"normalized_text": "developer", "language": "en", "occupations": 2}]
    assert w.a.conflicts() == []                                                           # sharing is not an official conflict


def test_one_source_edition_stating_one_official_label_for_two_occupations_is_a_reported_conflict(w):
    for k in (w.k1, w.k2):
        w.a.add_alias(k, "Same official label", language="en", language_basis="source_declared", alias_type="official_preferred", source_ref="off", taxonomy=("isco", "08"))
    assert w.a.conflicts() == [{"source_ref": "off", "edition_ref": "isco@08", "normalized_text": "same official label", "language": "en", "occupations": 2}]


def test_qualification_needs_a_reviewer_a_genuine_source_and_is_audited(w):
    a = w.a.add_alias(w.k1, "Qualifiable", language="en", language_basis="source_declared", alias_type="official_preferred", source_ref="off")
    with pytest.raises(AliasError):
        w.a.set_qualification(a["id"], "qualified", actor_user_id=None)
    with pytest.raises(AliasError):
        w.a.set_qualification(a["id"], "bogus", actor_user_id=1)
    assert w.a.set_qualification(a["id"], "engineering_checked", actor_user_id=None)["qualification_status"] == "engineering_checked"
    assert w.a.set_qualification(a["id"], "qualified", actor_user_id=7)["qualification_status"] == "qualified"
    hist = w.a.aliases_for(w.k1)[0]
    assert hist["qualification_status"] == "qualified"
    with w.sf() as s:
        row = s.get(GraphOccupationAlias, a["id"])
        assert [h["to"] for h in row.provenance["qualification_history"]] == ["engineering_checked", "qualified"]
    unk = w.a.add_alias(w.k1, "From unknown source", language_basis=None, source_ref="unk")
    with pytest.raises(AliasError):
        w.a.set_qualification(unk["id"], "qualified", actor_user_id=7)


def test_alias_input_validation(w):
    for bad in ("", "   ", "--", "x" * 301):
        with pytest.raises(AliasError):
            w.a.add_alias(w.k1, bad)
    with pytest.raises(AliasError):
        w.a.add_alias("ask4mo:occ:missing", "x")
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", alias_type="made_up")
    with pytest.raises(AliasError):
        w.a.add_alias(w.k1, "x", taxonomy=("isco", "1999"))


def test_alias_lookup_is_index_backed(w, sf):
    w.a.add_alias(w.k1, "Indexed", language="en", language_basis="curated_manual")
    with sf() as s:
        plan = " ".join(r[3] for r in s.execute(text("EXPLAIN QUERY PLAN SELECT id FROM graph_occupation_aliases WHERE normalized_text = 'indexed' AND language = 'en'")))
        plan2 = " ".join(r[3] for r in s.execute(text("EXPLAIN QUERY PLAN SELECT id FROM graph_occupation_aliases WHERE folded_text = 'indexed'")))
    assert "ix_graph_alias_normalized" in plan and "ix_graph_alias_folded" in plan2 and "SCAN" not in plan.replace("SCAN graph_occupation_aliases USING", "")


# ====================================================================================================================================== language coverage
def test_language_coverage_keeps_ui_taxonomy_alias_and_resolver_support_separate(sf):
    lc = LanguageCoverageService(sf)
    assert lc.seed() == 8 and lc.seed() == 8
    rows = {r["language"]: r for r in lc.all()}
    assert set(rows) == {"en", "de", "fr", "es", "it", "pt", "nl", "ru"} and all(r["ui_supported"] for r in rows.values())
    assert rows["en"]["alias_data_level"] == "data_available" and rows["de"]["taxonomy_level"] == "data_available" and rows["de"]["alias_data_level"] == "source_identified"
    for lang in ("fr", "es", "it", "pt", "nl", "ru"):
        assert rows[lang]["taxonomy_level"] == "targeted" and rows[lang]["alias_data_level"] == "targeted"                    # a UI locale establishes no occupation data
    assert "NOT assumed" in rows["ru"]["limitations"] and rows["ru"]["source_ids"] == []
    assert not any(r["alias_qualified"] for r in rows.values()) and not any("qualified" in (r["taxonomy_level"], r["alias_data_level"], r["resolver_level"]) for r in rows.values())
    assert all(lc.resolver_supports(lang) for lang in rows) and not lc.resolver_supports("pl") and not lc.resolver_supports(None) and not lc.resolver_supports("!!")
    assert lc.summary()["alias_qualified"] == 0 and lc.summary()["ui_supported"] == 8


def test_a_non_ui_language_can_be_covered_and_nothing_can_claim_qualified(sf):
    lc = LanguageCoverageService(sf)
    lc.upsert("pl", "Polish", ui_supported=False, alias_data_level="source_identified", resolver_level="implemented")
    assert lc.get("pl")["ui_supported"] is False and lc.resolver_supports("pl")
    for bad in ({"taxonomy_level": "qualified"}, {"alias_qualified": True}, {"resolver_level": "excellent"}):
        with pytest.raises(LanguageCoverageError):
            lc.upsert("pl", "Polish", **bad)
    with pytest.raises(LanguageCoverageError):
        lc.upsert("und", "Unknown")
    assert "country" not in LanguageCoverageService.get.__code__.co_varnames and "geography_code" not in {c.name for c in __import__("src.persistence", fromlist=["x"]).LanguageCoverage.__table__.columns}


def test_language_coverage_and_country_coverage_are_independent_tables(sf):
    cm, lc = CoverageMatrix(sf), LanguageCoverageService(sf)
    cm.seed()
    lc.seed()
    us, de = cm.get("US"), cm.get("DE")
    assert us["compensation_level"] == "data_available" and lc.get("en")["alias_data_level"] == "data_available"
    assert de["source_languages"] == ["en", "de"] and lc.get("ru")["resolver_level"] == "implemented" and cm.get("MX")["source_languages"] == []          # languages and countries do not imply each other


# ====================================================================================================================================== ISCO leading zeros
def _legacy_zero_world(tmp_path, sf):
    """A synthetic ESCO file whose 21 occupations map to the three Armed Forces unit groups (7 each), as in the real store's 21 stripped codes."""
    rows = ["conceptType,conceptUri,iscoGroup,preferredLabel,altLabels,status,code"]
    n = 0
    for code in ("0110", "0210", "0310"):
        for i in range(7):
            n += 1
            rows.append(f"Occupation,http://data.europa.eu/esco/occupation/bbbbbbbb-0000-0000-0000-{n:012d},{code},synthetic armed forces {n},,released,{code}.{i}")
    esco = tmp_path / "esco.csv"
    esco.write_text("\n".join(rows) + "\n", encoding="utf-8")
    isco = tmp_path / "isco.csv"
    isco.write_bytes(("ISCO_version,major,major_label,sub_major,sub_major_label,minor,minor_label,unit,description\n"
                      "ISCO-08,0,Armed forces,1,Commissioned,11,Commissioned officers,110,Commissioned armed forces officers\n"
                      "ISCO-08,0,Armed forces,2,Non-commissioned,21,Non-commissioned officers,210,Non-commissioned armed forces officers\n"
                      "ISCO-08,0,Armed forces,3,Other ranks,31,Other ranks,310,Armed forces occupations, other ranks\n").encode("cp1252"))
    SourceRegistry(sf).register("esco", origin="official_local")
    g = OccupationGraph(sf)
    TaxonomyCatalogue(sf).seed()
    erows, official = read_esco_occupations_csv(esco), read_isco_structure_csv(isco)
    register_esco_isco(g, erows, official)
    return g, erows, official


def test_all_21_stripped_isco_codes_are_assessed_and_restored_without_rewriting_the_legacy_store(tmp_path, sf):
    g, erows, official = _legacy_zero_world(tmp_path, sf)
    db = tmp_path / "roles.db"
    con = sqlite3.connect(db)
    con.executescript("create table occupations (occupation_code text, source_id text); create table occupation_mappings (occupation_code text, scheme text, code text, source_id text);")
    stripped = {"0110": "110", "0210": "210", "0310": "310"}
    con.executemany("insert into occupation_mappings values (?,?,?,?)", [(cid(esco_uri=f"{r.isco_code}.{i % 7}"), "isco", stripped[r.isco_code], "esco") for i, r in enumerate(erows)])
    con.commit()
    con.close()
    before = db.read_bytes()
    out = assess_legacy_store_mappings(db, erows, official)
    assert out["leading_zero_lost"] == 21 and out["mismatch"] == 0 and sorted(set(out["leading_zero_lost_codes"])) == ["110->0110", "210->0210", "310->0310"]
    assert db.read_bytes() == before                                                                       # the legacy store is untouched
    r = OccupationResolver(g, AliasStore(sf))
    for official_code, raw in stripped.items():
        res = r.resolve(MultilingualRequest(taxonomy_scheme="isco", taxonomy_code=raw, taxonomy_edition="08"))
        assert res.outcome is ResolutionOutcome.RESOLVED and res.candidates[0].grade == "code_zero_padding_restored" and res.warnings == [f"isco_zero_padding_restored:{raw}->{official_code}"]
        assert g.find_by_identifier("isco", official_code, "08")[0]["occupation_key"] == res.candidates[0].occupation_key and not g.find_by_identifier("isco", raw, "08")


def test_zero_padding_is_restored_only_against_the_authority_and_never_invented():
    ex = {"0110", "0210", "011", "0011"}.__contains__
    assert restore_isco_zero_padding("110", ex) == ("0110", "zero_padding_restored") and restore_isco_zero_padding("0110", ex) == ("0110", "exact")
    assert restore_isco_zero_padding("999", ex) == (None, "not_found") and restore_isco_zero_padding("abc", ex) == (None, "invalid_format") and restore_isco_zero_padding(None, ex) == (None, "invalid_format")
    assert restore_isco_zero_padding("11", ex) == (None, "ambiguous_padding")                              # 011 and 0011 both exist: never guessed
    assert restore_isco_zero_padding("110", {"110", "0110"}.__contains__) == ("110", "exact")                # a real official code is never "corrected"
    assert isco_padding_candidates("110") == ["0110"] and isco_padding_candidates("0110") == [] and isco_padding_candidates("1x") == []


def test_codes_are_strings_and_zero_padding_is_preserved(sf):
    g = OccupationGraph(sf)
    TaxonomyCatalogue(sf).seed()
    n = g.add_occupation("Zero code", [("isco", "08", "0110")], legacy_keys=[cid(isco_code="110")])
    assert g.identifiers(n["occupation_key"])[0]["native_code"] == "0110" and g.find_by_legacy_key(cid(isco_code="110"))["occupation_key"] == n["occupation_key"]


def test_a_default_identity_never_silently_merges_two_editions_of_one_scheme(sf):
    tax, g = TaxonomyCatalogue(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("isco", "88", status="historical", acquisition_status="identified_externally", code_pattern="[0-9]{1,4}")
    a = g.add_occupation("Edition 08", [("isco", "08", "9912")])
    b = g.add_occupation("Edition 88", [("isco", "88", "9912")])
    assert a["occupation_key"] != b["occupation_key"] and g.counts()["occupations"] == 2
    assert [h["edition"] for h in g.find_by_identifier("isco", "9912")] == ["08", "88"]


# ====================================================================================================================================== relationship qualification
def test_relationship_qualification_keeps_five_questions_distinct(w):
    w.reg.register("lic", origin="official_local", validation_status="unvalidated")
    g, kw = w.g, dict(from_taxonomy=("isco", "08"), to_taxonomy=("isco", "08"))
    k3 = g.add_occupation("Synthetic three", [("isco", "08", "9903")])["occupation_key"]
    k4 = g.add_occupation("Synthetic four", [("isco", "08", "9904")])["occupation_key"]
    curated = g.add_relationship(w.k1, w.k2, relationship_type="related", basis="curated_manual", mapping_status="unknown", limitations="test", **kw)
    q = qualify_relationship(curated, w.reg)
    assert q["structurally_valid"] and not q["source_linked"] and q["highest_level"] == "structurally_valid" and not q["operationally_approved"]
    fixture = g.add_relationship(w.k1, k3, relationship_type="broader", basis="source_provided", mapping_status="verified", source_ref="fx", **kw)
    q = qualify_relationship(fixture, w.reg)
    assert q["source_linked"] and not q["official_source_provided"] and q["highest_level"] == "source_linked"                    # VERIFIED against a fixture is not official
    official = g.add_relationship(w.k1, k4, relationship_type="broader", basis="source_provided", mapping_status="verified", source_ref="lic", **kw)
    q = qualify_relationship(official, w.reg)
    assert q["official_source_provided"] and not q["independently_reviewed"] and not q["licensed_for_runtime"] and not q["operationally_approved"] and q["highest_level"] == "official_source_provided"
    assert q["mapping_status"] == "verified" and q["qualification_status"] == "unqualified"                                       # VERIFIED is not operational approval
    summary = summarize_qualification([curated, fixture, official], w.reg)
    assert summary["relationships"] == 3 and summary["reached"]["operationally_approved"] == 0 and summary["reached"]["official_source_provided"] == 1


def test_a_relationship_is_operational_only_with_review_and_a_runtime_approved_licensed_source(w):
    w.reg.register("run", origin="official_local", validation_status="unvalidated")
    w.reg.set_licence("run", licence_id="PD", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use"):
        w.reg.transition("run", step)
    kw = dict(from_taxonomy=("isco", "08"), to_taxonomy=("isco", "08"))
    rel = w.g.add_relationship(w.k1, w.k2, relationship_type="broader", basis="source_provided", mapping_status="verified", source_ref="run", qualification_status="engineering_checked", **kw)
    assert qualify_relationship(rel, w.reg)["operationally_approved"] is False and qualify_relationship(rel, w.reg)["licensed_for_runtime"] is True
    assert qualify_relationship({**rel, "qualification_status": "qualified"}, w.reg)["operationally_approved"] is True
    assert qualify_relationship({**rel, "qualification_status": "qualified", "mapping_status": "partial"}, w.reg)["operationally_approved"] is False
    assert qualify_relationship({**rel, "qualification_status": "qualified", "superseded": True}, w.reg)["structurally_valid"] is False


# ====================================================================================================================================== ESCO adapter
ESCO_ES = """conceptType,conceptUri,iscoGroup,preferredLabel,altLabels,hiddenLabels,status,code
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000001,2512,desarrollador de software de prueba,"programador de prueba
analista programador de prueba",termino oculto de prueba,released,2512.1
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000001,2512,desarrollador de software de prueba,,,released,2512.1
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000002,0110,oficial de prueba,,,released,0110.1
Occupation,http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000099,9999,sin nodo de prueba,,,released,9999.1
Skill,http://data.europa.eu/esco/skill/x,,not an occupation,,,released,
"""


def _esco_world(tmp_path, sf, source_origin="synthetic_fixture"):
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    reg.register("esco_es_fx", origin=source_origin)
    a = g.add_occupation("Synthetic ESCO occupation A", [("esco", "1.2.1", "http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000001")])
    b = g.add_occupation("Synthetic ESCO occupation B", [("esco", "1.2.1", "http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000002")])
    f = tmp_path / "occupations_es.csv"
    f.write_text(ESCO_ES, encoding="utf-8")
    return NS(tax=tax, reg=reg, g=g, a=AliasStore(sf), ka=a["occupation_key"], kb=b["occupation_key"], rows=read_esco_labels_csv(f), file=f)


def test_the_esco_label_reader_keeps_isco_digits_and_language_comes_from_the_file_name(tmp_path, sf):
    e = _esco_world(tmp_path, sf)
    assert len(e.rows) == 4 and e.rows[0].alternatives == ("programador de prueba", "analista programador de prueba") and e.rows[0].hidden == ("termino oculto de prueba",)
    assert e.rows[2].isco_group == "0110" and language_from_filename(e.file) == "es" and language_from_filename("occupations_pt-BR.csv") == "pt-BR" and language_from_filename("x.csv") is None


def test_planning_is_read_only_and_needs_no_approval(tmp_path, sf):
    e = _esco_world(tmp_path, sf, source_origin="official_local")                                # licensing-pending real-origin source
    before = e.a.counts()
    rep = plan_esco_labels(e.g, e.rows)
    assert (rep.rows, rep.occupations_matched, rep.skipped_unknown_occupation, rep.labels_seen) == (4, 2, 1, 5) and rep.mode == "plan"
    assert e.a.counts() == before == {"aliases": 0, "by_language": {}}                              # nothing persisted


def test_a_production_import_is_refused_for_a_licensing_pending_or_fixture_source(tmp_path, sf):
    e = _esco_world(tmp_path, sf, source_origin="official_local")
    with pytest.raises(SourceNotApproved):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="production")
    with pytest.raises(SourceNotApproved):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="fixture")          # fixture mode needs a synthetic source
    with pytest.raises(SourceNotApproved):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="not_registered", mode="production")
    with pytest.raises(SourceNotApproved):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="bogus")
    assert e.a.counts()["aliases"] == 0


def test_a_synthetic_source_can_never_be_imported_in_production_mode(tmp_path, sf):
    e = _esco_world(tmp_path, sf)
    with pytest.raises(SourceNotApproved):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="production")
    assert e.reg.can_ingest("esco_es_fx") is False and e.a.counts()["aliases"] == 0


def test_a_production_import_succeeds_only_after_the_registry_approves_the_source(tmp_path, sf):
    e = _esco_world(tmp_path, sf, source_origin="official_local")
    e.reg.set_licence("esco_es_fx", licence_id="CC BY 4.0", licence_status="verified", attribution_required="yes", redistribution="yes")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion"):
        e.reg.transition("esco_es_fx", step)
    rep = import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="production")
    assert rep.aliases_added == 5 and rep.skipped_unknown_occupation == 1 and rep.occupations_matched == 2
    al = {x["normalized_text"]: x for x in e.a.aliases_for(e.ka)}
    assert al["desarrollador de software de prueba"]["alias_type"] == "official_preferred" and al["programador de prueba"]["alias_type"] == "official_alternative"
    assert al["termino oculto de prueba"]["alias_type"] == "source_synonym" and all(x["language"] == "es" and x["language_basis"] == "source_file" and x["edition_ref"] == "esco@1.2.1" for x in al.values())
    assert all(x["qualification_status"] == "unqualified" for x in al.values())                      # imported is not qualified
    assert import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="production").aliases_added == 0           # idempotent


def test_a_fixture_import_stores_labels_that_are_never_evidence(tmp_path, sf):
    e = _esco_world(tmp_path, sf)
    rep = import_esco_labels(e.g, e.a, e.reg, e.rows, language="es", source_ref="esco_es_fx", mode="fixture")
    assert rep.aliases_added == 5 and rep.mode == "fixture"
    assert all(x["language_basis"] == "fixture_declared" and x["evidence_eligible_origin"] is False for x in e.a.aliases_for(e.ka))
    assert e.reg.can_serve_as_evidence("esco_es_fx") is False


def test_a_label_import_needs_an_explicit_language_and_is_all_or_nothing(tmp_path, sf):
    e = _esco_world(tmp_path, sf)
    with pytest.raises(AliasError):
        import_esco_labels(e.g, e.a, e.reg, e.rows, language=None, source_ref="esco_es_fx", mode="fixture")                     # never guessed from the data
    bad = [e.rows[0], EscoLabelRow(e.rows[2].uri, "x" * 400, (), (), None, None)]                                              # an invalid label fails the whole import
    with pytest.raises(AliasError):
        import_esco_labels(e.g, e.a, e.reg, bad, language="es", source_ref="esco_es_fx", mode="fixture")
    assert e.a.counts()["aliases"] == 0


def test_the_legacy_alias_import_is_gated_per_source_and_never_invents_a_language(tmp_path, sf):
    e = _esco_world(tmp_path, sf)
    e.reg.register("legacy_fx", origin="synthetic_fixture")
    legacy_id = cid(esco_uri="2512.1")
    e.g.add_occupation("Legacy-linked", [("isco", "08", "9930")], legacy_keys=[legacy_id])
    db = tmp_path / "roles.db"
    con = sqlite3.connect(db)
    con.execute("create table occupation_aliases (occupation_code text, alias text, source_id text)")
    con.executemany("insert into occupation_aliases values (?,?,?)", [(legacy_id, "legacy one", "legacy_fx"), (legacy_id, "legacy two", "legacy_fx"), ("ask4mo:occ:unknown", "orphan", "legacy_fx")])
    con.commit()
    con.close()
    before = db.read_bytes()
    with pytest.raises(SourceNotApproved):
        import_legacy_aliases(e.g, e.a, e.reg, read_legacy_aliases(db), source_languages={}, mode="production")
    rep = import_legacy_aliases(e.g, e.a, e.reg, read_legacy_aliases(db), source_languages={}, mode="fixture")
    assert (rep.aliases_added, rep.skipped_unknown_occupation) == (2, 1) and db.read_bytes() == before
    rows = e.a.aliases_for(e.g.find_by_legacy_key(legacy_id)["occupation_key"])
    assert {r["language"] for r in rows} == {"und"} and {r["language_basis"] for r in rows} == {"unknown"} and {r["alias_type"] for r in rows} == {"legacy_alias"}
    rep2 = import_legacy_aliases(e.g, e.a, e.reg, read_legacy_aliases(db), source_languages={"legacy_fx": ("en", "fixture_declared")}, mode="fixture")
    assert rep2.aliases_added == 2                                                               # a declared language adds language-specific rows; the unknown ones stay unknown


# ====================================================================================================================================== resolver
def test_the_synthetic_corpus_is_loaded_only_from_synthetic_fixture_sources():
    c = load_corpus()
    assert c["schema"] == "resolver_fixture_corpus/1" and len(c["cases"]) >= 60 and all(s["origin"] == "synthetic_fixture" for s in c["sources"])
    assert all(i[2].startswith(("99", "0110")) for o in c["occupations"] for i in o["identifiers"] if i[0] != "soc") and "SYNTHETIC" in c["note"]
    assert all(o["label"].endswith("[synthetic fixture]") for o in c["occupations"])


def test_every_corpus_case_matches_its_expectation_and_no_occupation_is_ever_wrongly_resolved(corpus_world):
    results = evaluate_cases(corpus_world.r, corpus_world.keys)
    assert [r for r in results if not r["ok"]] == []
    assert not any(r["wrong_resolution"] for r in results) and not any(r["operational"] for r in results)                          # nothing is operational
    cats = {r["category"] for r in results}
    for needed in ("official_code", "multilingual_alias", "shared_alias", "false_friend", "editions", "leading_zero", "geography_independence", "abstention", "unsupported_language",
                   "unsupported_country", "missing_language_metadata", "mixed_language", "legacy", "normalization", "crosswalk", "conflict", "industry", "unknown"):
        assert needed in cats, needed


def test_a_shared_alias_is_ambiguous_and_the_first_match_is_never_chosen(corpus_world):
    r = corpus_world.r.resolve(MultilingualRequest(title="Developer", title_language="en"))
    assert r.outcome is ResolutionOutcome.AMBIGUOUS and len(r.candidates) == 2 and {"role_context", "taxonomy_code"} <= set(r.context_needed)
    assert sorted(c.occupation_key for c in r.candidates) == sorted([corpus_world.keys["swdev"], corpus_world.keys["webdev"]])


def test_context_narrows_only_with_curated_terms_never_by_title_similarity(corpus_world):
    ok = corpus_world.r.resolve(MultilingualRequest(title="Developer", title_language="en", industry="Embedded systems"))
    assert ok.outcome is ResolutionOutcome.RESOLVED and ok.candidates[0].occupation_key == corpus_world.keys["swdev"]
    both = corpus_world.r.resolve(MultilingualRequest(title="Developer", title_language="en", role_context="software and website"))
    assert both.outcome is ResolutionOutcome.AMBIGUOUS and len(both.candidates) == 2 and "context_narrowed_but_ambiguous" in both.reasons
    none = corpus_world.r.resolve(MultilingualRequest(title="Developer", title_language="en", role_context="we like developers"))
    assert none.outcome is ResolutionOutcome.AMBIGUOUS and "context_matched_no_candidate" in none.reasons


def test_the_resolver_has_no_interface_locale_input_and_language_never_selects_a_country(corpus_world):
    fields = set(MultilingualRequest.__dataclass_fields__)
    assert not fields & {"locale", "ui_language", "interface_language", "conversation_language", "ui_locale"} and {"title_language", "country"} <= fields
    base = dict(title="Krankenpfleger", title_language="de")
    keys = set()
    for country in (None, "DE", "CH", "AT", "US"):
        r = corpus_world.r.resolve(MultilingualRequest(country=country, **base))
        assert r.country_used == country and r.outcome is ResolutionOutcome.RESOLVED                       # German text, any country, same identity; the country is exactly as supplied
        keys.add(r.candidates[0].occupation_key)
    assert len(keys) == 1
    assert corpus_world.r.resolve(MultilingualRequest(title="Nurse", title_language="en", country="DE")).country_used == "DE"
    assert corpus_world.r.resolve(MultilingualRequest(title="Nurse", title_language="en")).country_used is None                 # English never implies a country
    assert corpus_world.r.resolve(MultilingualRequest(title="Nurse", title_language="en", country="ZZ")).outcome is ResolutionOutcome.UNSUPPORTED


def test_unsupported_unknown_and_abstaining_outcomes_are_explicit(corpus_world):
    r = corpus_world.r
    assert r.resolve(MultilingualRequest(title="Nurse", title_language="pl")).outcome is ResolutionOutcome.UNSUPPORTED
    assert r.resolve(MultilingualRequest(title="Astronaut")).outcome is ResolutionOutcome.NOT_FOUND
    assert r.resolve(MultilingualRequest()).outcome is ResolutionOutcome.INSUFFICIENT_CONTEXT
    assert r.resolve(MultilingualRequest(title="Legacy title")).outcome is ResolutionOutcome.INSUFFICIENT_CONTEXT              # unverified alias language
    code = r.resolve(MultilingualRequest(title="Legacy title", taxonomy_scheme="isco", taxonomy_code="9910"))
    assert code.outcome is ResolutionOutcome.RESOLVED                                                    # identity evidence needs no alias language
    assert r.resolve(MultilingualRequest(title="Nurse", title_language="en", seniority="principal")).ignored_inputs == ["seniority_does_not_change_occupation_identity"]


def test_a_conflicting_title_never_overrides_an_official_code(corpus_world):
    r = corpus_world.r.resolve(MultilingualRequest(title="Nurse", title_language="en", taxonomy_scheme="isco", taxonomy_code="9902", taxonomy_edition="08"))
    assert r.outcome is ResolutionOutcome.RESOLVED and r.candidates[0].occupation_key == corpus_world.keys["swdev"] and "title_conflicts_with_official_code" in r.warnings


def test_only_a_verified_source_provided_equivalence_joins_nodes(corpus_world):
    j = corpus_world.r.resolve(MultilingualRequest(title="Joinable", title_language="en"))
    assert j.outcome is ResolutionOutcome.RESOLVED and j.candidates[0].occupation_key in (corpus_world.keys["join_a"], corpus_world.keys["join_b"])
    k = corpus_world.r.resolve(MultilingualRequest(title="Relatable", title_language="en"))
    assert k.outcome is ResolutionOutcome.AMBIGUOUS                                                       # RELATED (even VERIFIED) is never EQUIVALENT


def test_title_similarity_does_not_override_codes_and_unknown_editions_are_not_compatible(corpus_world):
    r = corpus_world.r
    assert r.resolve(MultilingualRequest(title="Technician", title_language="en", taxonomy_scheme="isco", taxonomy_edition="08")).candidates[0].occupation_key == corpus_world.keys["ed08"]
    assert r.resolve(MultilingualRequest(title="Clerk", title_language="en", taxonomy_scheme="soc", taxonomy_edition="2018")).outcome is ResolutionOutcome.NOT_FOUND
    assert r.resolve(MultilingualRequest(title="Clerk", title_language="en", taxonomy_scheme="soc", taxonomy_edition="unknown")).outcome is ResolutionOutcome.RESOLVED


def test_fixture_aliases_are_never_operational_even_when_resolved(corpus_world):
    res = corpus_world.r.resolve(MultilingualRequest(title="Nurse", title_language="en"))
    assert res.outcome is ResolutionOutcome.RESOLVED and res.operational is False and res.candidates[0].evidence["evidence_eligible"] is False
    assert res.candidates[0].evidence["source_origin"] == "synthetic_fixture" and res.candidates[0].evidence["qualification_status"] == "unqualified"


def test_a_resolution_becomes_operational_only_through_a_qualified_alias_of_an_approved_source(sf):
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    reg.register("real", origin="official_local", validation_status="unvalidated")
    n = g.add_occupation("Synthetic op", [("isco", "08", "9940")])
    al = a.add_alias(n["occupation_key"], "Operational title", language="en", language_basis="source_declared", alias_type="official_preferred", source_ref="real")
    r = OccupationResolver(g, a, registry=reg)
    assert r.resolve(MultilingualRequest(title="operational title", title_language="en")).operational is False
    a.set_qualification(al["id"], "qualified", actor_user_id=3)
    assert r.resolve(MultilingualRequest(title="operational title", title_language="en")).operational is False                     # source still not approved
    reg.set_licence("real", licence_id="PD", licence_status="verified")
    for step in ("licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use"):
        reg.transition("real", step)
    assert r.resolve(MultilingualRequest(title="operational title", title_language="en")).operational is True


def test_the_legacy_identity_adapter_reports_state_status_and_evidence_without_forcing_a_match(corpus_world):
    ad = LegacyIdentityAdapter(corpus_world.g, corpus_world.reg)
    linked = ad.describe(legacy_id="ask4mo:occ:legacy-110")
    assert linked["identity_state"] == "linked" and linked["canonical_occupation_id"] == corpus_world.keys["armed"] and linked["mapping_status"] == "unknown"
    assert ad.describe(legacy_id="ask4mo:occ:nope")["identity_state"] == "unresolved"
    assert ad.describe(native=("isco", "9901"))["identity_state"] == "linked" and ad.describe(native=("isco", "9912"))["identity_state"] == "ambiguous"
    assert ad.describe(title="Coordinator A [synthetic fixture]")["identity_state"] == "linked" and ad.describe(title="nonexistent")["identity_state"] == "unresolved"
    joined = ad.describe(native=("onet_soc", "99-9922.00"))
    assert joined["mapping_status"] == "verified" and joined["relationship_qualification"]["reached"]["operationally_approved"] == 0
    assert ad.describe()["identity_state"] == "unresolved" and ad.describe(legacy_id="a", title="b")["reason"] == "exactly_one_legacy_reference_required"


def test_the_p10c_a_graph_resolver_contract_is_unchanged():
    from src.knowledge_foundation.resolver_contract import ResolutionRequest
    assert not set(ResolutionRequest.__dataclass_fields__) & {"language", "locale", "title_language"}


# ====================================================================================================================================== performance and security
def test_resolution_of_a_medium_inventory_is_fast_and_does_not_scan_all_occupations(sf):
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    reg.register("fxperf", origin="synthetic_fixture")
    n_occ = 1500

    def build(s):
        for i in range(n_occ):
            node = g.add_occupation(f"Synthetic perf occupation {i}", [("isco", "08", f"{9000 + i % 1000}"[:4]) if False else ("onet_soc", "31.0", f"99-{i:04d}.00")], _session=s)
            for j in range(3):
                a.add_alias(node["occupation_key"], f"perf alias {i} variant {j}", language="en", language_basis="fixture_declared", alias_type="source_synonym", source_ref="fxperf", _session=s)
            a.add_alias(node["occupation_key"], "generic common title", language="en", language_basis="fixture_declared", alias_type="recognized_title", source_ref="fxperf", _session=s) if i < 40 else None
    g.bulk(build)
    r = OccupationResolver(g, a)
    tracemalloc.start()
    t0 = time.perf_counter()
    for i in range(0, n_occ, 15):
        assert r.resolve(MultilingualRequest(title=f"perf alias {i} variant 1", title_language="en")).outcome is ResolutionOutcome.RESOLVED
    unique_ms = (time.perf_counter() - t0) * 1000 / len(range(0, n_occ, 15))
    t1 = time.perf_counter()
    amb = r.resolve(MultilingualRequest(title="generic common title", title_language="en"))
    amb_ms = (time.perf_counter() - t1) * 1000
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert amb.outcome is ResolutionOutcome.AMBIGUOUS and len(amb.candidates) == 40
    assert unique_ms < 100 and amb_ms < 500 and peak < 64 * 1024 * 1024
    assert r.resolve(MultilingualRequest(title="no such alias anywhere")).outcome is ResolutionOutcome.NOT_FOUND


def test_nothing_in_the_new_modules_is_imported_by_a_runtime_or_candidate_path():
    new = ("aliases", "codes", "esco_adapter", "fixtures", "language_coverage", "normalize", "occupation_resolver", "qualification")
    offenders = []
    for pkg in ("src/copilot", "src/agent", "src/api", "src/application", "src/career", "src/interview", "src/documents", "src/billing"):
        for f in (ROOT / pkg).rglob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                mods = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
                if any(m and m.startswith("src.knowledge_foundation") for m in mods):
                    offenders.append(str(f.relative_to(ROOT)))
    assert offenders == [] and all((ROOT / "src/knowledge_foundation" / f"{m}.py").exists() for m in new)
    for rel in ("src/copilot/knowledge/compensation.py", "src/copilot/knowledge/retrieval.py", "src/copilot/knowledge/router.py"):
        assert "knowledge_foundation" not in (ROOT / rel).read_text()


def test_the_new_modules_make_no_network_provider_or_salary_calls():
    banned = {"requests", "httpx", "urllib", "stripe", "openai", "boto3", "aiohttp", "socket"}
    for f in (ROOT / "src/knowledge_foundation").glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & banned, (f.name, mods & banned)
        src = f.read_text(encoding="utf-8").lower()
        for token in ("convert_currency", "annualis", "annualiz", "median(", "exchange_rate"):
            assert token not in src, (f.name, token)


def test_gates_stay_off_and_compensation_v1_is_unchanged():
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp
    assert not any([AP.AI_COST_LIMITS_ENFORCED, HA.HISTORY_RESTRICTIONS_ENFORCED, MP.MODEL_PROFILE_ENFORCED, UQ.USAGE_QUOTAS_ENFORCED, PA.PREMIUM_ANALYTICS_ENABLED, PP.PREPARATION_PACK_GENERATION_ENABLED])
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        assert getattr(bp, g) is False
    import src.copilot.knowledge.compensation as comp
    assert not hasattr(comp, "CompensationRecordV2") and not hasattr(__import__("src.persistence", fromlist=["x"]), "CompensationRecordV2")
    from src.copilot import constants
    assert set(constants.COUNTRY_SOURCE_PRIORITY) == {"DE", "US", "UK", "EU"}


def test_no_client_input_can_set_verified_or_approve_a_source():
    for rel in ("src/api",):
        for f in (ROOT / rel).rglob("*.py"):
            t = f.read_text(encoding="utf-8")
            assert "add_relationship" not in t and "SourceRegistry" not in t and "AliasStore" not in t, f


# ====================================================================================================================================== migration 0036
def test_migration_0036_is_additive_reversible_and_matches_the_orm(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect
    from tests.test_billing_f1_qualification import _alembic
    from src import persistence as P
    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0038_compensation_concepts"]
    new = ("graph_occupation_aliases", "language_coverage")
    command.upgrade(cfg, "0035_knowledge_foundation")
    assert not set(new) & set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert set(new) <= set(insp.get_table_names())
    for t in new:
        model = next(m for m in P.Base.metadata.tables.values() if m.name == t)
        assert {c["name"] for c in insp.get_columns(t)} == {c.name for c in model.columns}, t
    assert any(u["name"] == "uq_graph_alias" for u in insp.get_unique_constraints("graph_occupation_aliases"))
    assert {"ix_graph_alias_normalized", "ix_graph_alias_folded", "ix_graph_alias_occupation"} <= {i["name"] for i in insp.get_indexes("graph_occupation_aliases")}
    command.downgrade(cfg, "0035_knowledge_foundation")
    after = inspect(create_engine(url))
    assert not set(new) & set(after.get_table_names()) and {"graph_occupations", "global_sources", "geography_coverage"} <= set(after.get_table_names())          # P10C-A intact
    command.upgrade(cfg, "head")


def test_the_migration_seeds_nothing_and_keeps_existing_graph_data(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine
    from tests.test_billing_f1_qualification import _alembic
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0035_knowledge_foundation")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("insert into graph_occupations (occupation_key, canonical_label, status, legacy_keys, created_at) values ('ask4mo:occ:keep', 'keep', 'active', '[]', '2026-01-01')"))
    command.upgrade(cfg, "head")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from graph_occupations")).scalar() == 1                                      # preserved
        for t in ("graph_occupation_aliases", "language_coverage"):
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    command.downgrade(cfg, "0035_knowledge_foundation")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from graph_occupations")).scalar() == 1


def test_the_committed_fixture_corpus_is_stable_json():
    raw = CORPUS_PATH.read_text(encoding="utf-8")
    assert json.loads(raw)["schema"] == "resolver_fixture_corpus/1" and len(load_corpus()["occupations"]) == 28


# ====================================================================================================================================== scripts on a clean checkout
def _run_script(name, *args, cwd):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, cwd=cwd)


def _snapshot(root):
    return sorted((str(p.relative_to(root)), p.is_dir() or p.stat().st_size) for p in root.rglob("*"))


def test_the_inventory_script_validates_the_output_before_any_data_access_on_a_clean_checkout(tmp_path):
    root = tmp_path / "clean"
    (root / "data").mkdir(parents=True)
    (root / "evaluations").mkdir()
    (root / "alias").symlink_to(root / "data", target_is_directory=True)
    before = _snapshot(root)
    for target in ("data/x.json", "evaluations/y.json", "data/nested/z.json", "outside/../data/w.json", "alias/v.json", str(root / "data/abs.json")):
        r = _run_script("gkb3_alias_inventory.py", "--root", str(root), "--out", target, cwd=root)
        assert r.returncode == 2 and "refusing" in r.stderr and "Traceback" not in r.stderr, (target, r.stderr[-200:])
    r = _run_script("gkb3_alias_inventory.py", "--root", str(root), "--out", str(tmp_path / "elsewhere/inv.json"), cwd=root)
    assert r.returncode == 3 and "missing" in r.stderr and "Traceback" not in r.stderr and not (tmp_path / "elsewhere").exists()
    assert _snapshot(root) == before


def test_the_benchmark_script_refuses_protected_outputs_before_doing_any_work(tmp_path):
    for target in ("data/bench.json", "evaluations/bench.json"):
        r = _run_script("bench_occupation_resolver.py", "--out", str(ROOT / target), cwd=tmp_path)
        assert r.returncode == 2 and "refusing" in r.stderr and not (ROOT / target).exists()
