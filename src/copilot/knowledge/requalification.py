"""P10D knowledge-base requalification runner (offline, deterministic, isolated).

It rebuilds a throwaway SYNTHETIC knowledge base in its own temporary directory (in-memory structured stores plus a real ``ChromaStore`` with the offline
hash embedder), then drives the EXISTING candidate retrieval path with labelled cases: the production ``StructuredRetrievalCoordinator``, the production
hybrid retriever, ``CareerIntelligenceService.retrieve_evidence`` / ``answer`` (with a SCRIPTED responder, never a model), the RAG/output guards, the
loaders and the governed retriever. It adds no retrieval engine, no resolver and no lifecycle state, reads no developer store, makes no network or paid
call and qualifies or approves nothing.

Three evaluation modes are kept apart (the corpus ``mode`` field): A = deterministic component test, B = offline end-to-end over the fixture with a scripted
responder. Mode C (an actual model-generated answer-quality run) is NOT performed here and is never claimed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import statistics
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from src.copilot import constants

CORPUS_PATH = constants.REPO_ROOT / "evaluations/kb_requalification/p10d_corpus.json"
RESULT_SCHEMA = "p10d-results/1"
TOP_K = 5
SECRET_FIXTURE = "sk-or-" "ABCDEFGH12345678"   # split so the CI source secret scan does not mistake this obviously fake fixture for a real key


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


KINDS = {"retrieval", "evidence", "answer", "component", "ingest", "governed", "cache", "static"}


def validate_corpus(corpus: dict[str, Any]) -> list[str]:
    """Structural integrity of the corpus (empty list = sound). Never raises."""
    errors: list[str] = []
    if corpus.get("schema") != "p10d/1":
        errors.append("unexpected corpus schema")
    if corpus.get("synthetic") is not True:
        errors.append("the corpus must declare synthetic: true")
    fx = corpus.get("fixture", {})
    doc_ids = {d["id"] for d in fx.get("documents", [])}
    sources = {m["source_id"] for m in fx.get("manifest", [])}
    for m in fx.get("manifest", []):
        if not m["source_id"].startswith("fx_") or not str(m.get("source_url", "")).startswith("https://fixtures.invalid/"):
            errors.append(f"manifest {m['source_id']}: must be an fx_ id with a .invalid URL")
    seen: set[str] = set()
    for c in corpus.get("cases", []):
        cid = c.get("id", "?")
        if cid in seen:
            errors.append(f"duplicate case id {cid}")
        seen.add(cid)
        if c.get("kind") not in KINDS:
            errors.append(f"{cid}: unknown kind {c.get('kind')!r}")
        if c.get("mode") not in ("A", "B"):
            errors.append(f"{cid}: mode must be A or B (mode C is never part of this corpus)")
        if not c.get("tags"):
            errors.append(f"{cid}: needs at least one tag")
        if c.get("kind") == "retrieval":
            for rid in c.get("relevant", []):
                if rid not in doc_ids:
                    errors.append(f"{cid}: relevant id {rid} is not a fixture document")
            if c.get("relevant") and not c.get("rationale"):
                errors.append(f"{cid}: a judged case needs a rationale")
        for s in (c.get("expect", {}).get("sources_any", []) + c.get("expect", {}).get("sources_all", []) + c.get("expect", {}).get("forbid_sources", [])):
            if s not in sources and not s.startswith("fx_doc_"):
                errors.append(f"{cid}: unknown fixture source {s}")
        lim = c.get("limitation")
        if lim and lim not in corpus.get("limitations", {}):
            errors.append(f"{cid}: undeclared limitation {lim}")
    return errors


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# The throwaway world
# ---------------------------------------------------------------------------------------------------------------------------------------------------
@dataclass
class World:
    workdir: Path
    manifest: list
    role: Any
    comp: Any
    labour: Any
    cred: Any
    coordinator: Any
    store: Any
    retriever: Any
    keyword: Any
    vector: Any
    doc_by_chunk: dict = field(default_factory=dict)
    chunk_count: int = 0
    embedder: Any = None

    def service(self, responder=None, *, retriever: bool = True):
        from src.copilot.service import CareerIntelligenceService

        return CareerIntelligenceService(knowledge_coordinator=self.coordinator, retriever=self.retriever if (retriever and self.retriever is not None) else None, synthesis_responder=responder)


def _dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def build_world(corpus: dict[str, Any], workdir: Path, *, vector: bool = True, store_kind: str = "memory") -> World:
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.knowledge.compensation import CompensationRecord, CompensationRepository
    from src.copilot.knowledge.retrieval import StructuredRetrievalCoordinator
    from src.copilot.knowledge.roles import NormalisedOccupation, RoleRepository, Skill
    from src.copilot.knowledge.structured_ext import (
        CredentialRepository, LabourForecast, LabourMarketRepository, LabourOpenings, LabourShortage, LabourVacancy, OccupationLicence,
    )
    from src.copilot.models import DocumentChunk
    from src.copilot.retrieval.hybrid import HybridRetriever
    from src.copilot.retrieval.keyword import KeywordRetriever
    from src.copilot.retrieval.vector import VectorRetriever
    from src.copilot.vectorstore import ChromaStore, InMemoryVectorStore, _chroma_available

    fx = corpus["fixture"]
    manifest = [SimpleNamespace(**m) for m in fx["manifest"]]
    role = RoleRepository(":memory:")
    for o in fx["occupations"]:
        role.add_occupation(NormalisedOccupation(occupation_code=o["code"], title=o["title"], source_id=o["source_id"], aliases=o["aliases"], tasks=o["tasks"],
                                                 skills=[Skill(name=s) for s in o["skills"]], entry_education=o["education"]))
    comp = CompensationRepository(":memory:")
    for c in fx["compensation"]:
        comp.add(CompensationRecord(**c))
    labour = LabourMarketRepository(":memory:")
    for r in fx["labour"]["openings"]:
        labour.add_openings(LabourOpenings(**r))
    for r in fx["labour"]["forecast"]:
        labour.add_forecast(LabourForecast(**r))
    for r in fx["labour"]["shortage"]:
        labour.add_shortage(LabourShortage(**r))
    for r in fx["labour"].get("vacancy", []):
        labour.add_vacancy(LabourVacancy(**r))
    cred = CredentialRepository(":memory:")
    for r in fx["credentials"]["licences"]:
        cred.add_licence(OccupationLicence(**r))
    coordinator = StructuredRetrievalCoordinator(role_repo=role, comp_repo=comp, labour_repo=labour, credential_repo=cred, manifest_entries=manifest)

    embedder = LocalHashEmbedder()
    if not vector:   # a world for tests that never retrieve narrative text: no Chroma client is created
        return World(workdir=workdir, manifest=manifest, role=role, comp=comp, labour=labour, cred=cred, coordinator=coordinator, store=None, retriever=None, keyword=None, vector=None,
                     chunk_count=0, embedder=embedder)
    # ``memory`` (default; used by pytest and CI) is the production InMemoryVectorStore: the same BaseVectorStore interface, so hybrid fusion, the guards and the service run
    # unchanged, with no persistent Chroma client (whose background threads can abort the interpreter at exit on some platforms). ``chroma`` uses the real ChromaStore.
    store = (ChromaStore(embedder, persist_dir=str(workdir / "chroma"), collection_name="p10d_fixture") if (store_kind == "chroma" and _chroma_available()) else InMemoryVectorStore(embedder))
    chunks, doc_by_chunk = [], {}
    for i, d in enumerate(fx["documents"]):
        meta = {"source_id": d["source_id"], "manifest_source_id": d["source_id"], "source_url": d["source_url"], "title": d["title"], "document_type": d["document_type"],
                "language": d["language"], "chunk_index": 0}
        if d["country"]:
            meta["country"] = d["country"]
        if d["year"]:
            meta["reference_year"] = d["year"]
        chunks.append(DocumentChunk(chunk_id=d["id"], doc_id=d["id"], text=d["text"], position=i, metadata=meta))
        doc_by_chunk[d["id"]] = d["id"]
    store.add_chunks(chunks)
    keyword = KeywordRetriever.from_store(store)
    vector = VectorRetriever(store)
    return World(workdir=workdir, manifest=manifest, role=role, comp=comp, labour=labour, cred=cred, coordinator=coordinator, store=store, retriever=HybridRetriever(vector, keyword),
                 keyword=keyword, vector=vector, doc_by_chunk=doc_by_chunk, chunk_count=len(chunks), embedder=embedder)


@contextmanager
def temp_world(corpus: dict[str, Any], *, vector: bool = True, store_kind: str = "memory"):
    workdir = Path(tempfile.mkdtemp(prefix="p10d_world_"))
    world = None
    try:
        world = build_world(corpus, workdir, vector=vector, store_kind=store_kind)
        yield world
    finally:
        if world is not None:
            for r in (world.role, world.comp, world.labour, world.cred):
                try:
                    r.close()
                except Exception:  # noqa: BLE001
                    pass
            # Release the Chroma client BEFORE its directory is deleted: a live client over a removed directory can abort the interpreter at exit
            # ("recursive_mutex lock failed") on some platforms.
            try:
                from chromadb.api.client import SharedSystemClient

                client = getattr(world.store, "_client", None)
                if client is not None and hasattr(client, "_system"):
                    client._system.stop()          # stop the client's background components while the directory still exists
                world.store = world.retriever = world.keyword = world.vector = None
                SharedSystemClient.clear_system_cache()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Metrics (only over judged cases)
# ---------------------------------------------------------------------------------------------------------------------------------------------------
def hit_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if relevant & set(ranked[:k]) else 0.0


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(relevant & set(ranked[:k])) / len(relevant) if relevant else 0.0


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    top = ranked[:k]
    return len([r for r in top if r in relevant]) / len(top) if top else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str], k: int) -> float:
    for i, r in enumerate(ranked[:k], start=1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def _agg(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"judged_cases": 0}
    return {"judged_cases": n, f"hit@{TOP_K}": round(sum(r["hit"] for r in rows) / n, 4), f"recall@{TOP_K}": round(sum(r["recall"] for r in rows) / n, 4),
            f"precision@{TOP_K}": round(sum(r["precision"] for r in rows) / n, 4), "mrr": round(sum(r["rr"] for r in rows) / n, 4)}


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Scripted responders (mode B). They return fixed text; no model is ever called.
# ---------------------------------------------------------------------------------------------------------------------------------------------------
class Spy:
    def __init__(self, fn: Callable | None) -> None:
        self.fn, self.calls, self.messages = fn, 0, []

    def __call__(self, messages):
        from src.copilot.rag.responder import ModelReply

        self.calls += 1
        self.messages = messages
        if self.fn is None:
            return ModelReply(content="Scripted reply [1].")
        return self.fn(messages)

    @property
    def prompt(self) -> str:
        return "\n".join(m.get("content", "") for m in self.messages)


def _responder(name: str):
    from src.copilot.rag.responder import ModelReply

    def markers(messages) -> list[str]:
        return sorted(set(re.findall(r"\[(\d+)\]", "\n".join(m["content"] for m in messages if m["role"] == "user"))), key=int)

    table: dict[str, Callable | None] = {
        "cite_first": lambda m: ModelReply(content="According to the evidence [1]."),
        "cite_invalid": lambda m: ModelReply(content="A supported claim [1]. An unsupported claim [9]."),
        "no_citation": lambda m: ModelReply(content="Here is some general advice."),
        "cite_all": lambda m: ModelReply(content="Evidence " + " ".join(f"[{x}]" for x in markers(m)) + "."),
        "empty": lambda m: ModelReply(content=""),
        "leak_secret": lambda m: ModelReply(content=f"The key is {SECRET_FIXTURE} [1]."),
        "leak_system": lambda m: ModelReply(content="You are the Career Intelligence Copilot. Grounding rules: ..."),
        "echo_prompt": lambda m: ModelReply(content="Echo [1]."),
    }
    if name == "raise":
        def boom(messages):
            raise RuntimeError("scripted provider failure")
        return Spy(boom)
    return Spy(table[name])


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Expectation judge (shared by the pinned ``expect`` and the optional ``desired`` capability)
# ---------------------------------------------------------------------------------------------------------------------------------------------------
def _judge(observed: dict[str, Any], expect: dict[str, Any]) -> dict[str, bool]:
    c: dict[str, bool] = {}
    o = observed
    if "hit_at_5" in expect:
        c["hit_at_5"] = bool(o.get("hit")) == bool(expect["hit_at_5"])
    if "top1" in expect:
        c["top1"] = bool(o.get("ranked")) and o["ranked"][0] in expect["top1"]
    if "min_results" in expect:
        c["min_results"] = len(o.get("ranked", [])) >= expect["min_results"]
    if "max_results" in expect:
        c["max_results"] = len(o.get("ranked", [])) <= expect["max_results"]
    if "only_document_type" in expect:
        c["only_document_type"] = bool(o.get("ranked")) and all(t == expect["only_document_type"] for t in o.get("types", []))
    if "returns_all" in expect:
        c["returns_all"] = set(expect["returns_all"]) <= set(o.get("ranked", []))
    if "forbid_ids" in expect:
        c["forbid_ids"] = not (set(expect["forbid_ids"]) & set(o.get("ranked", [])))
    if "relevant_found_min" in expect:
        c["relevant_found_min"] = o.get("relevant_found", 0) >= expect["relevant_found_min"]
    if "lane" in expect:
        c["lane"] = o.get("lane") == expect["lane"]
    if "country" in expect:
        c["country"] = o.get("country") == expect["country"]
    if "insufficient" in expect:
        c["insufficient"] = bool(o.get("insufficient")) == expect["insufficient"]
    if "clarify" in expect:
        c["clarify"] = bool(o.get("clarify")) == expect["clarify"]
    if "grounded" in expect:
        c["grounded"] = bool(o.get("grounded")) == expect["grounded"]
    if "min_evidence" in expect:
        c["min_evidence"] = o.get("n_evidence", 0) >= expect["min_evidence"]
    if "max_evidence" in expect:
        c["max_evidence"] = o.get("n_evidence", 0) <= expect["max_evidence"]
    if "max_structured_evidence" in expect:
        c["max_structured_evidence"] = o.get("n_structured", 0) <= expect["max_structured_evidence"]
    if "min_structured_evidence" in expect:
        c["min_structured_evidence"] = o.get("n_structured", 0) >= expect["min_structured_evidence"]
    if "structured_countries_only" in expect:
        c["structured_countries_only"] = set(o.get("structured_countries", [])) == set(expect["structured_countries_only"])
    if expect.get("structured_geo_labelled"):
        c["structured_geo_labelled"] = all(o.get("structured_geographies", [""]))
    if "sources_any" in expect:
        c["sources_any"] = bool(set(expect["sources_any"]) & set(o.get("sources", [])))
    if "sources_all" in expect:
        c["sources_all"] = set(expect["sources_all"]) <= set(o.get("sources", []))
    if "forbid_sources" in expect:
        c["forbid_sources"] = not (set(expect["forbid_sources"]) & set(o.get("sources", [])))
    if "allowed_countries" in expect:
        c["allowed_countries"] = all(x in expect["allowed_countries"] for x in o.get("evidence_countries", []))
    if "occupation" in expect:
        c["occupation"] = (o.get("occupation") or "").lower() == expect["occupation"]
    if "note_contains" in expect:
        c["note_contains"] = any(expect["note_contains"] in n for n in o.get("notes", []))
    if "years_include" in expect:
        c["years_include"] = set(expect["years_include"]) <= set(o.get("years", []))
    # answer family
    if "citation_sources" in expect:
        c["citation_sources"] = set(expect["citation_sources"]) <= set(o.get("citation_sources", []))
    if "citations_min" in expect:
        c["citations_min"] = o.get("n_citations", 0) >= expect["citations_min"]
    if "citations_max" in expect:
        c["citations_max"] = o.get("n_citations", 0) <= expect["citations_max"]
    if expect.get("citation_titles_nonempty"):
        c["citation_titles_nonempty"] = bool(o.get("citation_titles")) and all(o["citation_titles"])
    if "citation_url_prefix" in expect:
        c["citation_url_prefix"] = bool(o.get("citation_urls")) and all(u and u.startswith(expect["citation_url_prefix"]) for u in o["citation_urls"])
    if "citation_title_contains" in expect:
        c["citation_title_contains"] = any(expect["citation_title_contains"] in t for t in o.get("citation_titles", []))
    if "citation_title_contains_country" in expect:
        c["citation_title_contains_country"] = any(expect["citation_title_contains_country"] in t for t in o.get("citation_titles", []))
    if expect.get("citation_markers_match_evidence"):
        c["citation_markers_match_evidence"] = o.get("markers_in_answer_subset_of_evidence", False)
    if "answer_contains" in expect:
        c["answer_contains"] = all(s in o.get("answer", "") for s in expect["answer_contains"])
    if "answer_not_contains" in expect:
        c["answer_not_contains"] = not any(s in o.get("answer", "") for s in expect["answer_not_contains"])
    if "prompt_contains" in expect:
        c["prompt_contains"] = all(s in o.get("prompt", "") for s in expect["prompt_contains"])
    if "prompt_not_contains" in expect:
        c["prompt_not_contains"] = not any(s in o.get("prompt", "") for s in expect["prompt_not_contains"])
    if "findings_contain" in expect:
        c["findings_contain"] = any(expect["findings_contain"].lower() in f.lower() for f in o.get("findings", []))
    if "degraded_contains" in expect:
        c["degraded_contains"] = expect["degraded_contains"] in o.get("degraded", [])
    if "excluded_chunks_min" in expect:
        c["excluded_chunks_min"] = o.get("excluded_chunks", 0) >= expect["excluded_chunks_min"]
    if "excluded_chunks_max" in expect:
        c["excluded_chunks_max"] = o.get("excluded_chunks", 0) <= expect["excluded_chunks_max"]
    if "blocked" in expect:
        c["blocked"] = bool(o.get("blocked")) == expect["blocked"]
    if "responder_called" in expect:
        c["responder_called"] = (o.get("responder_calls", 0) > 0) == expect["responder_called"]
    if "equals" in expect:
        c["equals"] = o.get("value") == expect["equals"]
    # ingestion / governance / cache
    for key in ("error_contains", "units", "no_exception", "no_size_limit_in_loader", "text_kept_verbatim", "screened_at_retrieval", "sidecar_overrides_metadata", "title_falls_back_to_filename",
                "zero_width_removed_by_cleaner", "returned_versions", "never", "importers", "ok", "touches_developer_cache", "expired_returns_none", "malformed_entry_ignored", "key_ignores_free_text"):
        if key in expect:
            if key == "error_contains":
                c[key] = expect[key].lower() in (o.get("error") or "").lower()
            elif key == "never":
                c[key] = not (set(expect[key]) & set(o.get("returned_versions", [])))
            elif key == "returned_versions":
                c[key] = sorted(o.get("returned_versions", [])) == sorted(expect[key])
            else:
                c[key] = o.get(key) == expect[key]
    return c


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Case handlers
# ---------------------------------------------------------------------------------------------------------------------------------------------------
def _h_retrieval(world: World, case: dict) -> dict:
    res = world.retriever.retrieve(case["query"], top_k=TOP_K, filters=case.get("filters"))
    ranked = [r.chunk.doc_id for r in res]
    rel = set(case.get("relevant", []))
    obs: dict[str, Any] = {"ranked": ranked, "types": [r.metadata.get("document_type") for r in res]}
    if rel:
        obs.update(hit=bool(hit_at_k(ranked, rel, TOP_K)), recall=recall_at_k(ranked, rel, TOP_K), precision=precision_at_k(ranked, rel, TOP_K), rr=reciprocal_rank(ranked, rel, TOP_K),
                   relevant_found=len(rel & set(ranked[:TOP_K])))
    else:
        obs["hit"] = False
    return obs


def _evidence_observed(world: World, query: str) -> dict:
    svc = world.service(responder=None)
    res = svc.retrieve_evidence(query)
    ev = res.evidence
    return {
        "lane": res.retrieval_lane, "country": res.resolved_geography, "insufficient": bool(res.insufficient_evidence), "clarify": bool(res.clarify), "grounded": bool(res.occupation_grounded),
        "n_evidence": len(ev), "n_structured": sum(1 for e in ev if e.retrieval_lane != "vector"), "sources": sorted({e.source_id for e in ev}),
        "evidence_countries": sorted({(e.country or "") for e in ev}),
        "structured_countries": sorted({(e.country or "") for e in ev if e.retrieval_lane != "vector"}),
        "structured_geographies": sorted({(e.country or e.geography or "") for e in ev if e.evidence_type == "compensation"}),
        "occupation": res.resolved_occupation, "notes": list(res.trace.notes) + list(res.trace.coverage_notes or []), "years": sorted({e.reference_year for e in ev if e.reference_year}),
        "citations": len(res.citations),
        "citations_complete": len(res.citations) == len(ev) and all(c.title and (c.doc_id or c.chunk_id) for c in res.citations),
    }


def _h_evidence(world: World, case: dict) -> dict:
    return _evidence_observed(world, case["query"])


def _h_answer(world: World, case: dict) -> dict:
    spy = _responder(case["responder"])
    svc = world.service(responder=spy, retriever=bool(case.get("needs_retriever")))
    res = svc.answer(case["query"])
    cites = res.response.citations
    answer = res.response.answer or ""
    ev_markers = {f"[{i}]" for i in range(1, len(res.response.evidence) + 1)}
    used = set(re.findall(r"\[\d+\]", answer))
    return {
        "answer": answer, "n_citations": len(cites), "citation_sources": sorted({c.doc_id for c in cites}), "citation_titles": [c.title or "" for c in cites], "citation_urls": [c.source_url for c in cites],
        "prompt": spy.prompt, "findings": list(res.trace.output_findings or []), "degraded": list(res.trace.degraded), "excluded_chunks": int(res.trace.excluded_chunks or 0), "blocked": bool(res.trace.blocked),
        "responder_calls": spy.calls, "markers_in_answer_subset_of_evidence": used <= ev_markers,
    }


def _component(case: dict, world: World) -> Any:
    fn, arg = case["fn"], case["arg"]
    if fn == "tokenize":
        from src.copilot.retrieval.keyword import tokenize
        return tokenize(arg)
    if fn == "scan_verdict":
        from src.copilot.security.injection import scan_text
        return scan_text(arg).verdict
    if fn == "detect_country":
        from src.copilot.knowledge.router import detect_country
        return detect_country(arg)
    if fn == "route_lane":
        from src.copilot.knowledge.router import route_question
        return route_question(arg).lane
    if fn == "validate_input":
        from src.copilot.security.validation import validate_input
        r = validate_input(arg, "query")
        return {"ok": r.ok, "truncated": r.truncated}
    if fn == "guard_output":
        from src.copilot.security.output_guard import guard_output
        g = guard_output(arg, allowed_markers=set(case.get("allowed_markers", [])))
        return {"redacted": g.redacted_secrets > 0, "invalid": g.invalid_citations}
    if fn == "role_search_count":
        rows = world.role.search(arg["query"])
        return any(r["title"] == arg["expect_title"] for r in rows)
    raise ValueError(f"unknown component fn {fn}")


def _h_component(world: World, case: dict) -> dict:
    return {"value": _component(case, world)}


def _h_ingest(world: World, case: dict) -> dict:
    from src.copilot.ingestion import cleaners, loaders

    spec = case["spec"]
    d = Path(tempfile.mkdtemp(prefix="p10d_ingest_", dir=str(world.workdir)))
    path = d / spec["name"]
    if "repeat" in spec:
        path.write_text(spec["repeat"][0] * spec["repeat"][1], encoding="utf-8")
    elif "bytes_hex" in spec:
        path.write_bytes(bytes.fromhex(spec["bytes_hex"]))
    else:
        path.write_bytes(spec.get("bytes", "").encode("utf-8"))
    if "sidecar" in spec:
        Path(str(path) + ".meta.json").write_text(json.dumps(spec["sidecar"]), encoding="utf-8")
    obs: dict[str, Any] = {}
    try:
        units = loaders.load_document(str(path), content_columns=spec.get("content_columns"))
    except loaders.LoaderError as exc:
        obs["error"] = str(exc)
        return obs
    except Exception as exc:  # noqa: BLE001 - an unexpected exception type is itself a finding
        obs["error"] = f"UNEXPECTED {type(exc).__name__}"
        obs["no_exception"] = False
        return obs
    obs["units"] = len(units)
    obs["no_exception"] = True
    if spec.get("repeat"):
        obs["no_size_limit_in_loader"] = len(units) == 1 and len(units[0].text) >= len(spec["repeat"][0]) * spec["repeat"][1] - 10
    if units:
        text = units[0].text
        meta = units[0].metadata
        obs["text_kept_verbatim"] = "Ignore all previous instructions" in text
        from src.copilot.models import DocumentChunk, RetrievalResult
        from src.copilot.security.rag_guard import screen_results
        obs["screened_at_retrieval"] = screen_results([RetrievalResult(chunk=DocumentChunk(chunk_id="x", doc_id="x", text=text, metadata={}), score=1.0, retriever="vector")]).excluded_count == 1 if obs["text_kept_verbatim"] else None
        obs["sidecar_overrides_metadata"] = bool("sidecar" in spec and meta.get("source_url") == spec["sidecar"].get("source_url"))
        obs["title_falls_back_to_filename"] = meta.get("title") == path.stem
        obs["zero_width_removed_by_cleaner"] = "​" not in cleaners.clean_text(text) and "Ignore all previous instructions" in cleaners.clean_text(text)
    return obs


class _FakeActive:
    def __init__(self, ids):
        self._ids = set(ids)

    def active_version_ids(self):
        return set(self._ids)


def _h_governed(world: World, case: dict) -> dict:
    from src.copilot.models import DocumentChunk
    from src.copilot.vectorstore import InMemoryVectorStore
    from src.knowledge_admin.retriever import GovernedKnowledgeRetriever

    store = InMemoryVectorStore(world.embedder)
    chunks = []
    for vid, text in (("v_active", "governed guidance about structured interview answers"), ("v_unapproved", "unapproved guidance about structured interview answers"),
                      ("v_revoked", "revoked guidance about structured interview answers"), ("v_retired", "retired guidance about structured interview answers")):
        chunks.append(DocumentChunk(chunk_id=vid, doc_id=vid, text=text, metadata={"knowledge_version_id": vid, "title": vid}))
    store.add_chunks(chunks)   # every version is PHYSICALLY present in the vector collection: only the control-plane active set may decide what is returned
    r = GovernedKnowledgeRetriever.__new__(GovernedKnowledgeRetriever)
    r.store = store
    r._active = _FakeActive(["v_active"] if case["scenario"] == "governed_active_set" else [])
    got = r.retrieve("structured interview answers", top_k=5)
    return {"returned_versions": sorted(x.chunk.metadata.get("knowledge_version_id") for x in got)}


def _scan_importers(patterns: list[str], exclude_dirs: tuple[str, ...]) -> list[str]:
    root = constants.REPO_ROOT / "src"
    hits = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(constants.REPO_ROOT).as_posix()
        if any(rel.startswith(e) for e in exclude_dirs):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pat, text, re.M) for pat in patterns):
            hits.append(rel)
    return hits


def gate_values() -> dict[str, bool]:
    """The 12 rollout and billing gates (6 enforcement or enablement constants and 6 billing-policy constants), read from the code. Every one must be False."""
    from src import ai_protection as AP
    from src.application import history_access as HA, model_profile_access as MP, preparation_pack as PP, progress_analytics as PA, usage_quota as UQ
    from src.billing import policy as bp

    values = {"AI_COST_LIMITS_ENFORCED": AP.AI_COST_LIMITS_ENFORCED, "HISTORY_RESTRICTIONS_ENFORCED": HA.HISTORY_RESTRICTIONS_ENFORCED, "MODEL_PROFILE_ENFORCED": MP.MODEL_PROFILE_ENFORCED,
              "USAGE_QUOTAS_ENFORCED": UQ.USAGE_QUOTAS_ENFORCED, "PREMIUM_ANALYTICS_ENABLED": PA.PREMIUM_ANALYTICS_ENABLED, "PREPARATION_PACK_GENERATION_ENABLED": PP.PREPARATION_PACK_GENERATION_ENABLED}
    for g in ("LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PROVIDER_READS_AUTHORIZED", "PAID_ENTITLEMENT_POLICY_APPROVED"):
        values[g] = getattr(bp, g)
    return values


def _h_static(world: World, case: dict) -> dict:
    s = case["scenario"]
    if s == "p10c_not_imported_by_runtime":
        return {"importers": _scan_importers([r"^\s*(?:from|import)\s+src\.knowledge" r"_foundation\b"], ("src/knowledge" "_foundation/",))}
    if s == "no_user_data_in_retrieval_signature":
        import inspect
        from src.copilot.knowledge.retrieval import StructuredRetrievalCoordinator
        from src.copilot.service import CareerIntelligenceService
        sigs = [inspect.signature(CareerIntelligenceService.retrieve_evidence), inspect.signature(StructuredRetrievalCoordinator.retrieve)]
        names = {n for s_ in sigs for n in s_.parameters}
        service_src = inspect.getsource(CareerIntelligenceService)
        return {"ok": not ({"user_id", "owner_id", "tenant", "workspace_id"} & names) and "candidate_documents" not in service_src and "DocumentsApplicationService" not in service_src}
    if s == "gates_false":
        return {"ok": all(v is False for v in gate_values().values()) and len(gate_values()) == 12}
    if s == "retrieval_modules_do_not_log_content":
        bad = []
        for rel in ("src/copilot/service.py", "src/copilot/retrieval/hybrid.py", "src/copilot/retrieval/vector.py", "src/copilot/retrieval/keyword.py", "src/copilot/security/rag_guard.py"):
            text = (constants.REPO_ROOT / rel).read_text(encoding="utf-8")
            if re.search(r"\blogger?\.(info|debug|warning|error|exception)\(.*(query|chunk\.text|\.text)", text):
                bad.append(rel)
        return {"ok": not bad}
    raise ValueError(f"unknown static scenario {s}")


def _h_cache(world: World, case: dict) -> dict:
    import subprocess
    import sys

    s = case["scenario"]
    root = constants.REPO_ROOT
    if s == "import_isolation":
        code = ("import tests.conftest\nfrom src.copilot.research import cache\nimport os\n"
                "cache.write('p10d_probe_key', {'x': 1})\n"
                "print('DEV' if os.path.exists(os.path.join(os.environ.get('P10D_ROOT','.'), 'data/cache/external/p10d_probe_key.json')) else 'ISOLATED')")
        proc = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); exec(%r)" % (str(root), code)], cwd=str(root), capture_output=True, text=True,
                              env={**__import__("os").environ, "P10D_ROOT": str(root)}, timeout=120)
        return {"touches_developer_cache": "DEV" in proc.stdout or proc.returncode != 0}
    if s == "cache_not_in_structured_path":
        hits = _scan_importers([r"research\.cache|research import cache"], ("src/copilot/research/", "src/copilot/knowledge/requalification.py"))
        return {"importers": [p for p in hits if p.startswith(("src/copilot/knowledge/", "src/copilot/retrieval/", "src/copilot/rag/", "src/knowledge" "_foundation/")) or p == "src/copilot/service.py"]}
    from src.copilot.research import cache

    d = Path(tempfile.mkdtemp(prefix="p10d_cache_", dir=str(world.workdir)))
    if s == "ttl_expiry":
        cache.write("k", {"a": 1}, cache_dir=d)
        blob = json.loads((d / "k.json").read_text())
        blob["_cached_at"] = time.time() - 7200
        (d / "k.json").write_text(json.dumps(blob))
        return {"expired_returns_none": cache.read("k", ttl_seconds=60, cache_dir=d) is None}
    if s == "tampered_entry":
        (d / "bad.json").write_text("{not json")
        (d / "bad2.json").write_text(json.dumps({"_cached_at": time.time(), "payload": {"status": "ready", "snippet": 123}}))
        from src.copilot.research.models import CurrentMarketResearchResult
        ok = cache.read("bad", cache_dir=d) is None
        try:
            CurrentMarketResearchResult.model_validate(cache.read("bad2", cache_dir=d))
            ok = False   # a structurally invalid payload must fail validation (the service then ignores the entry)
        except Exception:  # noqa: BLE001
            pass
        return {"malformed_entry_ignored": ok}
    if s == "key_safe":
        a = cache.cache_key("p", "company", role="nurse", country="DE", region=None, company=None, limit=5)
        return {"key_ignores_free_text": len(a) == 24 and a == cache.cache_key("p", "company", role="nurse", country="DE", region=None, company=None, limit=5) and "nurse" not in a}
    raise ValueError(f"unknown cache scenario {s}")


HANDLERS: dict[str, Callable[[World, dict], dict]] = {"retrieval": _h_retrieval, "evidence": _h_evidence, "answer": _h_answer, "component": _h_component, "ingest": _h_ingest,
                                                     "governed": _h_governed, "static": _h_static, "cache": _h_cache}


def run_case(world: World, case: dict) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        observed = HANDLERS[case["kind"]](world, case)
        error = None
    except Exception as exc:  # noqa: BLE001 - a crashing case is a failed case, never a crashed run
        observed, error = {}, f"{type(exc).__name__}: {exc}"
    checks = _judge(observed, case.get("expect", {})) if error is None else {"no_crash": False}
    if error is None and not checks:
        checks = {"no_crash": True}
    desired = case.get("desired")
    if desired is not None and not isinstance(desired, dict):
        desired = {"equals": desired}   # a component case states its fully capable value directly
    capability_met = all(_judge(observed, {**case.get("expect", {}), **desired}).values()) if (desired and error is None) else (all(checks.values()) if error is None else False)
    safe_obs = {k: v for k, v in observed.items() if k not in ("prompt", "answer")}
    return {"id": case["id"], "family": case["family"], "kind": case["kind"], "mode": case["mode"], "language": case.get("language"), "dimension": case.get("dimension"),
            "ok": all(checks.values()), "checks": checks, "capability_met": capability_met, "limitation": case.get("limitation"), "observed": safe_obs, "error": error,
            "seconds": round(time.perf_counter() - t0, 5)}


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------------------------------------------------------------------------------
def retrieval_metrics(corpus: dict, results: list[dict]) -> dict[str, Any]:
    by_id = {c["id"]: c for c in corpus["cases"]}
    judged = [r for r in results if r["kind"] == "retrieval" and by_id[r["id"]].get("relevant") and "hit" in r["observed"]]
    rows = [{**r["observed"], "language": r["language"], "dimension": r["dimension"]} for r in judged]
    per_lang: dict[str, list] = defaultdict(list)
    for r in rows:
        per_lang[r["language"]].append(r)
    return {"label": "SYNTHETIC RELEVANCE JUDGMENTS, offline lexical embedder (not semantic quality)", "k": TOP_K, "overall": _agg(rows),
            "by_language": {lang: _agg(rs) for lang, rs in sorted(per_lang.items())}, "unjudged_retrieval_cases": sum(1 for r in results if r["kind"] == "retrieval") - len(judged)}


def multilingual_matrix(results: list[dict]) -> dict[str, Any]:
    """Per language and dimension: how many labelled cases reach the FULLY capable (desired) behaviour. Reported separately for every language, never averaged across languages."""
    cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in results:
        if r["language"] and r["dimension"]:
            cell[(r["language"], r["dimension"])].append(r)
    langs = sorted({k[0] for k in cell}, key=lambda x: ["en", "de", "ar", "fr", "es", "it", "pt", "nl", "ru", "mixed"].index(x) if x in ["en", "de", "ar", "fr", "es", "it", "pt", "nl", "ru", "mixed"] else 99)
    dims = sorted({k[1] for k in cell})
    return {"languages": langs, "dimensions": dims,
            "cells": {f"{lang}|{dim}": {"cases": len(rs), "capability_met": sum(1 for x in rs if x["capability_met"]), "pinned_behaviour_ok": sum(1 for x in rs if x["ok"])}
                      for (lang, dim), rs in sorted(cell.items())}}


def tag_coverage(corpus: dict, results: list[dict]) -> dict[str, Any]:
    by_id = {c["id"]: c for c in corpus["cases"]}
    exercised: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for t in by_id[r["id"]]["tags"]:
            exercised[t].append(r["ok"])
    required = [t for tags in corpus["required_tags"].values() for t in tags]
    missing = sorted(t for t in required if t not in exercised)
    failing = sorted(t for t in required if t in exercised and not all(exercised[t]))
    return {"required_tags": len(required), "exercised": len(required) - len(missing), "missing_tags": missing, "failing_tags": failing}


def determinism_hash(results: list[dict]) -> str:
    stable = [{k: r[k] for k in ("id", "ok", "checks", "capability_met", "observed", "error")} for r in results]
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def run_all(corpus: dict | None = None, *, store_kind: str = "memory") -> dict[str, Any]:
    corpus = corpus or load_corpus()
    errors = validate_corpus(corpus)
    t0 = time.perf_counter()
    with temp_world(corpus, store_kind=store_kind) as world:
        results = [run_case(world, c) for c in corpus["cases"]]
        index = {"chunks": world.chunk_count, "chroma_bytes": _dir_bytes(world.workdir / "chroma") if (world.workdir / "chroma").exists() else 0}
    cov = tag_coverage(corpus, results)
    limitation_summary: dict[str, dict] = {}
    for r in results:
        if r["limitation"]:
            s = limitation_summary.setdefault(r["limitation"], {"description": corpus["limitations"][r["limitation"]], "cases": [], "capability_met": 0})
            s["cases"].append(r["id"])
            s["capability_met"] += int(r["capability_met"])
    families: dict[str, dict] = defaultdict(lambda: {"cases": 0, "ok": 0})
    for r in results:
        families[r["family"]]["cases"] += 1
        families[r["family"]]["ok"] += int(r["ok"])
    ok = not errors and all(r["ok"] for r in results) and not cov["missing_tags"] and not cov["failing_tags"]
    return {"schema": RESULT_SCHEMA, "corpus_version": corpus["version"], "store": store_kind, "ok": ok, "integrity_errors": errors, "cases": results, "total": len(results), "passed": sum(1 for r in results if r["ok"]),
            "families": dict(sorted(families.items())), "retrieval_metrics": retrieval_metrics(corpus, results), "multilingual_matrix": multilingual_matrix(results), "tags": cov,
            "limitations": limitation_summary, "index": index, "determinism_hash": determinism_hash(results), "seconds": round(time.perf_counter() - t0, 3),
            "claims": {"mode_c_model_quality_measured": False, "human_rated": False, "semantic_retrieval_measured": False, "real_world_citations_verified": False, "production_ready": False,
                       "product_coverage_gate_passed": False}}


# ---------------------------------------------------------------------------------------------------------------------------------------------------
# Performance (measured, never part of the determinism hash)
# ---------------------------------------------------------------------------------------------------------------------------------------------------
def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, math.ceil(q * len(xs)) - 1)], 3) if xs else 0.0


def measure_performance(corpus: dict | None = None, repeats: int = 5, *, store_kind: str = "chroma") -> dict[str, Any]:
    from src.copilot.models import KnowledgeEvidence
    from src.copilot.rag.translation import QueryTranslator

    corpus = corpus or load_corpus()
    out: dict[str, Any] = {"unit": "milliseconds", "repeats_per_query": repeats, "note": "Measured on the synthetic fixture with the offline hash embedder and the real Chroma store; wall-clock, machine dependent."}
    out["store"] = store_kind
    with temp_world(corpus, store_kind=store_kind) as world:
        queries = [(c["query"], c.get("language", "en")) for c in corpus["cases"] if c["kind"] == "retrieval"]
        series: dict[str, list[float]] = defaultdict(list)
        by_lang: dict[str, list[float]] = defaultdict(list)

        def timed(name, fn, lang=None):
            t = time.perf_counter()
            fn()
            ms = (time.perf_counter() - t) * 1000
            series[name].append(ms)
            if lang and name == "hybrid_retrieval":
                by_lang["english" if lang == "en" else "non_english"].append(ms)

        for q, lang in queries:
            for _ in range(repeats):
                timed("embedding_lookup", lambda: world.embedder.embed_query(q))
                timed("vector_retrieval", lambda: world.vector.retrieve(q, top_k=TOP_K))
                timed("keyword_retrieval", lambda: world.keyword.retrieve(q, top_k=TOP_K))
                timed("hybrid_retrieval", lambda: world.retriever.retrieve(q, top_k=TOP_K), lang)
        svc = world.service(responder=None)
        ev_queries = [c["query"] for c in corpus["cases"] if c["kind"] == "evidence"]
        for q in ev_queries:
            for _ in range(repeats):
                timed("retrieve_evidence_end_to_end", lambda: svc.retrieve_evidence(q))
        bundle = svc._gather_evidence("What does a Data Analyst do?", job_description=None, candidate_background=None, progress=None)
        for _ in range(50):
            timed("context_assembly", lambda: svc._assemble_evidence(bundle.structured_evidence, bundle.results))
            timed("citation_resolution", lambda: [e.to_citation(f"[{i}]") for i, e in enumerate(bundle.evidence, start=1)])
        tr = QueryTranslator(config=None)
        miss = []
        for i in range(50):
            t = time.perf_counter()
            tr.translate(f"What does a data analyst do number {i}?")
            miss.append((time.perf_counter() - t) * 1000)
        cache = svc._translation_cache
        cache.set("k", tr.translate("What does a data analyst do?"))
        hit = []
        for _ in range(50):
            t = time.perf_counter()
            cache.get("k")
            hit.append((time.perf_counter() - t) * 1000)
        series["translation_heuristic_miss"], series["translation_cache_hit"] = miss, hit
        out["stages"] = {k: {"n": len(v), "p50": round(statistics.median(v), 3), "p95": _pct(v, 0.95), "max": round(max(v), 3)} for k, v in sorted(series.items())}
        out["multilingual_overhead"] = {k: {"n": len(v), "p50": round(statistics.median(v), 3), "p95": _pct(v, 0.95)} for k, v in sorted(by_lang.items())}
        out["index"] = {"chunks": world.chunk_count, "chroma_bytes": _dir_bytes(world.workdir / "chroma") if (world.workdir / "chroma").exists() else 0}
        out["cache_behaviour"] = {"translation_cache_ttl_seconds": "configured per service (default 300)", "hit_over_miss_speedup": round(statistics.median(miss) / max(statistics.median(hit), 1e-9), 1)}
        _ = KnowledgeEvidence   # imported to make the dependency on the evidence contract explicit
    return out
