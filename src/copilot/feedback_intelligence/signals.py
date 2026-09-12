"""Signal adapters: turn SAFE local artifacts into typed FeedbackSignals (Phase 7G, §55).

Each adapter reads one approved source (never candidate content, never raw free text) and yields
:class:`FeedbackSignal`. A missing source is reported, never fatal (§56); a malformed artifact
produces a source-specific warning rather than silent zero-valued metrics (§57).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.copilot.feedback_intelligence.models import FeedbackSignal, SignalType


@runtime_checkable
class FeedbackSignalAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        """Return (signals, warnings). Never raises; a bad source → warnings, empty signals."""
        ...


def file_hash(path: str | Path) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else ""


def _load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (ValueError, OSError) as exc:
        return None, f"{path.name}: unreadable/malformed ({type(exc).__name__})"


def _metric_signal(sid, source, name, value, *, dataset_hash=None, version=None, domain=None):
    return FeedbackSignal(
        signal_id=sid, signal_type=SignalType.RETRIEVAL_EVALUATION if "retrieval" in source
        else (SignalType.RAGAS_EVALUATION if "ragas" in source
              else (SignalType.KNOWLEDGE_COVERAGE if "coverage" in source
                    else SignalType.EXTERNAL_RESEARCH_EVALUATION)),
        source=source, metric_name=name, metric_value=value,
        metric_dataset_hash=dataset_hash, metric_version=version, domain=domain,
        observed_at=datetime.now(timezone.utc))


# --- fixtures (synthetic; primary source for deterministic eval) ----------------------

class FixtureAdapter:
    name = "fixtures"

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def available(self) -> bool:
        return self._path.is_file()

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        if not self.available():
            return [], [f"{self.name}: fixture file not found ({self._path})"]
        data, err = _load_json(self._path)
        if err:
            return [], [err]
        raw = data["signals"] if isinstance(data, dict) and "signals" in data else data
        out, warnings = [], []
        for i, item in enumerate(raw):
            try:
                out.append(FeedbackSignal.model_validate(item))
            except Exception as exc:  # noqa: BLE001 - one bad record never sinks the batch
                warnings.append(f"{self.name}: signal #{i} invalid ({type(exc).__name__})")
        return out, warnings


# --- user feedback (structured only; NEVER the free-text comment, §7) -----------------

class UserFeedbackAdapter:
    name = "user_feedback"

    def __init__(self, repo=None) -> None:
        self._repo = repo

    def available(self) -> bool:
        return self._repo is not None

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        if self._repo is None:
            return [], ["user_feedback: no repository configured (source unavailable)"]
        try:
            items = self._repo.list_all()
        except Exception as exc:  # noqa: BLE001
            return [], [f"user_feedback: repository read failed ({type(exc).__name__})"]
        out = []
        for it in items:
            surface = getattr(it, "surface", None)
            rating = getattr(it, "rating", None)
            tid = getattr(it, "target_id", "") or ""
            run_hash = hashlib.sha256(tid.encode()).hexdigest()[:16] if tid else None
            out.append(FeedbackSignal(
                signal_id=f"uf:{getattr(it, 'id', surface)}:{run_hash or '0'}",
                signal_type=SignalType.USER_FEEDBACK, source=self.name,
                operation=surface, rating=rating, run_id_hash=run_hash,
                structured_feedback_category=surface))  # NOTE: comment text is never read
        return out, []


# --- evaluation-artifact adapters (committed, reviewed) -------------------------------

class RetrievalEvalAdapter:
    name = "retrieval_evaluation"

    def __init__(self, path: str | Path = "evaluations/knowledge/retrieval_after.json") -> None:
        self._path = Path(path)

    def available(self) -> bool:
        return self._path.is_file()

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        if not self.available():
            return [], [f"{self.name}: artifact absent ({self._path.name}) — regenerable"]
        data, err = _load_json(self._path)
        if err:
            return [], [err]
        s = data.get("summary", data) if isinstance(data, dict) else {}
        dh = file_hash(self._path)
        keys = ("pass_rate", "citation_completeness_rate", "geography_correctness_rate",
                "unknown_role_safety_rate", "unsupported_geography_safety_rate",
                "evidence_coverage_rate", "no_evidence_rate")
        out = [_metric_signal(f"ret:{k}", self.name, k, s[k], dataset_hash=dh, version="7C")
               for k in keys if isinstance(s.get(k), (int, float))]
        return out, ([] if out else [f"{self.name}: no recognised metrics"])


class RagasEvalAdapter:
    name = "ragas_evaluation"

    def __init__(self, path: str | Path = "evaluations/ragas/deterministic_baseline.json") -> None:
        self._path = Path(path)

    def available(self) -> bool:
        return self._path.is_file()

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        if not self.available():
            return [], [f"{self.name}: artifact absent"]
        data, err = _load_json(self._path)
        if err:
            return [], [err]
        dh = data.get("dataset_hash")
        out = []
        for name, key in (("id_context_precision", "id_context_precision"),
                          ("id_context_recall", "id_context_recall")):
            block = data.get(key) or {}
            val = block.get("mean")
            if isinstance(val, (int, float)):  # NOT_RUN/None is skipped, never scored 0 (§26)
                out.append(_metric_signal(f"ragas:{name}", self.name, name, val,
                                          dataset_hash=dh, version=data.get("ragas_version")))
        return out, ([] if out else [f"{self.name}: no numeric RAGAS means (NOT_RUN?)"])


class KnowledgeCoverageAdapter:
    name = "knowledge_coverage"

    def __init__(self, path: str | Path = "evaluations/knowledge/coverage_report.json") -> None:
        self._path = Path(path)

    def available(self) -> bool:
        return self._path.is_file()

    def signals(self) -> tuple[list[FeedbackSignal], list[str]]:
        if not self.available():
            return [], [f"{self.name}: artifact absent"]
        data, err = _load_json(self._path)
        if err:
            return [], [err]
        out = []
        gaps = data.get("top_remaining_gaps") or []
        for i, gap in enumerate(gaps):
            out.append(FeedbackSignal(
                signal_id=f"gap:{i}", signal_type=SignalType.KNOWLEDGE_COVERAGE,
                source=self.name, outcome="known_gap", domain="knowledge",
                metadata={"gap_index": i},
                observed_at=datetime.now(timezone.utc)))
        return out, ([] if out else [f"{self.name}: no coverage gaps listed"])
