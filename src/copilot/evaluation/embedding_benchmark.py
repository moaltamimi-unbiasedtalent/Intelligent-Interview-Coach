"""Reproducible multi-model embedding benchmark RUNNER (package 02E; OD-EMBED, OD-BUDGET). OFFLINE by construction; no model is selected here.

WHAT IT DOES: compares several embedding models on the frozen 02B seven-language dataset (49 passages, 49 questions) plus the frozen out-of-domain
abstention questions, through the existing provider abstraction (``BaseEmbedder``; the live factory builds the OpenAI-compatible embedder pointed at
OpenRouter's embeddings endpoint, never a direct OpenAI dependency). For every model it records recall@k, nDCG@k, MRR, the cross-language retrieval rate,
a per-language breakdown, a relevance-floor PROPOSAL (``calibrate``), and latency / throughput / token / cost accounting read from a provider-call record.

REPRODUCIBILITY: the model list comes from configuration (``evaluations/retrieval_quality/benchmark_models.json``, never from code); models run in
configuration order; queries and passages are processed in id order; ties break on id; the seed drives the bootstrap interval only; dataset hashes are
recorded and a changed dataset is refused; the result dict has a fixed schema and key order.

INDEX PER MODEL, VERSIONED (02B manifests): each model gets ``<root>/<model key>/v0001/{vectors.json, manifest.json}`` plus ``current.json``. The manifest is
the frozen 02K ``IndexManifestV2`` written by ``index_manifest.build_manifest``; before a stored index is reused it is checked with
``index_manifest.evaluate_index`` against the live embedder identity, so vectors of two embedders are never mixed or compared. A re-run REUSES a
compatible current index (no embedding spend). CONTROLLED REINDEX (``reindex=True``) builds the next version and flips ``current`` only after the new index is
complete; a failed build leaves the previous version current. ``rollback`` flips ``current`` back to the previous version.

SPEND CONTROL IS NOT BUILT HERE. The runner makes NO call unless (a) the 05C governor's approved-budget marker (``AI_BUDGET_APPROVED_MARKER``,
``OD-BUDGET:<ref>``) is present and valid, (b) the 02B paid-embedding guard is satisfied (explicit flag, marker, call ceiling) and (c) the planned call count
is within that ceiling. When the 05C governor module is importable it is consulted as well (see ``governor_guard``). A dry run prints calls and estimated tokens
per model from the dataset with no network and no key. Tests use a FAKE provider, accepted only with ``allow_fake=True`` (never exposed by the CLI).

HONESTY: the result carries ``production_embedder_selected: false`` and ``retrieval_quality_claimed: false``; a fake or local run is labelled as pipeline
evidence only; the dataset is synthetic and engineering-authored, so even a live result would be directional (49 questions, wide intervals), not independent.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.copilot import constants
from src.copilot.embedding_budget import (ApprovedBudget, BudgetedEmbedder, PaidEmbeddingRefused, estimate_embedding_run,
                                           require_paid_embedding_approval)
from src.copilot.embeddings import BaseEmbedder
from src.copilot.evaluation import multilingual_retrieval as ML
from src.copilot.index_manifest import (IndexIncompatibleError, build_manifest, evaluate_index, ManifestUnreadable, raise_if_refused, read_manifest,
                                        write_manifest)
from src.copilot.retrieval_quality import metrics as M
from src.copilot.retrieval_quality.accounting import RecordingEmbedder, summarise
from src.copilot.retrieval_quality.floor import ScoredQuery, calibrate
from src.knowledge_admin.contracts import EmbedderIdentity

__all__ = ["SCHEMA", "MODELS_PATH", "ABSTENTION_PATH", "FROZEN_ABSTENTION_SHA256", "ModelSpec", "BenchmarkRefused", "load_models", "load_abstention", "plan_run",
           "require_benchmark_approval", "governor_guard", "ModelIndexStore", "run_embedding_benchmark", "BUDGET_MARKER_ENV"]

SCHEMA = "embedding-benchmark/1"
ROOT = Path(__file__).resolve().parents[3]
MODELS_PATH = ROOT / "evaluations" / "retrieval_quality" / "benchmark_models.json"
ABSTENTION_PATH = ROOT / "evaluations" / "retrieval_quality" / "abstention_cases_v1.json"
FROZEN_ABSTENTION_SHA256 = "d333222f2031fe625881a415ee94330b2a748194d807b6c79998314291de51b6"
BUDGET_MARKER_ENV = "AI_BUDGET_APPROVED_MARKER"
_MARKER_RE = re.compile(r"^OD-BUDGET:[A-Za-z0-9._-]{4,64}$")
KS = (1, 3, 5, 10)
BOOTSTRAP_RESAMPLES = 200
FREE_PROVIDERS = ("local", "fake")


class BenchmarkRefused(Exception):
    """The run was refused before any provider call. ``codes`` are fixed identifiers; no environment value is ever included."""

    def __init__(self, codes: list[str]) -> None:
        super().__init__("embedding benchmark refused: " + ", ".join(codes))
        self.codes = list(codes)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model: str
    dimensions: int | None
    version: str
    provider: str = "openrouter"
    price_per_million_tokens_usd: float | None = None
    base_url: str | None = None


# ------------------------------------------------------------------ configuration and datasets
def load_models(path: Path | None = None) -> list[ModelSpec]:
    """The candidate list, in configuration order. Duplicate keys or models are refused; the file is data, not code."""
    try:
        data = json.loads((path or MODELS_PATH).read_text(encoding="utf-8"))
        specs = [ModelSpec(str(m["key"]), str(m["model"]), m.get("dimensions"), str(m["version"]), str(m.get("provider", "openrouter")),
                           m.get("price_per_million_tokens_usd"), data.get("base_url")) for m in data["models"]]
    except Exception:  # noqa: BLE001
        raise BenchmarkRefused(["models_config_invalid"]) from None
    if not specs or len({s.key for s in specs}) != len(specs) or len({s.model for s in specs}) != len(specs):
        raise BenchmarkRefused(["models_config_invalid"])
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", s.key) for s in specs):
        raise BenchmarkRefused(["models_config_invalid"])
    return specs


def load_abstention(path: Path | None = None, *, expected_sha256: str | None = None) -> dict:
    p = path or ABSTENTION_PATH
    raw = p.read_bytes()
    expected = FROZEN_ABSTENTION_SHA256 if expected_sha256 is None and path is None else expected_sha256
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ML.DatasetIntegrityError("the frozen abstention dataset does not match its recorded hash")
    return json.loads(raw.decode("utf-8"))


# ------------------------------------------------------------------ planning (no network)
def plan_run(models: list[ModelSpec], dataset: dict, abstention: dict, *, batch_size: int = constants.EMBED_BATCH_SIZE) -> dict:
    """Embedding calls and estimated tokens per model, from the datasets only. Models are independent (each embeds the whole corpus and every question)."""
    docs = [p["text"] for p in dataset["passages"]]
    qs = [q["text"] for q in dataset["queries"]] + [q["text"] for q in abstention["queries"]]
    est = estimate_embedding_run(document_texts=docs, query_texts=qs, batch_size=batch_size)
    per = []
    for m in models:
        price = m.price_per_million_tokens_usd
        per.append({"key": m.key, "model": m.model, "embedding_calls": est["embedding_calls"], "estimated_tokens": est["approx_tokens"],
                    "estimated_cost_usd": None if price is None else round(est["approx_tokens"] * price / 1_000_000, 6),
                    "cost_note": "price not configured: unknown" if price is None else "from the configured price (planning figure)"})
    return {"models": per, "total_embedding_calls": sum(p["embedding_calls"] for p in per), "total_estimated_tokens": sum(p["estimated_tokens"] for p in per),
            "documents": len(docs), "questions": len(qs), "network": "none: this is arithmetic over the frozen datasets",
            "assumptions": est["assumptions"]}


# ------------------------------------------------------------------ approval
def governor_guard(environ: Mapping[str, str] | None = None) -> None:
    """Consult the 05C governor when its module exists (it is merged separately). Raises :class:`BenchmarkRefused` if the governor refuses.
    Absent module: the marker and 02B guard checks in :func:`require_benchmark_approval` still apply and are mandatory."""
    try:
        from src.llm.budget import script_guard  # type: ignore[import-not-found]
    except ImportError:
        return
    code = script_guard.guard_paid_script("run_embedding_benchmark", category="embedding", environ=environ)
    if code is not None:
        raise BenchmarkRefused(["governor_refused"])


def require_benchmark_approval(env: Mapping[str, str] | None = None) -> ApprovedBudget:
    """All of: the 05C approved-budget marker, the 02B paid-embedding flag + marker + call ceiling. Returns the ceiling; raises :class:`BenchmarkRefused`."""
    e = os.environ if env is None else env
    codes: list[str] = []
    marker = (e.get(BUDGET_MARKER_ENV) or "").strip()
    if not marker:
        codes.append("governor_marker_missing")
    elif not _MARKER_RE.match(marker):
        codes.append("governor_marker_invalid")
    try:
        budget = require_paid_embedding_approval(e)
    except PaidEmbeddingRefused as exc:
        codes.extend(exc.codes)
        budget = None
    if codes or budget is None:
        raise BenchmarkRefused(codes or ["approval_missing"])
    return budget


# ------------------------------------------------------------------ versioned per-model index
class ModelIndexStore:
    """``<root>/<model key>/vNNNN/{vectors.json, manifest.json}`` + ``current.json`` (``{"current": N, "history": [..]}``). Never deletes a version."""

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)

    def _dir(self, key: str) -> Path:
        return self.root / key

    def _pointer(self, key: str) -> dict:
        p = self._dir(key) / "current.json"
        if not p.exists():
            return {"current": None, "history": []}
        return json.loads(p.read_text(encoding="utf-8"))

    def _set_pointer(self, key: str, current: int | None, history: list[int]) -> None:
        d = self._dir(key)
        d.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".current-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"current": current, "history": history}, sort_keys=True))
        os.replace(tmp, d / "current.json")

    def current_version(self, key: str) -> int | None:
        return self._pointer(key)["current"]

    def versions(self, key: str) -> list[int]:
        return list(self._pointer(key)["history"])

    def _vdir(self, key: str, n: int) -> Path:
        return self._dir(key) / f"v{n:04d}"

    def load_current(self, key: str, live: EmbedderIdentity) -> dict[str, list[float]] | None:
        """The current vectors when a version exists AND its manifest matches the live embedder; ``None`` when there is none.
        Raises :class:`IndexIncompatibleError` for a mismatching or unreadable manifest (never reuses vectors of another embedder)."""
        cur = self.current_version(key)
        if cur is None:
            return None
        v = self._vdir(key, cur)
        try:
            manifest = read_manifest(v / "manifest.json")
        except ManifestUnreadable:
            raise IndexIncompatibleError(["manifest_unreadable"], ("manifest",), key) from None
        vectors = json.loads((v / "vectors.json").read_text(encoding="utf-8"))
        status = evaluate_index(manifest, live, count=len(vectors), hosted=True, collection_id=key)   # hosted=True: unknown fields are never assumed compatible
        raise_if_refused(status)
        return vectors

    def write_version(self, key: str, live: EmbedderIdentity, vectors: dict[str, list[float]], *, embedder_label: str) -> int:
        """Write the next version completely, THEN flip ``current``. A failure before the flip leaves the previous version current."""
        hist = self.versions(key)
        n = (max(hist) if hist else 0) + 1
        v = self._vdir(key, n)
        v.mkdir(parents=True, exist_ok=False)
        (v / "vectors.json").write_text(json.dumps(vectors, sort_keys=True), encoding="utf-8")
        write_manifest(v / "manifest.json", build_manifest(live, collection_id=key, chunk_ids=list(vectors), embedder_label=embedder_label))
        self._set_pointer(key, n, hist + [n])
        return n

    def rollback(self, key: str) -> int:
        """Make the previous version current again. Refused (``IndexIncompatibleError``) when there is no previous version."""
        hist, cur = self.versions(key), self.current_version(key)
        if cur is None or cur not in hist or hist.index(cur) == 0:
            raise IndexIncompatibleError(["no_previous_version"], (), key)
        prev = hist[hist.index(cur) - 1]
        self._set_pointer(key, prev, hist)
        return prev


# ------------------------------------------------------------------ the run
def _bootstrap_ci(values: list[float], seed: int, key: str) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(f"{seed}:{key}")          # string seed: stable across processes (hash randomisation does not apply to Random(str))
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(BOOTSTRAP_RESAMPLES))
    return [round(means[int(0.025 * BOOTSTRAP_RESAMPLES)], 4), round(means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1], 4)]


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def _evaluate_model(spec: ModelSpec, rec: RecordingEmbedder, store: ModelIndexStore, ds: dict, neg: dict, *, reindex: bool, seed: int) -> dict:
    passages = sorted(ds["passages"], key=lambda p: p["id"])
    queries = sorted(ds["queries"], key=lambda q: q["id"])
    negatives = sorted(neg["queries"], key=lambda q: q["id"])
    live = rec.identity()
    vectors = None if reindex else store.load_current(spec.key, live)
    reused = vectors is not None
    if vectors is None:
        embedded = []
        step = constants.EMBED_BATCH_SIZE
        for i in range(0, len(passages), step):
            embedded.extend(rec.embed_documents([p["text"] for p in passages[i:i + step]]))
        vectors = {p["id"]: [float(x) for x in v] for p, v in zip(passages, embedded)}
        version_no = store.write_version(spec.key, live, vectors, embedder_label=type(rec._inner).__name__[:64])
    else:
        version_no = store.current_version(spec.key)
    qv = {q["id"]: rec.embed_query(q["text"]) for q in queries}
    nv = {q["id"]: rec.embed_query(q["text"]) for q in negatives}
    languages = {p["id"]: p["language"] for p in passages}

    def ranked(vec: list[float], corpus: list[dict]) -> list[tuple[float, str]]:
        return sorted(((ML._cosine(vec, vectors[p["id"]]), p["id"]) for p in corpus), key=lambda t: (-t[0], t[1]))

    slices: dict[str, Any] = {}
    mixed_cases: list[tuple[str, list[str], set[str]]] = []
    scored: list[ScoredQuery] = []
    for s in ML.SLICES:
        rows = []
        for q in queries:
            corpus = ML._corpus_for(s, q["language"], passages)
            rel = {p["id"] for p in corpus if p["topic"] == q["topic"]}
            order = ranked(qv[q["id"]], corpus)
            ids = [pid for _, pid in order]
            rows.append((q["language"], ids, rel))
            if s == "mixed_corpus":
                mixed_cases.append((q["language"], ids, rel))
                scored.append(ScoredQuery(q["id"], q["language"], tuple((sc, pid in rel) for sc, pid in order[:max(KS)]), True))
        by_lang: dict[str, dict] = {}
        for lang in ML.LANGUAGES:
            sub = [(i, r) for lg, i, r in rows if lg == lang]
            by_lang[lang] = {"n": len(sub), "recall@5": _r(M.mean_defined(M.recall_at_k(i, r, 5) for i, r in sub)), "mrr": _r(M.mean_reciprocal_rank(sub))}
        overall = {"n": len(rows), "mrr": _r(M.mean_reciprocal_rank([(i, r) for _, i, r in rows])),
                   **{f"recall@{k}": _r(M.mean_defined(M.recall_at_k(i, r, k) for _, i, r in rows)) for k in KS},
                   "ndcg@10": _r(M.mean_defined(M.ndcg_at_k(i, r, 10) for _, i, r in rows))}
        slices[s] = {"overall": overall, "by_question_language": by_lang}
    for q in negatives:
        order = ranked(nv[q["id"]], passages)
        scored.append(ScoredQuery(q["id"], q["language"], tuple((sc, False) for sc, _ in order[:max(KS)]), False))
    rr = [M.reciprocal_rank(i, r) for _, i, r in mixed_cases]
    xl = M.cross_language_retrieval_rate(mixed_cases, languages, k=5)
    return {"key": spec.key, "model": spec.model, "identity": {"provider": live.provider, "model": live.model, "version": live.version, "dimensions": live.dimensions},
            "index": {"version": version_no, "reused_existing": reused, "versions": store.versions(spec.key)},
            "results": slices, "cross_language_retrieval_rate@5_mixed": _r(xl),
            "mrr_ci95_mixed": _bootstrap_ci([x for x in rr if x is not None], seed, spec.key),
            "floor_proposal": calibrate(scored), "accounting": summarise(rec.records, price_per_million_tokens_usd=spec.price_per_million_tokens_usd)}


def run_embedding_benchmark(models: list[ModelSpec], embedder_factory: Callable[[ModelSpec], BaseEmbedder], *, store_root: str | os.PathLike,
                            dataset: dict | None = None, abstention: dict | None = None, env: Mapping[str, str] | None = None, seed: int = 20260101,
                            reindex: bool = False, allow_fake: bool = False, approval: Callable[[Mapping[str, str] | None], ApprovedBudget] = require_benchmark_approval,
                            clock: Callable[[], float] | None = None) -> dict:
    """Run every configured model and return the result dict. REFUSES (``BenchmarkRefused``, no provider call, nothing built) unless the run is free
    (``allow_fake`` with only fake/local providers) or fully approved (:func:`require_benchmark_approval`) with the planned call count inside the ceiling."""
    if not models:
        raise BenchmarkRefused(["no_models"])
    ds = dataset or ML.load_dataset()
    neg = abstention or load_abstention()
    plan = plan_run(models, ds, neg)
    paid = [m for m in models if m.provider not in FREE_PROVIDERS]
    fake_only = bool(models) and not paid
    if any(m.provider == "fake" for m in models) and not allow_fake:
        raise BenchmarkRefused(["fake_provider_not_allowed"])
    budget: ApprovedBudget | None = None
    if paid or not fake_only:
        budget = approval(env)
        governor_guard(env)
        # each paid model gets its own ceiling-bounded wrapper; refuse up front if one model alone would exceed the approved ceiling
        per_model_calls = plan["models"][0]["embedding_calls"]
        if per_model_calls * len(paid) > budget.max_calls:
            raise BenchmarkRefused(["planned_calls_exceed_approved_ceiling"])
    store = ModelIndexStore(store_root)
    out_models, failures = [], []
    for spec in models:
        inner = embedder_factory(spec)
        guarded: BaseEmbedder = inner if spec.provider in FREE_PROVIDERS else BudgetedEmbedder(inner, budget)   # type: ignore[arg-type]
        rec = RecordingEmbedder(guarded, **({} if clock is None else {"clock": clock}), price_per_million_tokens_usd=spec.price_per_million_tokens_usd)
        try:
            out_models.append(_evaluate_model(spec, rec, store, ds, neg, reindex=reindex, seed=seed))
        except (IndexIncompatibleError, PaidEmbeddingRefused) as exc:
            failures.append({"key": spec.key, "model": spec.model, "codes": list(exc.codes), "accounting": summarise(rec.records)})
        except Exception as exc:  # noqa: BLE001 - provider text never propagates; EmbeddingProviderError carries a fixed code
            failures.append({"key": spec.key, "model": spec.model, "codes": [getattr(exc, "code", "model_run_failed")], "accounting": summarise(rec.records)})
    return {"schema_version": SCHEMA,
            "label": "FAKE PROVIDER: pipeline verification only, NOT retrieval-quality evidence" if fake_only else "owner-approved governed run; synthetic engineering-authored dataset, directional only",
            "production_embedder_selected": False, "retrieval_quality_claimed": False, "selection": None,
            "selection_note": "Choosing the production embedding model is an owner decision (OD-EMBED) from measured evidence; this runner never selects one.",
            "seed": seed, "reindex": reindex,
            "datasets": {"multilingual": {"name": ds.get("name"), "sha256": ML.FROZEN_DATASET_SHA256, "passages": len(ds["passages"]), "queries": len(ds["queries"])},
                         "abstention": {"name": neg.get("name"), "sha256": FROZEN_ABSTENTION_SHA256, "queries": len(neg["queries"])}},
            "independence_limitation": "datasets are synthetic and authored by engineering; not independent, not native-reviewed; 49 + 21 questions give wide intervals",
            "plan": plan, "models": out_models, "failed_models": failures,
            "comparison_informational": [{"key": m["key"], "mrr_mixed": m["results"]["mixed_corpus"]["overall"]["mrr"],
                                          "recall@5_mixed": m["results"]["mixed_corpus"]["overall"]["recall@5"],
                                          "cross_language_retrieval_rate@5": m["cross_language_retrieval_rate@5_mixed"]} for m in out_models]}
