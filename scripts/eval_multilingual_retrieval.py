"""Seven-language retrieval benchmark (package 02B). OFFLINE by default; REFUSES any paid embedder without owner approval.

    python scripts/eval_multilingual_retrieval.py                  # local hash embedder, deterministic, writes only to a temp dir
    python scripts/eval_multilingual_retrieval.py --write PATH     # also write the JSON result to PATH
    python scripts/eval_multilingual_retrieval.py --estimate-only  # embedding-call count and cost class for a real run (no embedding at all)
    python scripts/eval_multilingual_retrieval.py --embedder configured
        # uses the configured embedder. If it is a PAID provider the run is REFUSED unless the owner has set ALL of
        #   ASK4MO_ALLOW_PAID_EMBEDDINGS=1, ASK4MO_EMBEDDING_BUDGET_MARKER=OD-BUDGET:<reference>, ASK4MO_EMBEDDING_MAX_CALLS=<n>
        # (never set by the repository, CI or an agent; see src/copilot/embedding_budget.py).

Local-embedder results are labelled "local embedder, NOT production quality evidence" and the output always states that the production-embedder
benchmark awaits OD-BUDGET. The script never claims semantic retrieval passed. Exit code 0 = ran; 2 = refused (paid embedder, no approval).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.embedding_budget import PaidEmbeddingRefused, describe_requirements, estimate_embedding_run  # noqa: E402
from src.copilot.embeddings import EmbeddingConfigurationError, LocalHashEmbedder, build_embedder  # noqa: E402
from src.copilot.evaluation.multilingual_retrieval import load_dataset, run_benchmark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embedder", choices=("local", "configured"), default="local")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--write", metavar="PATH", default=None)
    args = ap.parse_args(argv)

    ds = load_dataset()
    if args.estimate_only:
        est = estimate_embedding_run(document_texts=[p["text"] for p in ds["passages"]], query_texts=[q["text"] for q in ds["queries"]])
        print(json.dumps({"estimate": est, "to_run_a_paid_benchmark_the_owner_sets": describe_requirements(),
                          "note": "no embedding call was made; the production-embedder benchmark awaits OD-BUDGET"}, indent=1))
        return 0

    if args.embedder == "local":
        embedder = LocalHashEmbedder()
    else:
        from src.copilot.config import load_config

        try:
            embedder = build_embedder(load_config())
        except EmbeddingConfigurationError as exc:
            print(f"REFUSED: embedding configuration not acceptable ({', '.join(exc.codes)})", file=sys.stderr)
            return 2
    try:
        result = run_benchmark(embedder, dataset=ds)
    except PaidEmbeddingRefused as exc:
        print(f"REFUSED: a paid embedder needs explicit owner approval ({', '.join(exc.codes)}). {json.dumps(describe_requirements())}", file=sys.stderr)
        return 2

    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    out = Path(args.write) if args.write else Path(tempfile.gettempdir()) / "ask4mo_multilingual_retrieval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{result['label']}\n{result['pending']}\nresult written to {out}")
    for mode in ("vector", "bm25", "rrf"):
        for s in ("same_language", "cross_language", "mixed_corpus"):
            o = result["results"][mode][s]["overall"]
            print(f"  {mode:6s} {s:15s} recall@1={o['recall@1']} recall@5={o['recall@5']} mrr={o['mrr']} (n={o['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
