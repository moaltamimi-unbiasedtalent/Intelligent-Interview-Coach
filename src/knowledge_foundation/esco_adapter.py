"""Version-aware multilingual ESCO adapter contract (GKB-4) and the gated alias importer.

* ``plan_esco_labels`` is READ-ONLY: it parses a labels file and reports what an import WOULD do against the graph. It persists nothing, so it may be run on a local file for
  assessment without any approval (the P10C-A rule: assessment is not import).
* ``import_esco_labels`` / ``import_legacy_aliases`` persist. They go through the SOURCE REGISTRY and cannot be bypassed: ``production`` mode needs ``can_ingest(source)`` (approved
  for ingestion, verified licence, non-fixture origin); ``fixture`` mode needs a registered SYNTHETIC-FIXTURE source and stores labels that can never be evidence. Every import is one
  transaction (all or nothing), idempotent, edition-explicit and language-explicit. No file is downloaded and no label is translated, inferred or invented.
* Language is never guessed: it comes from the caller (for a file, the ``occupations_<language>.csv`` name) and is stored with its evidence basis.

State today (documented, not hidden): the local ESCO file is the English 1.2.1 release and its source (`esco`) is LICENSING PENDING, so a production import is refused until the
owner approves the source; no other language file has been acquired."""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from sqlalchemy import select

from src.knowledge_foundation.aliases import AliasError, AliasStore
from src.knowledge_foundation.codes import normalize_native_code
from src.knowledge_foundation.graph import GraphError, OccupationGraph
from src.knowledge_foundation.normalize import normalize_language_tag
from src.persistence import GraphOccupation

__all__ = ["SourceNotApproved", "EscoLabelRow", "LabelImportReport", "read_esco_labels_csv", "language_from_filename", "plan_esco_labels", "import_esco_labels",
           "read_legacy_aliases", "import_legacy_aliases"]

_FILE_LANG = re.compile(r"occupations_([a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?)\.csv$", re.IGNORECASE)


class SourceNotApproved(GraphError):
    """The source registry does not permit this import (approval, licence or origin)."""


@dataclass(frozen=True)
class EscoLabelRow:
    uri: str
    preferred: str
    alternatives: tuple[str, ...]
    hidden: tuple[str, ...]
    isco_group: str | None
    status: str | None


@dataclass
class LabelImportReport:
    rows: int = 0
    occupations_matched: int = 0
    skipped_unknown_occupation: int = 0
    skipped_empty_label: int = 0
    labels_seen: int = 0
    aliases_added: int = 0
    aliases_already_present: int = 0
    mode: str = "plan"
    notes: list[str] = field(default_factory=list)


def language_from_filename(path: str | Path) -> str | None:
    m = _FILE_LANG.search(Path(path).name)
    return normalize_language_tag(m.group(1)) if m else None


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(x.strip() for x in (value or "").replace("\r", "").split("\n") if x.strip())


def read_esco_labels_csv(path: str | Path) -> list[EscoLabelRow]:
    """Parse an ESCO occupations CSV (UTF-8). ISCO group strings keep their digits exactly. Duplicate URIs are kept as separate rows (the planner and importer deduplicate)."""
    out: list[EscoLabelRow] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            uri = (r.get("conceptUri") or "").strip()
            if not uri or (r.get("conceptType") or "Occupation").strip() != "Occupation":
                continue
            out.append(EscoLabelRow(uri, (r.get("preferredLabel") or "").strip(), _split(r.get("altLabels")), _split(r.get("hiddenLabels")),
                                    normalize_native_code("isco", r.get("iscoGroup")) or None, (r.get("status") or None)))
    return out


def _labels(row: EscoLabelRow) -> Iterator[tuple[str, str]]:
    if row.preferred:
        yield row.preferred, "official_preferred"
    for a in row.alternatives:
        yield a, "official_alternative"
    for h in row.hidden:
        yield h, "source_synonym"                           # ESCO hidden labels are search terms, not display labels


def plan_esco_labels(graph: OccupationGraph, rows: Iterable[EscoLabelRow], *, esco_edition: str = "1.2.1") -> LabelImportReport:
    """Read-only assessment against the graph. Writes nothing."""
    rep = LabelImportReport(mode="plan")
    seen: set[str] = set()
    for r in rows:
        rep.rows += 1
        if r.uri in seen:
            continue
        seen.add(r.uri)
        if not graph.find_by_identifier("esco", r.uri, esco_edition):
            rep.skipped_unknown_occupation += 1
            continue
        rep.occupations_matched += 1
        for _text, _t in _labels(r):
            rep.labels_seen += 1
    return rep


def _require_source(registry, source_ref: str, mode: str) -> None:
    src = registry.get(source_ref)
    if src is None:
        raise SourceNotApproved("the source is not registered")
    if mode == "production":
        if not registry.can_ingest(source_ref):
            raise SourceNotApproved("the source is not approved for ingestion (approval, verified licence and a genuine origin are required)")
    elif mode == "fixture":
        if src["origin"] != "synthetic_fixture":
            raise SourceNotApproved("fixture mode needs a synthetic-fixture source")
    else:
        raise SourceNotApproved("unknown import mode")


def import_esco_labels(graph: OccupationGraph, aliases: AliasStore, registry, rows: Iterable[EscoLabelRow], *, language: str, esco_edition: str = "1.2.1",
                       source_ref: str = "esco", mode: str = "production", language_from_file: bool = True) -> LabelImportReport:
    """Persist ESCO labels of ONE language for ONE edition as aliases of existing ESCO occupation nodes (the node must already exist; none is created from a label). One
    transaction. ``language_from_file`` records the language evidence as the source file (production) - fixtures record ``fixture_declared``."""
    _require_source(registry, source_ref, mode)
    lang = normalize_language_tag(language)
    if lang == "und":
        raise AliasError("a label import needs an explicit language")
    basis = "fixture_declared" if mode == "fixture" else ("source_file" if language_from_file else "curated_manual")
    rep = LabelImportReport(mode=mode)
    seen: set[str] = set()
    with graph._sf() as s:                                                         # one session = one transaction
        try:
            for r in rows:
                rep.rows += 1
                if r.uri in seen:
                    continue
                seen.add(r.uri)
                hits = graph.find_by_identifier("esco", r.uri, esco_edition)
                if not hits:
                    rep.skipped_unknown_occupation += 1
                    continue
                rep.occupations_matched += 1
                key = hits[0]["occupation_key"]
                for text, atype in _labels(r):
                    rep.labels_seen += 1
                    if not text.strip():
                        rep.skipped_empty_label += 1
                        continue
                    before = s.scalar(select(GraphOccupation.id).where(GraphOccupation.occupation_key == key))
                    existing = len(_existing(s, before, text, lang, atype, source_ref, f"esco@{esco_edition}"))
                    aliases.add_alias(key, text, language=lang, language_basis=basis, alias_type=atype, source_ref=source_ref, taxonomy=("esco", esco_edition),
                                      provenance={"import": "esco_labels", "mode": mode}, _session=s)
                    if existing:
                        rep.aliases_already_present += 1
                    else:
                        rep.aliases_added += 1
            s.commit()
        except Exception:
            s.rollback()
            raise
    return rep


def _existing(s, occ_id, text, lang, atype, source_ref, edition_ref):
    from src.knowledge_foundation.normalize import normalize_label
    from src.persistence import GraphOccupationAlias as A
    return s.scalars(select(A.id).where(A.occupation_id == occ_id, A.normalized_text == normalize_label(text), A.language == lang, A.alias_type == atype,
                                        A.source_ref == source_ref, A.edition_ref == edition_ref)).all()


# ----------------------------------------------------------------------------------------------------------------------------------------------- legacy store
def read_legacy_aliases(db_path: str | Path) -> Iterator[tuple[str, str, str]]:
    """Yield ``(legacy occupation code, alias, source_id)`` from a legacy ``occupation_aliases`` table, opened READ-ONLY and immutable (the store is never modified)."""
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        yield from con.execute("select occupation_code, alias, source_id from occupation_aliases order by rowid")
    finally:
        con.close()


def import_legacy_aliases(graph: OccupationGraph, aliases: AliasStore, registry, legacy_rows: Iterable[tuple[str, str, str]], *, source_languages: dict[str, tuple[str, str]],
                          mode: str = "production") -> LabelImportReport:
    """Persist legacy aliases as ``legacy_alias`` rows of the graph nodes they belong to (matched through the node's legacy key). ``source_languages`` maps a legacy source id to
    ``(language, evidence basis)`` ONLY where reliable evidence exists; a source absent from the map is stored with language UNKNOWN. Gated by the registry per source."""
    rep = LabelImportReport(mode=mode)
    approved: dict[str, bool] = {}
    nodes: dict[str, dict | None] = {}                                                  # one graph lookup per distinct legacy code
    with graph._sf() as s:
        try:
            for code, alias, source_id in legacy_rows:
                rep.rows += 1
                if source_id not in approved:
                    _require_source(registry, source_id, mode)               # raises for an unapproved source: nothing is persisted
                    approved[source_id] = True
                if code not in nodes:
                    nodes[code] = graph.find_by_legacy_key(code)
                node = nodes[code]
                if node is None:
                    rep.skipped_unknown_occupation += 1
                    continue
                lang, basis = source_languages.get(source_id, (None, None))
                before = len(_existing(s, s.scalar(select(GraphOccupation.id).where(GraphOccupation.occupation_key == node["occupation_key"])), alias,
                                       normalize_language_tag(lang), "legacy_alias", source_id, ""))
                aliases.add_alias(node["occupation_key"], alias, language=lang, language_basis=basis, alias_type="legacy_alias", source_ref=source_id,
                                  provenance={"import": "legacy_aliases", "mode": mode}, _session=s)
                rep.labels_seen += 1
                if before:
                    rep.aliases_already_present += 1
                else:
                    rep.aliases_added += 1
            s.commit()
        except Exception:
            s.rollback()
            raise
    return rep
