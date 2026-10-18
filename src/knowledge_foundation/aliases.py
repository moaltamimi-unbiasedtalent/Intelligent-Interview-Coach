"""Language-aware occupation aliases on the P10C-A canonical graph (GKB-3). One authority: aliases attach to existing ``graph_occupations`` nodes; there is no second occupation
store. Rules (service-validated AND database-constrained where a CHECK is possible):

* The original text is preserved; normalized and folded keys are derived (``normalize.py``).
* Language ``und`` means UNKNOWN. A known language must state its evidence basis (source-declared, source-file, fixture-declared, curated-manual); no language is ever guessed.
* An official alias type needs a registered source with a KNOWN origin (an unregistered or unknown-origin source can never make an alias "official"). A new alias is always
  ``unqualified``; ``qualified`` needs a named actor and a non-fixture, known-origin source.
* A synthetic-fixture source's aliases are stored but are never evidence-eligible.
* Two occupations may share an alias (that produces AMBIGUOUS in the resolver); one occupation may hold several aliases per language; the same alias may differ by taxonomy edition.
  Duplicates and conflicts are reported explicitly, never merged."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation import enums as E
from src.knowledge_foundation.normalize import NORMALIZATION_VERSION, UNKNOWN_LANGUAGE, detect_script, fold_label, normalize_label, normalize_language_tag
from src.persistence import (ALIAS_LANGUAGE_BASES, ALIAS_OFFICIAL_TYPES, ALIAS_TYPES, GlobalSource, GraphOccupation, GraphOccupationAlias, OccupationTaxonomy, QUALIFICATION_STATUSES)

__all__ = ["AliasStore", "AliasError"]


class AliasError(ValueError):
    """An alias rule was violated. Messages never contain source or candidate content."""


def _source_origin(s, source_ref: str) -> str | None:
    if not source_ref:
        return None
    return s.scalar(select(GlobalSource.origin).where(GlobalSource.source_id == source_ref))


def _row(a: GraphOccupationAlias, key: str | None = None, origin: str | None = None) -> dict[str, Any]:
    return {"id": a.id, "alias_text": a.alias_text, "normalized_text": a.normalized_text, "folded_text": a.folded_text, "language": a.language, "language_basis": a.language_basis,
            "script": a.script, "alias_type": a.alias_type, "source_ref": a.source_ref, "edition_ref": a.edition_ref, "qualification_status": a.qualification_status, "status": a.status,
            "context_terms": list(a.context_terms or []), "normalization_version": a.normalization_version, "occupation_key": key, "source_origin": origin,
            "evidence_eligible_origin": origin in E.EVIDENCE_ORIGINS, "country_applicability": [c for c in (a.provenance or {}).get("country_applicability", [])],
            "relationship": (a.provenance or {}).get("relationship"), "limitation": (a.provenance or {}).get("limitation")}


class AliasStore:
    def __init__(self, session_factory, *, reviewer_check=None) -> None:
        self._sf = session_factory
        self._reviewer_check = reviewer_check          # production wiring: verifies the actor is an active alias reviewer (see qualification_review.reviewer_check_for)

    # ------------------------------------------------------------------------------------------------------ writes
    def add_alias(self, occupation_key: str, text: str, *, language: str | None = None, language_basis: str | None = None, alias_type: str = "unknown", source_ref: str = "",
                  taxonomy: tuple[str, str] | None = None, context_terms: Iterable[str] = (), provenance: dict | None = None, valid_from: datetime | None = None,
                  valid_to: datetime | None = None, _session=None) -> dict[str, Any]:
        text = (text or "").strip()
        if not text or len(text) > 300:
            raise AliasError("an alias needs 1 to 300 characters")
        normalized = normalize_label(text)
        if not normalized:
            raise AliasError("an alias must contain at least one letter or digit")
        if alias_type not in ALIAS_TYPES:
            raise AliasError("unknown alias type")
        try:
            lang = normalize_language_tag(language)
        except ValueError as exc:
            raise AliasError(str(exc)) from exc
        basis = language_basis or "unknown"
        if basis not in ALIAS_LANGUAGE_BASES:
            raise AliasError("unknown language basis")
        if lang == UNKNOWN_LANGUAGE and basis != "unknown":
            raise AliasError("a language basis needs a language")
        if lang != UNKNOWN_LANGUAGE and basis == "unknown":
            raise AliasError("a known language must state the evidence basis (it is never guessed)")
        if basis in ("source_declared", "source_file") and not source_ref:
            raise AliasError("a source-based language basis needs a source")
        own = _session is None
        s = _session or self._sf()
        try:
            occ = s.scalar(select(GraphOccupation).where(GraphOccupation.occupation_key == occupation_key))
            if occ is None:
                raise AliasError("unknown occupation")
            origin = _source_origin(s, source_ref)
            if source_ref and origin is None:
                raise AliasError("the source is not registered")
            if alias_type in ALIAS_OFFICIAL_TYPES and (not source_ref or origin in (None, "unknown")):
                raise AliasError("an official alias needs a registered source with a known origin")
            if basis == "fixture_declared" and origin != "synthetic_fixture":
                raise AliasError("a fixture-declared language needs a synthetic fixture source")
            tax_id, edition_ref = None, ""
            if taxonomy is not None:
                t = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == taxonomy[0], OccupationTaxonomy.edition == (taxonomy[1] or "unknown")))
                if t is None:
                    raise AliasError("unknown taxonomy edition: register it first")
                tax_id, edition_ref = t.id, f"{t.scheme}@{t.edition}"
            hit = s.scalar(select(GraphOccupationAlias).where(
                GraphOccupationAlias.occupation_id == occ.id, GraphOccupationAlias.normalized_text == normalized, GraphOccupationAlias.language == lang,
                GraphOccupationAlias.alias_type == alias_type, GraphOccupationAlias.source_ref == source_ref, GraphOccupationAlias.edition_ref == edition_ref))
            if hit is None:
                hit = GraphOccupationAlias(occupation_id=occ.id, alias_text=text, normalized_text=normalized, folded_text=fold_label(normalized), normalization_version=NORMALIZATION_VERSION,
                                           language=lang, language_basis=basis, script=detect_script(text), alias_type=alias_type, source_ref=source_ref, taxonomy_id=tax_id,
                                           edition_ref=edition_ref, context_terms=sorted({normalize_label(c) for c in context_terms if normalize_label(c)}),
                                           provenance=provenance or {}, valid_from=valid_from, valid_to=valid_to)
                s.add(hit)
                s.flush()
            out = _row(hit, occupation_key, origin)
            if own:
                s.commit()
            return out
        except IntegrityError as exc:
            if own:
                s.rollback()
            raise AliasError("the alias violates a database constraint") from exc
        except Exception:
            if own:
                s.rollback()
            raise
        finally:
            if own:
                s.close()

    def set_qualification(self, alias_id: int, status: str, *, actor_user_id: int | None) -> dict[str, Any]:
        """Move an alias through ``unqualified`` / ``engineering_checked`` / ``qualified``. ``qualified`` needs a named actor and a known, non-fixture source origin. Audited in the
        alias provenance history. Never callable from a candidate request path."""
        if status not in QUALIFICATION_STATUSES:
            raise AliasError("unknown qualification status")
        with self._sf() as s:
            a = s.get(GraphOccupationAlias, alias_id)
            if a is None:
                raise AliasError("unknown alias")
            origin = _source_origin(s, a.source_ref)
            if status == "qualified" and (actor_user_id is None or origin not in E.EVIDENCE_ORIGINS):
                raise AliasError("qualification needs a named reviewer and a source of known, non-fixture origin")
            if status == "qualified" and self._reviewer_check is not None and not self._reviewer_check(actor_user_id):
                raise AliasError("qualification needs an active reviewer account holding the knowledge approval permission")
            hist = list((a.provenance or {}).get("qualification_history", []))
            hist.append({"from": a.qualification_status, "to": status, "actor_user_id": actor_user_id})
            a.provenance = {**(a.provenance or {}), "qualification_history": hist}
            a.qualification_status = status
            s.commit()
            return _row(a, None, origin)

    def add_review_note(self, alias_id: int, note: dict) -> dict[str, Any]:
        """Append an ENGINEERING review note (never a qualification) to the alias provenance. Idempotent per note version."""
        with self._sf() as s:
            a = s.get(GraphOccupationAlias, alias_id)
            if a is None:
                raise AliasError("unknown alias")
            notes = [n for n in (a.provenance or {}).get("engineering_reviews", []) if n.get("version") != note.get("version")] + [note]
            a.provenance = {**(a.provenance or {}), "engineering_reviews": notes}
            s.commit()
            return _row(a, None, _source_origin(s, a.source_ref))

    def annotate_scope(self, alias_id: int, *, relationship: str, limitation: str | None) -> dict[str, Any]:
        """Engineering annotation of the alias scope (relationship vocabulary and caveat text); never changes the qualification status. The earlier values are kept in the history."""
        with self._sf() as s:
            a = s.get(GraphOccupationAlias, alias_id)
            if a is None:
                raise AliasError("unknown alias")
            p = dict(a.provenance or {})
            if (p.get("relationship"), p.get("limitation")) != (relationship, limitation):
                hist = list(p.get("scope_history", [])) + [{"relationship": p.get("relationship"), "limitation": p.get("limitation")}]
                a.provenance = {**p, "relationship": relationship, "limitation": limitation, "scope_history": hist}
                s.commit()
            return _row(a, None, _source_origin(s, a.source_ref))

    def retire_alias(self, alias_id: int, *, reason: str, actor_user_id: int | None = None) -> dict[str, Any]:
        """Revoke an alias: its status becomes ``deprecated`` so lookups (and so the resolver) stop using it. Nothing is deleted; the decision is kept in the alias provenance history."""
        if not (reason or "").strip():
            raise AliasError("a revocation needs a reason")
        with self._sf() as s:
            a = s.get(GraphOccupationAlias, alias_id)
            if a is None:
                raise AliasError("unknown alias")
            hist = list((a.provenance or {}).get("status_history", []))
            hist.append({"from": a.status, "to": "deprecated", "actor_user_id": actor_user_id, "reason": reason[:300]})
            a.provenance = {**(a.provenance or {}), "status_history": hist}
            a.status = "deprecated"
            s.commit()
            return _row(a, None, _source_origin(s, a.source_ref))

    # ------------------------------------------------------------------------------------------------------ reads
    def lookup(self, text: str, *, folded: bool = False, include_inactive: bool = False) -> list[dict[str, Any]]:
        """All aliases (every language) whose exact normalized key (or, with ``folded``, tolerant key) equals the normalized ``text``. Index-backed; never scans all occupations."""
        n = normalize_label(text)
        if not n:
            return []
        col = GraphOccupationAlias.folded_text if folded else GraphOccupationAlias.normalized_text
        key = fold_label(n) if folded else n
        with self._sf() as s:
            stmt = (select(GraphOccupationAlias, GraphOccupation.occupation_key, GraphOccupation.canonical_label, GlobalSource.origin)
                    .join(GraphOccupation, GraphOccupation.id == GraphOccupationAlias.occupation_id)
                    .outerjoin(GlobalSource, GlobalSource.source_id == GraphOccupationAlias.source_ref)
                    .where(col == key))
            if not include_inactive:
                stmt = stmt.where(GraphOccupationAlias.status == "current")
            rows = s.execute(stmt.order_by(GraphOccupation.occupation_key, GraphOccupationAlias.id)).all()
            return [{**_row(a, k, o), "canonical_label": lbl} for a, k, lbl, o in rows]

    def aliases_for(self, occupation_key: str) -> list[dict[str, Any]]:
        with self._sf() as s:
            rows = s.execute(select(GraphOccupationAlias, GlobalSource.origin).join(GraphOccupation, GraphOccupation.id == GraphOccupationAlias.occupation_id)
                             .outerjoin(GlobalSource, GlobalSource.source_id == GraphOccupationAlias.source_ref).where(GraphOccupation.occupation_key == occupation_key)
                             .order_by(GraphOccupationAlias.language, GraphOccupationAlias.normalized_text, GraphOccupationAlias.id)).all()
            return [_row(a, occupation_key, o) for a, o in rows]

    def shared_aliases(self) -> list[dict[str, Any]]:
        """Normalized labels (per language) held by more than one occupation: each can legitimately produce AMBIGUOUS."""
        with self._sf() as s:
            rows = s.execute(select(GraphOccupationAlias.normalized_text, GraphOccupationAlias.language, func.count(func.distinct(GraphOccupationAlias.occupation_id)))
                             .group_by(GraphOccupationAlias.normalized_text, GraphOccupationAlias.language)
                             .having(func.count(func.distinct(GraphOccupationAlias.occupation_id)) > 1).order_by(GraphOccupationAlias.normalized_text, GraphOccupationAlias.language)).all()
            return [{"normalized_text": n, "language": lang, "occupations": c} for n, lang, c in rows]

    def conflicts(self) -> list[dict[str, Any]]:
        """A conflict is stricter than sharing: ONE source edition states the same OFFICIAL label for different occupations. Reported, never resolved automatically."""
        with self._sf() as s:
            rows = s.execute(select(GraphOccupationAlias.source_ref, GraphOccupationAlias.edition_ref, GraphOccupationAlias.normalized_text, GraphOccupationAlias.language,
                                    func.count(func.distinct(GraphOccupationAlias.occupation_id)))
                             .where(GraphOccupationAlias.alias_type.in_(ALIAS_OFFICIAL_TYPES))
                             .group_by(GraphOccupationAlias.source_ref, GraphOccupationAlias.edition_ref, GraphOccupationAlias.normalized_text, GraphOccupationAlias.language)
                             .having(func.count(func.distinct(GraphOccupationAlias.occupation_id)) > 1)).all()
            return [{"source_ref": r[0], "edition_ref": r[1], "normalized_text": r[2], "language": r[3], "occupations": r[4]} for r in rows]

    def counts(self) -> dict[str, Any]:
        with self._sf() as s:
            by_lang = dict(s.execute(select(GraphOccupationAlias.language, func.count()).group_by(GraphOccupationAlias.language)).all())
            total = s.scalar(select(func.count()).select_from(GraphOccupationAlias)) or 0
            return {"aliases": total, "by_language": dict(sorted(by_lang.items()))}
