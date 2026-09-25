"""Knowledge governance (Capstone P6): manifest, deterministic readiness, source health,
coverage matrix and the 7-language knowledge boundary.

This composes the EXISTING source manifest (``manifest.py``), the generated build metadata
and the new governed K1–K4 datasets into ONE auditable view of the governed KB — without
opening raw embeddings and without any model, network or secret.

Readiness is DETERMINISTIC and honest: a component is READY only when its concrete
artifacts exist and carry the required metadata — never merely because a folder or a code
path exists. Because the large runtime stores (structured DBs + Chroma index) are
generated and git-ignored, on a fresh clone they correctly report SOURCE_MISSING /
INDEX_MISSING while the committed governed K1–K4 datasets report READY. That mixed,
truthful picture is the point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from src.copilot import constants
from src.copilot.knowledge import governed_datasets as gd

__all__ = [
    "ReadinessState", "ComponentReadiness", "knowledge_manifest", "component_readiness",
    "overall_readiness", "source_health", "coverage_matrix", "language_boundary",
    "SUPPORTED_LANGUAGES",
]

SUPPORTED_LANGUAGES = ["en", "de", "fr", "es", "it", "pt", "nl"]

_BUILD_METADATA = Path("data/knowledge/build_metadata.json")
_COVERAGE_REPORT = Path("evaluations/knowledge/coverage_report.json")

_STRUCTURED_STORES = {
    "roles": constants.ROLE_DB_PATH,
    "compensation": constants.COMPENSATION_DB_PATH,
    "competencies": constants.COMPETENCY_DB_PATH,
    "labour_market": constants.LABOUR_MARKET_DB_PATH,
    "credentials": constants.CREDENTIAL_DB_PATH,
}


class ReadinessState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    SOURCE_MISSING = "source_missing"
    INDEX_MISSING = "index_missing"
    STALE = "stale"
    PARTIAL = "partial"
    READY = "ready"
    ERROR = "error"


@dataclass
class ComponentReadiness:
    component: str
    state: ReadinessState
    detail: str
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


def _read_json(path: Path) -> dict:
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing/malformed artifact → empty (safe)
        return {}


def _file_present(path_str: str) -> tuple[bool, int]:
    p = Path(path_str)
    try:
        return (p.is_file() and p.stat().st_size > 0, p.stat().st_size if p.is_file() else 0)
    except OSError:
        return (False, 0)


# --- readiness ---------------------------------------------------------------


def component_readiness() -> list[ComponentReadiness]:
    """Deterministic readiness per component. No model/network; file + metadata checks."""
    out: list[ComponentReadiness] = []

    # 1. Source manifest (committed) — integrity: loads, unique ids, non-empty.
    try:
        from src.copilot.knowledge import manifest as km
        entries = km.load_manifest()
        ids = [e.source_id for e in entries]
        unique = len(ids) == len(set(ids))
        state = ReadinessState.READY if (entries and unique) else ReadinessState.ERROR
        out.append(ComponentReadiness(
            "source_manifest", state,
            f"{len(entries)} sources, unique_ids={unique}",
            {"count": len(entries), "unique_ids": unique}))
    except Exception as exc:  # noqa: BLE001
        out.append(ComponentReadiness("source_manifest", ReadinessState.ERROR,
                                      f"manifest load failed: {type(exc).__name__}"))

    # 2. Governed K1–K4 datasets (committed) — each present with records.
    for summary in gd.governed_dataset_summaries():
        present = bool(summary.get("record_count"))
        out.append(ComponentReadiness(
            f"governed:{summary.get('requirement')}",
            ReadinessState.READY if present else ReadinessState.SOURCE_MISSING,
            f"{summary.get('dataset_id')} records={summary.get('record_count')} "
            f"review={summary.get('review_status')}",
            {"record_count": summary.get("record_count"),
             "review_status": summary.get("review_status")}))
    if not gd.governed_dataset_summaries():
        out.append(ComponentReadiness("governed:K1-K4", ReadinessState.SOURCE_MISSING,
                                      "governed datasets not found"))

    # 3. Structured runtime stores (generated, git-ignored).
    build = _read_json(_BUILD_METADATA)
    counts = build.get("runtime_counts", {}) or {}
    for name, path_str in _STRUCTURED_STORES.items():
        present, size = _file_present(path_str)
        has_counts = bool(counts.get(name))
        if present and has_counts:
            state = ReadinessState.READY
        elif present:
            state = ReadinessState.PARTIAL
        else:
            state = ReadinessState.SOURCE_MISSING
        out.append(ComponentReadiness(
            f"structured_store:{name}", state,
            f"present={present} size_bytes={size} has_build_counts={has_counts}",
            {"present": present, "size_bytes": size}))

    # 4. Vector index (generated, git-ignored).
    idx = Path(constants.CHROMA_PERSIST_DIR)
    idx_present = idx.is_dir() and any(idx.iterdir()) if idx.exists() else False
    out.append(ComponentReadiness(
        "vector_index",
        ReadinessState.READY if idx_present else ReadinessState.INDEX_MISSING,
        f"chroma_present={idx_present} dir={constants.CHROMA_PERSIST_DIR}",
        {"present": idx_present}))

    # 5. Build metadata provenance.
    out.append(ComponentReadiness(
        "build_metadata",
        ReadinessState.READY if build.get("built_at") else ReadinessState.SOURCE_MISSING,
        f"built_at={build.get('built_at')} "
        f"runtime_pipeline={build.get('runtime_pipeline_version')}",
        {"built_at": build.get("built_at")}))

    return out


def overall_readiness() -> dict:
    """Aggregate readiness. READY only if every component is READY; else PARTIAL/NOT_READY."""
    comps = component_readiness()
    states = [c.state for c in comps]
    ready = sum(1 for s in states if s is ReadinessState.READY)
    total = len(states)
    if ready == total:
        overall = ReadinessState.READY
    elif ready == 0:
        overall = ReadinessState.NOT_CONFIGURED
    else:
        overall = ReadinessState.PARTIAL
    return {
        "overall": overall.value,
        "ready_components": ready,
        "total_components": total,
        "components": [c.to_dict() for c in comps],
    }


# --- manifest ----------------------------------------------------------------


def knowledge_manifest() -> dict:
    """A first-class, auditable Knowledge Manifest — safe metadata only.

    Unifies: the governed K1–K4 datasets, the curated source-manifest entries (a safe
    projection) and the generated build provenance. No secrets, no candidate content, no
    raw embeddings.
    """
    build = _read_json(_BUILD_METADATA)
    sources: list[dict] = []
    try:
        from src.copilot.knowledge import manifest as km
        for e in km.load_manifest():
            sources.append({
                "source_id": e.source_id, "title": e.title, "publisher": e.publisher,
                "authority": e.authority, "authority_level": e.authority_level,
                "jurisdiction": e.country, "language": e.language,
                "source_type": e.source_type, "group": e.group,
                "version": e.version, "reference_year": e.reference_year,
                "publication_date": e.publication_date, "licence": e.licence,
                "storage_target": e.storage_target,
                "citation_capable": bool(e.source_url),
            })
    except Exception:  # noqa: BLE001
        sources = []
    return {
        "governed_datasets": gd.governed_dataset_summaries(),
        "curated_sources": sources,
        "curated_source_count": len(sources),
        "build_provenance": {
            "built_at": build.get("built_at"),
            "runtime_pipeline_version": build.get("runtime_pipeline_version"),
            "normalized_pipeline_version": build.get("normalized_pipeline_version"),
            "runtime_counts": build.get("runtime_counts", {}),
        },
    }


# --- source health -----------------------------------------------------------


def source_health() -> list[dict]:
    """Per-store health for the reviewer surface (deterministic file + metadata checks)."""
    build = _read_json(_BUILD_METADATA)
    counts = build.get("runtime_counts", {}) or {}
    health: list[dict] = []
    for name, path_str in _STRUCTURED_STORES.items():
        present, size = _file_present(path_str)
        health.append({
            "source": name, "configured": True, "present": present,
            "size_bytes": size, "record_count": counts.get(name),
            "last_build": build.get("built_at"),
            "warnings": [] if present else ["store file missing — run the knowledge build"],
        })
    for s in gd.governed_dataset_summaries():
        health.append({
            "source": s.get("dataset_id"), "configured": True, "present": True,
            "record_count": s.get("record_count"), "review_status": s.get("review_status"),
            "warnings": [] if s.get("review_status") in (None, "engineering_draft")
            else [],
            "note": "governed committed dataset",
        })
    return health


# --- coverage matrix ---------------------------------------------------------


def coverage_matrix() -> dict:
    """What the governed KB genuinely covers — never a universal-coverage claim.

    Dimensions: topic/domain, jurisdiction, language, source authority, readiness and a
    known limitation. Built from the governed datasets + curated source groups + the
    committed coverage report's known gaps.
    """
    coverage = _read_json(_COVERAGE_REPORT)
    rows = [
        {"domain": "compensation", "jurisdiction": "DE", "language": "de/en",
         "authority": "Bundesagentur für Arbeit / Destatis", "readiness": "partial",
         "requirement": "K1",
         "limitation": "Bounded declared occupation set; engineering-draft figures; not exhaustive."},
        {"domain": "credentials", "jurisdiction": "DE/UK", "language": "en/de",
         "authority": "Regulators (NMC, IHK/HWK, BRAK, …)", "readiness": "partial",
         "requirement": "K2",
         "limitation": "Declared profession/jurisdiction matrix only; abstains elsewhere."},
        {"domain": "role_aliases", "jurisdiction": "global", "language": "en",
         "authority": "Curated versioned aliases", "readiness": "partial", "requirement": "K3",
         "limitation": "Confident exact matches only; does not override existing resolution."},
        {"domain": "current_market", "jurisdiction": "multi", "language": "en",
         "authority": "Adzuna (advertised, self-reported)", "readiness": "spec_only",
         "requirement": "K4",
         "limitation": "Bounded operation spec; live provider calls UNVALIDATED / cost-gated."},
        {"domain": "occupations/skills/competencies", "jurisdiction": "EU/UK/US",
         "language": "en", "authority": "ESCO/O*NET/ISCO/DigComp/…", "readiness": "generated",
         "requirement": "C-rag",
         "limitation": "Runtime stores are generated/git-ignored; readiness depends on the build."},
    ]
    return {
        "rows": rows,
        "known_gaps": list(coverage.get("top_remaining_gaps", []) or [])[:8],
        "disclaimer": "Coverage is bounded and declared. Ask4Mo does NOT claim universal "
                      "career-market coverage; out-of-coverage queries abstain.",
    }


# --- 7-language knowledge boundary -------------------------------------------


def language_boundary() -> list[dict]:
    """Per supported language: honestly separate UI support from KB content coverage.

    UI/conversation/dictation support is delivered (P3/P3.5). Governed KB NATIVE-language
    content is overwhelmingly English (+ some German in K1/K2); retrieval across languages
    is only bounded-tested; live model quality is UNVALIDATED. This makes explicit that
    language support is NOT a knowledge-coverage claim.
    """
    native_de = {"de"}  # K1/K2 carry some German titles/authorities
    rows = []
    for lang in SUPPORTED_LANGUAGES:
        rows.append({
            "language": lang,
            "ui_supported": True,
            "conversation_supported": True,
            "dictation_supported": True,
            "governed_kb_native_content": "partial" if lang in native_de else ("full" if lang == "en" else "none"),
            "retrieval_tested": "bounded",   # multilingual fixtures, not parity
            "live_model_quality_tested": False,
        })
    return rows
