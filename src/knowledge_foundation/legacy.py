"""Legacy compatibility (GKB-2). Existing systems key labour-market records by occupation TITLE, compensation rows by native SOC / SOC 2020 CODE with an empty title, and the
runtime stores by ``ask4mo:occ:<hash>`` ids. This module only READS the graph to say how a legacy reference would map; it rewrites nothing, merges nothing and is not imported by
any runtime path. A legacy reference that cannot be linked is reported as unresolved and keeps its existing behaviour."""

from __future__ import annotations

from typing import Any

from src.knowledge_foundation.graph import OccupationGraph

__all__ = ["LegacyCompatibility", "LegacyIdentityAdapter"]


class LegacyCompatibility:
    def __init__(self, graph: OccupationGraph) -> None:
        self._g = graph

    def by_legacy_id(self, legacy_key: str) -> dict[str, Any]:
        node = self._g.find_by_legacy_key(legacy_key)
        return {"status": "linked" if node else "unresolved", "occupation": node, "basis": "legacy_key" if node else None}

    def by_native_code(self, scheme: str, code: str) -> dict[str, Any]:
        """A legacy SOC / SOC 2020 / O*NET-SOC code. The edition of a legacy row is usually unknown, so every edition is searched and reported; more than one distinct occupation is
        ``ambiguous`` (never auto-chosen) and none is ``unresolved``."""
        hits = self._g.find_by_identifier(scheme, code)
        keys = {h["occupation_key"] for h in hits}
        if not hits:
            return {"status": "unresolved", "occupation": None, "editions": []}
        if len(keys) > 1:
            return {"status": "ambiguous", "occupation": None, "editions": sorted({h["edition"] for h in hits}), "candidates": sorted(keys)}
        return {"status": "linked", "occupation": hits[0], "editions": sorted({h["edition"] for h in hits}), "edition_known": any(h["edition"] != "unknown" for h in hits)}

    def by_title(self, title: str) -> dict[str, Any]:
        """A legacy title. Several nodes sharing the title are never merged: the caller receives all of them with status ``ambiguous``."""
        hits = self._g.find_by_label(title)
        if not hits:
            return {"status": "unresolved", "candidates": []}
        return {"status": "linked" if len(hits) == 1 else "ambiguous", "candidates": [h["occupation_key"] for h in hits]}


class LegacyIdentityAdapter:
    """Compatibility adapter (P10C-B): for one legacy reference, report the legacy identifier, the canonical occupation identifier, the identity state (linked, ambiguous,
    unresolved), the mapping status and the source evidence behind it. READ-ONLY and not imported by any runtime path: it never forces a match, never picks among several, and never
    changes production title-based retrieval or Compensation V1."""

    def __init__(self, graph: OccupationGraph, registry=None) -> None:
        self._g, self._reg = graph, registry

    def describe(self, *, legacy_id: str | None = None, native: tuple[str, str] | None = None, title: str | None = None) -> dict[str, Any]:
        given = [x for x in (legacy_id, native, title) if x]
        if len(given) != 1:
            return {"identity_state": "unresolved", "reason": "exactly_one_legacy_reference_required", "canonical_occupation_id": None, "legacy_reference": None}
        if legacy_id:
            node = self._g.find_by_legacy_key(legacy_id)
            return self._one(node, {"kind": "legacy_id", "value": legacy_id}) if node else self._none({"kind": "legacy_id", "value": legacy_id})
        if native:
            scheme, code = native
            hits = self._g.find_by_identifier(scheme, str(code))
            keys = sorted({h["occupation_key"] for h in hits})
            ref = {"kind": "native_code", "scheme": scheme, "value": str(code)}
            if not keys:
                return self._none(ref)
            if len(keys) > 1:
                return {"identity_state": "ambiguous", "canonical_occupation_id": None, "candidates": keys, "legacy_reference": ref, "mapping_status": "ambiguous", "source_evidence": []}
            return self._one(self._g.get(keys[0]), ref)
        hits = self._g.find_by_label(title)
        ref = {"kind": "title", "value": title}
        if not hits:
            return self._none(ref)
        if len(hits) > 1:
            return {"identity_state": "ambiguous", "canonical_occupation_id": None, "candidates": [h["occupation_key"] for h in hits], "legacy_reference": ref, "mapping_status": "ambiguous",
                    "source_evidence": []}
        return self._one(hits[0], ref)

    @staticmethod
    def _none(ref: dict[str, Any]) -> dict[str, Any]:
        return {"identity_state": "unresolved", "canonical_occupation_id": None, "legacy_reference": ref, "mapping_status": "unknown", "source_evidence": []}

    def _one(self, node: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
        key = node["occupation_key"]
        ids = self._g.identifiers(key)
        rels = self._g.relationships(key) + self._g.relationships(key, direction="in")
        statuses = {r["mapping_status"] for r in rels}
        status = "unknown" if not rels else ("verified" if statuses == {"verified"} else ("mixed" if len(statuses) > 1 else next(iter(statuses))))
        evidence = [{"scheme": i["scheme"], "edition": i["edition"], "native_code": i["native_code"], "source_ref": i["source_ref"]} for i in ids]
        qual = None
        if self._reg is not None and rels:
            from src.knowledge_foundation.qualification import summarize_qualification
            qual = summarize_qualification(rels, self._reg)
        return {"identity_state": "linked", "canonical_occupation_id": key, "legacy_reference": ref, "legacy_keys": node["legacy_keys"], "mapping_status": status, "source_evidence": evidence,
                "relationship_qualification": qual}
