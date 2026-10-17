"""Deterministic synthetic fixture corpus for the occupation resolver (P10C-B). Loads ONLY synthetic structural data into a caller-supplied (throwaway) database: every source in the
corpus must be a synthetic fixture (so nothing here can ever be approved or serve as evidence), codes are unmistakably synthetic, and the loader writes no salary figure. The
corpus is committed (``data/resolver_fixture_corpus.json``) so the evaluation is reproducible in CI without any local knowledge data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.knowledge_foundation.aliases import AliasStore
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, MultilingualResult, OccupationResolver
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue

__all__ = ["CORPUS_PATH", "load_corpus", "load_into", "run_case", "evaluate_cases"]

CORPUS_PATH = Path(__file__).parent / "data" / "resolver_fixture_corpus.json"


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    if any(s["origin"] != "synthetic_fixture" for s in corpus["sources"]):
        raise ValueError("the fixture corpus may contain synthetic-fixture sources only")
    return corpus


def load_into(sf, corpus: dict[str, Any] | None = None) -> dict[str, str]:
    """Seed taxonomies and load the corpus. Returns ``{fixture id: occupation_key}``. Idempotent."""
    corpus = corpus or load_corpus()
    tax, reg, g, aliases = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    for t in corpus.get("taxonomies", []):
        tax.ensure(t["scheme"], t["edition"], status=t["status"], acquisition_status=t["acquisition_status"], code_pattern=t.get("code_pattern"))
    for s in corpus["sources"]:
        reg.register(s["source_id"], origin=s["origin"])
    keys: dict[str, str] = {}
    for o in corpus["occupations"]:
        node = g.add_occupation(o["label"], [tuple(i) for i in o["identifiers"]], legacy_keys=o.get("legacy_keys", ()))
        keys[o["id"]] = node["occupation_key"]
        for a in o["aliases"]:
            aliases.add_alias(node["occupation_key"], a["text"], language=a.get("language"), language_basis=a.get("basis"), alias_type=a["type"], source_ref=a["source"],
                              taxonomy=tuple(a["edition"]) if a.get("edition") else None, context_terms=a.get("context_terms", ()), provenance={"fixture": True})
    for r in corpus.get("relationships", []):
        g.add_relationship(keys[r["from"]], keys[r["to"]], relationship_type=r["type"], basis=r["basis"], mapping_status=r["status"], from_taxonomy=tuple(r["from_taxonomy"]),
                           to_taxonomy=tuple(r["to_taxonomy"]), source_ref=r["source"])
    return keys


def run_case(resolver: OccupationResolver, case: dict[str, Any]) -> MultilingualResult:
    req = dict(case["request"])
    if "known_occupation_keys" in req:
        req["known_occupation_keys"] = tuple(req["known_occupation_keys"])
    return resolver.resolve(MultilingualRequest(**req))


def evaluate_cases(resolver: OccupationResolver, keys: dict[str, str], corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run every case; each entry says whether it matched its expectation and, separately, whether a WRONG resolution (resolved to the wrong occupation) occurred."""
    corpus = corpus or load_corpus()
    out = []
    for c in corpus["cases"]:
        res = run_case(resolver, c)
        exp = c["expect"]
        want = sorted(keys[i] for i in exp["occupations"])
        got = sorted(x.occupation_key for x in res.candidates)
        problems = []
        if res.outcome.value != exp["outcome"]:
            problems.append(f"outcome {res.outcome.value} != {exp['outcome']}")
        if exp["occupations"] and got != want:
            problems.append("candidates differ")
        problems += [f"missing warning {w}" for w in exp["warnings"] if w not in res.warnings]
        problems += [f"missing reason {r}" for r in exp["reasons"] if r not in res.reasons]
        problems += [f"missing context {x}" for x in exp["context_needed"] if x not in res.context_needed]
        if exp.get("grade") and (not res.candidates or res.candidates[0].grade != exp["grade"]):
            problems.append("grade differs")
        wrong = res.outcome.value == "resolved" and (exp["outcome"] != "resolved" or (bool(want) and got != want))
        out.append({"id": c["id"], "category": c["category"], "expected": exp["outcome"], "actual": res.outcome.value, "ok": not problems, "problems": problems, "wrong_resolution": wrong,
                    "operational": res.operational})
    return out
