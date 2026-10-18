"""Salary comparison safety (GKB-14). Three modes, one contract.

* NOMINAL: two measurements are compared only when EVERYTHING that defines the quantity matches and is KNOWN: currency, pay period, statistic (and percentile), gross or net basis,
  earnings concept, population, evidence method, reference year, evidence class, occupation specificity and granularity, and geographic level. The result is the exact Decimal difference
  (no ratios, no rounding, no annualisation) with caveats; anything else is NOT_COMPARABLE with every reason, never a direct salary difference. An unknown value matches nothing.
* FX-CONVERTED and PURCHASING-POWER: NOT_CONFIGURED. Approved sources and methodology are PENDING OWNER DECISION D-10. These functions never read, fetch, invent or apply a rate or factor
  and never call a provider (the provider interfaces in ``resolver.py`` are not used here)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

__all__ = ["ComparisonStatus", "NominalComparison", "compare_nominal", "compare_fx", "compare_ppp"]


class ComparisonStatus(str, Enum):
    COMPARABLE_NOMINAL = "comparable_nominal"
    NOT_COMPARABLE = "not_comparable"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


@dataclass
class NominalComparison:
    status: ComparisonStatus
    reasons: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    currency: str | None = None
    pay_period: str | None = None
    difference: Decimal | None = None          # second minus first, exact
    operational: bool = False                  # true only when BOTH sides are operational

    def to_public_dict(self) -> dict:
        d = dict(self.__dict__)
        d["status"] = self.status.value
        d["difference"] = str(self.difference) if self.difference is not None else None
        return d


def compare_nominal(a, b) -> NominalComparison:
    """Compare two ``CompensationResponse`` objects."""
    reasons: list[str] = []
    for name, r in (("first", a), ("second", b)):
        if r.outcome.value != "evidence":
            reasons.append(f"{name}_has_no_evidence_{r.outcome.value}")
    if reasons:
        return NominalComparison(ComparisonStatus.UNAVAILABLE, reasons)
    checks = (("currency", a.currency, b.currency, False), ("pay_period", a.pay_period, b.pay_period, False), ("statistic", (a.measure, a.percentile), (b.measure, b.percentile), False),
              ("pay_basis", a.pay_basis, b.pay_basis, True), ("earnings_concept", a.earnings_concept, b.earnings_concept, True), ("population_scope", a.population_scope, b.population_scope, True),
              ("evidence_method", a.evidence_method, b.evidence_method, True), ("reference_year", a.reference_year, b.reference_year, False), ("evidence_class", a.evidence_class, b.evidence_class, False),
              ("occupation_specificity", a.occupation_specificity, b.occupation_specificity, False), ("occupation_granularity", a.occupation_level, b.occupation_level, False),
              ("geography_level", a.geography_level, b.geography_level, False))
    for name, x, y, must_be_known in checks:
        if must_be_known and "unknown" in (x, y):
            reasons.append(f"{name}_unknown")
        elif x != y:
            reasons.append(f"{name}_differs")
    out = NominalComparison(ComparisonStatus.NOT_COMPARABLE, reasons, currency=a.currency if a.currency == b.currency else None, pay_period=a.pay_period if a.pay_period == b.pay_period else None)
    if "currency_differs" in reasons:
        out.caveats.append("fx_comparison_not_configured")
    if reasons:
        return out
    out.status = ComparisonStatus.COMPARABLE_NOMINAL
    out.difference = Decimal(b.value) - Decimal(a.value)
    out.operational = bool(a.operational and b.operational)
    if a.country != b.country:
        out.caveats.append("different_countries: labour markets, taxation and cost of living differ; nominal only")
    if not out.operational:
        out.caveats.append("non_operational_evidence")
    return out


def _not_configured(mode: str) -> NominalComparison:
    return NominalComparison(ComparisonStatus.NOT_CONFIGURED, [f"{mode}_not_configured_no_approved_source_or_methodology_D-10"])


def compare_fx(a, b, *, provider=None, as_of=None) -> NominalComparison:
    """FX-converted comparison: always NOT_CONFIGURED. ``provider`` and ``as_of`` are accepted so a future approved implementation keeps this signature; neither is used."""
    return _not_configured("fx_converted")


def compare_ppp(a, b, *, provider=None, as_of=None) -> NominalComparison:
    """Purchasing-power comparison: always NOT_CONFIGURED (see ``compare_fx``)."""
    return _not_configured("ppp_adjusted")
