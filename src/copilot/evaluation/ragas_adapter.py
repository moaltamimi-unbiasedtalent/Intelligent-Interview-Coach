"""Optional RAGAS generation-quality adapter (isolated from production runtime).

RAGAS is an OPTIONAL secondary evaluation layer. This module:

* defines a plain, RAGAS-independent evaluation contract (:class:`RagasEvalCase`);
* converts a Career Intelligence result into that plain contract (no LangChain /
  Chroma / SQLite / Streamlit objects, and no private candidate/JD content);
* lazy-imports RAGAS and the evaluator model only when a live run is requested;
* normalises RAGAS output to plain dictionaries.

Nothing here is imported by the chat runtime — the app works identically when
RAGAS is not installed. Missing package or missing evaluator credentials degrade
to a clean, explicit skip, never a crash.
"""

from __future__ import annotations

import base64
import json
import math
import os
import struct
from collections import Counter
from contextlib import ExitStack, contextmanager
from copy import copy, deepcopy
from dataclasses import dataclass, field
from functools import partial
from threading import Lock

__all__ = [
    "RagasEvalCase",
    "EvaluatorConfig",
    "RagasNotInstalled",
    "RagasNotConfigured",
    "ragas_available",
    "evaluator_config_from_env",
    "case_from_service_result",
    "load_cases",
    "run_ragas",
    "is_valid_score",
    "has_usable_scores",
    "STATUS_COMPLETE",
    "STATUS_PARTIAL",
    "STATUS_FAILED",
    "METRIC_FAITHFULNESS",
    "METRIC_RESPONSE_RELEVANCY",
    "METRIC_CONTEXT_PRECISION",
    "METRIC_CONTEXT_RECALL",
]

# Deterministic execution-status labels (technical validity, NOT model quality).
STATUS_COMPLETE = "COMPLETE"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"


def is_valid_score(value) -> bool:
    """A usable metric score is a finite real number (not bool, NaN, or inf)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def has_usable_scores(run: dict) -> bool:
    """True if the run produced at least one valid (finite) evaluator score."""
    return int(run.get("valid_score_count", 0)) > 0

# Project-facing metric names (stable; independent of RAGAS column renames).
METRIC_FAITHFULNESS = "faithfulness"
METRIC_RESPONSE_RELEVANCY = "response_relevancy"
METRIC_CONTEXT_PRECISION = "context_precision"
METRIC_CONTEXT_RECALL = "context_recall"

_MAX_CONTEXTS = 20
_MAX_CONTEXT_CHARS = 2000

_GOVERNED_RAGAS_VERSION = "0.2.15"
_GOVERNED_SCORING_PROTOCOL = "ask4mo-ragas-07b"
_GOVERNED_SCORING_VERSION = 1
_GOVERNED_QUESTION_COUNT = 1
_MAX_REUSABLE_RESULTS = 256
_SDK_ACTIVITY_LOCK = Lock()
_ordinary_sdk_runs = 0
_governed_sdk_running = False


class RagasNotInstalled(RuntimeError):
    """Raised when a live RAGAS run is requested but the package is absent."""


class RagasNotConfigured(RuntimeError):
    """Raised when a live RAGAS run is requested without evaluator credentials."""


class InvalidContextText(ValueError):
    """Strict extraction received malformed evidence or provenance."""


@dataclass
class RagasEvalCase:
    """A plain, RAGAS-independent evaluation record (safe to serialise)."""

    case_id: str
    question: str
    answer: str
    retrieved_contexts: list[str] = field(default_factory=list)
    reference: str | None = None
    reference_contexts: list[str] | None = None
    source_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def has_reference(self) -> bool:
        return bool((self.reference or "").strip())

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "answer": self.answer,
            "retrieved_contexts": list(self.retrieved_contexts),
            "reference": self.reference,
            "reference_contexts": self.reference_contexts,
            "source_ids": list(self.source_ids),
            "metadata": dict(self.metadata),
        }


@dataclass
class EvaluatorConfig:
    """Evaluator-model configuration, independent of production chat."""

    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"

    def safe_dict(self) -> dict:
        """Config for run_config.json — NEVER includes the API key."""
        return {
            "evaluator_model": self.model,
            "evaluator_base_url": self.base_url or "default",
            "evaluator_embedding_model": self.embedding_model,
        }


def ragas_available() -> bool:
    """True if the RAGAS package can be imported (no side effects on the app)."""
    import importlib.util

    return importlib.util.find_spec("ragas") is not None


def evaluator_config_from_env(*, allow_chat_fallback: bool = False) -> EvaluatorConfig | None:
    """Build evaluator config from ``RAGAS_EVAL_*`` env vars, or ``None``.

    The production chat credential is only reused when ``allow_chat_fallback`` is
    explicitly set (the CLI exposes this behind an opt-in flag).
    """
    api_key = os.environ.get("RAGAS_EVAL_API_KEY")
    base_url = os.environ.get("RAGAS_EVAL_BASE_URL")
    model = os.environ.get("RAGAS_EVAL_MODEL", "gpt-4o-mini")
    embedding_model = os.environ.get("RAGAS_EVAL_EMBEDDING_MODEL", "text-embedding-3-small")
    if not api_key and allow_chat_fallback:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("COPILOT_API_KEY")
        base_url = base_url or os.environ.get("COPILOT_BASE_URL")
    if not api_key:
        return None
    return EvaluatorConfig(api_key=api_key, model=model, base_url=base_url,
                           embedding_model=embedding_model)


def _dedupe_bounded(texts) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for text in texts:
        cleaned = (str(text) or "").strip()[:_MAX_CONTEXT_CHARS]
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
        if len(out) >= _MAX_CONTEXTS:
            break
    return out


def _strict_contexts(response, result) -> tuple[list[str], list[str]]:
    from types import SimpleNamespace

    from src.copilot.models import DocumentChunk, KnowledgeEvidence, RetrievalResult
    from src.knowledge_approval import source_key

    evidence = getattr(response, "evidence", None)
    retrieved = getattr(response, "retrieved", None)
    if retrieved is None and response is not result:
        retrieved = getattr(result, "retrieved", None)
    for channel in (evidence, retrieved):
        if channel is not None and type(channel) is not list and type(channel) is not tuple:
            raise InvalidContextText("Retrieved evidence must be a list or tuple.")

    contexts: list[str] = []
    source_ids: list[str] = []

    def add(entry) -> None:
        text = getattr(entry, "text", None)
        source = getattr(entry, "source_id", "")
        metadata = getattr(entry, "metadata", None)
        if type(text) is not str or type(source) is not str:
            raise InvalidContextText("Retrieved text and source identifiers must be strings.")
        if metadata is None:
            metadata = {}
        if type(metadata) is not dict or any(
            type(metadata.get(key, "")) is not str
            for key in ("knowledge_source_id", "manifest_source_id", "source_id")
        ):
            raise InvalidContextText("Retrieved source identifiers must be strings.")
        if text.strip():
            contexts.append(text)
            identity = source_key(metadata, source)
            if identity and identity not in source_ids:
                source_ids.append(identity)

    for entry in evidence or ():
        if type(entry) is not KnowledgeEvidence and type(entry) is not SimpleNamespace:
            raise InvalidContextText("Unsupported structured evidence entry.")
        add(entry)
    for entry in retrieved or ():
        if type(entry) is not RetrievalResult and type(entry) is not SimpleNamespace:
            raise InvalidContextText("Unsupported retrieved evidence entry.")
        chunk = getattr(entry, "chunk", None)
        if type(chunk) is not DocumentChunk and type(chunk) is not SimpleNamespace:
            raise InvalidContextText("Unsupported retrieved evidence chunk.")
        add(chunk)
    return contexts, source_ids


def case_from_service_result(
    case_id: str,
    question: str,
    result,
    *,
    category: str | None = None,
    reference: str | None = None,
    reference_contexts: list[str] | None = None,
    strict_context_text: bool = False,
) -> RagasEvalCase:
    """Convert a Career Intelligence result into a plain :class:`RagasEvalCase`.

    Only the question, the generated answer, and the answer's evidence/citation
    text are used. Private inputs (candidate background, raw job description,
    transcripts, uploaded company files) are never read here.
    Strict extraction validates both collections before iteration and derives
    context and source identities from the same evidence entries.
    """
    response = getattr(result, "response", result)
    answer = getattr(result, "answer", None) or getattr(response, "answer", "")

    if strict_context_text:
        contexts, source_ids = _strict_contexts(response, result)
    else:
        contexts = []
        for ev in getattr(response, "evidence", None) or []:
            text = getattr(ev, "text", None)
            if text:
                contexts.append(text)
        for r in getattr(response, "retrieved", None) or getattr(result, "retrieved", None) or []:
            text = getattr(getattr(r, "chunk", None), "text", None)
            if text:
                contexts.append(text)

        source_ids = []
        for ev in getattr(response, "evidence", None) or []:
            sid = getattr(ev, "source_id", None)
            if sid and sid not in source_ids:
                source_ids.append(sid)
        for c in getattr(response, "citations", None) or getattr(result, "citations", None) or []:
            sid = getattr(c, "doc_id", None) or getattr(c, "source", None)
            if sid and sid not in source_ids:
                source_ids.append(sid)

    metadata = {"category": category} if category else {}
    return RagasEvalCase(
        case_id=case_id,
        question=question,
        answer=answer,
        retrieved_contexts=_dedupe_bounded(contexts),
        reference=reference,
        reference_contexts=reference_contexts,
        source_ids=source_ids,
        metadata=metadata,
    )


def load_cases(path: str) -> list[RagasEvalCase]:
    """Load public evaluation cases from a cases.json file."""
    import json

    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    rows = data.get("cases", data) if isinstance(data, dict) else data
    cases: list[RagasEvalCase] = []
    for row in rows:
        cases.append(RagasEvalCase(
            case_id=row["case_id"],
            question=row["question"],
            answer=row.get("answer", ""),
            retrieved_contexts=list(row.get("retrieved_contexts", [])),
            reference=row.get("reference"),
            reference_contexts=row.get("reference_contexts"),
            source_ids=list(row.get("source_ids", [])),
            metadata={k: row[k] for k in ("category", "geography", "expected_source_family")
                      if k in row},
        ))
    return cases


# --- Live run (lazy RAGAS import) -------------------------------------------


def _evaluator_bounds() -> tuple[dict, dict]:
    """Resolve bounds without importing the optional evaluator SDK."""
    from src.llm.budget.config import GOVERNED_07B_MAX_EMBEDDING_INPUTS
    from src.llm.budget.governor import OP_HEADER, active_governor

    governor = active_governor()
    if governor is not None and governor.governed_07b:
        limits = governor.config.limits
        return (
            {"max_tokens": limits.max_output_tokens, "timeout": limits.request_timeout_s,
             "max_retries": 0, "use_responses_api": False, "disable_streaming": True,
             "default_headers": {OP_HEADER: "ragas"}},
            {"timeout": limits.request_timeout_s, "max_retries": 0, "check_embedding_ctx_length": False,
             "chunk_size": GOVERNED_07B_MAX_EMBEDDING_INPUTS,
             "default_headers": {OP_HEADER: "evaluator_embedding"}},
        )
    if not os.environ.get("ASK4MO_PROVIDER_MODE"):
        return {}, {}
    # Capstone live demonstration: every request must carry an output cap, a timeout and at most one retry so the EUR ledger can reserve its worst case; embeddings are
    # sent as plain strings (no client-side tokenisation) so the ledger can price them.
    return {"max_tokens": 2048, "timeout": 60, "max_retries": 1}, {"timeout": 60, "max_retries": 1, "check_embedding_ctx_length": False}


def _build_evaluator(config: EvaluatorConfig):
    """Build LangChain-wrapped evaluator LLM + embeddings for RAGAS."""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    from src.llm.budget.governor import active_governor

    chat_bounds, emb_bounds = _evaluator_bounds()
    governor = active_governor()
    if governor is not None and governor.governed_07b:
        clients = {"http_client": governor.prototype_client(),
                   "http_async_client": governor.prototype_client(asynchronous=True)}
        chat_bounds.update(clients)
        emb_bounds.update(clients)
    chat = ChatOpenAI(model=config.model, api_key=config.api_key,
                      base_url=config.base_url, temperature=0.0, **chat_bounds)
    emb = OpenAIEmbeddings(model=config.embedding_model, api_key=config.api_key,
                           base_url=config.base_url, **emb_bounds)
    return LangchainLLMWrapper(chat), LangchainEmbeddingsWrapper(emb)


def _build_metrics(reference_free_only: bool):
    """Instantiate the RAGAS metric objects for this run."""
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        ResponseRelevancy,
    )

    metrics = [
        (METRIC_FAITHFULNESS, Faithfulness()),
        (METRIC_RESPONSE_RELEVANCY, ResponseRelevancy()),
        (METRIC_CONTEXT_PRECISION, LLMContextPrecisionWithoutReference()),
    ]
    if not reference_free_only:
        from ragas.metrics import LLMContextRecall

        metrics.append((METRIC_CONTEXT_RECALL, LLMContextRecall()))
    return metrics


def _to_sample(case: RagasEvalCase, *, with_reference: bool):
    from ragas.dataset_schema import SingleTurnSample

    kwargs = dict(
        user_input=case.question,
        response=case.answer,
        retrieved_contexts=case.retrieved_contexts or [""],
    )
    if with_reference and case.has_reference:
        kwargs["reference"] = case.reference
    return SingleTurnSample(**kwargs)


def run_ragas(
    cases: list[RagasEvalCase],
    *,
    config: EvaluatorConfig,
    evaluate_fn=None,
    build_evaluator_fn=None,
    build_metrics_fn=None,
    to_sample_fn=None,
) -> dict:
    """Run RAGAS over ``cases`` and return plain, normalised results.

    The ``*_fn`` hooks are injection points for offline tests; in production they
    default to the real RAGAS entry points. Raises :class:`RagasNotInstalled` if
    the package is missing and :class:`RagasNotConfigured` if ``config`` is falsy.
    """
    if not ragas_available() and evaluate_fn is None:
        raise RagasNotInstalled(
            "RAGAS is not installed. Install with: pip install -e \".[evaluation]\"")
    if config is None:
        raise RagasNotConfigured("Evaluator credentials are not configured.")

    _evaluate = evaluate_fn or _default_evaluate
    _make_metrics = build_metrics_fn or _build_metrics
    _make_sample = to_sample_fn or _to_sample
    llm, embeddings = (build_evaluator_fn or _build_evaluator)(config) if evaluate_fn is None \
        else (None, None)

    reuse = None
    if evaluate_fn is None:
        governor = _active_07b()
        if governor is not None:
            reuse = _EvaluationReuse(governor)
            _evaluate = partial(_default_evaluate, reuse=reuse)

    with_ref = [c for c in cases if c.has_reference]

    per_case: dict[str, dict] = {c.case_id: {"case_id": c.case_id,
                                             "category": c.metadata.get("category", "")}
                                 for c in cases}
    context_recall_run = bool(with_ref)

    # Reference-free metrics run on every case.
    rf_metrics = _make_metrics(reference_free_only=True)
    rf_scores = _evaluate(
        [_make_sample(c, with_reference=False) for c in cases],
        rf_metrics, llm, embeddings)
    _merge_scores(per_case, cases, rf_scores, [m[0] for m in rf_metrics])

    # Context Recall runs only on the referenced subset.
    if with_ref:
        cr_metrics = [m for m in _make_metrics(reference_free_only=False)
                      if m[0] == METRIC_CONTEXT_RECALL]
        cr_scores = _evaluate(
            [_make_sample(c, with_reference=True) for c in with_ref],
            cr_metrics, llm, embeddings)
        _merge_scores(per_case, with_ref, cr_scores, [METRIC_CONTEXT_RECALL])

    metric_names = [METRIC_FAITHFULNESS, METRIC_RESPONSE_RELEVANCY, METRIC_CONTEXT_PRECISION]
    if context_recall_run:
        metric_names.append(METRIC_CONTEXT_RECALL)

    rows = list(per_case.values())
    aggregates = _aggregate(rows, metric_names)

    # Execution validity (technical coverage, NOT model quality). Only finite
    # scores count; a failed evaluator job leaves its score absent.
    reference_free = [METRIC_FAITHFULNESS, METRIC_RESPONSE_RELEVANCY, METRIC_CONTEXT_PRECISION]
    expected = len(reference_free) * len(cases) + (len(with_ref) if context_recall_run else 0)
    valid = sum(1 for r in rows for name in metric_names if is_valid_score(r.get(name)))
    valid_case_count = sum(1 for r in rows
                           if any(is_valid_score(r.get(name)) for name in metric_names))
    metrics_with_scores = [name for name in metric_names if aggregates.get(name) is not None]
    if valid == 0:
        status = STATUS_FAILED
    elif valid >= expected:
        status = STATUS_COMPLETE
    else:
        status = STATUS_PARTIAL

    result = {
        "metrics": aggregates,
        "per_case": rows,
        "metric_names": metric_names,
        "metrics_with_scores": metrics_with_scores,
        "context_recall_run": context_recall_run,
        "referenced_case_count": len(with_ref),
        "case_count": len(cases),
        "valid_score_count": valid,
        "expected_score_count": expected,
        "failed_score_count": max(0, expected - valid),
        "valid_case_count": valid_case_count,
        "score_coverage": round(valid / expected, 4) if expected else 0.0,
        "status": status,
    }
    if evaluate_fn is None and build_metrics_fn is None:
        result["evaluation_method"] = _evaluation_method(metric_names, rf_metrics, reuse)
    return result


def _evaluation_method(metric_names, reference_free_metrics, reuse):
    from importlib.metadata import version

    config = {"metrics": metric_names}
    if reuse is None:
        return {
            "ragas_sdk_version": version("ragas"),
            "protocol_id": "ragas-sdk-default",
            "protocol_version": 1,
            "scope": "ordinary",
            "response_relevancy_generated_questions": dict(reference_free_metrics)[METRIC_RESPONSE_RELEVANCY].strictness,
            "settled_response_reuse": False,
            "metric_config": config,
        }
    return {
        "ragas_sdk_version": _GOVERNED_RAGAS_VERSION,
        "protocol_id": _GOVERNED_SCORING_PROTOCOL,
        "protocol_version": _GOVERNED_SCORING_VERSION,
        "scope": "governed_07b",
        "response_relevancy_generated_questions": _GOVERNED_QUESTION_COUNT,
        "settled_response_reuse": True,
        "metric_config": {**config, "parser_repair_requests": 0,
                          "sdk_attempts": 1, "max_workers": 1, "batch_size": 1},
        "reuse_hits": reuse.hits,
    }


def _active_07b():
    from src.llm.budget.governor import active_governor

    governor = active_governor()
    return governor if governor is not None and governor.governed_07b else None


@contextmanager
def _sdk_activity(*, governed):
    """The governed CLI owns its SDK process and may drain its global analytics worker."""
    global _ordinary_sdk_runs, _governed_sdk_running
    with _SDK_ACTIVITY_LOCK:
        if _governed_sdk_running or (governed and _ordinary_sdk_runs):
            raise RagasNotConfigured("The governed evaluator requires a dedicated SDK worker.")
        if governed:
            _governed_sdk_running = True
        else:
            _ordinary_sdk_runs += 1
    try:
        yield
    finally:
        with _SDK_ACTIVITY_LOCK:
            if governed:
                _governed_sdk_running = False
            else:
                _ordinary_sdk_runs -= 1


def _unique_response_object(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError("Duplicate response key.")
    if ("prompt_tokens" in obj and "input_tokens" in obj and obj["prompt_tokens"] != obj["input_tokens"]
            or "completion_tokens" in obj and "output_tokens" in obj
            and obj["completion_tokens"] != obj["output_tokens"]):
        raise ValueError("Conflicting usage totals.")
    return obj


def _reject_json_constant(_):
    raise ValueError("Invalid JSON number.")


def _ordered_embedding_entries(body, payload):
    entries = body.get("data")
    inputs = payload["input"]
    if body.get("model") != payload["model"] or not isinstance(entries, list) or len(entries) != len(inputs):
        raise ValueError("Invalid embedding response identity or count.")
    by_index = {}
    dimensions = payload.get("dimensions")
    for entry in entries:
        index = entry.get("index") if isinstance(entry, dict) else None
        if type(index) is not int or not 0 <= index < len(inputs) or index in by_index:
            raise ValueError("Invalid embedding response index.")
        vector = entry.get("embedding")
        if isinstance(vector, str):
            raw = base64.b64decode(vector, validate=True)
            if len(raw) % 4:
                raise ValueError("Incomplete binary embedding vector.")
            size = len(raw) // 4
            finite = all(math.isfinite(value) for (value,) in struct.iter_unpack("<f", raw))
        elif isinstance(vector, list):
            size = len(vector)
            finite = all(map(is_valid_score, vector))
        else:
            raise ValueError("Invalid embedding vector structure.")
        if not size or not finite or dimensions is not None and size != dimensions:
            raise ValueError("Invalid embedding vector values or dimensions.")
        dimensions = size
        by_index[index] = entry
    return [by_index[index] for index in range(len(inputs))]


class _EvaluationReuse:
    """Own validated SDK outputs for one governed run and its bound approval/ledger."""

    def __init__(self, governor):
        self.governor = governor
        self.config = governor.config
        self.ledger = governor.ledger
        self.policy_hash = governor.config.raw_hash
        self.budget_class = governor.budget_class
        self.results = {}
        self.pending = False
        self.hits = {"chat": 0, "embeddings": 0}

    def key(self, namespace, client, endpoint, payload):
        from src.llm.budget.governor import _request_fingerprint

        url = str(client.base_url.join(endpoint))
        return (namespace, _GOVERNED_RAGAS_VERSION, _GOVERNED_SCORING_PROTOCOL,
                _GOVERNED_SCORING_VERSION, _request_fingerprint("POST", url, payload))

    def _check_reuse_scope(self):
        from src.llm.budget.errors import BudgetError

        governor = self.governor
        if (_active_07b() is not governor or governor.config is not self.config
                or governor.ledger is not self.ledger or governor.budget_class != self.budget_class):
            raise BudgetError("evaluation_scope_changed", "The governed evaluation binding changed.")
        governor._open_or_refuse()
        status = governor.status()
        if status.get("killed") or status.get("state") == "killed":
            raise BudgetError("kill_switch", "The AI budget kill switch is engaged; no evaluator result is reused.")
        if not status.get("integrity", {}).get("consistent"):
            raise BudgetError("ledger_error", "07B could not verify result settlement.")
        states = status["calls_by_state"]
        if states.get("unknown") or states.get("reserved"):
            raise BudgetError("reconciliation_required", "07B has outstanding accounting exposure.")

    def _matches_receipt(self, receipt, key, kind):
        from src.llm.budget.ledger import _SettlementReceipt

        return (isinstance(receipt, _SettlementReceipt) and receipt.outcome == "settled"
                and type(receipt.entry_id) is int and receipt.entry_id > 0
                and receipt.endpoint == receipt.binding.endpoint == kind
                and receipt.entry_id == receipt.binding.entry_id
                and receipt.binding.ledger_identity is self.ledger._receipt_identity
                and receipt.binding.policy_hash == self.policy_hash
                and receipt.binding.fingerprint == key[-1]
                and receipt.binding.operation == ("ragas" if kind == "chat" else "evaluator_embedding"))

    @contextmanager
    def request(self, key, http_client, kind):
        """Only publish a hit after exact wire identity, durable settlement and SDK validation."""
        from src.llm.budget.errors import BudgetError
        from src.llm.budget.governor import _request_fingerprint

        if self.pending:
            raise BudgetError("evaluation_request_pending", "A governed evaluator request is pending.")
        if http_client not in self.governor._prototype_clients or any(http_client.event_hooks.values()):
            raise BudgetError("transport_not_qualified", "The governed evaluation requires its qualified receiver.")
        self._check_reuse_scope()
        bound_key = http_client, key
        if bound_key in self.results:
            receipt, cached = self.results[bound_key]
            if not self._matches_receipt(receipt, key, kind):
                raise BudgetError("evaluation_result_unverified", "07B could not verify the cached settlement.")
            self.hits[kind] += 1
            yield deepcopy(cached), None
            return
        if len(self.results) >= _MAX_REUSABLE_RESULTS:
            raise BudgetError("evaluation_reuse_limit", "The governed evaluator reuse limit was reached.")

        self.pending = True
        seen = []
        result = []

        def observe(response):
            request = response.request
            payload = json.loads(request.content)
            if response.status_code == 200:
                try:
                    body = json.loads(response.content, object_pairs_hook=_unique_response_object,
                                      parse_constant=_reject_json_constant)
                    if kind == "embeddings":
                        ordered = _ordered_embedding_entries(body, payload)
                        if ordered != body["data"]:
                            # The pinned SDK reads .json() and then discards indices.
                            # Expose the ordered view while retaining raw response bytes.
                            body["data"] = ordered
                            response.json = lambda **_: deepcopy(body)
                except (ValueError, OverflowError, RecursionError):
                    raise BudgetError("evaluation_result_unverified", "07B received an invalid evaluator response.") from None
            seen.append((response, _request_fingerprint(request.method, str(request.url), payload)))

        async def observe_async(response):
            observe(response)

        hooks = http_client.event_hooks["response"]
        observer = observe_async if kind == "chat" else observe
        hooks.insert(0, observer)
        try:
            with self.governor._capture_07b_settlement(http_client) as settlements:
                yield None, result.append
                self._check_reuse_scope()
                if len(seen) != 1 or len(settlements) != 1 or len(result) != 1:
                    raise BudgetError("evaluation_result_unverified", "07B could not attest the evaluator response.")
                observed, wire_fingerprint = seen[0]
                settled_response, receipt = settlements[0]
                if (observed is not settled_response or observed.status_code != 200 or wire_fingerprint != key[-1]
                        or not self._matches_receipt(receipt, key, kind)):
                    raise BudgetError("evaluation_result_unverified", "07B could not match the response to its settlement.")
                self.results[bound_key] = receipt, deepcopy(result[0])
        finally:
            hooks.remove(observer)
            self.pending = False


def _validate_prompt_completion(prompt, response, n, data):
    from ragas.exceptions import RagasOutputParserException
    from ragas.metrics._answer_relevance import ResponseRelevanceOutput
    from ragas.metrics._context_precision import Verification
    from ragas.metrics._context_recall import ContextRecallClassifications
    from ragas.metrics._faithfulness import NLIStatementOutput

    try:
        completions, = response.generations
        if len(completions) != n:
            raise ValueError("Unexpected completion count.")
        for completion in completions:
            text = completion.text.strip()
            if text.startswith("```json\n") and text.endswith("\n```"):
                text = text.removeprefix("```json\n").removesuffix("\n```")
            value = json.loads(text, object_pairs_hook=_unique_response_object,
                               parse_constant=_reject_json_constant)
            parsed = prompt.output_model.model_validate(value, strict=True)
            if isinstance(parsed, ResponseRelevanceOutput) and (
                    not parsed.question.strip() or parsed.noncommittal not in (0, 1)):
                raise ValueError("Invalid Response Relevancy output.")
            if isinstance(parsed, Verification) and parsed.verdict not in (0, 1):
                raise ValueError("Invalid Context Precision verdict.")
            if isinstance(parsed, ContextRecallClassifications) and any(
                    item.attributed not in (0, 1) for item in parsed.classifications):
                raise ValueError("Invalid Context Recall attribution.")
            if isinstance(parsed, NLIStatementOutput) and (
                    any(item.verdict not in (0, 1) for item in parsed.statements)
                    or Counter(item.statement for item in parsed.statements) != Counter(data.statements)):
                raise ValueError("Invalid or misaligned Faithfulness verdicts.")
    except (ValueError, TypeError, RecursionError):
        # The SDK parser can locally repair incomplete JSON. A partial or
        # coerced response cannot qualify as reusable governed evidence.
        raise RagasOutputParserException() from None


def _without_output_repair(prompt, reuse, namespace):
    guarded = copy(prompt)

    async def generate_multiple(llm, data, n=1, temperature=None, stop=None,
                                callbacks=None, retries_left=0):
        import asyncio

        # Capture the rendered prompt supplied by RAGAS itself. Keep the
        # request pending until its original validator has accepted the output.
        task = asyncio.current_task()
        with ExitStack() as stack:
            publish = None
            candidate = None

            async def generate(prompt_value, *, n, temperature, stop, callbacks):
                nonlocal publish, candidate
                chat = llm.langchain_llm
                payload = chat._get_request_payload(
                    prompt_value, stop=stop, n=n,
                    temperature=llm.get_temperature(n) if temperature is None else temperature,
                )
                key = reuse.key(namespace, chat.root_async_client, "chat/completions", payload)
                cached, publish = stack.enter_context(reuse.request(key, chat.http_async_client, "chat"))
                if publish is None:
                    return cached
                candidate = await llm.generate(
                    prompt_value, n=n, temperature=temperature, stop=stop, callbacks=callbacks,
                )
                _validate_prompt_completion(prompt, candidate, n, data)
                return candidate

            guarded_llm = copy(llm)
            guarded_llm.generate = generate
            # Parser repair can send a request outside the SDK retry limit.
            output = await prompt.generate_multiple(
                guarded_llm, data, n=n, temperature=temperature, stop=stop,
                callbacks=callbacks, retries_left=0,
            )
            if task.cancelling():
                raise asyncio.CancelledError
            if publish is not None:
                publish(candidate)
            return output

    guarded.generate_multiple = generate_multiple
    return guarded


def _governed_evaluate(evaluate, dataset, metrics, llm, embeddings, *, timeout, reuse):
    import asyncio
    from langsmith import tracing_context
    from ragas._analytics import _analytics_batcher, do_not_track
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import ResponseRelevancy
    from ragas.run_config import RunConfig

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RagasNotConfigured("The governed evaluator requires its own synchronous worker.")

    class RelevancyEmbeddings(LangchainEmbeddingsWrapper):
        # Governed relevancy generates one question. Both SDK embedding paths
        # use the same single-input request shape and share only that shape.
        def embed_query(self, text):
            return self.embed_documents([text])[0]

        def embed_documents(self, texts):
            model = self.embeddings
            vectors = []
            for text in texts:
                payload = {"input": [text], "encoding_format": "base64", **model._invocation_params}
                key = reuse.key(("ragas", "relevancy_embeddings"), model.client._client, "embeddings", payload)
                with reuse.request(key, model.http_client, "embeddings") as (cached, publish):
                    if publish is not None:
                        vector, = super().embed_documents([text])
                        if not isinstance(vector, list) or not vector or not all(map(is_valid_score, vector)):
                            raise RagasNotConfigured("The governed evaluator returned an invalid vector.")
                        publish(vector)
                    else:
                        vector = cached
                vectors.append(vector)
            return vectors

    governed_metrics = []
    for metric in metrics:
        guarded = copy(metric)
        guarded.set_prompts(**{
            name: _without_output_repair(prompt, reuse, ("ragas", metric.name, name))
            for name, prompt in guarded.get_prompts().items()
        })
        if isinstance(guarded, ResponseRelevancy):
            # Three identical prompt submissions conflict with 07B's durable replay guard.
            guarded.strictness = _GOVERNED_QUESTION_COUNT
        governed_metrics.append(guarded)

    # RAGAS 0.2.15 starts a process-global analytics daemon at import. The
    # governed CLI owns this evaluation process. Disable emission before
    # draining the daemon and ensure it cannot outlive the governed run.
    previous_tracking = os.environ.get("RAGAS_DO_NOT_TRACK")
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    do_not_track.cache_clear()
    try:
        _analytics_batcher.shutdown()
        _analytics_batcher._flush_thread.join(timeout=2)
        if _analytics_batcher._flush_thread.is_alive():
            raise RagasNotConfigured("The governed RAGAS analytics worker did not stop.")
        with asyncio.Runner() as worker, tracing_context(enabled=False):
            # The SDK's nest_asyncio uses the installed loop. Runner closes it
            # and drains pending work even when scoring raises.
            worker.get_loop()
            run_config = RunConfig(max_workers=1, max_retries=1, timeout=timeout)
            return evaluate(
                dataset=dataset, metrics=governed_metrics, llm=llm,
                embeddings=RelevancyEmbeddings(embeddings.embeddings, run_config), run_config=run_config,
                raise_exceptions=True, batch_size=1, show_progress=False,
            )
    finally:
        _analytics_batcher.shutdown()
        if previous_tracking is None:
            os.environ.pop("RAGAS_DO_NOT_TRACK", None)
        else:
            os.environ["RAGAS_DO_NOT_TRACK"] = previous_tracking
        do_not_track.cache_clear()


def _default_evaluate(samples, metrics, llm, embeddings, *, reuse=None):
    """Call ragas.evaluate and return {case_index: {metric_name: score}}."""
    governor = _active_07b()
    if reuse is not None and governor is not reuse.governor:
        raise RagasNotConfigured("The governed evaluation binding changed.")
    if governor is not None:
        from importlib.metadata import version

        # Analytics cleanup uses SDK internals verified with this version.
        if version("ragas") != _GOVERNED_RAGAS_VERSION:
            raise RagasNotConfigured("The governed evaluator requires the qualified RAGAS version.")

    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset

    dataset = EvaluationDataset(samples=samples)
    selected = [metric for _, metric in metrics]
    with _sdk_activity(governed=governor is not None):
        if governor is None:
            result = evaluate(dataset=dataset, metrics=selected, llm=llm, embeddings=embeddings)
        else:
            result = _governed_evaluate(
                evaluate, dataset, selected, llm, embeddings,
                timeout=governor.config.limits.request_timeout_s,
                reuse=reuse or _EvaluationReuse(governor),
            )
    frame = result.to_pandas()
    out: dict[int, dict] = {}
    for idx in range(len(frame)):
        row = frame.iloc[idx]
        scores = {}
        for name, metric in metrics:
            col = getattr(metric, "name", name)
            if col in frame.columns:
                scores[name] = float(row[col])
        out[idx] = scores
    return out


def _merge_scores(per_case, cases, scores_by_index, metric_names) -> None:
    for idx, case in enumerate(cases):
        scores = scores_by_index.get(idx, {})
        for name in metric_names:
            # Only store finite scores; a failed evaluator job (NaN/inf/None)
            # stays absent rather than becoming a misleading numeric value.
            if is_valid_score(scores.get(name)):
                per_case[case.case_id][name] = round(float(scores[name]), 4)


def _aggregate(rows, metric_names) -> dict:
    agg: dict[str, float | None] = {}
    for name in metric_names:
        values = [float(r[name]) for r in rows if is_valid_score(r.get(name))]
        agg[name] = round(sum(values) / len(values), 4) if values else None
    return agg
