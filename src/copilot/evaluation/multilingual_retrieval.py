"""Seven-language retrieval benchmark harness (package 02B). OFFLINE and deterministic with the local embedder.

Compares retrieval MODES (vector, BM25, and their reciprocal-rank fusion) on a FROZEN dataset (``evaluations/retrieval_multilingual/dataset_v1.json``,
SHA-256 recorded in :data:`FROZEN_DATASET_SHA256`; a changed file is refused) of 7 topics x 7 languages (en, de, fr, es, it, pt, nl) with one question per
topic and language. Three slices:

* ``same_language``   the corpus holds only passages in the question's language; relevant = the topic's passage.
* ``cross_language``  the corpus holds only passages in OTHER languages (question language differs from every source language); relevant = the
                      topic's passages in those languages. This is the cross-language question-vs-source-language case.
* ``mixed_corpus``    the corpus holds all 49 passages; relevant = the topic's passage in every language.

Metrics: recall@k (fraction of the relevant set found in the top k) and MRR (first relevant rank), overall and per question language.

HONESTY RULES (enforced by tests): results computed with the local hash embedder are labelled ``local embedder, NOT production quality evidence``;
the result always carries the statement that the production-embedder benchmark awaits OD-BUDGET; this module never claims semantic retrieval
passed, never calls the network, and refuses to run a paid embedder without the approval guard in ``src.copilot.embedding_budget``.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.copilot.embedding_budget import estimate_embedding_run, guard_embedder
from src.copilot.embeddings import BaseEmbedder
from src.copilot.models import DocumentChunk, RetrievalResult
from src.copilot.retrieval.fusion import reciprocal_rank_fusion
from src.copilot.retrieval.keyword import KeywordRetriever

DATASET_PATH = Path(__file__).resolve().parents[3] / "evaluations" / "retrieval_multilingual" / "dataset_v1.json"
FROZEN_DATASET_SHA256 = "6d9a10614b3f2de953f7228f0b21b062d42faa667b49c4ab02bf1477d10bd8af"
LANGUAGES = ("en", "de", "fr", "es", "it", "pt", "nl")
SLICES = ("same_language", "cross_language", "mixed_corpus")
MODES = ("vector", "bm25", "rrf")
KS = (1, 3, 5, 10)
LOCAL_LABEL = "local embedder, NOT production quality evidence"
PENDING_STATEMENT = ("The production-embedder benchmark awaits OD-BUDGET (owner budget approval) and has NOT been run. No semantic retrieval quality "
                     "is claimed by this result.")


class DatasetIntegrityError(Exception):
    """The dataset file does not match the recorded hash (it is frozen)."""


def dataset_sha256(path: Path | None = None) -> str:
    return hashlib.sha256((path or DATASET_PATH).read_bytes()).hexdigest()


def load_dataset(path: Path | None = None, *, expected_sha256: str | None = FROZEN_DATASET_SHA256) -> dict:
    p = path or DATASET_PATH
    raw = p.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise DatasetIntegrityError("the frozen dataset does not match its recorded hash")
    data = json.loads(raw.decode("utf-8"))
    return data


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0.0 or nb == 0.0 else dot / (na * nb)


def _chunk(p: dict) -> DocumentChunk:
    return DocumentChunk(chunk_id=p["id"], doc_id=p["id"], text=p["text"], metadata={"language": p["language"], "topic": p["topic"]})


def _corpus_for(slice_name: str, lang: str, passages: list[dict]) -> list[dict]:
    if slice_name == "same_language":
        return [p for p in passages if p["language"] == lang]
    if slice_name == "cross_language":
        return [p for p in passages if p["language"] != lang]
    return list(passages)


def _metrics(ranked_ids: list[str], relevant: set[str], ks: tuple[int, ...]) -> dict:
    out: dict[str, float] = {}
    for k in ks:
        out[f"recall@{k}"] = len(set(ranked_ids[:k]) & relevant) / len(relevant) if relevant else 0.0
    rr = 0.0
    for rank, cid in enumerate(ranked_ids, start=1):
        if cid in relevant:
            rr = 1.0 / rank
            break
    out["mrr"] = rr
    return out


def _aggregate(rows: list[dict], ks: tuple[int, ...]) -> dict:
    n = len(rows)
    keys = [f"recall@{k}" for k in ks] + ["mrr"]
    return {"n": n, **{k: (round(sum(r[k] for r in rows) / n, 4) if n else None) for k in keys}}


def run_benchmark(embedder: BaseEmbedder, *, dataset: dict | None = None, ks: tuple[int, ...] = KS, label: str | None = None) -> dict:
    """Run every mode on every slice. Deterministic for a deterministic embedder. The embedder is passed through the paid-call guard first, so a
    paid embedder cannot be used without the explicit owner approval environment (see ``src.copilot.embedding_budget``)."""
    embedder = guard_embedder(embedder)
    ds = dataset or load_dataset()
    passages, queries = ds["passages"], ds["queries"]
    is_local = getattr(embedder, "provider", None) == "local"

    doc_vecs = dict(zip((p["id"] for p in passages), embedder.embed_documents([p["text"] for p in passages])))
    q_vecs = {q["id"]: embedder.embed_query(q["text"]) for q in queries}
    keyword_cache: dict[tuple[str, str], KeywordRetriever] = {}

    rows: dict[str, dict[str, list[dict]]] = {m: {s: [] for s in SLICES} for m in MODES}
    by_lang: dict[str, dict[str, dict[str, list[dict]]]] = {m: {s: defaultdict(list) for s in SLICES} for m in MODES}
    top = max(ks)
    for q in queries:
        for s in SLICES:
            corpus = _corpus_for(s, q["language"], passages)
            relevant = {p["id"] for p in corpus if p["topic"] == q["topic"]}
            vec = sorted(((_cosine(q_vecs[q["id"]], doc_vecs[p["id"]]), p["id"]) for p in corpus), key=lambda t: (-t[0], t[1]))
            vector_results = [RetrievalResult(chunk=_chunk(next(p for p in corpus if p["id"] == pid)), score=sc, retriever="vector")
                              for sc, pid in vec[:top]]
            key = (s, q["language"] if s != "mixed_corpus" else "*")
            if key not in keyword_cache:
                keyword_cache[key] = KeywordRetriever([_chunk(p) for p in corpus])
            kw_results = keyword_cache[key].retrieve(q["text"], top_k=top)
            fused = reciprocal_rank_fusion([vector_results, kw_results], top_k=top)
            ranked = {"vector": [r.chunk.chunk_id for r in vector_results], "bm25": [r.chunk.chunk_id for r in kw_results],
                      "rrf": [r.chunk.chunk_id for r in fused]}
            for m in MODES:
                row = _metrics(ranked[m], relevant, ks)
                rows[m][s].append(row)
                by_lang[m][s][q["language"]].append(row)

    results: dict[str, Any] = {}
    for m in MODES:
        results[m] = {}
        for s in SLICES:
            results[m][s] = {"overall": _aggregate(rows[m][s], ks),
                             "by_question_language": {lang: _aggregate(by_lang[m][s][lang], ks) for lang in LANGUAGES if lang in by_lang[m][s]}}
    est = estimate_embedding_run(document_texts=[p["text"] for p in passages], query_texts=[q["text"] for q in queries])
    ident = embedder.identity()
    return {
        "schema_version": 1,
        "label": label or (LOCAL_LABEL if is_local else "paid embedder run (owner-approved); NOT yet reviewed as production evidence"),
        "production_quality_evidence": False,
        "semantic_retrieval_passed": False,
        "pending": PENDING_STATEMENT,
        "embedder": {"provider": ident.provider, "model": ident.model, "version": ident.version, "dimensions": ident.dimensions,
                     "lexical_only": is_local},
        "dataset": {"name": ds.get("name"), "sha256": FROZEN_DATASET_SHA256, "passages": len(passages), "queries": len(queries),
                    "languages": list(LANGUAGES), "topics": len(ds.get("topics", [])), "authored_by": "engineering (not native-reviewed)"},
        "ks": list(ks),
        "slices": {"same_language": "corpus = question language only", "cross_language": "corpus = other languages only (question language never matches a source language)",
                   "mixed_corpus": "corpus = all languages; relevant = the topic in every language"},
        "results": results,
        "real_run_estimate": est,
        "limitations": ["49 passages and 49 questions: wide confidence intervals; differences between modes are directional only",
                        "passages and questions are synthetic and engineering-authored, not real knowledge-base content",
                        "the hash embedder is lexical (ASCII tokens): it cannot match across languages except through shared tokens"],
    }
