"""02D (PG-05, OD-LANG-02, OD-US-CONTENT): market source approval register, fail-closed validator and the Candidate retrieval filter.

Deterministic, 0 paid/live calls, no network. The mechanism is proven ONLY with synthetic records injected through the test-only seam; the committed
register ships EMPTY and a test asserts it. Nothing here approves a source: the synthetic reviewer names are fixtures.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import knowledge_approval as ka
from src.application.career_service import CareerApplicationService
from src.application.models import CareerChatRequest, KnowledgeSearchRequest
from src.copilot.config import CopilotConfig
from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.knowledge import approval_filter as af
from src.copilot.knowledge import manifest as km
from src.copilot.models import DocumentChunk, KnowledgeEvidence
from src.copilot.rag.responder import ModelReply
from src.copilot.rag.translation import QueryTranslator
from src.copilot.retrieval import build_retriever
from src.copilot.service import CareerIntelligenceService
from src.copilot.vectorstore import InMemoryVectorStore

ROOT = Path(__file__).resolve().parent.parent
COMMITTED = ROOT / "docs" / "production" / "execution" / "source_approval_register.json"
TODAY = date.today()
CONFIG = CopilotConfig()


def record(source="eurostat_earnings", market="DE", **over) -> dict:
    rec = {
        "source_id": source, "market": market, "licence_class": "public_official",
        "licence_terms_reference": "Synthetic fixture: Eurostat reuse notice read on the fixture date",
        "rights_holder": "Synthetic Rights Holder", "authority_tier": 1,
        "coverage_statement": "Synthetic fixture coverage statement for the test market",
        "features": ["compensation"], "approver": "Fixture Reviewer", "approved_on": (TODAY - timedelta(days=3)).isoformat(),
        "evidence_reference": "fixtures/synthetic-evidence-001", "release_sha": "0123456789abcdef0123456789abcdef01234567",
        "staleness_rule": {"valid_until": (TODAY + timedelta(days=200)).isoformat()}, "enabled": True,
    }
    rec.update(over)
    return rec


def register(*records) -> dict:
    return {"schema_version": 1, "records": list(records)}


TIERS = {e.source_id: e.authority_level for e in km.load_manifest()}


def resolved(*records, mode=ka.MODE_ENFORCED, tiers=TIERS):
    return ka.resolve(register(*records), mode, manifest_tiers=tiers)


@pytest.fixture(autouse=True)
def _clean_seam():
    ka.clear_synthetic_register()
    yield
    ka.clear_synthetic_register()


@pytest.fixture
def hosted(monkeypatch):
    """Hosted semantics (enforced) without a hosted environment: the in-memory test store uses the local hash embedder, which a real hosted environment refuses
    (02B). The API_ENV to mode mapping itself is asserted in test_mode_comes_from_api_env_and_unknown_is_enforced."""
    monkeypatch.setattr(ka, "approval_mode", lambda environ=None: ka.MODE_ENFORCED)


# ---------------------------------------------------------------- the committed register and the empty state
def test_committed_register_ships_empty_and_nothing_is_enabled():
    data, err = ka.load_committed(COMMITTED)
    assert err is None and data["records"] == []
    reg = ka.resolve(data, ka.MODE_ENFORCED, manifest_tiers=TIERS)
    assert reg.empty and reg.file_error is None
    assert ka.beta_scope_view(reg) == {"schema_version": 1, "enabled_features": [], "approved_markets": [], "qualified_sources": []}
    assert ka.public_summary(reg)["none_enabled"] is True


def test_runtime_reads_the_committed_register_and_it_is_empty():
    assert ka.current().empty


@pytest.mark.parametrize("mkt", ka.MARKETS)
def test_every_market_and_every_manifest_source_is_refused_when_empty(hosted, mkt):
    reg = ka.current()
    assert reg.enforced
    for sid in TIERS:
        assert not ka.decide(reg, sid, mkt).allowed


# ---------------------------------------------------------------- validator: a complete record enables, anything else fails closed
def test_complete_record_enables_exactly_its_pair():
    reg = resolved(record())
    assert reg.enabled == {("eurostat_earnings", "DE")}
    assert reg.features[("eurostat_earnings", "DE")] == {"compensation"}
    assert ka.decide(reg, "eurostat_earnings", "DE").allowed


@pytest.mark.parametrize("field", [f for f in ka._REQUIRED_FIELDS])
def test_each_missing_field_fails_closed(field):
    rec = record()
    del rec[field]
    reg = resolved(rec)
    assert not reg.enabled, field
    assert not ka.decide(reg, "eurostat_earnings", "DE").allowed


@pytest.mark.parametrize("over", [
    {"approver": "TBD"}, {"approver": ""}, {"approver": "Claude"}, {"approver": "GitHub Actions"}, {"approver": "engineering team"}, {"approver": 7},
    {"approver": "Licensing Reviewer"},
    {"approved_on": (TODAY + timedelta(days=2)).isoformat()}, {"approved_on": "22/10/2026"}, {"approved_on": None},
    {"release_sha": "HEAD"}, {"release_sha": ""}, {"release_sha": "xyz"},
    {"licence_class": "unclear"}, {"licence_class": "restricted"}, {"licence_class": "made_up"},
    {"licence_terms_reference": ""}, {"licence_terms_reference": "tbd"}, {"rights_holder": "n/a"}, {"coverage_statement": "x"}, {"evidence_reference": ""},
    {"authority_tier": 0}, {"authority_tier": 4}, {"authority_tier": True}, {"authority_tier": 2},       # 2 disagrees with the manifest tier (1)
    {"features": []}, {"features": ["not_a_feature"]}, {"features": ["compensation", "compensation"]}, {"features": "compensation"},
    {"market": "XX"}, {"market": "de"}, {"market": ""}, {"source_id": "no_such_source"}, {"source_id": "../etc"},
    {"staleness_rule": {}}, {"staleness_rule": {"valid_until": "soon"}}, {"staleness_rule": {"valid_until": (TODAY - timedelta(days=1)).isoformat()}},
    {"staleness_rule": {"valid_until": (TODAY + timedelta(days=900)).isoformat()}}, {"staleness_rule": {"valid_until": (TODAY + timedelta(days=9)).isoformat(), "extra": 1}},
    {"enabled": False}, {"enabled": "yes"}, {"enabled": None},                                          # the claim must equal the derived result
    {"unexpected_field": 1},
])
def test_partial_forged_stale_or_malformed_record_is_not_enabled(over):
    reg = resolved(record(**over))
    assert not reg.enabled, over
    assert not ka.decide(reg, over.get("source_id", "eurostat_earnings"), "DE").allowed


def test_a_forged_enabled_claim_on_a_partial_record_cannot_enable():
    partial = {"source_id": "eurostat_earnings", "market": "DE", "enabled": True, "approver": "Fixture Reviewer"}
    reg = resolved(partial)
    assert not reg.enabled
    assert any("enabled claim" in p or "missing" in p for r in reg.records for p in r.problems)


def test_stale_record_becomes_disabled_when_valid_until_passes():
    rec = record(staleness_rule={"valid_until": (TODAY + timedelta(days=10)).isoformat()})
    assert ka.resolve(register(rec), ka.MODE_ENFORCED, manifest_tiers=TIERS).enabled
    later = ka.resolve(register(rec), ka.MODE_ENFORCED, today=TODAY + timedelta(days=11), manifest_tiers=TIERS)
    assert not later.enabled


def test_governed_source_ids_are_accepted_but_unknown_manifest_ids_are_not():
    assert resolved(record(source="governed:abc123", authority_tier=1)).enabled == {("governed:abc123", "DE")}
    assert not resolved(record(source="abc123")).enabled


@pytest.mark.parametrize("bad", [
    "not json", "[]", '{"schema_version": 1, "records": {}}', '{"schema_version": 2, "records": []}', '{"records": []}',
    '{"schema_version": 1, "records": [], "records": []}',
])
def test_malformed_or_duplicate_key_file_fails_closed(tmp_path, bad):
    p = tmp_path / "r.json"
    p.write_text(bad, encoding="utf-8")
    data, err = ka.load_committed(p)
    reg = ka.resolve(data, ka.MODE_ENFORCED, file_error=err, manifest_tiers=TIERS)
    assert reg.empty and not ka.decide(reg, "eurostat_earnings", "DE").allowed


def test_missing_file_fails_closed(tmp_path):
    data, err = ka.load_committed(tmp_path / "absent.json")
    assert data is None and err
    assert ka.resolve(data, ka.MODE_ENFORCED, file_error=err).empty


def test_duplicate_pair_makes_the_whole_file_untrustworthy():
    reg = resolved(record(), record(source="eurostat_earnings", market="DE"), record(source="ons_ashe", market="UK"))
    assert reg.empty and reg.file_error


# ---------------------------------------------------------------- decision: modes, cross-market isolation, US content
def test_hosted_refuses_and_development_labels():
    enforced, labelled = resolved(mode=ka.MODE_ENFORCED), resolved(mode=ka.MODE_LABELLED)
    d1, d2 = ka.decide(enforced, "eurostat_earnings", "DE"), ka.decide(labelled, "eurostat_earnings", "DE")
    assert not d1.allowed
    assert d2.allowed and d2.labelled_unqualified


@pytest.mark.parametrize("env,mode", [("production", "enforced"), ("staging", "enforced"), ("anything-else", "enforced"), ("", "labelled"),
                                      ("development", "labelled"), ("test", "labelled"), ("DEV", "labelled")])
def test_mode_comes_from_api_env_and_unknown_is_enforced(env, mode):
    assert ka.approval_mode({"API_ENV": env} if env else {}) == mode


def test_cross_market_isolation():
    reg = resolved(record("eurostat_earnings", "DE"))
    assert ka.decide(reg, "eurostat_earnings", "DE").allowed
    for other in ("FR", "ES", "IT", "PT", "NL", "IE", "UK", "US", "EU"):
        assert not ka.decide(reg, "eurostat_earnings", other).allowed
    assert not ka.decide(reg, "esco", "DE").allowed          # another source in the same market


def test_unknown_or_unspecified_market_enables_nothing():
    reg = resolved(record())
    for mkt in (None, "", "global", "other", "br", "XX"):
        assert not ka.decide(reg, "eurostat_earnings", mkt).allowed


def test_gb_is_the_uk_market_and_language_codes_are_not_markets():
    assert ka.normalise_market("gb") == "UK" and ka.normalise_market("uk") == "UK"
    # a language is not a market: "de" as a LOCALE would have to be passed as a geography by the caller; the filter API has no language parameter at all
    import inspect

    assert "language" not in inspect.signature(af.effective_market).parameters
    assert "locale" not in inspect.signature(af.apply).parameters and "language" not in inspect.signature(af.apply).parameters


def test_us_content_for_a_non_us_market_is_refused_even_with_a_record_while_undecided():
    assert ka.US_GENERAL_INFORMATION_DECIDED is False
    reg = resolved(record("bls_ooh", "DE", features=["role_definition"]), record("bls_ooh", "US", features=["role_definition"]))
    assert reg.enabled == {("bls_ooh", "DE"), ("bls_ooh", "US")}
    assert not ka.decide(reg, "bls_ooh", "DE", source_country="US").allowed
    assert not ka.decide(reg, "bls_ooh", None, source_country="US").allowed
    assert ka.decide(reg, "bls_ooh", "US", source_country="US").allowed          # a US market with a record is allowed


def test_us_general_information_mechanism_is_labelled_when_the_owner_decides(monkeypatch):
    monkeypatch.setattr(ka, "US_GENERAL_INFORMATION_DECIDED", True)
    reg = resolved(record("bls_ooh", "DE", features=["role_definition"]))
    d = ka.decide(reg, "bls_ooh", "DE", source_country="US")
    assert d.allowed and d.general_information
    assert not ka.decide(reg, "bls_ooh", "FR", source_country="US").allowed       # still needs its own record per market


def test_test_seam_refuses_outside_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError):
        ka.install_synthetic_register(register())


def test_production_code_never_uses_the_test_seam():
    for p in (ROOT / "src").rglob("*.py"):
        if p.name == "knowledge_approval.py":
            continue
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"knowledge_approval[^\n]*install_synthetic_register|ka\.install_synthetic_register", text), p


# ---------------------------------------------------------------- consistency check against the manifests
def test_every_manifest_source_has_a_licence_entry_and_committed_register_is_consistent():
    data, _ = ka.load_committed(COMMITTED)
    assert ka.consistency_problems(data, km.load_manifest()) == []


def test_missing_licence_entry_is_reported():
    entries = km.load_manifest()
    bad = entries[0].model_copy(update={"licence": None, "licence_review_required": False})
    problems = ka.consistency_problems(register(), [bad] + entries[1:])
    assert any(bad.source_id in p and "no licence entry" in p for p in problems)


def test_enabled_record_must_reference_an_existing_source_and_tier():
    entries = km.load_manifest()
    problems = ka.consistency_problems(register(record(source="ghost_source")), entries)
    assert any("ghost_source" in p and "existing manifest source" in p for p in problems)
    problems = ka.consistency_problems(register(record(authority_tier=3)), entries)
    assert any("disagrees with the manifest" in p for p in problems)


def test_enabling_a_review_required_source_demands_the_manifest_update():
    entries = km.load_manifest()
    assert next(e for e in entries if e.source_id == "esco").licence_review_required
    problems = ka.consistency_problems(register(record(source="esco")), entries)
    assert any("review_required" in p for p in problems)
    assert ka.consistency_problems(register(record(source="eurostat_earnings")), entries) == []


def test_unusable_register_is_a_consistency_problem():
    assert any("unusable" in p for p in ka.consistency_problems({"schema_version": 9}, km.load_manifest()))


# ---------------------------------------------------------------- the 02E adapter
def test_beta_scope_view_reflects_exactly_the_enabled_pairs():
    reg = resolved(record("eurostat_earnings", "DE", features=["compensation", "labour_outlook"]), record("ons_ashe", "UK", features=["compensation"]),
                   record("esco", "FR", features=["bogus"]))                    # the invalid one contributes nothing
    view = ka.beta_scope_view(reg)
    assert view["approved_markets"] == ["DE", "UK"]
    assert view["enabled_features"] == ["compensation", "labour_outlook"]
    assert view["qualified_sources"] == [{"source_id": "eurostat_earnings", "market": "DE"}, {"source_id": "ons_ashe", "market": "UK"}]
    assert set(view) == {"schema_version", "enabled_features", "approved_markets", "qualified_sources"}


def test_02e_snapshot_agrees_with_the_register_when_that_file_is_present():
    snap = ROOT / "evaluations" / "beta_scope_coverage" / "approval_register.json"
    if not snap.exists():
        return                                                                  # 02E not merged on this tree: the adapter is the contract
    d = json.loads(snap.read_text(encoding="utf-8"))
    view = ka.beta_scope_view(ka.resolve(ka.load_committed(COMMITTED)[0], ka.MODE_ENFORCED, manifest_tiers=TIERS))
    assert d["enabled_features"] == view["enabled_features"] and d["approved_markets"] == view["approved_markets"]
    assert d["qualified_sources"] == view["qualified_sources"]


def test_features_vocabulary_equals_the_02e_one_when_present():
    p = ROOT / "src" / "copilot" / "evaluation" / "beta_scope_coverage.py"
    if not p.exists():
        return
    m = re.search(r"FEATURES = \{(.*?)\n\}", p.read_text(encoding="utf-8"), re.S)
    assert m and tuple(re.findall(r'^\s+"(\w+)":', m.group(1), re.M)) == ka.FEATURES


# ---------------------------------------------------------------- the engineering filter, end to end through the Career service
def _translator():
    payload = {"intent": "skill_research", "retrieval_required": True, "rewritten_query": "nurse role outlook", "alternate_queries": [],
               "metadata_filters": {}, "explanation": "ok"}
    return QueryTranslator(responder=lambda m: ModelReply(content=json.dumps(payload)))


def _store():
    s = InMemoryVectorStore(LocalHashEmbedder())
    s.add_chunks([
        DocumentChunk(chunk_id="ooh", doc_id="d1", text="Registered nurses provide and coordinate patient care nurse role outlook.",
                      metadata={"title": "OOH nurses", "document_type": "occupation", "manifest_source_id": "bls_ooh", "country": "US"}),
        DocumentChunk(chunk_id="eu", doc_id="d2", text="Nurse role outlook across the euro area from the earnings survey.",
                      metadata={"title": "EU earnings", "document_type": "labour_market", "manifest_source_id": "eurostat_earnings", "country": "EU"}),
        DocumentChunk(chunk_id="gov", doc_id="d3", text="Nurse role outlook note uploaded by an administrator.",
                      metadata={"title": "Gov note", "document_type": "governed_knowledge", "knowledge_source_id": "src-77", "country": ""}),
        DocumentChunk(chunk_id="anon", doc_id="d4", text="Nurse role outlook anonymous passage without any source identity.",
                      metadata={"title": "Anon", "document_type": "occupation"}),
    ])
    return s


class _Coordinator:
    """Returns the Phase 00 finding: curated US compensation and narrative records reachable by a Candidate."""

    def retrieve(self, route_decision, query, country=None):
        def ev(eid, sid, etype, geo):
            return KnowledgeEvidence(evidence_id=eid, text=f"{sid} record text", source_id=sid, source_title=sid, evidence_type=etype,
                                     retrieval_lane="compensation", geography=geo, country=geo, score=1.0)
        return SimpleNamespace(evidence=[ev("c1", "bls_oews", "compensation", "US"), ev("c2", "ons_ashe", "compensation", "UK"),
                                         ev("c3", "eurostat_earnings", "compensation", "EU")],
                               sources_considered=[], source_precedence=[], structured_queries=[], notes=[], resolved=None, clarify=False)


def _svc():
    return CareerIntelligenceService(config=CONFIG, retriever=build_retriever(CONFIG, mode="hybrid", store=_store()), translator=_translator(),
                                     synthesis_responder=lambda m: ModelReply(content="Answer [1]."), knowledge_coordinator=_Coordinator())


_TITLE_TO_SOURCE = {"OOH nurses": "bls_ooh", "EU earnings": "eurostat_earnings", "Gov note": "governed:src-77", "Anon": None}


def _sources(result) -> set[str | None]:
    """Source identity of each returned evidence item (narrative evidence is mapped through its chunk title, as its metadata is a reduced projection)."""
    return {ka.source_key(e.metadata, e.source_id) or _TITLE_TO_SOURCE.get(e.source_title) for e in result.evidence}


def test_phase_00_finding_curated_us_sources_are_reachable_in_development_but_labelled(monkeypatch):
    monkeypatch.setenv("API_ENV", "development")
    result = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="UK")
    srcs = _sources(result)
    assert {"bls_ooh", "bls_oews"} <= srcs                                     # the finding, still visible in development
    flagged = [e for e in result.evidence if (e.metadata or {}).get("source_qualification") == "UNQUALIFIED"]
    assert flagged and len(flagged) == len(result.evidence)                       # ...and every item is labelled UNQUALIFIED
    assert any("labelled UNQUALIFIED" in n for n in result.trace.notes)


@pytest.mark.parametrize("market", ["UK", "DE", "US", "EU", None, "FR"])
def test_phase_00_finding_closed_in_hosted_mode_nothing_is_retrievable_with_an_empty_register(hosted, market):
    result = _svc().retrieve_evidence("What is the outlook for a nurse role?", market=market)
    assert result.evidence == [] and result.insufficient_evidence is True
    assert result.citations == []
    assert any("Withheld" in n for n in result.trace.notes)
    full = _svc().answer("What does a nurse earn?", market=market)
    assert not full.response.retrieved and not full.response.evidence


def test_hosted_bls_ooh_passage_is_not_retrievable_even_with_a_us_record_for_a_uk_candidate(hosted):
    ka.install_synthetic_register(register(record("bls_ooh", "US", features=["role_definition"]), record("bls_oews", "US")))
    uk = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="UK")
    assert not ({"bls_ooh", "bls_oews"} & _sources(uk))                           # cross-market isolation (and OD-US-CONTENT undecided)
    us = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="US")
    assert {"bls_ooh", "bls_oews"} <= _sources(us)                                 # a US market with complete records may receive them
    assert not ({"eurostat_earnings", "ons_ashe", "governed:src-77"} & _sources(us))


def test_hosted_us_record_for_a_non_us_market_does_not_enable_us_content(hosted):
    ka.install_synthetic_register(register(record("bls_ooh", "DE", features=["role_definition"]), record("bls_oews", "DE")))
    de = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="DE")
    assert not ({"bls_ooh", "bls_oews"} & _sources(de))


def test_hosted_only_the_approved_pair_is_served_and_unidentified_sources_are_dropped(hosted):
    ka.install_synthetic_register(register(record("eurostat_earnings", "DE"), record("governed:src-77", "DE", features=["role_definition"])))
    de = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="DE")
    assert _sources(de) == {"eurostat_earnings", "governed:src-77"}                # anonymous chunk (no source identity) is dropped, ons_ashe/US not enabled
    fr = _svc().retrieve_evidence("What is the outlook for a nurse role?", market="FR")
    assert fr.evidence == []                                                       # cross-market isolation


def test_market_falls_back_to_the_country_the_question_names_and_never_to_a_language(hosted):
    ka.install_synthetic_register(register(record("eurostat_earnings", "DE"), record("governed:src-77", "DE", features=["role_definition"])))
    named = _svc().retrieve_evidence("What is the outlook for a nurse role in Germany?")
    assert _sources(named) >= {"eurostat_earnings"}
    unnamed = _svc().retrieve_evidence("Was ist die Aussicht fuer eine Pflegekraft?")      # German words, no country, no selected market
    assert unnamed.evidence == []
    assert af.effective_market(None, None) is None
    assert af.effective_market("fr", "DE") == "FR" and af.effective_market("", "gb") == "UK"


def test_apply_reports_counts_and_ids_only(hosted):
    res, ev, rep = af.apply([], [KnowledgeEvidence(evidence_id="x", text="secret body", source_id="bls_oews", source_title="t", evidence_type="compensation",
                                                    retrieval_lane="compensation")], selected_market="UK", detected_country=None)
    assert ev == [] and rep.dropped_count == 1
    assert "secret body" not in (rep.note() or "")


def test_application_service_passes_the_selected_market_only_when_set():
    seen = []

    class Svc:
        def answer(self, query, **kw):
            seen.append(("answer", kw))
            return SimpleNamespace(insufficient_evidence=False)

        def retrieve_evidence(self, query, **kw):
            seen.append(("search", kw))
            return SimpleNamespace(insufficient_evidence=False)

    app = CareerApplicationService(CONFIG, service=Svc())
    app.chat(CareerChatRequest(query="q", market="de"))
    app.chat(CareerChatRequest(query="q"))
    app.search_knowledge(KnowledgeSearchRequest(query="q", market="fr"))
    app.search_knowledge(KnowledgeSearchRequest(query="q"))
    assert seen[0][1]["market"] == "de" and "market" not in seen[1][1]
    assert seen[2][1]["market"] == "fr" and "market" not in seen[3][1]


def test_chat_route_passes_the_account_geography_not_a_language(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api import dependencies as deps
    from src.api.main import create_app

    captured = {}

    class Svc:
        def chat(self, request):
            captured["market"], captured["lang"] = request.market, request.conversation_language
            return SimpleNamespace(answer="a", citations=[], retrieved=[], insufficient_evidence=True, trace=None, response=SimpleNamespace(retrieved=[]))

    monkeypatch.setenv("API_ENV", "development")
    app = create_app()
    app.dependency_overrides[deps.get_career_service] = lambda: Svc()
    app.dependency_overrides[deps.get_current_principal] = lambda: SimpleNamespace(career_geography="ie", user_id=1)
    try:
        with TestClient(app) as c:
            c.post("/api/v1/career/chat", json={"question": "What does a nurse do?", "conversation_language": "de"})
    except Exception:  # noqa: BLE001 - response shaping is out of scope here; only the request mapping is asserted
        pass
    assert captured.get("market") == "ie" and captured.get("lang") == "de"       # German conversation language did not become the German market


def test_deep_copy_of_register_data_is_not_mutated_by_resolve():
    data = register(record())
    snap = copy.deepcopy(data)
    ka.resolve(data, ka.MODE_ENFORCED, manifest_tiers=TIERS)
    assert data == snap
