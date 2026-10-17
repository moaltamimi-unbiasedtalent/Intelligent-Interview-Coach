"""Language coverage (GKB-3/GKB-4), reported separately from country coverage (GKB-1). Five independent facts per language: UI-supported, taxonomy-supported, alias-data available,
alias-data qualified, resolver-supported. A UI locale never establishes occupation data; a language never implies a country; nothing is QUALIFIED by this wave."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.knowledge_foundation import enums as E
from src.knowledge_foundation.normalize import normalize_language_tag
from src.persistence import LanguageCoverage

__all__ = ["LanguageCoverageService", "LanguageCoverageError", "COVERAGE_PATH"]

COVERAGE_PATH = Path(__file__).parent / "data" / "language_coverage.json"


class LanguageCoverageError(ValueError):
    pass


def _row(r: LanguageCoverage) -> dict[str, Any]:
    return {"language": r.language, "label": r.label, "ui_supported": bool(r.ui_supported), "taxonomy_level": r.taxonomy_level, "alias_data_level": r.alias_data_level,
            "alias_qualified": bool(r.alias_qualified), "resolver_level": r.resolver_level, "source_ids": list(r.source_ids or []), "limitations": r.limitations}


class LanguageCoverageService:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def upsert(self, language: str, label: str, **fields: Any) -> dict[str, Any]:
        try:
            lang = normalize_language_tag(language)
        except ValueError as exc:
            raise LanguageCoverageError(str(exc)) from exc
        if lang == "und":
            raise LanguageCoverageError("a coverage row needs a concrete language")
        for dim in ("taxonomy_level", "alias_data_level", "resolver_level"):
            if dim in fields and fields[dim] not in E.COVERAGE_LEVELS_:
                raise LanguageCoverageError("unknown coverage level")
            if fields.get(dim) == "qualified":
                raise LanguageCoverageError("qualified coverage needs a qualification record (not available in this wave)")
        if fields.get("alias_qualified"):
            raise LanguageCoverageError("alias qualification needs a reviewer workflow (not available in this wave)")
        with self._sf() as s:
            r = s.scalar(select(LanguageCoverage).where(LanguageCoverage.language == lang))
            if r is None:
                r = LanguageCoverage(language=lang, label=label[:60], source_ids=[])
                s.add(r)
            r.label = label[:60]
            for k in ("ui_supported", "taxonomy_level", "alias_data_level", "resolver_level", "source_ids", "limitations"):
                if k in fields:
                    setattr(r, k, fields[k])
            s.commit()
            return _row(r)

    def get(self, language: str | None) -> dict[str, Any] | None:
        try:
            lang = normalize_language_tag(language)
        except ValueError:
            return None
        with self._sf() as s:
            r = s.scalar(select(LanguageCoverage).where(LanguageCoverage.language == lang))
            return _row(r) if r else None

    def all(self) -> list[dict[str, Any]]:
        with self._sf() as s:
            return [_row(r) for r in s.scalars(select(LanguageCoverage).order_by(LanguageCoverage.language))]

    def resolver_supports(self, language: str | None) -> bool:
        """True when the language has a coverage row whose resolver level is at least ``implemented``. An absent row (or ``und``) is NOT supported."""
        row = self.get(language)
        return bool(row) and E.level_rank(row["resolver_level"]) >= E.level_rank("implemented")

    def summary(self) -> dict[str, Any]:
        rows = self.all()
        return {"languages": len(rows), "ui_supported": sum(1 for r in rows if r["ui_supported"]), "alias_qualified": sum(1 for r in rows if r["alias_qualified"]),
                "taxonomy_level": _count(rows, "taxonomy_level"), "alias_data_level": _count(rows, "alias_data_level"), "resolver_level": _count(rows, "resolver_level")}

    def seed(self, path: Path = COVERAGE_PATH) -> int:
        """Idempotent. Re-seeding refreshes metadata but cannot raise a level above what the committed file states, and never sets a qualified flag."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))["languages"]
        for d in data:
            self.upsert(d["language"], d["label"], ui_supported=d["ui_supported"], taxonomy_level=d["taxonomy_level"], alias_data_level=d["alias_data_level"],
                        resolver_level=d["resolver_level"], source_ids=d["source_ids"], limitations=d["limitations"])
        return len(data)


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return dict(sorted(out.items()))
