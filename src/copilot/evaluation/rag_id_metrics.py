"""Deterministic, FREE ID-based context precision / recall for RAG retrieval (Phase 7E).

These are NON-LLM metrics computed from the real deterministic retrieval layer: for a case with
a defensible reference (a known ``expected_source_family``), we compare the *source ids* of the
retrieved evidence against the set of source ids that family may legitimately come from.

* **ID context precision** = retrieved evidence in the expected family / retrieved evidence.
  "Is the retrieved evidence drawn from the right authoritative sources?"
* **ID context recall** = 1.0 if at least one expected-family source was retrieved, else 0.0
  (source-family granularity). "Did we retrieve from the family the question needs?"

Cases without a defensible reference family (open-ended, or safety cases whose correct behaviour
is *insufficient evidence*) are marked ``NOT_APPLICABLE`` — never scored 0 (§15). No network, no
LLM, no paid call: retrieval uses the runtime's free offline embedder.

The metric granularity is deliberately the stable **source id / source family** (never a mutable
vector rank), so results are reproducible across runs (§12).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

RAGAS_CASES_PATH = "evaluations/ragas/cases.json"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Which source ids legitimately satisfy each expected source family. Families overlap (ESCO
# serves role/skills/competency) — precision measures membership in the expected family's set.
# Uses the real runtime source ids (structured + narrative). Deterministic and documented.
SOURCE_FAMILIES: dict[str, set[str]] = {
    "role": {"onet", "esco", "isco08", "kldb", "bls_ooh", "bls_projections",
             "opm_occupational_groups", "uk_hr_success_profiles",
             "uk_civil_service_success_profiles"},
    "skills": {"esco", "onet", "nice_framework", "digcomp", "esco_handbook", "esco_matrix"},
    "compensation": {"bls_oews", "ons_ashe", "eurostat_earnings"},
    "labour_market": {"bls_projections", "cedefop_clssi", "cedefop_skills_forecast",
                      "eurostat_occ_vacancy", "wef_future_of_jobs"},
    "competency": {"nice_framework", "digcomp", "eqf", "esco", "esco_matrix",
                   "e-cf", "ecf"},
}


@dataclass
class CaseIdResult:
    case_id: str
    category: str | None
    expected_family: str | None
    retrieved_sources: list[str]
    precision: float | str      # float or NOT_APPLICABLE
    recall: float | str         # float or NOT_APPLICABLE
    insufficient_evidence: bool


@dataclass
class IdMetricsReport:
    case_count: int = 0
    per_case: list[dict] = field(default_factory=list)
    precision_mean: float | None = None
    precision_applicable: int = 0
    recall_mean: float | None = None
    recall_applicable: int = 0
    not_applicable: int = 0
    dataset_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "case_count": self.case_count,
            "id_context_precision": {"mean": self.precision_mean,
                                     "applicable_cases": self.precision_applicable},
            "id_context_recall": {"mean": self.recall_mean,
                                  "applicable_cases": self.recall_applicable},
            "not_applicable_cases": self.not_applicable,
            "dataset_hash": self.dataset_hash,
            "per_case": self.per_case,
        }


def dataset_hash(path: str | Path) -> str:
    """Short, stable sha256 of the dataset bytes so a report is tied to its exact cases."""
    p = Path(path)
    if not p.is_file():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def load_ragas_cases(path: str | Path = RAGAS_CASES_PATH) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["cases"] if isinstance(data, dict) and "cases" in data else data


def _evidence_sources(result: Any) -> list[str]:
    return [(getattr(e, "source_id", "") or "").lower()
            for e in (getattr(result, "evidence", []) or [])
            if getattr(e, "source_id", "")]


def score_case(case: dict, result: Any) -> CaseIdResult:
    """Score one case's ID precision/recall from its retrieval result."""
    family = (case.get("expected_source_family") or "").strip().lower() or None
    sources = _evidence_sources(result)
    insufficient = bool(getattr(result, "insufficient_evidence", False))
    expected = SOURCE_FAMILIES.get(family) if family else None

    if not family or family == "none" or expected is None:
        # No defensible reference family (open-ended / safety / insufficient-by-design) → N/A.
        precision: float | str = NOT_APPLICABLE
        recall: float | str = NOT_APPLICABLE
    else:
        in_family = [s for s in sources if s in expected]
        precision = (len(in_family) / len(sources)) if sources else NOT_APPLICABLE
        recall = 1.0 if in_family else 0.0
    return CaseIdResult(
        case_id=case.get("case_id", "?"), category=case.get("category"),
        expected_family=family, retrieved_sources=sources,
        precision=precision, recall=recall, insufficient_evidence=insufficient)


def compute_id_metrics(cases: list[dict], retrieve_fn: Callable[[str], Any],
                       *, dataset_path: str | Path = RAGAS_CASES_PATH) -> IdMetricsReport:
    """Run deterministic retrieval over ``cases`` and aggregate ID precision/recall.

    ``retrieve_fn(question)`` returns a ``KnowledgeRetrievalResult``-like object exposing
    ``evidence[].source_id`` and ``insufficient_evidence``. No LLM/network here.
    """
    report = IdMetricsReport(case_count=len(cases), dataset_hash=dataset_hash(dataset_path))
    prec_vals: list[float] = []
    rec_vals: list[float] = []
    for case in cases:
        result = retrieve_fn(case.get("question") or case.get("query") or "")
        r = score_case(case, result)
        if isinstance(r.precision, float):
            prec_vals.append(r.precision)
        if isinstance(r.recall, float):
            rec_vals.append(r.recall)
        if r.precision == NOT_APPLICABLE and r.recall == NOT_APPLICABLE:
            report.not_applicable += 1
        report.per_case.append({
            "case_id": r.case_id, "category": r.category, "expected_family": r.expected_family,
            "precision": r.precision, "recall": r.recall,
            "retrieved_sources": r.retrieved_sources[:8],
            "insufficient_evidence": r.insufficient_evidence,
        })
    report.precision_applicable = len(prec_vals)
    report.recall_applicable = len(rec_vals)
    report.precision_mean = round(sum(prec_vals) / len(prec_vals), 4) if prec_vals else None
    report.recall_mean = round(sum(rec_vals) / len(rec_vals), 4) if rec_vals else None
    return report


def default_retrieve_fn():
    """Build the runtime deterministic retrieval function (free offline embedder). Lazily
    imported so importing this module never constructs the career service."""
    from src.application.factories import build_career_service
    from src.copilot.config import CopilotConfig
    service = build_career_service(CopilotConfig())
    return service.retrieve_evidence
