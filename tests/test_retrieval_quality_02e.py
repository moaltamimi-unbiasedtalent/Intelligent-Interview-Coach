"""02E: metrics, calibrated relevance floor (mechanism, resolution, calibration, abstention) and provider-call accounting. Offline and deterministic."""

from __future__ import annotations

import json
import math

import pytest

from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.models import DocumentChunk, RetrievalResult
from src.copilot.retrieval import vector as vector_mod
from src.copilot.retrieval_quality import accounting as A
from src.copilot.retrieval_quality import floor as F
from src.copilot.retrieval_quality import metrics as M


# ------------------------------------------------------------------ metrics
def test_recall_precision_known_values():
    ranked = ["a", "x", "b", "y", "c"]
    assert M.recall_at_k(ranked, {"a", "b", "c"}, 1) == pytest.approx(1 / 3)
    assert M.recall_at_k(ranked, {"a", "b", "c"}, 5) == 1.0
    assert M.precision_at_k(ranked, {"a", "b", "c"}, 4) == 0.5
    assert M.recall_at_k(ranked, set(), 3) is None            # undefined, never 0 or 1
    assert M.precision_at_k([], {"a"}, 3) is None
    assert M.recall_at_k(["a", "a", "a", "b"], {"a", "b"}, 2) == 1.0     # duplicates keep the first occurrence only
    for bad in (0, -1, True, 2.5):
        with pytest.raises(ValueError):
            M.recall_at_k(["a"], {"a"}, bad)  # type: ignore[arg-type]


def test_ndcg_known_values_and_graded_gains():
    assert M.ndcg_at_k(["a", "b"], {"a", "b"}, 2) == pytest.approx(1.0)
    # relevant item at rank 2 of 1 relevant: DCG = 1/log2(3); IDCG = 1
    assert M.ndcg_at_k(["x", "a"], {"a"}, 5) == pytest.approx(1 / math.log2(3))
    assert M.ndcg_at_k(["x", "y"], {"a"}, 5) == 0.0
    assert M.ndcg_at_k(["a"], {}, 5) is None
    graded = {"a": 3.0, "b": 1.0}
    best = M.ndcg_at_k(["a", "b"], graded, 2)
    worse = M.ndcg_at_k(["b", "a"], graded, 2)
    assert best == pytest.approx(1.0) and 0.0 < worse < best
    with pytest.raises(ValueError):
        M.ndcg_at_k(["a"], {"a": -1.0}, 3)


def test_mrr_skips_cases_without_relevant_items():
    assert M.reciprocal_rank(["x", "a"], {"a"}) == 0.5
    assert M.reciprocal_rank(["x"], {"a"}) == 0.0
    assert M.reciprocal_rank(["x"], set()) is None
    assert M.mean_reciprocal_rank([(["a"], {"a"}), (["x", "a"], {"a"}), (["x"], set())]) == pytest.approx(0.75)
    assert M.mean_reciprocal_rank([]) is None


def test_cross_language_retrieval_rate():
    langs = {"p.en": "en", "p.de": "de", "p.fr": "fr"}
    cases = [("en", ["p.de", "p.en"], {"p.en", "p.de"}),       # a German source relevant to an English question: found
             ("en", ["p.en", "p.fr"], {"p.de"}),               # the only cross-language source is missed
             ("de", ["p.de"], {"p.de"})]                       # no cross-language source exists: not applicable
    assert M.cross_language_retrieval_rate(cases, langs, k=1) == pytest.approx(0.5)
    assert M.cross_language_retrieval_rate([("de", ["p.de"], {"p.de"})], langs) is None


def test_citation_accuracy_and_abstention_correctness():
    assert M.citation_accuracy([(["a", "b"], {"a"}), (["c"], {"c"})]) == pytest.approx(2 / 3)
    assert M.citation_accuracy([([], {"a"})]) is None          # nothing cited: neither accurate nor inaccurate
    out = M.abstention_correctness([(True, True), (False, False), (False, True), (True, False)])
    assert out["accuracy"] == 0.5 and out["false_answer_rate"] == 0.5 and out["false_abstention_rate"] == 0.5
    assert out["counts"] == {"abstained_correctly": 1, "abstained_wrongly": 1, "answered_correctly": 1, "answered_wrongly": 1}
    empty = M.abstention_correctness([])
    assert empty["accuracy"] is None and empty["false_answer_rate"] is None


# ------------------------------------------------------------------ floor mechanism
def _result(score: float, cid: str = "c") -> RetrievalResult:
    return RetrievalResult(chunk=DocumentChunk(chunk_id=cid, doc_id=cid, text="t"), score=score, retriever="vector")


def test_floor_is_exclusive_and_an_irrelevant_only_result_set_abstains():
    results = [_result(0.31, "i1"), _result(0.2, "i2"), _result(0.05, "i3")]       # all irrelevant, all below a 0.35 floor
    assert F.abstains(results, F.RelevanceFloor(0.35, "calibrated"))
    kept = F.apply_floor([_result(0.9, "good"), *results], 0.35)
    assert [r.chunk.chunk_id for r in kept] == ["good"]
    assert F.apply_floor([_result(0.35, "edge")], 0.35) == []                      # strictly above
    assert [r.chunk.chunk_id for r in F.apply_floor([_result(float("nan"), "nan"), _result(0.9, "ok")], 0.1)] == ["ok"]
    assert F.abstains([_result(float("nan"))], F.DEFAULT_FLOOR)                    # a NaN score never survives


def test_default_floor_abstains_on_no_similarity_and_is_the_resolved_default(tmp_path):
    fl = F.resolve_floor(("openai", "m", "v1", 8), env={}, table_path=tmp_path / "none.json")
    assert (fl.value, fl.source) == (0.0, "default")
    assert F.abstains([_result(0.0), _result(-0.2)], fl)


def test_environment_override_wins_and_an_invalid_override_never_loosens(tmp_path):
    assert F.resolve_floor(None, env={F.FLOOR_ENV: "0.42"}, table_path=tmp_path / "x.json").value == 0.42
    for bad in ("abc", "1.0", "-0.1", "nan"):
        with pytest.raises(F.FloorConfigurationError):
            F.resolve_floor(None, env={F.FLOOR_ENV: bad}, table_path=tmp_path / "x.json")


def _table(tmp_path, entries):
    p = tmp_path / "floors.json"
    p.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return p


def test_only_approved_exact_identity_entries_apply(tmp_path):
    ident = ("openai", "model-a", "v1", 8)
    key = F.identity_key(*ident)
    table = _table(tmp_path, [{"identity": key, "language": "*", "floor": 0.4, "approved": True},
                              {"identity": key, "language": "de", "floor": 0.5, "approved": True},
                              {"identity": F.identity_key("openai", "model-b", "v1", 8), "language": "*", "floor": 0.9, "approved": True},
                              {"identity": key, "language": "fr", "floor": 0.99, "approved": False}])
    assert F.resolve_floor(ident, env={}, table_path=table).value == 0.4
    assert F.resolve_floor(ident, language="de", env={}, table_path=table).value == 0.5
    assert F.resolve_floor(ident, language="fr", env={}, table_path=table).value == 0.4        # unapproved entry ignored
    assert F.resolve_floor(("openai", "model-a", "v2", 8), env={}, table_path=table).source == "default"   # other version
    assert F.resolve_floor(("openai", "model-a", None, 8), env={}, table_path=table).source == "default"   # unknown field never inherits
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(F.FloorConfigurationError):
        F.resolve_floor(ident, env={}, table_path=tmp_path / "bad.json")


def test_committed_floor_table_is_empty_so_every_embedder_uses_the_default():
    data = json.loads(F.FLOOR_TABLE_PATH.read_text(encoding="utf-8"))
    assert data["entries"] == []


# ------------------------------------------------------------------ calibration
def _q(qid, lang, scored, answerable=True):
    return F.ScoredQuery(qid, lang, tuple(scored), answerable)


def test_calibration_proposes_the_highest_recall_floor_meeting_precision_and_abstention():
    qs = [_q(f"a{i}", "en", [(0.8, True), (0.45, False), (0.2, False)]) for i in range(3)]
    qs += [_q(f"b{i}", "en", [(0.6, True), (0.5, True), (0.3, False)]) for i in range(2)]
    qs += [_q(f"n{i}", "en", [(0.42, False), (0.3, False)], answerable=False) for i in range(3)]
    out = F.calibrate(qs, min_precision=0.9, min_queries_per_language=1)
    en = out["by_language"]["en"]
    # floors below 0.45 keep an irrelevant 0.45 on answerable queries and (<0.42) an irrelevant citation on unanswerable ones; 0.45 is the lowest clean floor
    assert en["proposed_floor"] == 0.45
    assert en["at_proposal"]["irrelevant_citation_rate"] == 0.0 and en["at_proposal"]["precision"] == 1.0
    assert en["at_proposal"]["recall"] == pytest.approx(7 / 7)
    assert out["applied"] is False
    assert [p["floor"] for p in en["curve"]] == sorted(p["floor"] for p in en["curve"])


def test_calibration_is_per_language_and_flags_thin_samples():
    qs = [_q("e1", "en", [(0.9, True), (0.1, False)]), _q("e2", "en", [(0.2, False)], False),
          _q("d1", "de", [(0.5, True), (0.45, False)]), _q("d2", "de", [(0.44, False)], False)]
    out = F.calibrate(qs)
    assert set(out["by_language"]) == {"de", "en"}
    assert out["by_language"]["en"]["proposed_floor"] != out["by_language"]["de"]["proposed_floor"]
    assert all(v["confidence"] == "insufficient_sample" for v in out["by_language"].values())     # 2 queries each, far below the planning bound


def test_calibration_without_a_clean_floor_proposes_nothing():
    # the irrelevant chunk outscores the relevant one: no floor can reach the precision target, so the safe default stays
    qs = [_q("q", "en", [(0.9, False), (0.5, True)])]
    out = F.calibrate(qs, min_precision=0.9, min_queries_per_language=1)
    assert out["by_language"]["en"]["proposed_floor"] is None


def test_calibration_without_unanswerable_queries_is_flagged_unmeasured():
    out = F.calibrate([_q("q", "en", [(0.9, True)])], min_queries_per_language=1)
    assert out["by_language"]["en"]["confidence"] == "insufficient_sample" and out["by_language"]["en"]["unanswerable"] == 0
    with pytest.raises(ValueError):
        F.calibrate([], min_precision=1.5)


# ------------------------------------------------------------------ wiring into the vector retriever
class _Hit:
    def __init__(self, cid, score):
        self.chunk_id, self.doc_id, self.text, self.score, self.metadata = cid, cid, "t", score, {}


class _Store:
    embedder = LocalHashEmbedder(16)

    def __init__(self, hits):
        self._hits = hits

    def query(self, query, top_k=5, filters=None):
        return self._hits


def test_vector_retriever_uses_the_default_floor_and_a_configured_one(monkeypatch):
    monkeypatch.delenv(F.FLOOR_ENV, raising=False)
    hits = [_Hit("hi", 0.8), _Hit("mid", 0.3), _Hit("zero", 0.0), _Hit("neg", -0.1)]
    default = vector_mod.VectorRetriever(_Store(hits), floor=None).retrieve("q")
    assert [r.chunk.chunk_id for r in default] == ["hi", "mid"]                       # P10D behaviour preserved
    strict = vector_mod.VectorRetriever(_Store(hits), floor=F.RelevanceFloor(0.5, "calibrated")).retrieve("q")
    assert [r.chunk.chunk_id for r in strict] == ["hi"]
    irrelevant_only = [_Hit("a", 0.2), _Hit("b", 0.1)]
    assert vector_mod.VectorRetriever(_Store(irrelevant_only), floor=F.RelevanceFloor(0.35, "calibrated")).retrieve("q") == []   # abstains
    monkeypatch.setenv(F.FLOOR_ENV, "0.5")
    assert [r.chunk.chunk_id for r in vector_mod.VectorRetriever(_Store(hits)).retrieve("q")] == ["hi"]


# ------------------------------------------------------------------ accounting
class _Inner(LocalHashEmbedder):
    provider = "fake"


def test_summarise_percentiles_throughput_and_unknown_cost():
    recs = [A.ProviderCallRecord("m", "documents", 4, 100, 100.0), A.ProviderCallRecord("m", "query", 1, 10, 50.0),
            A.ProviderCallRecord("m", "query", 1, 10, 150.0, ok=False, error_code="provider_error")]
    s = A.summarise(recs)
    assert (s["calls"], s["failed_calls"], s["texts"], s["tokens"]) == (3, 1, 6, 120)
    assert s["latency_ms"]["p50"] == 100.0 and s["latency_ms"]["p95"] == 150.0
    assert s["throughput"]["tokens_per_second"] == pytest.approx(120 / 0.3, rel=1e-3)
    assert s["cost_usd"] is None and s["cost_basis"] == "unknown"                       # unknown is never 0
    priced = A.summarise(recs, price_per_million_tokens_usd=2.0)
    assert priced["cost_usd"] == pytest.approx(120 * 2.0 / 1e6) and priced["cost_basis"] == "configured_price"
    assert A.summarise([])["latency_ms"]["p50"] is None


def test_recording_embedder_records_every_call_and_failures_with_a_code_only():
    ticks = iter([0.0, 0.010, 1.0, 1.020, 2.0, 2.005])
    rec = A.RecordingEmbedder(_Inner(8), clock=lambda: next(ticks))
    rec.embed_documents(["a" * 40, "b" * 8])
    rec.embed_query("q" * 12)

    class Boom(_Inner):
        def embed_query(self, text):
            raise RuntimeError("secret provider detail")

    bad = A.RecordingEmbedder(Boom(8), clock=lambda: next(ticks))
    with pytest.raises(RuntimeError):
        bad.embed_query("x")
    assert [(r.kind, r.texts, r.tokens, r.ok) for r in rec.records] == [("documents", 2, 12, True), ("query", 1, 3, True)]
    assert rec.records[0].latency_ms == pytest.approx(10.0)
    assert bad.records[0].ok is False and bad.records[0].error_code == "provider_error" and "secret" not in json.dumps(bad.records[0].to_dict())


def test_relevance_floor_evaluator_runs_offline_and_never_applies_its_proposal(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out_file = tmp_path / "floor.json"
    out = subprocess.run([sys.executable, str(root / "scripts" / "eval_relevance_floor.py"), "--write", str(out_file)], capture_output=True, text=True,
                         cwd=tmp_path, timeout=300, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(root)})
    assert out.returncode == 0, out.stderr
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["applied"] is False and "NOT production quality evidence" in data["label"]
    assert set(data["by_language"]) == {"en", "de", "fr", "es", "it", "pt", "nl"} and data["curves"]["overall"]
    assert json.loads(F.FLOOR_TABLE_PATH.read_text(encoding="utf-8"))["entries"] == []     # nothing was written into the floor table
