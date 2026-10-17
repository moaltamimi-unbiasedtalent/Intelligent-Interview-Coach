"""Deterministic, idempotent, non-destructive importers for taxonomy data ALREADY HELD locally (GKB-2). They read official files read-only and write only to the graph database
they are given. They never download anything, never touch the legacy runtime stores for writing, and never mark a mapping VERIFIED unless the official file states it AND the target
code exists in the official target structure. Rows that cannot be validated are skipped and reported, never repaired by guesswork.

This wave does NOT run an import against any developer database; tests run on fixtures and a validation run uses a throwaway database."""

from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.copilot.knowledge.canonical import canonical_occupation_id
from src.knowledge_foundation.graph import ConflictingMapping, GraphError, OccupationGraph, occupation_key_for

__all__ = ["EscoRow", "ImportReport", "read_esco_occupations_csv", "read_isco_structure_csv", "register_esco_isco", "assess_legacy_store_mappings"]


@dataclass(frozen=True)
class EscoRow:
    uri: str
    label: str
    isco_code: str
    status: str = ""
    code: str = ""                 # the ESCO dotted code (e.g. 2654.1.7); the LEGACY runtime store derived its occupation ids from this value


@dataclass
class ImportReport:
    esco_rows: int = 0
    esco_nodes: int = 0
    isco_nodes: int = 0
    relationships_verified: int = 0
    skipped_invalid_isco: list[str] = field(default_factory=list)
    skipped_conflicting_duplicates: list[str] = field(default_factory=list)
    identical_duplicates: int = 0
    conflicts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"esco_rows": self.esco_rows, "esco_nodes": self.esco_nodes, "isco_nodes": self.isco_nodes, "relationships_verified": self.relationships_verified,
                "skipped_invalid_isco": len(self.skipped_invalid_isco), "skipped_conflicting_duplicates": len(self.skipped_conflicting_duplicates),
                "identical_duplicates": self.identical_duplicates, "conflicts": len(self.conflicts)}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def read_esco_occupations_csv(path: str | Path) -> list[EscoRow]:
    """The official ESCO ``occupations_en.csv`` (read-only). Codes are kept as the strings the file holds (leading zeros preserved)."""
    text = _decode(Path(path).read_bytes())
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("conceptType", "Occupation") != "Occupation":
            continue
        rows.append(EscoRow(uri=(r.get("conceptUri") or "").strip(), label=(r.get("preferredLabel") or "").strip(), isco_code=(r.get("iscoGroup") or "").strip(), status=(r.get("status") or "").strip(), code=(r.get("code") or "").strip()))
    return rows


def read_isco_structure_csv(path: str | Path, version: str = "ISCO-08") -> dict[str, str]:
    """The official ISCO structure file (read-only) as ``{code: label}`` for ONE version (the file mixes ISCO-08, -88, -68 and -58: rows of other versions are ignored).

    Codes are restored to their official WIDTH per level (major 1, sub-major 2, minor 3, unit 4 characters). The file stores some codes as numbers, which dropped the leading zero of
    the armed-forces groups (official 01, 011 and 0110 appear as 1, 11 and 110); zero-padding to the level width is a deterministic format restoration, not a guess, and the
    restored codes are exactly the ones ESCO publishes (for example 0110). Every restored code is reported by ``tests`` against the official ESCO file."""
    text = _decode(Path(path).read_bytes())
    out: dict[str, str] = {}
    for r in csv.DictReader(io.StringIO(text)):
        if (r.get("ISCO_version") or "").strip() != version:
            continue
        for code_col, label_col, width in (("major", "major_label", 1), ("sub_major", "sub_major_label", 2), ("minor", "minor_label", 3), ("unit", "description", 4)):
            code = (r.get(code_col) or "").strip()
            if code and code.isdigit():
                code = code.zfill(width)
                if code not in out:
                    out[code] = (r.get(label_col) or "").strip()
    return out


def register_esco_isco(graph: OccupationGraph, esco_rows: list[EscoRow], isco_authority: dict[str, str], *, esco_edition: str = "1.2.1", isco_edition: str = "08",
                       esco_source_ref: str = "esco") -> ImportReport:
    """Register ESCO occupations, the ISCO-08 structure and the ESCO -> ISCO relationships in ONE transaction (all or nothing). Relationship: the ESCO occupation is NARROWER than its
    ISCO unit group (``to`` is BROADER), basis source-provided, status VERIFIED because the official file states it and the code exists in the official ISCO structure.
    ESCO rows whose ISCO code is not in the structure, and URIs that appear with conflicting codes, are skipped and reported. Re-running adds nothing."""
    report = ImportReport(esco_rows=len(esco_rows))
    by_uri: dict[str, EscoRow] = {}
    conflicting: set[str] = set()
    for r in esco_rows:
        prev = by_uri.get(r.uri)
        if prev is None:
            by_uri[r.uri] = r
        elif prev.isco_code == r.isco_code:
            report.identical_duplicates += 1
        else:
            conflicting.add(r.uri)
    for uri in sorted(conflicting):
        report.skipped_conflicting_duplicates.append(uri)

    def run(s):
        for code, label in sorted(isco_authority.items()):
            # Legacy identity: the runtime store keyed ISCO nodes by the code WITHOUT its leading zeros. It is kept as a legacy key only where that stripped code is unambiguous (the
            # armed-forces unit groups 0110, 0210, 0310); the six groups whose stripped code collides with another real group (01, 02, 03, 011, 021, 031) get NO legacy key.
            stripped = code.lstrip("0")
            legacy = [canonical_occupation_id(isco_code=stripped)] if (code.startswith("0") and len(code) == 4 and stripped and stripped not in isco_authority) else []
            graph.add_occupation(label or code, [("isco", isco_edition, code)], source_ref="isco08", legacy_keys=legacy, _session=s)
            report.isco_nodes += 1
        for uri in sorted(by_uri):
            r = by_uri[uri]
            if uri in conflicting:
                continue
            if r.isco_code not in isco_authority:
                report.skipped_invalid_isco.append(uri)
                continue
            esco = graph.add_occupation(r.label or uri, [("esco", esco_edition, uri)], source_ref=esco_source_ref,
                                        legacy_keys=[canonical_occupation_id(esco_uri=r.code)] if r.code else [], _session=s)
            report.esco_nodes += 1
            try:
                graph.add_relationship(esco["occupation_key"], occupation_key_for("isco", isco_edition, r.isco_code), relationship_type="broader", basis="source_provided",
                                       mapping_status="verified", from_taxonomy=("esco", esco_edition), to_taxonomy=("isco", isco_edition), source_ref=esco_source_ref,
                                       limitations="ESCO assigns the occupation to an ISCO-08 unit group; the group is broader, not equivalent.", qualification_status="engineering_checked", _session=s)
                report.relationships_verified += 1
            except ConflictingMapping as exc:
                report.conflicts.append(uri)
                raise GraphError("conflicting ESCO to ISCO mapping") from exc

    graph.bulk(run)
    return report


def assess_legacy_store_mappings(roles_db: str | Path, esco_rows: list[EscoRow], isco_authority: dict[str, str]) -> dict[str, Any]:
    """READ-ONLY comparison of the legacy runtime store's ESCO -> ISCO mapping rows against the official files. Opens the store with SQLite ``mode=ro`` and writes nothing.
    Classifies each stored mapping: ``exact`` (matches the official file), ``leading_zero_lost`` (stored code equals the official code without its leading zeros), ``mismatch`` and ``no_official_row``."""
    official = {canonical_occupation_id(esco_uri=r.code): r for r in esco_rows if r.code}      # the legacy store derived ids from the ESCO dotted code
    con = sqlite3.connect(f"file:{Path(roles_db).as_posix()}?mode=ro", uri=True)
    try:
        stored = con.execute("select occupation_code, code from occupation_mappings where scheme='isco'").fetchall()
        isco_nodes = con.execute("select count(*) from occupations where source_id='isco08'").fetchone()[0]
        total = con.execute("select count(*) from occupation_mappings").fetchone()[0]
    finally:
        con.close()
    out = {"stored_mappings": total, "exact": 0, "leading_zero_lost": 0, "mismatch": 0, "no_official_row": 0, "stored_isco_nodes": isco_nodes, "official_isco_codes": len(isco_authority),
           "leading_zero_lost_codes": []}
    for occ, code in stored:
        r = official.get(occ)
        if r is None:
            out["no_official_row"] += 1
        elif r.isco_code == code:
            out["exact"] += 1
        elif r.isco_code.lstrip("0") == code and r.isco_code in isco_authority:
            out["leading_zero_lost"] += 1
            out["leading_zero_lost_codes"].append(f"{code}->{r.isco_code}")
        else:
            out["mismatch"] += 1
    out["leading_zero_lost_codes"] = sorted(set(out["leading_zero_lost_codes"]))
    return out
