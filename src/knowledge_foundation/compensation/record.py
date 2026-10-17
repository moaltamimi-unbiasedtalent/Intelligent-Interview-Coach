"""CompensationRecordV2 (GKB-5): a typed, source-governed compensation measurement linked to a canonical occupation. PROPOSED ENGINEERING DESIGN (owner approval of the detailed schema
is pending). Unknown is explicit: pay basis and measure default to ``unknown`` and a record with an unknown basis or measure is never comparable with another; a missing value is a status,
never zero. Nothing is converted: the original currency, pay period, gross/net basis and statistic travel with the value."""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.knowledge_foundation.compensation.money import from_units, scale_of, to_units, validate_currency

__all__ = ["CompensationRecordV2", "record_key_for", "row_values", "from_row"]

PayPeriod = Literal["hourly", "daily", "weekly", "monthly", "annual"]
PayBasis = Literal["gross", "net", "unknown"]
Measure = Literal["median", "mean", "percentile", "unknown"]
ValueStatus = Literal["reported", "suppressed", "not_available"]
OccupationLevel = Literal["detailed", "broad", "unknown"]
GeographyLevel = Literal["national", "regional", "eu_aggregate", "unknown"]
EvidenceClass = Literal["C1", "C2", "C3"]
EarningsConcept = Literal["unknown", "individual_earnings", "employment_income", "wage_statistic", "household_income", "formal_sector_compensation"]
PopulationScope = Literal["unknown", "all_workers", "employees", "formal_sector", "full_time_employees"]
EvidenceMethod = Literal["unknown", "survey", "administrative_records", "census", "other_documented"]


class CompensationRecordV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- occupation identity (the canonical node is resolved from the NATIVE code in an explicit taxonomy edition; never from a title)
    taxonomy_scheme: str
    taxonomy_edition: str
    native_code: str
    occupation_level: OccupationLevel = "unknown"
    # --- geography (explicit; never derived from a language)
    country: str
    region: str | None = None
    geography_level: GeographyLevel = "unknown"
    # --- measurement (original units preserved)
    currency: str
    pay_period: PayPeriod
    pay_basis: PayBasis = "unknown"
    measure: Measure = "unknown"
    percentile: int = 0
    earnings_concept: EarningsConcept = "unknown"         # what the figure MEASURES (never combined across concepts)
    population_scope: PopulationScope = "unknown"         # who it covers
    evidence_method: EvidenceMethod = "unknown"           # how it was produced
    value_status: ValueStatus = "reported"
    value: Decimal | None = None
    lower_value: Decimal | None = None
    upper_value: Decimal | None = None
    bounds_semantic: str = "unknown"
    # --- source and time
    source_ref: str
    source_edition: str
    reference_year: int
    reference_period: str | None = None
    publication_date: datetime | None = None
    data_vintage: str = ""
    limitations: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        return validate_currency(v)

    @field_validator("country")
    @classmethod
    def _country(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not (2 <= len(v) <= 8) or not v.isalpha():
            raise ValueError("country must be an explicit code")
        return v

    @field_validator("native_code", "source_ref", "source_edition", "taxonomy_scheme", "taxonomy_edition")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("required")
        return v.strip()

    @model_validator(mode="after")
    def _consistent(self):
        if self.value_status == "reported":
            if self.value is None or self.value <= 0:
                raise ValueError("a reported value must be positive")
        elif self.value is not None or self.lower_value is not None or self.upper_value is not None:
            raise ValueError("a suppressed or unavailable measurement carries no amount")
        if (self.lower_value is None) != (self.upper_value is None):
            raise ValueError("bounds come as a pair")
        if self.lower_value is not None and (self.lower_value <= 0 or self.upper_value < self.lower_value):
            raise ValueError("invalid bounds")
        if (self.measure == "percentile") != (self.percentile > 0) or not 0 <= self.percentile < 100:
            raise ValueError("a percentile is only valid for the percentile measure")
        if not 1900 <= self.reference_year <= 2200:
            raise ValueError("invalid reference year")
        return self

    # ---------------------------------------------------------------------------------------------------------------------- derived
    @property
    def region_key(self) -> str:
        return (self.region or "").strip()

    def scale(self) -> int:
        return max([scale_of(x) for x in (self.value, self.lower_value, self.upper_value) if x is not None] or [0])

    def comparability_key(self) -> tuple:
        """Two measurements are only comparable when EVERYTHING that defines the quantity matches. An unknown pay basis or measure is never comparable (``None`` marks it)."""
        return (self.country, self.region_key, self.geography_level, self.currency, self.pay_period, self.pay_basis if self.pay_basis != "unknown" else None,
                (self.measure, self.percentile) if self.measure != "unknown" else None, self.reference_year, self.earnings_concept, self.population_scope, self.evidence_method)


def record_key_for(r: CompensationRecordV2, taxonomy_id: int) -> str:
    """Deterministic identity of a measurement: the natural key, never the value (so a re-import with a different value is detected as a conflict, not stored as a new record)."""
    parts = [r.source_ref, r.source_edition, str(taxonomy_id), r.native_code, r.country, r.region_key, str(r.reference_year), r.pay_period, r.currency, r.pay_basis, r.measure,
             str(r.percentile), r.data_vintage]
    parts += [f"{k}={v}" for k, v in (("c", r.earnings_concept), ("p", r.population_scope), ("m", r.evidence_method)) if v != "unknown"]      # unknown keeps the P10C-C key unchanged
    return "cv2_" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:40]


def row_values(r: CompensationRecordV2) -> dict[str, Any]:
    s = r.scale()
    return {"amount_scale": s, "value_units": to_units(r.value, s) if r.value is not None else None,
            "lower_units": to_units(r.lower_value, s) if r.lower_value is not None else None, "upper_units": to_units(r.upper_value, s) if r.upper_value is not None else None}


def from_row(row) -> dict[str, Any]:
    """A plain dict view of a stored row with exact Decimal amounts (the storage columns are integers)."""
    return {"id": row.id, "record_key": row.record_key, "native_code": row.native_code, "occupation_level": row.occupation_level, "country": row.country, "region": row.region_key or None,
            "geography_level": row.geography_level, "currency": row.currency, "pay_period": row.pay_period, "pay_basis": row.pay_basis, "measure": row.measure, "percentile": row.percentile, "earnings_concept": row.earnings_concept, "population_scope": row.population_scope, "evidence_method": row.evidence_method,
            "value_status": row.value_status, "value": from_units(row.value_units, row.amount_scale), "lower_value": from_units(row.lower_units, row.amount_scale),
            "upper_value": from_units(row.upper_units, row.amount_scale), "bounds_semantic": row.bounds_semantic, "source_ref": row.source_ref, "source_edition": row.source_edition,
            "publisher": row.publisher, "dataset_name": row.dataset_name, "source_url": row.source_url, "reference_year": row.reference_year, "reference_period": row.reference_period,
            "publication_date": row.publication_date, "data_vintage": row.data_vintage, "evidence_class": row.evidence_class, "precedence_category": row.precedence_category,
            "qualification_status": row.qualification_status, "status": row.status, "limitations": row.limitations, "link_basis": row.link_basis, "occupation_id": row.occupation_id,
            "taxonomy_id": row.taxonomy_id}
