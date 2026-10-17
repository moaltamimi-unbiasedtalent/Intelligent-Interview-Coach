"""Legacy compatibility (GKB-2). Existing systems key labour-market records by occupation TITLE, compensation rows by native SOC / SOC 2020 CODE with an empty title, and the
runtime stores by ``ask4mo:occ:<hash>`` ids. This module only READS the graph to say how a legacy reference would map; it rewrites nothing, merges nothing and is not imported by
any runtime path. A legacy reference that cannot be linked is reported as unresolved and keeps its existing behaviour."""

from __future__ import annotations

from typing import Any

from src.knowledge_foundation.graph import OccupationGraph

__all__ = ["LegacyCompatibility"]


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
