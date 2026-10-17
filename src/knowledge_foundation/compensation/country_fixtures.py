"""Deterministic SYNTHETIC corpus for the Canada, Mexico and Brazil foundations (P10C-D). Loads only invented structural data into a caller-supplied throwaway database through the SAME
registry-gated importers production would use (fixture mode): taxonomy nodes, crosswalks and compensation rows all pass the real gates, and every source is a synthetic fixture that can never
be approved or serve as evidence. Committed so evaluation is reproducible in CI without any local knowledge data. Editions (fx-ed1, fx-ed2), codes, labels and amounts are invented and make
no claim about any real taxonomy or dataset."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.knowledge_foundation.aliases import AliasStore
from src.knowledge_foundation.compensation import country_adapters as CA
from src.knowledge_foundation.compensation.country_import import import_crosswalk, import_taxonomy_nodes
from src.knowledge_foundation.compensation.fixtures import check_expectations
from src.knowledge_foundation.compensation.resolver import CompensationRequest, CompensationResolver
from src.knowledge_foundation.compensation.store import CompensationStoreV2
from src.knowledge_foundation.coverage import CoverageMatrix
from src.knowledge_foundation.graph import OccupationGraph
from src.knowledge_foundation.language_coverage import LanguageCoverageService
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue

__all__ = ["CORPUS_PATH", "load_corpus", "load_world", "evaluate_cases", "evaluate_blocks"]

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "country_fixture_corpus.json"
_ADAPTERS = {"canada": CA.canada_records, "mexico": CA.mexico_records, "brazil": CA.brazil_records}


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _adapter_kwargs(block: dict[str, Any]) -> dict[str, Any]:
    kw = {k: block[k] for k in ("statistic_map", "period_map", "concept_map", "population_map", "method_map", "code_pattern") if k in block}
    kw["statistic_map"] = {k: tuple(v) for k, v in kw["statistic_map"].items()}
    if "level_by_code_length" in block:
        kw["level_by_code_length"] = {int(k): v for k, v in block["level_by_code_length"].items()}
    return kw


def load_world(sf, corpus: dict[str, Any] | None = None) -> SimpleNamespace:
    corpus = corpus or load_corpus()
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    for t in corpus["taxonomies"]:
        tax.ensure(t["scheme"], t["edition"], status="unknown", acquisition_status="not_acquired", code_pattern=t["code_pattern"])
    cov, lc = CoverageMatrix(sf), LanguageCoverageService(sf)
    cov.seed()
    lc.seed()
    for s in corpus["sources"]:
        reg.register(s["source_id"], origin="synthetic_fixture", publisher=s["publisher"], dataset_name=s["dataset_name"], source_url=s["source_url"], precedence_category=s["precedence_category"])
    node_reports = [import_taxonomy_nodes(g, a, reg, b["rows"], scheme=b["scheme"], edition=b["edition"], source_ref=b["source"], mode="fixture") for b in corpus["nodes"]]
    xwalk_reports = [import_crosswalk(g, reg, x["rows"], source_ref=x["source"], from_taxonomy=tuple(x["from"]), to_taxonomy=tuple(x["to"]), mode="fixture") for x in corpus["crosswalks"]]
    store = CompensationStoreV2(sf, reg, g)
    comp_reports, adapter_rejections = [], []
    for b in corpus["compensation"]:
        if b["adapter"] == "raw":
            rows, rej = b["rows"], {}
        else:
            rows, rej = _ADAPTERS[b["adapter"]](b["rows"], source_ref=b["source"], source_edition=b["source_edition"], taxonomy_edition=b["taxonomy_edition"], reference_year=b["reference_year"], **_adapter_kwargs(b))
        adapter_rejections.append(dict(rej))
        comp_reports.append(store.import_records(rows, source_ref=b["source"], source_edition=b["source_edition"], mode="fixture", transformation=f"{b['adapter']} synthetic fixture"))
    occ = OccupationResolver(g, a, coverage=cov, language_coverage=lc, registry=reg)
    return SimpleNamespace(sf=sf, reg=reg, g=g, a=a, store=store, cov=cov, lc=lc, occ=occ, node_reports=node_reports, xwalk_reports=xwalk_reports, comp_reports=comp_reports,
                           adapter_rejections=adapter_rejections, resolver=CompensationResolver(store, occ, g, reg, coverage=cov))


def evaluate_blocks(world: SimpleNamespace, corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Check the import and adapter expectations of every corpus block (reason codes and counts)."""
    corpus = corpus or load_corpus()
    out = []
    for i, x in enumerate(corpus["crosswalks"]):
        rep, e = world.xwalk_reports[i], x["expect"]
        out.append({"id": f"crosswalk-{i}", "ok": rep.added == e["added"] and rep.rejections == e["rejections"], "detail": f"added {rep.added}, rejected {rep.rejections}"})
    for i, b in enumerate(corpus["compensation"]):
        rep, e = world.comp_reports[i], b["expect"]
        ok = rep.added == e["added"] and rep.rejections == e.get("rejections", {}) and world.adapter_rejections[i] == e.get("adapter_rejections", {})
        out.append({"id": f"compensation-{b['source']}-{b['source_edition']}", "ok": ok, "detail": f"added {rep.added}, import {rep.rejections}, adapter {world.adapter_rejections[i]}"})
    return out


def _request(case: dict[str, Any]) -> CompensationRequest:
    q = dict(case["request"])
    occ = MultilingualRequest(title=q.pop("title", None), title_language=q.pop("title_language", None), taxonomy_scheme=q.pop("taxonomy_scheme", None),
                              taxonomy_code=q.pop("taxonomy_code", None), taxonomy_edition=q.pop("taxonomy_edition", None))
    country = q.pop("country", None)
    return CompensationRequest(occupation=occ, country=country, require_operational=not case.get("internal", True), **q)


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
