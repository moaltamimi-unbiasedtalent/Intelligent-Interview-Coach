"""Knowledge Base application boundary (Streamlit-free, read-only).

Callable operations a frontend needs to show knowledge-base status. Retrieval
logic, source precedence, hybrid retrieval, structured repositories, embeddings
and RAGAS are untouched — this only exposes existing read-only snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Committed, offline evidence artifacts (no secrets, no candidate data, no raw
# embeddings or retrieval contents). Read-only diagnostics for the reviewer surface.
_BUILD_METADATA = Path("data/knowledge/build_metadata.json")
_RETRIEVAL_AFTER = Path("evaluations/knowledge/retrieval_after.json")
_COVERAGE_REPORT = Path("evaluations/knowledge/coverage_report.json")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a missing/malformed artifact is a safe empty section
        return {}


def get_knowledge_diagnostics() -> dict:
    """Safe read-only Knowledge/RAG diagnostics from committed offline artifacts.

    Separates the KNOWLEDGE RUNTIME (governed structured/vector counts + build
    provenance) from OFFLINE RETRIEVAL EVALUATION (deterministic retrieval-quality
    metrics). Exposes only counts, versions, rates and known gaps — never embeddings,
    raw retrieval contents, private paths, prompts or secrets.
    """
    build = _read_json(_BUILD_METADATA)
    counts = build.get("runtime_counts", {}) or {}
    roles = counts.get("roles", {}) or {}
    labour = counts.get("labour_market", {})
    labour_total = (
        sum(v for v in labour.values() if isinstance(v, (int, float)))
        if isinstance(labour, dict)
        else labour
    )

    retrieval = (_read_json(_RETRIEVAL_AFTER).get("summary", {}) or {})
    coverage = _read_json(_COVERAGE_REPORT)

    try:
        source_count = len(list_sources())
    except Exception:  # noqa: BLE001
        source_count = None

    return {
        "runtime": {
            "occupations": roles.get("occupations"),
            "aliases": roles.get("occupation_aliases"),
            "skills": roles.get("occupation_skills"),
            "tasks": roles.get("occupation_tasks"),
            "knowledge_areas": roles.get("occupation_knowledge"),
            "work_activities": roles.get("occupation_activities"),
            "compensation": counts.get("compensation"),
            "labour_market": labour_total,
            "competencies": counts.get("competencies"),
            "credentials": counts.get("credentials"),
            "sources": source_count,
            "runtime_pipeline_version": build.get("runtime_pipeline_version"),
            "normalized_pipeline_version": build.get("normalized_pipeline_version"),
            "built_at": build.get("built_at"),
        },
        "retrieval_evaluation": {
            "cases": retrieval.get("cases"),
            "passed": retrieval.get("passed"),
            "pass_rate": retrieval.get("pass_rate"),
            "evidence_coverage_rate": retrieval.get("evidence_coverage_rate"),
            "citation_completeness_rate": retrieval.get("citation_completeness_rate"),
            "geography_correctness_rate": retrieval.get("geography_correctness_rate"),
            "unknown_role_safety_rate": retrieval.get("unknown_role_safety_rate"),
            "unsupported_geography_safety_rate": retrieval.get("unsupported_geography_safety_rate"),
            "no_fabricated_citation_rate": retrieval.get("no_fabricated_citation_rate"),
            "safety_pass_rate": retrieval.get("safety_pass_rate"),
        },
        "known_gaps": list(coverage.get("top_remaining_gaps", []) or [])[:6],
    }


def get_ingestion_snapshot() -> dict:
    """Narrative ingestion status (documents, chunks, by_type, per_document…)."""
    from src.copilot.ingestion import indexer

    return indexer.load_manifest() or {}


def list_sources() -> list[Any]:
    """The curated source registry entries (id, group, licence disposition…)."""
    from src.copilot.knowledge import manifest as km

    return km.load_manifest()
