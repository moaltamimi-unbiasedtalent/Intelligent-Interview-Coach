"""Deterministic SYNTHETIC fixture corpus for Compensation V2 (P10C-C). Loads only invented structural data into a caller-supplied throwaway database: every source is a synthetic
fixture (so none can be approved or serve as evidence), every amount is invented, and nothing is official. Committed so evaluation is reproducible in CI without any local knowledge data."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.knowledge_foundation.aliases import AliasStore
from src.knowledge_foundation.compensation.resolver import CompensationRequest, CompensationResolver
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.coverage import CoverageMatrix
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.language_coverage import LanguageCoverageService
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue

__all__ = ["CORPUS_PATH", "load_corpus", "load_world", "evaluate_cases", "check_expectations"]

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "compensation_fixture_corpus.json"


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_world(sf, corpus: dict[str, Any] | None = None) -> SimpleNamespace:
    corpus = corpus or load_corpus()
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    for t in corpus["taxonomies"]:
        tax.ensure(t["scheme"], t["edition"], status=t["status"], acquisition_status=t["acquisition_status"], code_pattern=t.get("code_pattern"))
    cov, lc = CoverageMatrix(sf), LanguageCoverageService(sf)
    cov.seed()
    lc.seed()
    for s in corpus["sources"]:
        reg.register(s["source_id"], origin="synthetic_fixture", publisher=s["publisher"], dataset_name=s["dataset_name"], source_url=s["source_url"], precedence_category=s["precedence_category"])
    keys: dict[str, str] = {}
    for sc in corpus["scenarios"]:
        node = g.add_occupation(sc["label"], [tuple(i) for i in sc["identifiers"]])
        keys[sc["id"]] = node["occupation_key"]
        for item in sc["aliases"]:
            text, lang = (item, "en") if isinstance(item, str) else (item["text"], item["language"])
            a.add_alias(node["occupation_key"], text, language=lang, language_basis="fixture_declared", alias_type="source_synonym", source_ref="fx_occ")
    for sc in corpus["scenarios"]:
        for r in sc["relationships"]:
            g.add_relationship(keys[sc["id"]], keys[r["to"]], relationship_type=r["type"], basis=r["basis"], mapping_status=r["status"], from_taxonomy=tuple(r["from_taxonomy"]),
                               to_taxonomy=tuple(r["to_taxonomy"]), source_ref=r.get("source", ""), limitations=r.get("limitations"))
    store = CompensationStoreV2(sf, reg, g)
    by_source: dict[str, list[dict[str, Any]]] = {}
    for sc in corpus["scenarios"]:
        for rec in sc["records"]:
            by_source.setdefault(rec["source_ref"], []).append(rec)
    reports = {sid: store.import_records(rows, source_ref=sid, source_edition=corpus["source_editions"][sid], mode="fixture", transformation="synthetic fixture load") for sid, rows in by_source.items()}
    occ = OccupationResolver(g, a, coverage=cov, language_coverage=lc, registry=reg)
    return SimpleNamespace(sf=sf, reg=reg, g=g, a=a, store=store, cov=cov, lc=lc, keys=keys, reports=reports, occ=occ, resolver=CompensationResolver(store, occ, g, reg, coverage=cov))


def _request(case: dict[str, Any]) -> CompensationRequest:
    q = dict(case["request"])
    occ = MultilingualRequest(title=q.pop("title", None), title_language=q.pop("title_language", None), taxonomy_code=q.pop("taxonomy_code", None))
    country = q.pop("country", None)
    return CompensationRequest(occupation=occ, country=country, require_operational=not case.get("internal", True), **q)


def check_expectations(r, e: dict[str, Any]) -> list[str]:
    """Compare a ``CompensationResponse`` with a corpus expectation; returns the list of problems (empty when it matches)."""
    problems: list[str] = []
    if r.outcome.value != e["outcome"]:
        problems.append(f"outcome {r.outcome.value} != {e['outcome']}")
    for field_name, got in (("evidence_class", r.evidence_class), ("currency", r.currency), ("pay_period", r.pay_period), ("pay_basis", r.pay_basis), ("reference_year", r.reference_year),
                            ("specificity", r.occupation_specificity), ("bounds", r.bounds_semantic), ("abstention", r.abstention_reason), ("geography_level", r.geography_level),
                            ("region", r.region), ("earnings_concept", r.earnings_concept), ("population_scope", r.population_scope), ("evidence_method", r.evidence_method)):
        if field_name in e and got != e[field_name]:
            problems.append(f"{field_name} {got} != {e[field_name]}")
    if "value" in e and (r.value is None or Decimal(r.value) != Decimal(e["value"])):
        problems.append("value differs")
    if e.get("citation") and not r.citation:
        problems.append("citation missing")
    if e.get("no_value") and r.value is not None:
        problems.append("a value was returned")
    if "limitation_contains" in e and not any(e["limitation_contains"].lower() in x.lower() for x in r.coverage_limitations):
        problems.append("limitation missing")
    if "contextual_class" in e and not any(c["evidence_class"] == e["contextual_class"] and c["broader_occupation_code"] and c["broader_occupation_label"] for c in r.contextual_evidence):
        problems.append("labelled broader-group context missing")
    if "contextual_count" in e and len(r.contextual_evidence) != e["contextual_count"]:
        problems.append("contextual evidence count differs")
    if "contextual_warning_contains" in e and not any(e["contextual_warning_contains"].lower() in c["warning"].lower() for c in r.contextual_evidence):
        problems.append("non-equivalence warning missing")
    if "corroborating" in e and len(r.corroborating) != e["corroborating"]:
        problems.append("corroborating differs")
    if "withheld" in e and not r.withheld.get(e["withheld"]):
        problems.append("withheld counter missing")
    if "context_needed" in e and e["context_needed"] not in r.context_needed:
        problems.append("context missing")
    if "state" in e and (r.evidence_assessment or {}).get("state") != e["state"]:
        problems.append(f"evidence state {(r.evidence_assessment or {}).get('state')} != {e['state']}")
    for k, v in (e.get("factors") or {}).items():
        if ((r.evidence_assessment or {}).get("factors") or {}).get(k) != v:
            problems.append(f"factor {k} differs")
    for w in e.get("weak_factors", []):
        if w not in ((r.evidence_assessment or {}).get("weak_factors") or []):
            problems.append(f"weak factor {w} missing")
    if "precedence_pending" in e and r.precedence_pending != e["precedence_pending"]:
        problems.append("precedence_pending differs")
    if "fallback_stage" in e and (r.fallback_trace or {}).get("selected_stage") != e["fallback_stage"]:
        problems.append("fallback stage differs")
    if "freshness_year" in e and (r.freshness or {}).get("reference_year") != e["freshness_year"]:
        problems.append("freshness year differs")
    return problems


def evaluate_cases(world: SimpleNamespace, corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    corpus = corpus or load_corpus()
    out = []
    for c in corpus["cases"]:
        r = world.resolver.resolve(_request(c))
        problems = check_expectations(r, c["expect"])
        invented = r.outcome.value != "evidence" and (r.value is not None or r.lower_value is not None)
        out.append({"id": c["id"], "category": c["category"], "ok": not problems, "problems": problems, "outcome": r.outcome.value, "invented_value": invented,
                    "presentable": r.candidate_presentable, "operational": r.operational})
    return out
