"""Relationship qualification (GKB-2/GKB-3). Five DISTINCT questions are asked of every stored relationship and never conflated:

1. structurally valid   - a current (not superseded) relationship whose vocabulary, endpoints and editions passed the graph rules;
2. source linked        - it names a source that exists in the registry;
3. official source      - its basis is ``source_provided`` and that source has a genuine (non-fixture, known) origin;
4. independently reviewed - its qualification status is ``qualified`` (a named human review; ``engineering_checked`` is NOT review);
5. licensed for runtime - the source is approved for runtime use with a verified licence (``SourceRegistry.can_serve_as_evidence``).

``operationally_approved`` is true only when 3, 4 and 5 all hold and the mapping status is VERIFIED. A relationship that is merely structurally valid, or even VERIFIED against an
official file, is not operational. Read-only: nothing here changes a relationship, a source or a status."""

from __future__ import annotations

from typing import Any, Iterable

from src.knowledge_foundation import enums as E

__all__ = ["qualify_relationship", "summarize_qualification"]

LEVELS = ("structurally_valid", "source_linked", "official_source_provided", "independently_reviewed", "licensed_for_runtime", "operationally_approved")


def qualify_relationship(rel: dict[str, Any], registry) -> dict[str, Any]:
    src = registry.get(rel["source_ref"]) if rel.get("source_ref") else None
    structurally = not rel.get("superseded") and rel.get("mapping_status") != "unsupported"
    linked = src is not None
    official = bool(linked and rel.get("basis") == "source_provided" and src["origin"] in E.EVIDENCE_ORIGINS)
    reviewed = rel.get("qualification_status") == "qualified"
    licensed = bool(linked and registry.can_serve_as_evidence(rel["source_ref"]))
    operational = bool(official and reviewed and licensed and rel.get("mapping_status") == "verified")
    flags = {"structurally_valid": structurally, "source_linked": linked, "official_source_provided": official, "independently_reviewed": reviewed, "licensed_for_runtime": licensed,
             "operationally_approved": operational}
    highest = "none"
    for level in LEVELS:                                                                    # the highest level reached in order; never skipping a missing step
        if not flags[level]:
            break
        highest = level
    return {**flags, "highest_level": highest, "mapping_status": rel.get("mapping_status"), "qualification_status": rel.get("qualification_status")}


def summarize_qualification(relationships: Iterable[dict[str, Any]], registry) -> dict[str, Any]:
    counts = {level: 0 for level in LEVELS}
    highest: dict[str, int] = {}
    n = 0
    for rel in relationships:
        q = qualify_relationship(rel, registry)
        n += 1
        for level in LEVELS:
            counts[level] += 1 if q[level] else 0
        highest[q["highest_level"]] = highest.get(q["highest_level"], 0) + 1
    return {"relationships": n, "reached": counts, "highest_level": dict(sorted(highest.items()))}
