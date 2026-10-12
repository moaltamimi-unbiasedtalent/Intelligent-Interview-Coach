"""Pilot 2 remediation P2-02: the isolated, synthetic, offline Pilot knowledge fixture.

Proves fixture construction, store isolation, production retrieval integration (search_knowledge -> retrieve_evidence over the real
hybrid retriever and ChromaStore), citation/provenance flow and the fail-closed protected-path guard. Everything runs in tmp_path with the
offline local embedder; any network connection or synthesis-model call fails the test. It does NOT prove human Sources discoverability,
model-generated citation quality, live-provider behaviour, multilingual KB quality, production corpus quality or semantic embedding quality.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pilot_isolated_knowledge", ROOT / "scripts/pilot/isolated_knowledge.py")
ik = importlib.util.module_from_spec(_spec)
sys.modules["pilot_isolated_knowledge"] = ik
_spec.loader.exec_module(ik)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """The fixture must be fully offline: any socket connection fails the test."""
    def blocked(self, *a, **k):
        raise AssertionError("network access is not allowed in the Pilot knowledge fixture")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    for var in ("OPENROUTER_API_KEY", "COPILOT_API_KEY", "COPILOT_EMBEDDING_API_KEY", "OPENAI_API_KEY", "COPILOT_CHROMA_DIR"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def kb(tmp_path):
    out = tmp_path / "pilot-kb"
    report = ik.build(out)
    return out, report


def _repo_data_snapshot() -> dict[str, tuple[int, int]]:
    data = ROOT / "data"
    snap: dict[str, tuple[int, int]] = {}
    if data.exists():
        for p in data.rglob("*"):
            if p.is_file():
                st = p.stat()
                snap[str(p)] = (st.st_size, st.st_mtime_ns)
    return snap


def test_fixture_is_clearly_synthetic_and_carries_no_authority_or_url():
    fx = ik.load_fixture()
    assert fx["synthetic"] is True and "SYNTHETIC" in fx["warning"]
    text = json.dumps(fx).lower()
    assert "http" not in text and "www." not in text                       # no fabricated external domain
    assert "authority_level" not in text                                    # never masquerades as authority 1/2/3
    assert "participant" not in text and "curriculum" not in text           # no participant or CV content
    for chunk in ik.fixture_chunks(fx):
        assert chunk.text.startswith("[Synthetic pilot test data]")
        assert "source_url" not in chunk.metadata and "authority_level" not in chunk.metadata
        assert chunk.metadata["publisher"].endswith("(synthetic test data)")


def test_builds_into_tmp_path_with_the_production_store_settings(kb):
    out, report = kb
    from src.copilot import constants
    assert report.embedding_provider == "local" and report.embedding_model == constants.LOCAL_EMBEDDING_MODEL == "local-hash-v1"
    assert report.collection == constants.CHROMA_COLLECTION_NAME == "career_knowledge_base"
    assert Path(report.chroma_dir) == (out / "chroma").resolve()
    assert (out / ik.MARKER_NAME).is_file() and (out / "chroma").is_dir()
    assert report.sources == 4 and report.chunks == 10 and report.total_in_collection == 10 and report.added == 10


def test_never_writes_to_repository_data(tmp_path):
    before = _repo_data_snapshot()
    ik.build(tmp_path / "kb")
    assert _repo_data_snapshot() == before


@pytest.mark.parametrize("target", ["REPO", "REPO/data", "REPO/data/chroma", "REPO/anything", "/", "HOME"])
def test_refuses_protected_or_unsafe_paths(target):
    path = target.replace("REPO", str(ROOT)).replace("HOME", str(Path.home()))
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(path)


def test_refuses_the_configured_developer_chroma_dir(monkeypatch, tmp_path):
    protected = tmp_path / "dev-chroma"
    protected.mkdir()
    monkeypatch.setenv("COPILOT_CHROMA_DIR", str(protected))
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(protected)
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(protected / "nested")


def test_refuses_symlinks_git_trees_and_populated_foreign_directories(tmp_path):
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "link"; link.symlink_to(real)
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(link)
    repo = tmp_path / "gitrepo"; (repo / ".git").mkdir(parents=True)
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(repo / "kb")
    foreign = tmp_path / "foreign"; foreign.mkdir(); (foreign / "important.txt").write_text("x")
    with pytest.raises(ik.UnsafeOutputError):
        ik.ensure_safe_output_dir(foreign)
    assert (foreign / "important.txt").read_text() == "x"                  # untouched


def test_reset_only_applies_to_an_existing_fixture_directory(tmp_path):
    fresh = tmp_path / "fresh"
    with pytest.raises(ik.UnsafeOutputError):
        ik.build(fresh, reset=True)                                        # no marker: refuse (cannot be used to wipe an arbitrary store)
    assert not (fresh / "chroma").exists()
    ik.build(fresh)
    again = ik.build(fresh, reset=True)
    assert again.total_in_collection == 10 and again.added == 10


def test_build_is_deterministic_and_idempotent(tmp_path):
    first = ik.build(tmp_path / "kb")
    second = ik.build(tmp_path / "kb")
    assert (first.chunks, first.sources) == (second.chunks, second.sources) == (10, 4)
    assert second.added == 0 and second.skipped_existing == 10 and second.total_in_collection == 10   # no duplicate chunks
    ids = [c.chunk_id for c in ik.fixture_chunks(ik.load_fixture())]
    assert len(ids) == len(set(ids)) == 10
    assert ids == [c.chunk_id for c in ik.fixture_chunks(ik.load_fixture())]                          # stable ids


def test_no_provider_credential_is_required_or_read(kb):
    out, report = kb
    cfg = ik._config(out / "chroma")
    assert cfg.api_key is None and cfg.embedding_api_key is None and cfg.embedding_provider == "local"
    assert ik._chroma_store(cfg).embedder.provider == "local"


def test_validation_passes_through_the_production_retrieval_boundary(kb):
    out, _ = kb
    result = ik.validate(out)
    assert result.ok, result.failed()
    assert result.details["known_sources"] > 0 and result.details["known_citations"] >= 1
    assert result.details["known_strategy"] == "hybrid"


def test_search_knowledge_returns_fixture_evidence_citations_and_provenance(kb):
    out, _ = kb
    from src.application.career_service import CareerApplicationService
    from src.application.models import KnowledgeSearchRequest
    from src.copilot.rag.translation import QueryTranslator
    from src.copilot.retrieval import build_retriever
    from src.copilot.service import CareerIntelligenceService, KnowledgeRetrievalResult

    cfg = ik._config(out / "chroma")
    store = ik._chroma_store(cfg)
    retriever = build_retriever(cfg, mode="hybrid", store=store)
    # BM25 and vector read the SAME store chunks.
    assert {c.chunk_id for c in retriever.keyword.chunks} == {c.chunk_id for c in store.all_chunks()} if hasattr(retriever, "keyword") and hasattr(getattr(retriever, "keyword"), "chunks") else True
    svc = CareerIntelligenceService(config=cfg, retriever=retriever, translator=QueryTranslator(config=cfg), knowledge_coordinator=None)
    res = CareerApplicationService(cfg, service=svc).search_knowledge(KnowledgeSearchRequest(query=ik.KNOWN_QUERY))
    assert isinstance(res, KnowledgeRetrievalResult)
    assert res.evidence and res.source_count > 0 and res.insufficient_evidence is False and res.citations
    fixture_ids = {c.chunk_id: c for c in ik.fixture_chunks(ik.load_fixture())}
    for cit in res.citations:
        chunk = fixture_ids[cit.chunk_id]                                  # the citation points at real fixture evidence
        assert cit.doc_id == chunk.doc_id and cit.title == chunk.metadata["title"]
        assert cit.source in (chunk.metadata["source"], chunk.doc_id)      # provenance flows from the stored chunk metadata
        assert cit.source_url is None                                      # no invented URL; the no-URL rendering is the correct one
        assert "pilot fixture" in cit.title.lower()                        # the displayed title itself says it is the Pilot fixture
    for ev in res.evidence:
        assert ev.text.startswith("[Synthetic pilot test data]")
        assert (ev.publisher or "").endswith("(synthetic test data)") or ev.publisher is None


def test_no_synthesis_model_and_no_tool_is_invoked(kb, monkeypatch):
    out, _ = kb
    ik._NoSynthesis.calls = 0
    import src.copilot.rag.translation as tr
    monkeypatch.setattr(tr, "build_openrouter_responder", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no provider responder may be built")), raising=False)
    assert ik.validate(out).ok
    assert ik._NoSynthesis.calls == 0


def test_unrelated_and_injection_queries_do_not_invent_fixture_claims(kb):
    out, _ = kb
    res = ik.validate(out)
    assert res.checks["unrelated_query_does_not_invent_fixture_claims"] and res.checks["injection_query_is_blocked_with_no_evidence"]
    assert res.details["unrelated_evidence"] == 0 and res.details["unrelated_insufficient"] is True and res.details["injection_blocked"] is True


def test_validation_refuses_a_directory_that_is_not_a_fixture(tmp_path):
    with pytest.raises(ik.UnsafeOutputError):
        ik.validate(tmp_path / "empty-or-missing")


def test_deleting_the_fixture_directory_leaves_everything_else_untouched(tmp_path):
    before = _repo_data_snapshot()
    out = tmp_path / "kb"
    ik.build(out)
    import shutil
    shutil.rmtree(out)
    assert not out.exists()
    assert _repo_data_snapshot() == before


def test_cli_exits_nonzero_for_a_protected_path_and_zero_for_a_safe_one(tmp_path, capsys):
    cli = importlib.util.spec_from_file_location("pilot_build_cli", ROOT / "scripts/pilot/build_isolated_knowledge.py")
    mod = importlib.util.module_from_spec(cli); cli.loader.exec_module(mod)
    assert mod.main(["--output-dir", str(ROOT / "data" / "chroma")]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert mod.main(["--output-dir", str(tmp_path / "ok"), "--validate"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC PILOT TEST DATA" in out and "COPILOT_CHROMA_DIR=" in out and "COPILOT_EMBEDDING_PROVIDER=local" in out
