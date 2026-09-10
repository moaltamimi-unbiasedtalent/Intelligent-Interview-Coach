#!/usr/bin/env python
"""Ask4Mo demo-knowledge readiness check.

Answers one question for a reviewer/operator: *is this environment ready for an
evidence-backed Ask4Mo demo?* It inspects the local knowledge indexes (structured
stores + vector store + source registry), then runs ONE deterministic retrieval smoke
query (no provider / no LLM call) and confirms the citation pipeline returns sources.

The built indexes are gitignored (`data/knowledge/*`, `data/chroma/*`), so a fresh
checkout is EMPTY and this check reports NOT READY with the exact build command.

Usage:
    python scripts/check_demo_knowledge.py

Exit code: 0 when the required demo evidence is present and the smoke query returns
cited sources; non-zero otherwise (safe to use as a pre-demo / CI readiness gate).
"""

from __future__ import annotations

import os
import sqlite3
import sys

# Repo root on path when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.copilot import constants  # noqa: E402

SMOKE_QUERY = "What skills and responsibilities are important for a registered nurse?"
SMOKE_ROLE = "registered nurse"

# The canonical local-first build sequence (see README → Career Intelligence).
BUILD_STEPS = (
    "python scripts/source_status.py",
    "python scripts/download_sources.py         # only public sources; no proprietary scraping",
    "python scripts/normalise_roles.py",
    "python scripts/load_competencies.py",
    "python scripts/load_labour_market.py",
    "python scripts/load_compensation.py",
    "python scripts/load_credentials.py",
    "python scripts/rebuild_vector_index.py",
)

# Structured stores: (label, path, required-for-demo?)
STRUCTURED = (
    ("Structured roles", constants.ROLE_DB_PATH, True),
    ("Competencies", constants.COMPETENCY_DB_PATH, False),
    ("Compensation", constants.COMPENSATION_DB_PATH, False),
    ("Labour market", constants.LABOUR_MARKET_DB_PATH, False),
    ("Credentials", constants.CREDENTIAL_DB_PATH, False),
)


def _sqlite_row_count(path: str) -> int:
    """Total rows across all user tables in a SQLite DB (0 if unreadable/missing)."""
    if not os.path.exists(path):
        return 0
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = [
                r[0]
                for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ]
            return sum(con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables)
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def _vector_passage_count() -> int:
    """Number of embedded passages in the Chroma store (0 if absent/unreadable)."""
    db = os.path.join(constants.CHROMA_PERSIST_DIR, "chroma.sqlite3")
    if not os.path.exists(db):
        return 0
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return con.execute("SELECT count(*) FROM embeddings").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def _run_smoke_query():
    """Deterministic retrieval-only smoke query. Returns (source_count, has_citations,
    insufficient, lane) or raises on unexpected failure."""
    from src.application.factories import build_career_service
    from src.copilot.config import CopilotConfig

    service = build_career_service(CopilotConfig())
    res = service.retrieve_evidence(SMOKE_QUERY)
    citations = list(getattr(res, "citations", None) or [])
    return (
        int(getattr(res, "source_count", 0) or 0),
        len(citations) > 0,
        bool(getattr(res, "insufficient_evidence", False)),
        getattr(res, "retrieval_lane", None),
    )


def main() -> int:
    print("ASK4MO DEMO KNOWLEDGE CHECK\n")

    problems: list[str] = []

    # --- structured stores ---
    for label, path, required in STRUCTURED:
        rows = _sqlite_row_count(path)
        ready = rows > 0
        print(f"{label}: {'READY' if ready else 'MISSING'}" + (f" ({rows:,} rows)" if ready else ""))
        if required and not ready:
            problems.append(f"{label} ({path})")

    # --- vector store ---
    passages = _vector_passage_count()
    vector_ready = passages > 0
    print(f"Vector index: {'READY' if vector_ready else 'MISSING'}")
    print(f"\nVector passages: {passages:,}")
    if not vector_ready:
        problems.append(f"Vector index ({constants.CHROMA_PERSIST_DIR})")

    # --- source registry ---
    registry_ready = os.path.exists(constants.SOURCE_MANIFEST_PATH)
    print(f"Source registry: {'READY' if registry_ready else 'MISSING'}")

    # --- deterministic retrieval smoke query (no provider) ---
    print(f"\nSmoke query:\n{SMOKE_ROLE}\n")
    citation_pass = False
    try:
        source_count, has_citations, insufficient, lane = _run_smoke_query()
        print(f"Sources returned: {source_count}")
        print(f"Retrieval lane: {lane}")
        citation_pass = source_count >= 1 and has_citations and not insufficient
    except Exception as exc:  # noqa: BLE001 - readiness check must never crash
        print(f"Smoke query could not run: {type(exc).__name__}")
        problems.append("retrieval smoke query")

    print(f"\nCITATION PIPELINE:\n{'PASS' if citation_pass else 'FAIL'}")
    if not citation_pass:
        problems.append("citation smoke query returned no cited sources")

    ready = not problems
    print(f"\nDEMO KNOWLEDGE:\n{'READY' if ready else 'NOT READY'}")

    if not ready:
        print("\nMissing for an evidence-backed demo:")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nThe built indexes are gitignored, so a fresh checkout is empty. Build them\n"
            "from the local-first loaders (public sources only — no proprietary scraping):\n"
        )
        for step in BUILD_STEPS:
            print(f"  {step}")
        print("\nSee the README 'Knowledge base & citations' section for details.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
