"""Shared orchestration for optional live RAGAS runs (CLI + Evaluation UI).

One place owns: loading the PUBLIC cases, filtering, building Career Intelligence,
generating answers, converting to plain eval cases, running RAGAS, validating the
result (COMPLETE / PARTIAL / FAILED via the finite-score guard), and persisting
artifacts to a unique timestamp directory. Both ``scripts/eval_ragas.py`` and the
Streamlit Evaluation page call :func:`run_live_ragas` — no duplicated logic, and
RAGAS never runs unless a caller explicitly asks.

Security: only ``evaluations/ragas/cases.json`` is evaluated (public benchmark).
No private candidate/JD/transcript/company data is ever read. API keys are never
returned, logged, or written.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from src.copilot.evaluation import ragas_adapter as ra

__all__ = [
    "CASES_PATH",
    "RUNS_DIR",
    "PRESETS",
    "RagasRunResult",
    "check_configuration",
    "run_live_ragas",
    "write_artifacts",
    "summary_markdown",
]

CASES_PATH = "evaluations/ragas/cases.json"
RUNS_DIR = Path("evaluations/ragas/runs")
_Q01_CASE_MARKETS = {
    "role_us_data_analyst": "US",
    "role_uk_operations_manager": "UK",
}
_Q01_SOURCES = {"US": "q01-synthetic-us", "UK": "q01-synthetic-uk"}
_Q01_UNAPPROVED_SOURCE = "q01-synthetic-unapproved"
_Q01_METRICS = [ra.METRIC_FAITHFULNESS, ra.METRIC_RESPONSE_RELEVANCY,
                ra.METRIC_CONTEXT_PRECISION, ra.METRIC_CONTEXT_RECALL]
_Q01_FAILURE_MESSAGES = {
    "q01_offline_unavailable": "Q01 requires a network-denied worker.",
    "q01_invalid_options": "Q01 requires fixed synthetic fixtures and no overrides.",
    "q01_invalid_selection": "Q01 requires the two approved case IDs in order.",
    "q01_invalid_benchmark": "Q01 requires one benchmark row for each approved case.",
    "q01_missing_reference": "Both Q01 cases require a nonempty benchmark reference.",
    "q01_invalid_market": "Both Q01 cases require their approved explicit market.",
    "q01_unverified_market": "Q01 requires an effective source-approval market matching the case.",
    "q01_invalid_context": "Q01 retrieved context or provenance is malformed.",
    "q01_no_context": "Q01 requires a nonempty retrieved context for each case.",
    "q01_unverified_approval": "Q01 requires the expected synthetic source approval and refusals.",
    "no_valid_scores": "Synthetic evaluator returned no valid scores.",
}

# The ONLY case-count choices exposed in the UI (no free-form counts).
# label -> limit (None = full benchmark).
PRESETS: dict[str, int | None] = {
    "Smoke test — 2 cases": 2,
    "Baseline — 10 cases": 10,
    "Full benchmark — 35 cases": None,
}


@dataclass
class RagasRunResult:
    """Plain, safe result of a live RAGAS run (never contains keys/prompts)."""

    status: str  # COMPLETE | PARTIAL | FAILED
    case_count: int = 0
    metrics: dict = field(default_factory=dict)
    metric_names: list = field(default_factory=list)
    per_case: list = field(default_factory=list)
    valid_score_count: int = 0
    expected_score_count: int = 0
    failed_score_count: int = 0
    score_coverage: float = 0.0
    referenced_case_count: int = 0
    context_recall_run: bool = False
    output_directory: str | None = None
    error_category: str | None = None
    safe_message: str | None = None
    q01_diagnostics: list[dict] = field(default_factory=list)

    @property
    def is_failed(self) -> bool:
        return self.status == ra.STATUS_FAILED

    @property
    def persisted(self) -> bool:
        return self.output_directory is not None


# --- Safe configuration inspection ------------------------------------------


def check_configuration(*, allow_chat_fallback: bool = False) -> dict:
    """Return a SAFE view of RAGAS run readiness — never any secret value.

    Reports package availability, whether the evaluator credential and the Career
    Intelligence chat credential are configured, the (non-secret) evaluator model
    / embedding / base-URL disposition, the names of any missing env vars, and any
    configuration warnings (e.g. an OpenRouter-looking key with a default base URL).
    """
    import os

    ragas_ready = ra.ragas_available()
    evaluator = ra.evaluator_config_from_env(allow_chat_fallback=allow_chat_fallback)

    try:
        from src.copilot.config import load_config
        career_configured = bool(load_config().is_configured)
    except Exception:  # noqa: BLE001 - config must never crash the page
        career_configured = False

    missing: list[str] = []
    warnings: list[str] = []
    if not ragas_ready:
        missing.append("ragas package (pip install -e \".[evaluation]\")")
    if evaluator is None:
        missing.append("RAGAS_EVAL_API_KEY")
    if not career_configured:
        missing.append("Career Intelligence chat credential (e.g. COPILOT_API_KEY)")

    base_url_state = "default (OpenAI)"
    evaluator_model = None
    embedding_model = None
    if evaluator is not None:
        base_url_state = "configured" if evaluator.base_url else "default (OpenAI)"
        evaluator_model = evaluator.model
        embedding_model = evaluator.embedding_model
        # Safe heuristic (never exposes the key): an OpenRouter-style key sent to
        # the default OpenAI endpoint is the known all-NaN misconfiguration.
        looks_openrouter = (evaluator.api_key or "").startswith("sk-or-")
        if looks_openrouter and not evaluator.base_url:
            warnings.append(
                "The evaluator key looks like an OpenRouter key but no base URL is "
                "set. Set RAGAS_EVAL_BASE_URL=https://openrouter.ai/api/v1, or the "
                "evaluator will fail to authenticate.")

    return {
        "ragas_ready": ragas_ready,
        "evaluator_configured": evaluator is not None,
        "career_configured": career_configured,
        "base_url_state": base_url_state,
        "evaluator_model": evaluator_model,
        "embedding_model": embedding_model,
        "missing": missing,
        "warnings": warnings,
        "can_run": ragas_ready and evaluator is not None and career_configured,
        # RAGAS_EVAL_BASE_URL presence (name only; never the value).
        "base_url_env_set": bool(os.environ.get("RAGAS_EVAL_BASE_URL")),
    }


# --- Live run ----------------------------------------------------------------


def _load_filtered_cases(cases_path: str, category: str | None, limit: int | None,
                         case_ids: list[str] | None = None):
    cases = ra.load_cases(cases_path)
    if case_ids:
        # Preserve the fixed subset's order for stable, comparable paid runs (§24).
        by_id = {c.case_id: c for c in cases}
        cases = [by_id[cid] for cid in case_ids if cid in by_id]
    if category:
        cases = [c for c in cases if c.metadata.get("category") == category]
    if limit:
        cases = cases[:limit]
    return cases


def _default_service(config):
    from src.copilot.embeddings import build_embedder
    from src.copilot.knowledge.retrieval import build_default_coordinator
    from src.copilot.retrieval import build_retriever
    from src.copilot.service import CareerIntelligenceService
    from src.copilot.vectorstore import build_vector_store

    store = build_vector_store(config, embedder=build_embedder(config))
    retriever = build_retriever(config, mode=config.retrieval_mode, store=store)
    coordinator = build_default_coordinator(config)
    return CareerIntelligenceService(
        config=config, retriever=retriever, knowledge_coordinator=coordinator)


def _q01_failure(category: str, diagnostics=None) -> RagasRunResult:
    return RagasRunResult(
        status=ra.STATUS_FAILED, error_category=category, safe_message=_Q01_FAILURE_MESSAGES[category],
        q01_diagnostics=diagnostics if diagnostics is not None else [],
    )


def _q01_known_source_ids(values) -> list[str]:
    if type(values) is not list:
        return []
    known = (*_Q01_SOURCES.values(), _Q01_UNAPPROVED_SOURCE)
    return list(dict.fromkeys(value for value in values if type(value) is str and value in known))


def _q01_approved_context(diagnostic: dict) -> bool:
    market = diagnostic["intended_market"]
    return (
        diagnostic["source_approval_market"] == market
        and diagnostic["approval_enforced"] is True
        and diagnostic["retrieved_context_count"] == 1
        and diagnostic["source_ids"] == [_Q01_SOURCES[market]]
        and diagnostic["dropped_source_ids"] == [
            *(source for key, source in _Q01_SOURCES.items() if key != market),
            _Q01_UNAPPROVED_SOURCE,
        ]
    )


def _q01_valid_diagnostics(diagnostics: list) -> bool:
    from src.copilot.knowledge.countries import NAMED_COUNTRY_CODES
    from src.knowledge_approval import MARKETS

    if len(diagnostics) > len(_Q01_CASE_MARKETS):
        return False
    for item, (case_id, market) in zip(diagnostics, _Q01_CASE_MARKETS.items()):
        if (
            type(item) is not dict or item.keys() != {
                "case_id", "intended_market", "detected_country", "source_approval_market",
                "retrieved_context_count", "source_ids", "dropped_source_ids", "approval_enforced",
            }
            or item["case_id"] != case_id or item["intended_market"] != market
            or item["detected_country"] not in (None, *NAMED_COUNTRY_CODES)
            or item["source_approval_market"] not in (None, *MARKETS)
            or type(item["approval_enforced"]) is not bool
            or type(item["retrieved_context_count"]) is not int
            or not 0 <= item["retrieved_context_count"] <= ra._MAX_CONTEXTS
            or _q01_known_source_ids(item["source_ids"]) != item["source_ids"]
            or _q01_known_source_ids(item["dropped_source_ids"]) != item["dropped_source_ids"]
            or (item["retrieved_context_count"] == 0 and item["source_ids"])
        ):
            return False
    return True


def _q01_valid_refusal(error: str, diagnostics: list) -> bool:
    if error in ("q01_offline_unavailable", "q01_invalid_benchmark",
                 "q01_missing_reference", "q01_invalid_market"):
        return not diagnostics
    if not diagnostics or not all(_q01_approved_context(item) for item in diagnostics[:-1]):
        return False
    last = diagnostics[-1]
    matched = last["intended_market"] == last["source_approval_market"]
    count = last["retrieved_context_count"]
    if error == "q01_unverified_market":
        return not matched and count == 0
    if error in ("q01_invalid_context", "q01_no_context"):
        return matched and count == 0
    return error == "q01_unverified_approval" and matched and count > 0


def _q01_valid_scores(reply: dict) -> bool:
    rows = reply["per_case"]
    diagnostics = reply["q01_diagnostics"]
    if (
        reply["case_count"] != 2 or reply["referenced_case_count"] != 2
        or reply["context_recall_run"] is not True or len(rows) != 2 or len(diagnostics) != 2
        or not all(_q01_approved_context(item) for item in diagnostics)
        or reply["metric_names"] != _Q01_METRICS or reply["metrics"].keys() != set(_Q01_METRICS)
        or any(value is not None and not ra.is_valid_score(value) for value in reply["metrics"].values())
    ):
        return False
    for row, case_id in zip(rows, _Q01_CASE_MARKETS, strict=True):
        if (
            type(row) is not dict or row.get("case_id") != case_id
            or row.get("category") != "role_responsibilities"
            or any(name not in _Q01_METRICS or not ra.is_valid_score(value)
                   for name, value in row.items() if name not in ("case_id", "category"))
        ):
            return False
    expected = 8
    valid = sum(name in row for row in rows for name in _Q01_METRICS)
    status = ra.STATUS_FAILED if valid == 0 else (ra.STATUS_COMPLETE if valid == expected else ra.STATUS_PARTIAL)
    error = "no_valid_scores" if valid == 0 else None
    return (
        reply["status"] == status and reply["error_category"] == error
        and reply["safe_message"] == _Q01_FAILURE_MESSAGES.get(error)
        and reply["expected_score_count"] == expected and reply["valid_score_count"] == valid
        and reply["failed_score_count"] == expected - valid
        and reply["score_coverage"] == round(valid / expected, 4)
        and reply["metrics"] == ra._aggregate(rows, _Q01_METRICS)
    )


def _q01_json_object(pairs) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate Q01 response field.")
    return result


def _decode_q01_response(payload: bytes) -> RagasRunResult:
    failure = _q01_failure("q01_offline_unavailable")
    if len(payload) > 8192:
        return failure
    reply = json.loads(payload, object_pairs_hook=_q01_json_object)
    if type(reply) is not dict or reply.keys() != {item.name for item in fields(RagasRunResult)}:
        return failure
    diagnostics = reply["q01_diagnostics"]
    if (
        reply["status"] not in (ra.STATUS_COMPLETE, ra.STATUS_PARTIAL, ra.STATUS_FAILED)
        or reply["output_directory"] is not None
        or type(reply["context_recall_run"]) is not bool
        or type(reply["metrics"]) is not dict
        or any(type(reply[key]) is not list for key in ("metric_names", "per_case", "q01_diagnostics"))
        or any(type(reply[key]) is not int or reply[key] < 0 for key in (
            "case_count", "referenced_case_count", "expected_score_count", "valid_score_count", "failed_score_count",
        ))
        or not ra.is_valid_score(reply["score_coverage"])
        or not _q01_valid_diagnostics(diagnostics)
    ):
        return failure
    if reply["case_count"]:
        return RagasRunResult(**reply) if _q01_valid_scores(reply) else failure
    error = reply["error_category"]
    if (
        type(error) is str
        and _q01_valid_refusal(error, diagnostics)
        and reply == asdict(_q01_failure(error, diagnostics))
    ):
        return RagasRunResult(**reply)
    return failure


def _q01_worker_profile(scratch: str) -> str:
    return (
        "(version 1)(allow default)(deny network*)(deny file-write*)"
        f"(allow file-write* (subpath {json.dumps(scratch)}))"
    )


def _launch_q01() -> RagasRunResult:
    import subprocess
    import sys
    from tempfile import TemporaryDirectory

    failure = _q01_failure("q01_offline_unavailable")
    if sys.platform != "darwin":
        return failure

    source = Path(__file__).resolve().parents[3]
    bootstrap = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from src.copilot.evaluation.ragas_runner import _q01_worker_output; "
        "_q01_worker_output()"
    )
    try:
        with TemporaryDirectory(prefix="ask4mo-q01-") as directory:
            scratch = str(Path(directory).resolve())
            worker = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", _q01_worker_profile(scratch), sys.executable,
                 "-I", "-B", "-c", bootstrap, str(source)],
                cwd=scratch,
                env={"HOME": scratch, "TMPDIR": scratch, "XDG_CACHE_HOME": scratch,
                     "PATH": "/usr/bin:/bin", "PYTHON_DOTENV_DISABLED": "1",
                     "ASK4MO_PROVIDER_MODE": "offline"},
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, check=True, timeout=30,
            )
        return _decode_q01_response(worker.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, OverflowError, RecursionError):
        return failure


def _q01_network_denied() -> bool:
    import errno
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            return probe.connect_ex(("127.0.0.1", 1)) in (errno.EPERM, errno.EACCES)
    except PermissionError:
        return True
    except OSError:
        return False


def _q01_worker_output() -> None:
    print(json.dumps(asdict(_run_q01_worker()), allow_nan=False))


def _q01_fixture_answer(question: str, *, market: str):
    from types import SimpleNamespace

    from src import knowledge_approval as ka
    from src.copilot.knowledge import approval_filter
    from src.copilot.knowledge.router import detect_country
    from src.copilot.models import KnowledgeEvidence
    from src.copilot.service import PipelineTrace

    # An already-resolved, in-memory fixture register. Production approvals
    # and the test-only global register override are outside this worker.
    register = ka.Register(mode=ka.MODE_ENFORCED, records=tuple(
        ka.RecordStatus(source, approved_market, enabled=True)
        for approved_market, source in _Q01_SOURCES.items()
    ))
    evidence = [
        KnowledgeEvidence(evidence_id=source, source_id=source,
                          text=f"Synthetic Q01 evidence from {source}.")
        for source in (*_Q01_SOURCES.values(), _Q01_UNAPPROVED_SOURCE)
    ]
    detected = detect_country(question)
    retrieved, filtered, approval = approval_filter.apply(
        [], evidence, selected_market=market, detected_country=detected, register=register,
    )
    return SimpleNamespace(
        trace=PipelineTrace(detected_country=detected, source_approval_market=approval.market),
        approval=approval,
        response=SimpleNamespace(answer="Synthetic Q01 answer.", evidence=filtered, retrieved=retrieved),
    )


def _q01_fixture_score(cases):
    def metrics(*, reference_free_only):
        names = _Q01_METRICS[:-1] if reference_free_only else _Q01_METRICS
        return [(name, None) for name in names]

    def evaluate(samples, selected_metrics, _llm, _embeddings):
        # Fixed values exercise accounting only. They are not model-quality scores.
        return {index: {name: 0.0 for name, _ in selected_metrics}
                for index in range(len(samples))}

    return ra.run_ragas(
        cases, config=object(), evaluate_fn=evaluate, build_metrics_fn=metrics,
        to_sample_fn=lambda case, **_: case,
    )


def _run_q01_worker() -> RagasRunResult:
    if not _q01_network_denied():
        return _q01_failure("q01_offline_unavailable")

    from src.copilot.knowledge.countries import NAMED_COUNTRY_CODES
    from src.knowledge_approval import MARKETS, normalise_market

    benchmark_path = Path(__file__).resolve().parents[3] / CASES_PATH
    selected = [case for case in ra.load_cases(str(benchmark_path))
                if case.case_id in _Q01_CASE_MARKETS]
    by_id = {case.case_id: case for case in selected}
    if len(selected) != len(_Q01_CASE_MARKETS) or by_id.keys() != _Q01_CASE_MARKETS.keys():
        return _q01_failure("q01_invalid_benchmark")
    cases = [by_id[case_id] for case_id in _Q01_CASE_MARKETS]
    if not all(case.has_reference for case in cases):
        return _q01_failure("q01_missing_reference")
    case_markets = {case.case_id: normalise_market(case.metadata.get("geography")) for case in cases}
    if case_markets != _Q01_CASE_MARKETS:
        return _q01_failure("q01_invalid_market")

    eval_cases = []
    diagnostics = []
    for case in cases:
        market = case_markets[case.case_id]
        result = _q01_fixture_answer(case.question, market=market)
        trace = getattr(result, "trace", None)
        approval = getattr(result, "approval", None)
        detected = getattr(trace, "detected_country", None)
        observed = getattr(approval, "market", None)
        effective_market = observed if type(observed) is str and observed in MARKETS else None
        dropped = getattr(approval, "dropped_sources", None)
        diagnostic = {
            "case_id": case.case_id,
            "intended_market": market,
            "detected_country": detected if type(detected) is str and detected in NAMED_COUNTRY_CODES else None,
            "source_approval_market": effective_market,
            "retrieved_context_count": 0,
            "source_ids": [],
            "dropped_source_ids": _q01_known_source_ids(dropped),
            "approval_enforced": getattr(approval, "enforced", None) is True,
        }
        diagnostics.append(diagnostic)
        if effective_market != market:
            return _q01_failure("q01_unverified_market", diagnostics)
        try:
            adapted = ra.case_from_service_result(
                case.case_id, case.question, result, category=case.metadata.get("category"),
                reference=case.reference, strict_context_text=True,
            )
        except ra.InvalidContextText:
            return _q01_failure("q01_invalid_context", diagnostics)
        if not adapted.retrieved_contexts:
            return _q01_failure("q01_no_context", diagnostics)
        diagnostic["retrieved_context_count"] = len(adapted.retrieved_contexts)
        diagnostic["source_ids"] = _q01_known_source_ids(adapted.source_ids)
        if (
            not _q01_approved_context(diagnostic)
            or diagnostic["source_ids"] != adapted.source_ids
            or len(diagnostic["dropped_source_ids"]) != len(dropped)
            or approval.dropped_count != len(dropped)
            or approval.labelled_count != 0
        ):
            return _q01_failure("q01_unverified_approval", diagnostics)
        eval_cases.append(adapted)

    run = _q01_fixture_score(eval_cases)
    base = _scored_result(run)
    base.q01_diagnostics = diagnostics
    if not ra.has_usable_scores(run):
        base.error_category = "no_valid_scores"
        base.safe_message = _Q01_FAILURE_MESSAGES["no_valid_scores"]
    return base


def _scored_result(run: dict) -> RagasRunResult:
    return RagasRunResult(
        status=run["status"],
        case_count=run["case_count"],
        metrics=run["metrics"],
        metric_names=run["metric_names"],
        per_case=run["per_case"],
        valid_score_count=run["valid_score_count"],
        expected_score_count=run["expected_score_count"],
        failed_score_count=run["failed_score_count"],
        score_coverage=run["score_coverage"],
        referenced_case_count=run["referenced_case_count"],
        context_recall_run=run["context_recall_run"],
    )


def run_live_ragas(
    *,
    config,
    evaluator_config,
    limit: int | None = None,
    category: str | None = None,
    case_ids: list[str] | None = None,
    persist: bool = True,
    cases_path: str = CASES_PATH,
    runs_dir: Path | str = RUNS_DIR,
    output_dir: str | None = None,
    service=None,
    service_factory=None,
    run_ragas_fn=None,
    timestamp: str | None = None,
    q01_diagnostic: bool = False,
) -> RagasRunResult:
    """Generate answers over the public cases and score them with RAGAS.

    Returns a plain :class:`RagasRunResult`. A FAILED run (no valid evaluator
    scores) is NEVER persisted — no directory or artifacts are created. The
    ``*_fn`` / ``service`` / ``timestamp`` hooks are injection points for offline
    tests; production uses the real defaults.

    Q01 runs fixed synthetic fixtures in a network-denied worker, with no
    caller-supplied dependencies, runtime configuration or persistence.
    """
    if q01_diagnostic:
        if (
            persist is not False or output_dir is not None
            or config is not None or evaluator_config is not None
            or service is not None or service_factory is not None or run_ragas_fn is not None
            or category is not None or limit is not None or cases_path != CASES_PATH
            or runs_dir != RUNS_DIR or timestamp is not None
        ):
            return _q01_failure("q01_invalid_options")
        if ((type(case_ids) is not list and type(case_ids) is not tuple)
                or len(case_ids) != len(_Q01_CASE_MARKETS)
                or any(type(case_id) is not str for case_id in case_ids)
                or tuple(case_ids) != tuple(_Q01_CASE_MARKETS)):
            return _q01_failure("q01_invalid_selection")
        return _launch_q01()

    cases = _load_filtered_cases(cases_path, category, limit, case_ids)
    if not cases:
        return RagasRunResult(status=ra.STATUS_FAILED, error_category="no_cases",
                              safe_message="No matching cases to evaluate.")

    if service is None:
        service = (service_factory or _default_service)(config)

    eval_cases = []
    for qc in cases:
        result = service.answer(qc.question)
        eval_cases.append(ra.case_from_service_result(
            qc.case_id, qc.question, result,
            category=qc.metadata.get("category"), reference=qc.reference))

    run = (run_ragas_fn or ra.run_ragas)(eval_cases, config=evaluator_config)
    base = _scored_result(run)

    # HARD STOP: an all-invalid run must not be persisted as a normal result.
    if not ra.has_usable_scores(run):
        base.error_category = "no_valid_scores"
        base.safe_message = (
            "Evaluator returned no valid scores. Check RAGAS_EVAL_API_KEY, "
            "RAGAS_EVAL_BASE_URL, RAGAS_EVAL_MODEL and RAGAS_EVAL_EMBEDDING_MODEL.")
        return base

    if persist:
        if timestamp is None:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = Path(output_dir) if output_dir else Path(runs_dir) / timestamp
        out.mkdir(parents=True, exist_ok=True)
        write_artifacts(out, run, evaluator_config, timestamp)
        base.output_directory = str(out)
    return base


# --- Artifact persistence (shared) ------------------------------------------


def _git_sha() -> str | None:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - git optional
        return None


def write_artifacts(out: Path, run: dict, evaluator, stamp: str) -> None:
    """Write results.csv/json, summary.md and run_config.json (strict JSON)."""
    import csv

    try:
        import ragas
        ragas_version = getattr(ragas, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        ragas_version = "unknown"

    run_config = {
        "timestamp": stamp,
        "ragas_version": ragas_version,
        "status": run["status"],
        "case_count": run["case_count"],
        "referenced_case_count": run["referenced_case_count"],
        "context_recall_run": run["context_recall_run"],
        "valid_score_count": run["valid_score_count"],
        "expected_score_count": run["expected_score_count"],
        "failed_score_count": run["failed_score_count"],
        "score_coverage": run["score_coverage"],
        "metric_names": run["metric_names"],
        "git_commit": _git_sha(),
        **evaluator.safe_dict(),  # never includes the API key
    }
    # allow_nan=False is a fail-loud backstop: no NaN/inf can reach JSON.
    (out / "run_config.json").write_text(
        json.dumps(run_config, indent=2, allow_nan=False), encoding="utf-8")
    (out / "results.json").write_text(
        json.dumps({"metrics": run["metrics"], "per_case": run["per_case"],
                    "run_config": run_config}, indent=2, allow_nan=False),
        encoding="utf-8")

    fieldnames = ["case_id", "category", *run["metric_names"]]
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in run["per_case"]:
            writer.writerow(row)

    (out / "summary.md").write_text(summary_markdown(run, run_config), encoding="utf-8")


def _fmt(value) -> str:
    return f"{value}" if ra.is_valid_score(value) else "n/a"


def _avg(rows, name) -> str:
    vals = [float(r[name]) for r in rows if ra.is_valid_score(r.get(name))]
    return f"{round(sum(vals) / len(vals), 3)}" if vals else "n/a"


def summary_markdown(run: dict, run_config: dict) -> str:
    m = run["metrics"]
    lines = [
        "# RAGAS — generation quality\n",
        f"Run {run_config['timestamp']} · RAGAS {run_config['ragas_version']} · "
        f"evaluator `{run_config['evaluator_model']}` · {run['case_count']} case(s).",
        "Measured values (baseline — not pass/fail). Optional secondary layer; the "
        "deterministic retrieval evaluations remain the primary gate.\n",
        "## Execution status\n",
        f"Status: **{run['status']}**",
        f"Valid scores: {run['valid_score_count']} / {run['expected_score_count']}",
        f"Score coverage: {round(run['score_coverage'] * 100, 1)}%",
        ("\n_Some evaluator jobs did not return valid numeric scores. Metrics below "
         "are aggregated only from valid scores. This is technical evaluation "
         "coverage, not model quality._" if run["status"] == ra.STATUS_PARTIAL else ""),
        "",
        "## Overall\n",
        f"- Faithfulness: **{_fmt(m.get(ra.METRIC_FAITHFULNESS))}**",
        f"- Response Relevancy: **{_fmt(m.get(ra.METRIC_RESPONSE_RELEVANCY))}**",
        f"- Context Precision: **{_fmt(m.get(ra.METRIC_CONTEXT_PRECISION))}**",
        f"- Context Recall: **{_fmt(m.get(ra.METRIC_CONTEXT_RECALL))}** "
        f"({run['referenced_case_count']} referenced case(s))"
        if run["context_recall_run"] else
        "- Context Recall: not run (no referenced cases in this selection)",
        "",
        "## By category\n",
        "| Category | n | Faithfulness | Response Relevancy | Context Precision |",
        "|---|---|---|---|---|",
    ]
    by_cat: dict[str, list] = {}
    for row in run["per_case"]:
        by_cat.setdefault(row.get("category", ""), []).append(row)
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        lines.append(
            f"| {cat or '—'} | {len(rows)} | "
            f"{_avg(rows, ra.METRIC_FAITHFULNESS)} | "
            f"{_avg(rows, ra.METRIC_RESPONSE_RELEVANCY)} | "
            f"{_avg(rows, ra.METRIC_CONTEXT_PRECISION)} |")

    lowest = sorted(
        (r for r in run["per_case"] if ra.is_valid_score(r.get(ra.METRIC_FAITHFULNESS))),
        key=lambda r: r[ra.METRIC_FAITHFULNESS])[:5]
    if lowest:
        lines += ["", "## Lowest-faithfulness cases (review, not automatic failures)\n"]
        for r in lowest:
            lines.append(f"- `{r['case_id']}` — faithfulness {r[ra.METRIC_FAITHFULNESS]}")
    return "\n".join(lines) + "\n"
