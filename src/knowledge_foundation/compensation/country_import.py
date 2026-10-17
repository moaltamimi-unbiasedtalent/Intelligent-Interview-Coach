"""Registry-gated transformation contracts for country taxonomies and official crosswalks (GKB-8 to GKB-10). Persisting goes through the P10C-A source registry and cannot be bypassed:
``production`` mode needs ``can_ingest`` (approved for ingestion, verified licence, non-fixture origin) and a KNOWN taxonomy edition; ``fixture`` mode needs a synthetic-fixture source and
stores nodes that can never be evidence. One transaction, idempotent, edition-explicit; rows are rejected with reason codes (no content). Nothing is downloaded, translated or inferred, and
no crosswalk is manufactured: only rows a registered source STATES can become relationships, and an unknown edition on either side supports no relationship."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from sqlalchemy import select

from src.knowledge_foundation.aliases import AliasError, AliasStore
from src.knowledge_foundation.graph import ConflictingMapping, GraphError, IdentityConflict, OccupationGraph
from src.knowledge_foundation.registry import SourceRegistry
from src.knowledge_foundation.taxonomy import validate_code
from src.persistence import MAPPING_STATUSES, REL_TYPES, OccupationTaxonomy

__all__ = ["CountryImportNotApproved", "CountryImportReport", "import_taxonomy_nodes", "import_crosswalk"]

_UNKNOWN = ("unknown", "")


class CountryImportNotApproved(PermissionError):
    """The source registry does not permit this import. Carries no source content."""


@dataclass
class CountryImportReport:
    mode: str = ""
    rows: int = 0
    added: int = 0
    existing: int = 0
    rejected: int = 0
    rejections: dict[str, int] = field(default_factory=dict)


def _gate(registry: SourceRegistry, source_ref: str, mode: str, editions: Iterable[str]) -> None:
    src = registry.get(source_ref)
    if src is None:
        raise CountryImportNotApproved("the source is not registered")
    if mode == "production":
        if not registry.can_ingest(source_ref):
            raise CountryImportNotApproved("the source is not approved for ingestion (approval, verified licence and a genuine origin are required)")
        if any((e or "").strip().lower() in _UNKNOWN for e in editions):
            raise CountryImportNotApproved("the taxonomy edition must be known for a production import")
    elif mode == "fixture":
        if src["origin"] != "synthetic_fixture":
            raise CountryImportNotApproved("fixture mode needs a synthetic-fixture source")
    else:
        raise CountryImportNotApproved("unknown import mode")


def import_taxonomy_nodes(graph: OccupationGraph, aliases: AliasStore, registry: SourceRegistry, rows: Iterable[Mapping[str, Any]], *, scheme: str, edition: str, source_ref: str,
                          mode: str, language_basis: str | None = None) -> CountryImportReport:
    """Register national taxonomy nodes ``(scheme, edition, native code)``. Row: ``code``, ``label``, optional ``labels`` [{text, language}] (an official label is stored only with an explicit
    language; the language evidence is ``fixture_declared`` in fixture mode or the caller's ``language_basis`` in production). A node is never created from a label."""
    _gate(registry, source_ref, mode, [edition])
    rep = CountryImportReport(mode=mode)
    rej: Counter = Counter()
    seen: set[str] = set()
    with graph._sf() as s:
        tax = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == edition))
        if tax is None:
            raise CountryImportNotApproved("the taxonomy edition is not registered")
        try:
            for row in rows:
                rep.rows += 1
                code = str(row.get("code") if row.get("code") is not None else "").strip()
                label = str(row.get("label") or "").strip()
                if not code or not validate_code({"code_pattern": tax.code_pattern}, code):
                    rej["invalid_native_code"] += 1
                    continue
                if not label:
                    rej["missing_label"] += 1
                    continue
                before = graph.find_by_identifier(scheme, code, edition) or (code in seen)
                seen.add(code)
                try:
                    node = graph.add_occupation(label, [{"scheme": scheme, "edition": edition, "code": code, "native_label": label}], source_ref=source_ref, _session=s)
                except IdentityConflict:
                    rej["identity_conflict"] += 1
                    continue
                rep.existing += 1 if before else 0
                rep.added += 0 if before else 1
                for lab in row.get("labels") or []:
                    lang = lab.get("language")
                    if not lang:
                        rej["label_without_language"] += 1
                        continue
                    basis = "fixture_declared" if mode == "fixture" else (language_basis or "source_file")
                    try:
                        aliases.add_alias(node["occupation_key"], lab["text"], language=lang, language_basis=basis, alias_type="official_preferred", source_ref=source_ref,
                                          taxonomy=(scheme, edition), _session=s)
                    except AliasError:
                        rej["label_rejected"] += 1
            s.commit()
        except Exception:
            s.rollback()
            raise
    rep.rejected, rep.rejections = sum(rej.values()), dict(rej)
    return rep


def import_crosswalk(graph: OccupationGraph, registry: SourceRegistry, rows: Iterable[Mapping[str, Any]], *, source_ref: str, from_taxonomy: tuple[str, str], to_taxonomy: tuple[str, str],
                     mode: str) -> CountryImportReport:
    """Register relationships a registered source STATES. Row: ``from_code``, ``to_code``, ``relationship_type``, ``mapping_status``. Both editions must be known; an equivalence needs a
    VERIFIED statement; a conflicting statement about the same pair is rejected, never overwritten; a RELATED row stays RELATED."""
    _gate(registry, source_ref, mode, [from_taxonomy[1], to_taxonomy[1]])
    rep = CountryImportReport(mode=mode)
    rej: Counter = Counter()
    with graph._sf() as s:
        try:
            for row in rows:
                rep.rows += 1
                if from_taxonomy[1].lower() in _UNKNOWN or to_taxonomy[1].lower() in _UNKNOWN:
                    rej["taxonomy_edition_unknown"] += 1
                    continue
                rtype, status = row.get("relationship_type"), row.get("mapping_status")
                if rtype not in REL_TYPES or status not in MAPPING_STATUSES:
                    rej["invalid_relationship_vocabulary"] += 1
                    continue
                if rtype == "equivalent" and status != "verified":
                    rej["equivalence_requires_a_verified_statement"] += 1
                    continue
                a = graph.find_by_identifier(from_taxonomy[0], str(row.get("from_code", "")).strip(), from_taxonomy[1])
                b = graph.find_by_identifier(to_taxonomy[0], str(row.get("to_code", "")).strip(), to_taxonomy[1])
                if len({h["occupation_key"] for h in a}) != 1:
                    rej["from_code_not_in_graph"] += 1
                    continue
                if len({h["occupation_key"] for h in b}) != 1:
                    rej["to_code_not_in_graph"] += 1
                    continue
                existing = [r for r in graph.relationships(a[0]["occupation_key"]) if r["to_key"] == b[0]["occupation_key"]]
                try:
                    graph.add_relationship(a[0]["occupation_key"], b[0]["occupation_key"], relationship_type=rtype, basis="source_provided", mapping_status=status,
                                           from_taxonomy=from_taxonomy, to_taxonomy=to_taxonomy, source_ref=source_ref, _session=s)
                except ConflictingMapping:
                    rej["conflicting_statement"] += 1
                    continue
                except GraphError:
                    rej["relationship_rejected"] += 1
                    continue
                if existing and any(r["relationship_type"] == rtype and r["mapping_status"] == status and r["source_ref"] == source_ref for r in existing):
                    rep.existing += 1
                else:
                    rep.added += 1
            s.commit()
        except Exception:
            s.rollback()
            raise
    rep.rejected, rep.rejections = sum(rej.values()), dict(rej)
    return rep
