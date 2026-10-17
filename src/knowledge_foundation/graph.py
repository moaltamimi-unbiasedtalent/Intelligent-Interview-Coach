"""Canonical occupation graph (GKB-2). Persistent, queryable, edition-aware. Reuses the established ``canonical_occupation_id`` identity (so existing identities survive) rather than
creating a second authority. Relationships are governed: type and mapping status are separate, RELATED is never EQUIVALENT, a VERIFIED mapping must name a source-provided
basis, label similarity is not a permitted basis, and conflicting statements about the same pair are reported, never silently overwritten."""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import String, cast, func, select
from sqlalchemy.exc import IntegrityError

from src.copilot.knowledge.canonical import canonical_occupation_id
from src.knowledge_foundation import enums as E
from src.knowledge_foundation.taxonomy import validate_code
from src.persistence import (GlobalSource, GraphOccupation, GraphOccupationIdentifier, GraphOccupationRelationship, OccupationTaxonomy)

__all__ = ["OccupationGraph", "GraphError", "IdentityConflict", "ConflictingMapping", "occupation_key_for"]

_CANONICAL_ARG = {"esco": "esco_uri", "onet_soc": "onet_soc_code", "isco": "isco_code", "soc": "soc_code", "kldb": "kldb_code"}


class GraphError(ValueError):
    """A graph rule was violated. Messages never contain source or candidate content."""


class IdentityConflict(GraphError):
    """A native code already belongs to a different occupation in the same taxonomy edition."""


class ConflictingMapping(GraphError):
    """A different statement about the same occupation pair already exists (type or status differs); nothing was overwritten."""


def occupation_key_for(scheme: str, edition: str, code: str) -> str:
    """The stable internal identity for a (scheme, edition, code): the established canonical id where the scheme is one it already supports, else a deterministic native key.
    Independent of any display title."""
    arg = _CANONICAL_ARG.get(scheme)
    if arg:
        return canonical_occupation_id(**{arg: code})
    return canonical_occupation_id(source=f"{scheme}@{edition}", source_occupation_id=code)


def _occ(o: GraphOccupation) -> dict[str, Any]:
    return {"occupation_key": o.occupation_key, "canonical_label": o.canonical_label, "status": o.status, "legacy_keys": list(o.legacy_keys or []), "superseded_by_key": o.superseded_by_key}


class OccupationGraph:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------------------------------------------------ nodes
    def _taxonomy(self, s, scheme: str, edition: str) -> OccupationTaxonomy:
        t = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == (edition or "unknown")))
        if t is None:
            raise GraphError("unknown taxonomy edition: register it first")
        return t

    def add_occupation(self, label: str, identifiers: Iterable[tuple[str, str, str]] | Iterable[dict], *, occupation_key: str | None = None, legacy_keys: Iterable[str] = (),
                       source_ref: str = "", provenance: dict | None = None, _session=None) -> dict[str, Any]:
        """Register an occupation node with one or more identifiers ``(scheme, edition, native_code)`` (a dict may add ``native_label``). Idempotent on an existing identifier.
        A code already held by a DIFFERENT occupation in the same taxonomy edition raises ``IdentityConflict`` (no silent merge, no overwrite)."""
        ids = [i if isinstance(i, dict) else {"scheme": i[0], "edition": i[1], "code": i[2]} for i in identifiers]
        if not label or not ids:
            raise GraphError("an occupation needs a label and at least one identifier")
        own = _session is None
        s = _session or self._sf()
        try:
            resolved = []
            for i in ids:
                t = self._taxonomy(s, i["scheme"], i.get("edition", "unknown"))
                if not validate_code({"code_pattern": t.code_pattern}, i["code"]):
                    raise GraphError("native code does not match the taxonomy's code format")
                resolved.append((t, i))
            existing: GraphOccupation | None = None
            for t, i in resolved:
                hit = s.scalar(select(GraphOccupationIdentifier).where(GraphOccupationIdentifier.taxonomy_id == t.id, GraphOccupationIdentifier.native_code == i["code"]))
                if hit is not None:
                    occ = s.get(GraphOccupation, hit.occupation_id)
                    if existing is not None and existing.id != occ.id:
                        raise IdentityConflict("the identifiers belong to different occupations")
                    existing = occ
            key = occupation_key or occupation_key_for(resolved[0][0].scheme, resolved[0][0].edition, resolved[0][1]["code"])
            if existing is not None:
                if occupation_key and existing.occupation_key != occupation_key:
                    raise IdentityConflict("an identifier already belongs to a different occupation")
                node = existing
            else:
                node = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == key))
                if node is not None and not occupation_key:
                    # A default key must never silently merge different EDITIONS of one scheme (the established legacy id ignores the edition): when the node that owns the
                    # derived key already holds this scheme in another edition, this registration gets its own edition-aware identity instead.
                    t0 = resolved[0][0]
                    clash = s.scalar(select(GraphOccupationIdentifier.id).join(OccupationTaxonomy, OccupationTaxonomy.id == GraphOccupationIdentifier.taxonomy_id)
                                     .where(GraphOccupationIdentifier.occupation_id == node.id, OccupationTaxonomy.scheme == t0.scheme, OccupationTaxonomy.edition != t0.edition))
                    if clash is not None:
                        key = canonical_occupation_id(source=f"{t0.scheme}@{t0.edition}", source_occupation_id=resolved[0][1]["code"])
                        node = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == key))
                if node is None:
                    node = GraphOccupation(occupation_key=key, canonical_label=label[:300], legacy_keys=sorted(set(legacy_keys)))
                    s.add(node)
                    s.flush()
            for t, i in resolved:
                hit = s.scalar(select(GraphOccupationIdentifier).where(GraphOccupationIdentifier.taxonomy_id == t.id, GraphOccupationIdentifier.native_code == i["code"]))
                if hit is None:
                    s.add(GraphOccupationIdentifier(occupation_id=node.id, taxonomy_id=t.id, native_code=i["code"], native_label=(i.get("native_label") or label)[:300],
                                                    source_ref=source_ref, provenance=provenance or {}))
                elif hit.occupation_id != node.id:
                    raise IdentityConflict("an identifier already belongs to a different occupation")
            for lk in legacy_keys:
                if lk not in (node.legacy_keys or []):
                    node.legacy_keys = sorted({*(node.legacy_keys or []), lk})
            s.flush()
            out = _occ(node)
            if own:
                s.commit()
            return out
        except IntegrityError as exc:
            if own:
                s.rollback()
            raise IdentityConflict("identifier or key already exists") from exc
        except Exception:
            if own:
                s.rollback()
            raise
        finally:
            if own:
                s.close()

    def get(self, occupation_key: str) -> dict[str, Any] | None:
        with self._sf() as s:
            o = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == occupation_key))
            return _occ(o) if o else None

    def identifiers(self, occupation_key: str) -> list[dict[str, Any]]:
        with self._sf() as s:
            rows = s.execute(select(GraphOccupationIdentifier, OccupationTaxonomy).join(OccupationTaxonomy, OccupationTaxonomy.id == GraphOccupationIdentifier.taxonomy_id)
                             .join(GraphOccupation, GraphOccupation.id == GraphOccupationIdentifier.occupation_id).where(GraphOccupation.occupation_key == occupation_key)
                             .order_by(OccupationTaxonomy.scheme, OccupationTaxonomy.edition, GraphOccupationIdentifier.native_code)).all()
            return [{"scheme": t.scheme, "edition": t.edition, "native_code": i.native_code, "native_label": i.native_label, "status": i.status, "source_ref": i.source_ref} for i, t in rows]

    def find_by_identifier(self, scheme: str, code: str, edition: str | None = None) -> list[dict[str, Any]]:
        """Nodes holding ``code`` in ``scheme``. With no edition, EVERY edition is searched and the caller sees which edition matched; nothing is merged across editions."""
        with self._sf() as s:
            stmt = (select(GraphOccupation, OccupationTaxonomy).join(GraphOccupationIdentifier, GraphOccupationIdentifier.occupation_id == GraphOccupation.id)
                    .join(OccupationTaxonomy, OccupationTaxonomy.id == GraphOccupationIdentifier.taxonomy_id)
                    .where(OccupationTaxonomy.scheme == scheme, GraphOccupationIdentifier.native_code == code))
            if edition is not None:
                stmt = stmt.where(OccupationTaxonomy.edition == edition)
            return [{**_occ(o), "scheme": t.scheme, "edition": t.edition} for o, t in s.execute(stmt.order_by(OccupationTaxonomy.edition)).all()]

    def find_by_label(self, label: str) -> list[dict[str, Any]]:
        """Exact, case-insensitive label match across canonical labels and native labels. Same-titled occupations in different taxonomies remain DIFFERENT nodes."""
        low = (label or "").strip().lower()
        if not low:
            return []
        with self._sf() as s:
            ids = set(s.scalars(select(GraphOccupation.id).where(func.lower(GraphOccupation.canonical_label) == low)))
            ids |= set(s.scalars(select(GraphOccupationIdentifier.occupation_id).where(func.lower(GraphOccupationIdentifier.native_label) == low)))
            return [_occ(o) for o in s.scalars(select(GraphOccupation).where(GraphOccupation.id.in_(ids)).order_by(GraphOccupation.occupation_key))] if ids else []

    def find_by_legacy_key(self, key: str) -> dict[str, Any] | None:
        with self._sf() as s:
            o = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == key))
            if o is None:
                o = s.scalar(select(GraphOccupation).where(cast(GraphOccupation.legacy_keys, String).like(f'%{json.dumps(key)}%')))
            return _occ(o) if o else None

    # ------------------------------------------------------------------------------------------------------ relationships
    def add_relationship(self, from_key: str, to_key: str, *, relationship_type: str, basis: str, mapping_status: str, from_taxonomy: tuple[str, str], to_taxonomy: tuple[str, str],
                         source_ref: str = "", limitations: str | None = None, qualification_status: str = "unqualified", _session=None) -> dict[str, Any]:
        """Create a governed relationship. Rules: valid vocabulary; a VERIFIED mapping needs a registered ``source_ref`` and basis ``source_provided``; ``equivalent`` can never
        rest on a derived rule; a derived rule can never be VERIFIED; each endpoint must actually hold an identifier in the stated taxonomy edition; an existing relationship with a
        different status is a ``ConflictingMapping`` (never overwritten); an identical one is returned unchanged."""
        if relationship_type not in E.REL_TYPES_ or basis not in E.REL_BASES_ or mapping_status not in E.MAPPING_STATUSES_ or qualification_status not in E.QUALIFICATION_:
            raise GraphError("invalid relationship value")
        if from_key == to_key:
            raise GraphError("an occupation cannot relate to itself")
        if mapping_status == "verified" and (not source_ref or basis != "source_provided"):
            raise GraphError("a verified mapping needs a source-provided basis and a source")
        if relationship_type == "equivalent" and basis == "derived_rule":
            raise GraphError("equivalence cannot rest on a derived rule")
        if basis == "derived_rule" and not (limitations or "").strip():
            raise GraphError("a derived rule must state its limitation")
        own = _session is None
        s = _session or self._sf()
        try:
            a = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == from_key))
            b = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == to_key))
            if a is None or b is None:
                raise GraphError("both occupations must exist")
            if source_ref and s.scalar(select(GlobalSource.id).where(GlobalSource.source_id == source_ref)) is None:
                raise GraphError("the source is not registered")
            ta, tb = self._taxonomy(s, *from_taxonomy), self._taxonomy(s, *to_taxonomy)
            for node, tax in ((a, ta), (b, tb)):
                if s.scalar(select(GraphOccupationIdentifier.id).where(GraphOccupationIdentifier.occupation_id == node.id, GraphOccupationIdentifier.taxonomy_id == tax.id)) is None:
                    raise GraphError("an endpoint holds no identifier in the stated taxonomy edition")
            current = list(s.scalars(select(GraphOccupationRelationship).where(
                GraphOccupationRelationship.from_occupation_id == a.id, GraphOccupationRelationship.to_occupation_id == b.id, GraphOccupationRelationship.superseded.is_(False))))
            for ex in current:
                if (ex.relationship_type, ex.mapping_status) != (relationship_type, mapping_status):
                    raise ConflictingMapping("a different mapping for this pair already exists")     # disagreement is reported, never resolved by overwriting
            for ex in current:
                if ex.source_ref == source_ref:
                    return self._rel(s, ex)                                                         # identical statement: idempotent
            rel = GraphOccupationRelationship(from_occupation_id=a.id, to_occupation_id=b.id, from_taxonomy_id=ta.id, to_taxonomy_id=tb.id, relationship_type=relationship_type, basis=basis,
                                              mapping_status=mapping_status, qualification_status=qualification_status, source_ref=source_ref, limitations=limitations)
            s.add(rel)
            s.flush()
            out = self._rel(s, rel)
            if own:
                s.commit()
            return out
        except IntegrityError as exc:
            if own:
                s.rollback()
            raise GraphError("relationship violates a graph constraint") from exc
        except Exception:
            if own:
                s.rollback()
            raise
        finally:
            if own:
                s.close()

    @staticmethod
    def _rel(s, r: GraphOccupationRelationship) -> dict[str, Any]:
        a = s.get(GraphOccupation, r.from_occupation_id)
        b = s.get(GraphOccupation, r.to_occupation_id)
        ta, tb = s.get(OccupationTaxonomy, r.from_taxonomy_id), s.get(OccupationTaxonomy, r.to_taxonomy_id)
        return {"from_key": a.occupation_key, "to_key": b.occupation_key, "relationship_type": r.relationship_type, "basis": r.basis, "mapping_status": r.mapping_status,
                "qualification_status": r.qualification_status, "source_ref": r.source_ref, "limitations": r.limitations, "superseded": bool(r.superseded),
                "from_taxonomy": (ta.scheme, ta.edition), "to_taxonomy": (tb.scheme, tb.edition)}

    def relationships(self, occupation_key: str, *, direction: str = "out", include_superseded: bool = False) -> list[dict[str, Any]]:
        with self._sf() as s:
            node = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == occupation_key))
            if node is None:
                return []
            col = GraphOccupationRelationship.from_occupation_id if direction == "out" else GraphOccupationRelationship.to_occupation_id
            stmt = select(GraphOccupationRelationship).where(col == node.id)
            if not include_superseded:
                stmt = stmt.where(GraphOccupationRelationship.superseded.is_(False))
            return [self._rel(s, r) for r in s.scalars(stmt.order_by(GraphOccupationRelationship.id))]

    def supersede_relationship(self, from_key: str, to_key: str) -> int:
        """Mark the current relationship for a pair superseded (history is kept); a corrected one can then be added."""
        with self._sf() as s:
            a = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == from_key))
            b = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == to_key))
            if a is None or b is None:
                return 0
            n = 0
            for r in s.scalars(select(GraphOccupationRelationship).where(GraphOccupationRelationship.from_occupation_id == a.id, GraphOccupationRelationship.to_occupation_id == b.id,
                                                                         GraphOccupationRelationship.superseded.is_(False))):
                r.superseded = True
                n += 1
            s.commit()
            return n

    def conflicts(self) -> list[dict[str, Any]]:
        """Pairs whose non-superseded statements DISAGREE on type or mapping status (normally impossible through ``add_relationship``, which refuses them; this surfaces any that
        entered another way). Agreeing statements from several sources are corroboration, not conflict."""
        with self._sf() as s:
            rows = s.execute(select(GraphOccupationRelationship.from_occupation_id, GraphOccupationRelationship.to_occupation_id,
                                    func.count(func.distinct(GraphOccupationRelationship.relationship_type + "|" + GraphOccupationRelationship.mapping_status)))
                             .where(GraphOccupationRelationship.superseded.is_(False)).group_by(GraphOccupationRelationship.from_occupation_id, GraphOccupationRelationship.to_occupation_id)
                             .having(func.count(func.distinct(GraphOccupationRelationship.relationship_type + "|" + GraphOccupationRelationship.mapping_status)) > 1)).all()
            return [{"from_id": a, "to_id": b, "distinct_statements": n} for a, b, n in rows]

    def counts(self) -> dict[str, int]:
        with self._sf() as s:
            return {"occupations": s.scalar(select(func.count()).select_from(GraphOccupation)) or 0,
                    "identifiers": s.scalar(select(func.count()).select_from(GraphOccupationIdentifier)) or 0,
                    "relationships": s.scalar(select(func.count()).select_from(GraphOccupationRelationship)) or 0}

    def bulk(self, fn) -> Any:
        """Run ``fn(graph_session_api)`` in ONE transaction: any failure rolls the whole batch back (no partial import)."""
        with self._sf() as s:
            try:
                out = fn(s)
                s.commit()
                return out
            except Exception:
                s.rollback()
                raise
