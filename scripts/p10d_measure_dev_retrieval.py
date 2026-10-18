#!/usr/bin/env python
"""P10D developer-local retrieval measurement over the REAL generated knowledge stores (read-only). It copies the vector store to a temporary directory (the original is never opened for
writing), builds the production hybrid retriever and structured coordinator over it, and times the stages for the 412 product-coverage questions. Developer-local only: in a clean
checkout the stores do not exist and the script reports NOT RUN (exit 2) and creates nothing. Numbers are wall-clock on the machine that ran it; they are measurements, not benchmarks.

    python scripts/p10d_measure_dev_retrieval.py [--json PATH] [--repeats N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (isolation: temporary DB, no .env; the vector store is copied, never opened in place)

from src.copilot import constants  # noqa: E402
from src.copilot.config import CopilotConfig  # noqa: E402
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 3)


def summary(xs):
    return {"n": len(xs), "p50": round(statistics.median(xs), 3), "p95": pct(xs, 0.95), "max": round(max(xs), 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--repeats", type=int, default=1)
    a = ap.parse_args(argv)
    if a.json and output_is_protected(a.json, ROOT):
        raise SystemExit("refusing to write inside a protected location")
    src_chroma = ROOT / "data/chroma"
    stores = [constants.ROLE_DB_PATH, constants.COMPENSATION_DB_PATH, constants.LABOUR_MARKET_DB_PATH, constants.COMPETENCY_DB_PATH, constants.CREDENTIAL_DB_PATH]
    if not (src_chroma / "chroma.sqlite3").exists() or not all(Path(s).is_file() for s in stores):
        print("NOT RUN: developer-local measurement; the generated knowledge stores are absent in this environment. Nothing was created.")
        return 2
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.knowledge.retrieval import build_default_coordinator
    from src.copilot.retrieval.hybrid import HybridRetriever
    from src.copilot.retrieval.keyword import KeywordRetriever
    from src.copilot.retrieval.vector import VectorRetriever
    from src.copilot.service import CareerIntelligenceService
    from src.copilot.vectorstore import ChromaStore

    tmp = Path(tempfile.mkdtemp(prefix="p10d_dev_retrieval_"))
    try:
        shutil.copytree(src_chroma, tmp / "chroma")
        embedder = LocalHashEmbedder()
        t0 = time.perf_counter()
        store = ChromaStore(embedder, persist_dir=str(tmp / "chroma"))
        open_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        keyword = KeywordRetriever.from_store(store)
        bm25_build_ms = (time.perf_counter() - t0) * 1000
        vector = VectorRetriever(store)
        hybrid = HybridRetriever(vector, keyword)
        coord = build_default_coordinator(CopilotConfig())
        svc = CareerIntelligenceService(knowledge_coordinator=coord, retriever=hybrid)
        queries = [c["query"] for c in json.loads((ROOT / "evaluations/product_coverage/cases.json").read_text())["cases"]]
        series: dict[str, list[float]] = {k: [] for k in ("embedding_lookup", "vector_retrieval", "keyword_retrieval", "hybrid_retrieval", "retrieve_evidence_end_to_end")}
        for q in queries:
            for _ in range(a.repeats):
                for name, fn in (("embedding_lookup", lambda: embedder.embed_query(q)), ("vector_retrieval", lambda: vector.retrieve(q, top_k=5)), ("keyword_retrieval", lambda: keyword.retrieve(q, top_k=5)),
                                 ("hybrid_retrieval", lambda: hybrid.retrieve(q, top_k=5)), ("retrieve_evidence_end_to_end", lambda: svc.retrieve_evidence(q))):
                    t = time.perf_counter()
                    fn()
                    series[name].append((time.perf_counter() - t) * 1000)
        chunks = store.count()
        res = {"environment": "developer_local (real generated stores; the vector store was COPIED to a temporary directory and the copy was queried)", "unit": "milliseconds", "questions": len(queries),
               "repeats": a.repeats, "index": {"chunks": chunks, "chroma_bytes_on_disk": sum(p.stat().st_size for p in src_chroma.rglob("*") if p.is_file()), "embedding_dimensions": embedder.dimensions,
                                               "embedder": f"{embedder.provider}/{embedder.model}"},
               "one_off": {"open_chroma_ms": round(open_ms, 1), "bm25_index_build_ms": round(bm25_build_ms, 1)}, "stages": {k: summary(v) for k, v in series.items()}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"index": res["index"], "one_off": res["one_off"], "stages": res["stages"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
