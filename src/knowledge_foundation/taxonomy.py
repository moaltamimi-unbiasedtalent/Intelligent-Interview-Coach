"""Taxonomy namespaces and editions (GKB-2). A native occupation code means nothing without its scheme AND edition; an edition that was not recorded is the explicit value
``unknown`` and two different editions (or an unknown one) are never treated as equivalent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.knowledge_foundation import enums as E
from src.persistence import OccupationTaxonomy

__all__ = ["TaxonomyError", "TaxonomyCatalogue", "editions_compatible", "validate_code"]

CATALOGUE_PATH = Path(__file__).parent / "data" / "taxonomy_catalogue.json"


class TaxonomyError(ValueError):
    pass


def editions_compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two taxonomy rows are compatible only when they are the SAME scheme and the SAME KNOWN edition. An unknown edition is compatible with nothing (not even another unknown
    edition of the same scheme), and a superseded edition is not compatible with its successor without an explicit mapping."""
    return a["scheme"] == b["scheme"] and a["edition"] == b["edition"] and a["edition"] != "unknown"


def validate_code(taxonomy: dict[str, Any], code: str) -> bool:
    pattern = taxonomy.get("code_pattern")
    return bool(code) and (not pattern or re.fullmatch(pattern, code) is not None)


def _row(t: OccupationTaxonomy) -> dict[str, Any]:
    return {c.name: getattr(t, c.name) for c in t.__table__.columns}


class TaxonomyCatalogue:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def ensure(self, scheme: str, edition: str = "unknown", *, label: str | None = None, status: str = "unknown", acquisition_status: str = "not_acquired",
               code_pattern: str | None = None, geographies: list[str] | None = None, notes: str | None = None, source_row_id: int | None = None) -> dict[str, Any]:
        """Idempotent. An existing row is never silently re-labelled with a different status or acquisition state (use ``update`` for that)."""
        if scheme not in E.SCHEMES or status not in E.TAXONOMY_STATUSES_ or acquisition_status not in E.ACQUISITION:
            raise TaxonomyError("invalid taxonomy value")
        if not edition:
            edition = "unknown"
        if code_pattern:
            re.compile(code_pattern)
        with self._sf() as s:
            t = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == edition))
            if t is None:
                t = OccupationTaxonomy(scheme=scheme, edition=edition, label=label, status=status, acquisition_status=acquisition_status, code_pattern=code_pattern,
                                       geographies=geographies or [], notes=notes, source_row_id=source_row_id)
                s.add(t)
                s.commit()
            return _row(t)

    def update(self, scheme: str, edition: str, **fields: Any) -> dict[str, Any]:
        with self._sf() as s:
            t = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == edition))
            if t is None:
                raise TaxonomyError("unknown taxonomy edition")
            if "status" in fields and fields["status"] not in E.TAXONOMY_STATUSES_ or "acquisition_status" in fields and fields["acquisition_status"] not in E.ACQUISITION:
                raise TaxonomyError("invalid taxonomy value")
            for k in ("label", "status", "acquisition_status", "code_pattern", "geographies", "notes", "source_row_id"):
                if k in fields:
                    setattr(t, k, fields[k])
            s.commit()
            return _row(t)

    def get(self, scheme: str, edition: str = "unknown") -> dict[str, Any] | None:
        with self._sf() as s:
            t = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == edition))
            return _row(t) if t else None

    def editions(self, scheme: str) -> list[dict[str, Any]]:
        with self._sf() as s:
            return [_row(t) for t in s.scalars(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme).order_by(OccupationTaxonomy.edition))]

    def supersede(self, scheme: str, old_edition: str, new_edition: str) -> None:
        """Mark an edition historical and point it at its successor. Codes of the two editions stay separate namespaces: nothing is merged or mapped by this call."""
        with self._sf() as s:
            old = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == old_edition))
            new = s.scalar(select(OccupationTaxonomy).where(OccupationTaxonomy.scheme == scheme, OccupationTaxonomy.edition == new_edition))
            if old is None or new is None or old.id == new.id:
                raise TaxonomyError("both editions must exist and differ")
            old.status, old.superseded_by_id = "historical", new.id
            s.commit()

    def seed(self, path: Path = CATALOGUE_PATH) -> int:
        """Register the catalogue shipped with the repository (statuses recorded from evidence; absent editions are ``unknown``). Idempotent; acquires nothing."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        n = 0
        for t in data["taxonomies"]:
            self.ensure(t["scheme"], t.get("edition", "unknown"), label=t.get("label"), status=t.get("status", "unknown"), acquisition_status=t["acquisition_status"],
                        code_pattern=t.get("code_pattern"), geographies=t.get("geographies", []), notes=t.get("notes"))
            n += 1
        return n
