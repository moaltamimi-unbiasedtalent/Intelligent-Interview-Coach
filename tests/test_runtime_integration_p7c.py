"""Phase 7C — runtime knowledge integration, occupation-grounding guard, geography safety.

Deterministic; no network; no provider calls; small in-memory / tmp fixtures (never the full
runtime stores). Covers:

* the §39/§40 occupation-grounding guard (unknown role → not grounded / insufficient; ambiguous
  → clarify with no evidence; known role → grounded with evidence; general query → labelled
  general),
* §18/§36 compensation geography safety (no other-nation salary substitution),
* the resolver intent-noun stripping (salary/skills phrasings resolve),
* the runtime build from a normalized fixture: reconstruction, atomic promotion, build metadata,
  reproducibility, and that runtime queries need no Parquet,
* vector-passage provenance metadata survival (§24).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.copilot.knowledge import canonical as C
from src.copilot.knowledge import normalize as N
from src.copilot.knowledge.compensation import CompensationRecord as SrcComp
from src.copilot.knowledge.compensation import CompensationRepository
from src.copilot.knowledge.resolver import resolve_occupation, title_variants
from src.copilot.knowledge.retrieval import StructuredRetrievalCoordinator
from src.copilot.knowledge.roles import NormalisedOccupation, RoleRepository, Skill
from src.copilot.service import CareerIntelligenceService

_ROOT = Path(__file__).resolve().parent.parent

_MANIFEST = [
    type("E", (), {"source_id": "onet", "title": "O*NET", "source_url": "https://onet.org",
                   "publisher": "US DOL", "authority_level": 1, "region": "US", "country": "US"})(),
    type("E", (), {"source_id": "bls_oews", "title": "BLS OEWS", "source_url": "https://bls.gov",
                   "publisher": "BLS", "authority_level": 1, "region": "US", "country": "US"})(),
]


class _ExplodingResponder:
    def __call__(self, messages):  # pragma: no cover
        raise AssertionError("retrieve_evidence must not synthesize")


def _role_repo() -> RoleRepository:
    repo = RoleRepository(":memory:")
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:11-2021", title="Product Manager", source_id="onet",
        tasks=["Own the roadmap"], skills=[Skill(name="Discovery"), Skill(name="Prioritisation")]))
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:29-1141", title="Registered Nurse", source_id="onet",
        tasks=["Assess patients"], skills=[Skill(name="Clinical judgement")]))
    return repo


def _service(repo, comp_repo=None):
    coord = StructuredRetrievalCoordinator(role_repo=repo, comp_repo=comp_repo,
                                           manifest_entries=_MANIFEST)
    return CareerIntelligenceService(
        knowledge_coordinator=coord, synthesis_responder=_ExplodingResponder(), retriever=None)


# --- §40 occupation-grounding guard --------------------------------------------------

def test_known_occupation_is_grounded_with_evidence():
    res = _service(_role_repo()).retrieve_evidence("What does a product manager do?")
    assert res.occupation_grounded is True
    assert res.general_evidence is False
    assert res.source_count > 0 and not res.insufficient_evidence
    assert len(res.citations) == res.source_count


def test_unknown_named_occupation_is_not_grounded_and_insufficient():
    res = _service(_role_repo()).retrieve_evidence("What does a moon whisperer do?")
    assert res.occupation_grounded is False
    assert res.insufficient_evidence is True
    assert res.source_count == 0 and res.citations == []


def test_ambiguous_occupation_asks_to_clarify_without_evidence():
    repo = RoleRepository(":memory:")
    for code, title in [("a", "Data Analyst"), ("b", "Data Scientist")]:
        repo.add_occupation(NormalisedOccupation(occupation_code=code, title=title,
                            source_id="onet", skills=[Skill(name="SQL")]))
    res = _service(repo).retrieve_evidence("what does a data do")  # ambiguous 'data'
    # Either clarifies (preferred) or is safely insufficient — never a guessed grounded answer.
    assert res.occupation_grounded is False
    assert res.source_count == 0


# --- §18/§36 compensation geography safety -------------------------------------------

def _comp_repo() -> CompensationRepository:
    repo = CompensationRepository(":memory:")
    repo.add(SrcComp(source_id="bls_oews", occupation_code="15-1252",
                     occupation_title="Software Developers", geography="US", country="US",
                     year=2025, currency="USD", pay_period="annual", statistic_type="median",
                     value=128000.0))
    return repo


def test_us_salary_query_returns_us_compensation():
    repo = _role_repo()
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:15-1252", title="Software Developers", source_id="onet",
        skills=[Skill(name="Python")]))
    res = _service(repo, comp_repo=_comp_repo()).retrieve_evidence(
        "software developer salary in the United States")
    comp = [e for e in res.evidence if e.evidence_type == "compensation"]
    assert comp and all((e.country or "US").upper() == "US" for e in comp)


def test_german_salary_query_never_substitutes_us_data():
    repo = _role_repo()
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:15-1252", title="Software Developers", source_id="onet",
        skills=[Skill(name="Python")]))
    res = _service(repo, comp_repo=_comp_repo()).retrieve_evidence(
        "software developer salary in Germany")
    # No US (or any other nation's) compensation may be presented as a German salary (§18/§36).
    us_comp = [e for e in res.evidence
               if e.evidence_type == "compensation" and (e.country or "").upper() == "US"]
    assert us_comp == []


# --- resolver intent-noun stripping --------------------------------------------------

def test_intent_nouns_are_stripped_so_occupation_resolves():
    repo = _role_repo()
    repo.add_occupation(NormalisedOccupation(
        occupation_code="onet:15-1252", title="Software Developers", source_id="onet",
        skills=[Skill(name="Python")]))
    assert "software developer" in title_variants("software developer salary")
    assert "product manager" in title_variants("product manager responsibilities")
    r = resolve_occupation(repo, "software developer salary in the US")
    assert r.candidates, "occupation should resolve once the intent noun is stripped"


# --- runtime build from a normalized fixture -----------------------------------------

def _load_builder():
    path = _ROOT / "scripts" / "knowledge" / "build_runtime_knowledge.py"
    spec = importlib.util.spec_from_file_location("build_runtime_knowledge", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_runtime_knowledge"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_normalized_fixture(norm: Path):
    norm.mkdir(parents=True, exist_ok=True)
    reg = C.CanonicalIdRegistry()
    occ = NormalisedOccupation(
        occupation_code="http://esco/dev", title="Software Developer", source_id="esco",
        isco_code="2512", description="Builds software.",
        aliases=["software engineer", "programmer"],
        skills=[Skill(name="Python", skill_type="technology"), Skill(name="Algorithms")],
        knowledge=["computer science"], tasks=["write code"], activities=["testing"],
        entry_education="Bachelor's degree",
        relationships=[], mappings=[])
    can, aliases, facts, xwalks, rels, srec = N.occupation_to_canonical(occ, reg)
    skills = [f for f in facts if f.fact_type == C.FactType.SKILL]
    tech = [f for f in facts if f.fact_type == C.FactType.TECHNOLOGY_SKILL]
    know = [f for f in facts if f.fact_type == C.FactType.KNOWLEDGE]
    tasks = [f for f in facts if f.fact_type == C.FactType.TASK]
    acts = [f for f in facts if f.fact_type == C.FactType.WORK_ACTIVITY]
    attrs = [f for f in facts if (f.metadata or {}).get("attribute")]
    comp, _ = N.compensation_to_canonical(SrcComp(
        source_id="bls_oews", occupation_code="15-1252", country="US", geography="US",
        year=2025, currency="USD", pay_period="annual", statistic_type="median",
        value=128000.0), reg)

    def _w(name, recs):
        if recs:
            C.write_parquet(recs, norm / f"{name}.parquet")

    _w("occupations", [can]); _w("occupation_aliases", aliases)
    _w("occupation_skills", skills); _w("technology_skills", tech)
    _w("knowledge_areas", know); _w("tasks", tasks); _w("work_activities", acts)
    _w("occupation_attributes", attrs); _w("compensation", [comp])
    (norm / "build_metadata.json").write_text(json.dumps(
        {"pipeline_version": "7B.test", "source_versions": {}, "record_counts": {}}), encoding="utf-8")


def test_runtime_build_from_normalized_and_reproducible(tmp_path):
    bnk = _load_builder()
    norm = tmp_path / "normalized"
    _write_normalized_fixture(norm)
    kdir = tmp_path / "knowledge"

    report = bnk.build(do_structured=True, do_vector=False, validate_only=False,
                       normalized_dir=str(norm), knowledge_dir=str(kdir))
    assert report["counts"]["roles"]["occupations"] == 1
    # Stores promoted + queryable without any Parquet at query time.
    roles = RoleRepository(str(kdir / "roles.db"))
    hits = roles.search("software", limit=5)
    assert hits, "rebuilt roles.db must resolve the occupation"
    occ = roles.get_occupation(hits[0]["occupation_code"])
    assert occ and occ["skills"], "skills must be reconstructed"
    roles.close()
    assert (kdir / "build_metadata.json").is_file()
    meta = json.loads((kdir / "build_metadata.json").read_text())
    assert meta["runtime_pipeline_version"] == bnk.RUNTIME_PIPELINE_VERSION

    # Reproducible: a second build yields the same occupation + skill counts.
    kdir2 = tmp_path / "knowledge2"
    bnk.build(do_structured=True, do_vector=False, validate_only=False,
              normalized_dir=str(norm), knowledge_dir=str(kdir2))
    r1 = RoleRepository(str(kdir / "roles.db")).counts()
    r2 = RoleRepository(str(kdir2 / "roles.db")).counts()
    assert r1 == r2


def test_validate_only_does_not_write_runtime(tmp_path):
    bnk = _load_builder()
    norm = tmp_path / "normalized"
    _write_normalized_fixture(norm)
    kdir = tmp_path / "knowledge"
    bnk.build(do_structured=True, do_vector=False, validate_only=True,
              normalized_dir=str(norm), knowledge_dir=str(kdir))
    assert not (kdir / "roles.db").exists()


# --- vector provenance metadata (§24) -----------------------------------------------

def test_vector_sanitize_keeps_provenance_keys():
    from src.copilot.vectorstore import sanitize_metadata
    meta = {"source_id": "esco", "source_url": "https://x", "title": "Software Developer",
            "canonical_occupation_id": "ask4mo:occ:abc", "geography": "US", "country": "US",
            "domain": "occupation_description", "reference_year": 2025, "language": "en",
            "nefarious": "drop me"}
    clean = sanitize_metadata(meta, doc_id="d1")
    assert clean["canonical_occupation_id"] == "ask4mo:occ:abc"
    assert clean["geography"] == "US" and clean["country"] == "US"
    assert clean["domain"] == "occupation_description" and clean["reference_year"] == 2025
    assert "nefarious" not in clean  # only allow-listed keys survive
