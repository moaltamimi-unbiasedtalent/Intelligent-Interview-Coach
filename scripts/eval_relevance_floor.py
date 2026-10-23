"""Relevance-floor calibration evaluator (package 02E). OFFLINE: runs the LOCAL lexical hash embedder over the frozen datasets, so no network and no cost.

    python scripts/eval_relevance_floor.py [--write PATH]

Computes the per-language precision / recall trade-off and the abstention behaviour on the frozen out-of-domain questions, and PROPOSES a floor with its
evidence. The embedder is the lexical hash embedder (development only), so the numbers are NOT production-quality evidence and the proposal is NOT applied:
a floor is bound to an exact embedder identity and a real embedder's score distribution is unknown until the governed live benchmark runs. Writes only to a
temporary directory unless ``--write`` is given. Exit 0 = ran.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.embeddings import LocalHashEmbedder  # noqa: E402
from src.copilot.evaluation import embedding_benchmark as EB  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", metavar="PATH", default=None)
    args = ap.parse_args(argv)
    spec = EB.ModelSpec("local-hash", "local-hash-v1", LocalHashEmbedder().dimensions, "local", "local")
    with tempfile.TemporaryDirectory() as tmp:
        result = EB.run_embedding_benchmark([spec], lambda s: LocalHashEmbedder(), store_root=tmp)
    model = result["models"][0]
    cal = model["floor_proposal"]
    out = {"label": "LOCAL LEXICAL embedder: NOT production quality evidence; the proposal is NOT applied", "applied": False,
           "embedder": model["identity"], "constraints": cal["constraints"], "overall": {k: v for k, v in cal["overall"].items() if k != "curve"},
           "by_language": {lang: {k: v for k, v in s.items() if k != "curve"} for lang, s in cal["by_language"].items()},
           "curves": {"overall": cal["overall"]["curve"], **{lang: s["curve"] for lang, s in cal["by_language"].items()}},
           "note": cal["note"], "independence_limitation": result["independence_limitation"]}
    print(out["label"])
    for lang, s in out["by_language"].items():
        print(f"  {lang}: proposed floor={s['proposed_floor']} confidence={s['confidence']} at proposal={s['at_proposal']}")
    print(f"  overall: proposed floor={out['overall']['proposed_floor']} confidence={out['overall']['confidence']}")
    if args.write:
        p = Path(args.write)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"written to {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
