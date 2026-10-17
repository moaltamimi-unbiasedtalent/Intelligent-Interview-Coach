"""Geography coverage matrix (GKB-1). Country-level and explicit. TARGETED is not operational: six ordered levels per dimension, nothing is QUALIFIED without a qualification
record, and the overall level is the WEAKEST dimension. Language support lists the languages of the available SOURCES and never determines or implies a country."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.knowledge_foundation import enums as E
from src.persistence import GeographyCoverage

__all__ = ["CoverageMatrix", "CoverageError", "MATRIX_PATH", "OPERATIONAL_LEVELS"]

MATRIX_PATH = Path(__file__).parent / "data" / "coverage_matrix.json"
OPERATIONAL_LEVELS = ("implemented", "qualified")
_DIMENSIONS = ("taxonomy_level", "crosswalk_level", "compensation_level", "outlook_level")


class CoverageError(ValueError):
    pass


def _row(r: GeographyCoverage) -> dict[str, Any]:
    d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
    d["overall_level"] = E.weakest_level(*(d[k] for k in _DIMENSIONS))
    return d


class CoverageMatrix:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def upsert(self, code: str, label: str, group: str, **levels: Any) -> dict[str, Any]:
        if group not in E.COVERAGE_GROUPS_:
            raise CoverageError("invalid coverage group")
        for k in _DIMENSIONS:
            if k in levels and levels[k] not in E.COVERAGE_LEVELS_:
                raise CoverageError(f"invalid level for {k}")
        with self._sf() as s:
            r = s.scalar(select(GeographyCoverage).where(GeographyCoverage.geography_code == code))
            if r is None:
                r = GeographyCoverage(geography_code=code, label=label, coverage_group=group, source_languages=[], source_ids=[])
                s.add(r)
            r.label, r.coverage_group = label, group
            for k in (*_DIMENSIONS, "source_languages", "source_ids", "limitations"):
                if k in levels:
                    setattr(r, k, levels[k])
            s.commit()
            return _row(r)

    def get(self, code: str) -> dict[str, Any] | None:
        with self._sf() as s:
            r = s.scalar(select(GeographyCoverage).where(GeographyCoverage.geography_code == code))
            return _row(r) if r else None

    def all(self) -> list[dict[str, Any]]:
        with self._sf() as s:
            return [_row(r) for r in s.scalars(select(GeographyCoverage).order_by(GeographyCoverage.geography_code))]

    def is_operational(self, code: str, dimension: str) -> bool:
        """True only when the dimension is IMPLEMENTED or QUALIFIED. TARGETED, SOURCE_IDENTIFIED and DATA_AVAILABLE are never reported as operational coverage."""
        r = self.get(code)
        return bool(r and dimension in _DIMENSIONS and r[dimension] in OPERATIONAL_LEVELS)

    def summary(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {d: {lv: 0 for lv in E.COVERAGE_LEVELS_} for d in (*_DIMENSIONS, "overall_level")}
        for r in self.all():
            for d in out:
                out[d][r[d]] += 1
        return out

    def seed(self, path: Path = MATRIX_PATH) -> int:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for row in data["geographies"]:
            self.upsert(row["code"], row["label"], row["group"], **{k: row[k] for k in (*_DIMENSIONS, "source_languages", "source_ids", "limitations") if k in row})
        return len(data["geographies"])


def build_default_matrix() -> dict[str, Any]:
    """The matrix shipped with the repository, derived from the P10C-0 evidence (see the P10C-A document). Pure and deterministic; ``coverage_matrix.json`` must equal this output."""
    eu27 = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus", "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France",
            "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
            "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden"}
    eea = {"IS": "Iceland", "LI": "Liechtenstein", "NO": "Norway"}
    sa = {"AR": "Argentina", "BO": "Bolivia", "CL": "Chile", "CO": "Colombia", "EC": "Ecuador", "GY": "Guyana", "PY": "Paraguay", "PE": "Peru", "SR": "Suriname", "UY": "Uruguay", "VE": "Venezuela"}
    rows: list[dict[str, Any]] = []

    def add(code, label, group, tax, cross, comp, outlook, langs, sources, limits):
        rows.append({"code": code, "label": label, "group": group, "taxonomy_level": tax, "crosswalk_level": cross, "compensation_level": comp, "outlook_level": outlook,
                     "source_languages": langs, "source_ids": sources, "limitations": limits})
    eu_note = ("EU-level classifications (ESCO, ISCO-08) are held locally in English only and apply to every member state; there is no national occupation, compensation or "
               "outlook source for this country. Eurostat earnings is declared in the manifest but no rows are held. ILOSTAT is only a named future fallback.")
    for code, label in eu27.items():
        if code == "DE":
            add(code, label, "eu27", "implemented", "targeted", "source_identified", "source_identified", ["en", "de"], ["esco", "isco08", "kldb", "ba_entgeltatlas", "eurostat_occ_vacancy"],
                "KldB 2010 is held (no crosswalk to ISCO). The K1 German compensation set is a bounded engineering draft (not reviewed); Entgeltatlas is licence-pending and credential-gated. Not qualified.")
        else:
            add(code, label, "eu27", "data_available", "data_available", "targeted", "source_identified", ["en"], ["esco", "isco08", "eurostat_occ_vacancy", "cedefop_clssi"], eu_note)
    add("GB", "United Kingdom", "uk", "source_identified", "targeted", "data_available", "targeted", ["en"], ["ons_ashe", "isco08"],
        "ONS ASHE (527 rows, weekly GBP) is held but keyed by UK SOC 2020, which is not acquired and not yet in the approved list; no crosswalk to ESCO, ISCO or O*NET exists. No outlook source.")
    for code, label in eea.items():
        add(code, label, "eea_non_eu", "data_available", "data_available", "targeted", "targeted", ["en"], ["esco", "isco08"],
            "Only EU-level classifications (ESCO, ISCO-08) are held; no national source is identified or assessed.")
    add("CH", "Switzerland", "switzerland", "data_available", "targeted", "targeted", "targeted", ["en"], ["isco08"],
        "Only the global ISCO-08 reference is held; no Swiss national classification or source is identified or assessed.")
    add("US", "United States", "us", "implemented", "source_identified", "data_available", "data_available", ["en"], ["onet", "bls_ooh", "bls_projections", "bls_oews", "opm_occupational_groups"],
        "O*NET (1,016 occupations) and BLS data are held and the strongest coverage. Native SOC and O*NET-SOC codes are not persisted in the runtime store, so compensation and outlook records are not joined to occupations by code (P10C-B). Not qualified.")
    add("CA", "Canada", "canada", "source_identified", "targeted", "source_identified", "targeted", [], [],
        "NOC (Statistics Canada) and the Job Bank wage data were identified in planning only; nothing is acquired, assessed for licence, or held. P10C-D added an adapter contract and a province and territory vocabulary (synthetic fixtures only): no occupation node, crosswalk or compensation record exists, so no level is raised and nothing is qualified.")
    add("MX", "Mexico", "mexico", "source_identified", "targeted", "targeted", "targeted", [], [], "SINCO (INEGI) was identified in planning only; nothing is acquired or assessed for licence. P10C-D added an adapter contract and a state vocabulary (synthetic fixtures only): no occupation node, crosswalk or compensation record exists, so no level is raised and nothing is qualified.")
    add("BR", "Brazil", "brazil", "source_identified", "targeted", "targeted", "targeted", [], [], "CBO was identified in planning only; nothing is acquired or assessed for licence. P10C-D added an adapter contract and a state vocabulary (synthetic fixtures only): no occupation node, crosswalk or compensation record exists, so no level is raised and nothing is qualified.")
    for code, label in sa.items():
        comp = "source_identified" if code in ("CL", "CO") else "targeted"
        note = {"CL": "Chile ESI was named in planning as a national broad (C2) example; nothing is acquired or assessed for licence.",
                "CO": "Colombia DANE GEIH was named in planning as a national broad (C2) example; nothing is acquired or assessed for licence."}.get(
            code, "No national source is identified. ILOSTAT is only a named future international fallback (not acquired).")
        add(code, label, "south_america_other", "targeted", "targeted", comp, "targeted", [], [], note)
    return {"schema": "geography_coverage/1", "levels": list(E.COVERAGE_LEVELS_), "geographies": rows}
