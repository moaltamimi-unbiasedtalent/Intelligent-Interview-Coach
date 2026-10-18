#!/usr/bin/env python
"""P10D knowledge-base requalification: retrieval, multilingual, geography, occupation, citation, grounding, ingestion security, research-cache isolation.

Offline and deterministic: it rebuilds a throwaway SYNTHETIC knowledge base in a temporary directory (in-memory structured stores plus a real Chroma store with the
offline hash embedder), drives the EXISTING candidate retrieval path (production coordinator, hybrid retriever, service, guards) with the committed corpus
(``evaluations/kb_requalification/p10d_corpus.json``) and a SCRIPTED responder, repeats the run to prove determinism and disposes of what it created. It touches no
developer store, makes no network call, uses no paid model, never claims a model-generated answer-quality result (mode C) and approves or qualifies nothing. Exit 0 is NOT a
product-coverage, source-qualification or production claim: the 412-case coverage gate is measured separately and remains BELOW GATE.

    python scripts/eval_kb_requalification.py [--repeat N] [--json PATH] [--md PATH] [--perf]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (test isolation: temporary databases and a temporary research cache only, no developer store)

from src.copilot.knowledge import requalification as Q  # noqa: E402
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402


def render_md(res: dict) -> str:
    m = res["retrieval_metrics"]
    lines = ["# P10D knowledge-base requalification: generated results", "",
             f"Corpus v{res['corpus_version']}, {res['passed']}/{res['total']} cases behave as pinned, determinism hash `{res['determinism_hash'][:16]}`. Mode A and B only; mode C (a real model run) was NOT performed.", "",
             "## Families", "", "| Family | Cases | Pinned behaviour holds |", "|---|---|---|"]
    lines += [f"| {k} | {v['cases']} | {v['ok']} |" for k, v in res["families"].items()]
    lines += ["", f"## Retrieval metrics ({m['label']})", "", "| Language | Judged | hit@5 | recall@5 | precision@5 | MRR |", "|---|---|---|---|---|---|"]
    for lang, a in [("ALL", m["overall"]), *m["by_language"].items()]:
        lines.append(f"| {lang} | {a['judged_cases']} | {a.get('hit@5', '')} | {a.get('recall@5', '')} | {a.get('precision@5', '')} | {a.get('mrr', '')} |")
    mm = res["multilingual_matrix"]
    lines += ["", "## Multilingual matrix (cases that reach the FULLY capable behaviour / cases)", "", "| Language | " + " | ".join(mm["dimensions"]) + " |", "|---|" + "---|" * len(mm["dimensions"])]
    for lang in mm["languages"]:
        row = []
        for d in mm["dimensions"]:
            cell = mm["cells"].get(f"{lang}|{d}")
            row.append(f"{cell['capability_met']}/{cell['cases']}" if cell else "")
        lines.append(f"| {lang} | " + " | ".join(row) + " |")
    lines += ["", "## Documented limitations (pinned, not hidden)", ""]
    for k, v in res["limitations"].items():
        lines.append(f"- **{k}** ({', '.join(v['cases'])}; capability met in {v['capability_met']}/{len(v['cases'])}): {v['description']}")
    lines += ["", f"Required tags exercised: {res['tags']['exercised']}/{res['tags']['required_tags']}. Index: {res['index']['chunks']} chunks, {res['index']['chroma_bytes']} bytes of Chroma data."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--perf", action="store_true")
    ap.add_argument("--store", choices=("memory", "chroma"), default="memory", help="vector store for the fixture: the production InMemoryVectorStore (default) or the real ChromaStore")
    a = ap.parse_args(argv)
    for out in (a.json, a.md):
        if out and output_is_protected(out, ROOT):
            raise SystemExit("refusing to write inside a protected location")
    t0 = time.perf_counter()
    runs = [Q.run_all(store_kind=a.store) for _ in range(max(1, a.repeat))]
    first = runs[0]
    hashes = sorted({r["determinism_hash"] for r in runs})
    ok = all(r["ok"] for r in runs) and len(hashes) == 1
    res = {**first, "ok": ok, "repeat": len(runs), "deterministic_across_runs": len(hashes) == 1, "wall_seconds": round(time.perf_counter() - t0, 2)}
    if a.perf:
        res["performance"] = Q.measure_performance(store_kind="chroma")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(render_md(res), encoding="utf-8")
    print(f"P10D KB requalification [{a.store} store] v{first['corpus_version']}: {first['passed']}/{first['total']} cases | tags {first['tags']['exercised']}/{first['tags']['required_tags']} | repeat {len(runs)} deterministic={len(hashes) == 1} | {res['wall_seconds']}s")
    for fam, v in first["families"].items():
        print(f"  {fam}: {v['ok']}/{v['cases']}")
    if not ok:
        print("FAIL:", json.dumps({"integrity": first["integrity_errors"], "missing_tags": first["tags"]["missing_tags"], "failing_tags": first["tags"]["failing_tags"],
                                   "failed_cases": [(r["id"], [k for k, v in r["checks"].items() if not v], r["error"]) for r in first["cases"] if not r["ok"]][:60], "hashes": hashes}, ensure_ascii=False))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
