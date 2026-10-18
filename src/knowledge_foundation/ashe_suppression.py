"""P10C-F2B: the machine-readable ONS ASHE suppression record (correction of 19 December 2025) and the guard that keeps suppressed measurements MISSING. The rules are conservative: where a
record could fall inside the notice (UK SOC code 33, 331 or 3312, an ANNUAL pay period, the UK or a named affected geography) it is refused unless the table is provably outside the notice.
Nothing here reconstructs, estimates or fills a value, and weekly pay is not touched by this notice."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = ["rules", "is_suppressed", "violates", "assert_respected", "SuppressionViolation"]

RULES_PATH = Path(__file__).parent / "data" / "ashe_suppression_rules.json"


class SuppressionViolation(ValueError):
    """A record would restore a measurement the publisher suppressed. Carries no value."""


@lru_cache(maxsize=1)
def rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().replace("-", " ").split())


def is_suppressed(occupation_code: str, *, pay_period: str, geography: str | None, table: str | None = None, measure_kind: str | None = None) -> bool:
    """True when the notice covers this cell. An unknown table or measure kind is treated as possibly covered (never as safe)."""
    r = rules()
    if (occupation_code or "").strip() not in r["occupation_codes"] or pay_period not in r["pay_periods_affected"]:
        return False
    geo = _norm(geography) or "uk"
    if geo not in {_norm(g) for g in r["geographies"]}:
        return False
    if table is not None and str(table) not in r["tables"]:
        return False
    return measure_kind is None or measure_kind in r["measure_kinds"]


def violates(rec) -> bool:
    """Does a ``CompensationRecordV2`` of the ASHE source carry a value the notice suppressed? Only reported values can violate (a missing measurement is the required state)."""
    if getattr(rec, "source_ref", None) != "ons_ashe" or getattr(rec, "value_status", "reported") != "reported":
        return False
    prov = rec.provenance or {}
    return is_suppressed(rec.native_code, pay_period=rec.pay_period, geography=rec.region or "UK", table=prov.get("table"), measure_kind=prov.get("measure_kind"))


def assert_respected(records) -> None:
    bad = [r.native_code for r in records if violates(r)]
    if bad:
        raise SuppressionViolation(f"{len(bad)} record(s) would restore suppressed ASHE annual measurements")
