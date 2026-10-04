"""Minimum-cohort suppression (P10B-W10.12). An ENGINEERING privacy control, not an anonymisation guarantee and not a legal threshold.

* A candidate-derived cell is shown only when its DISTINCT-CANDIDATE cohort reaches ``REPORTING_MIN_COHORT``. A suppressed cell carries ``value = None`` and
  never the real count, a "<5" marker or a range.
* A rate is shown only when its DENOMINATOR cohort qualifies.
* Partitions (by model, plan, category...) get SECONDARY suppression: when exactly one bucket is suppressed the smallest remaining bucket is suppressed too,
  so a displayed grand total cannot reveal the single hidden bucket by subtraction. Residual limitation: differencing across two overlapping periods is not
  prevented by this control.
"""

from __future__ import annotations

from typing import Any, Sequence

from src.reporting.definitions import (
    REPORTING_MIN_COHORT, STATE_AVAILABLE, STATE_NOT_CAPTURED, STATE_PARTIAL, STATE_SUPPRESSED, STATE_UNAVAILABLE,
)


def qualifies(cohort: int | None) -> bool:
    return cohort is not None and cohort >= REPORTING_MIN_COHORT


def metric(metric_id: str, label: str, value: Any, *, cohort: int | None = None, unit: str = "count", coverage: str = "", note: str = "",
           partial: bool = False, state: str | None = None, operational: bool = False) -> dict:
    """One metric. ``cohort`` is the distinct-candidate count behind it (never returned). ``operational`` metrics skip candidate suppression."""
    if state is not None:                                      # explicit unavailable / not_captured
        return {"metric_id": metric_id, "label": label, "figure": None, "unit": unit, "state": state, "coverage": coverage, "note": note}
    if not operational and (not qualifies(cohort) or value is None):      # a None candidate value is a suppressed rate, never a quiet zero
        return {"metric_id": metric_id, "label": label, "figure": None, "unit": unit, "state": STATE_SUPPRESSED, "coverage": coverage, "note": note}
    return {"metric_id": metric_id, "label": label, "figure": value, "unit": unit, "state": STATE_PARTIAL if partial else STATE_AVAILABLE, "coverage": coverage, "note": note}


def unavailable(metric_id: str, label: str, note: str, coverage: str = "") -> dict:
    return metric(metric_id, label, None, state=STATE_UNAVAILABLE, note=note, coverage=coverage)


def not_captured(metric_id: str, label: str, note: str, coverage: str = "") -> dict:
    return metric(metric_id, label, None, state=STATE_NOT_CAPTURED, note=note, coverage=coverage)


def rate(numerator: int, denominator: int, *, cohort: int | None = None) -> float | None:
    """A percentage, or None when it would disclose a small group: the DENOMINATOR cohort must qualify, and neither the numerator nor its complement may be a
    small non-zero count (a 3-of-6 rate would reveal that exactly 3 candidates did the thing)."""
    cohort = denominator if cohort is None else cohort
    if not qualifies(cohort) or denominator <= 0:
        return None
    rest = denominator - numerator
    if 0 < numerator < REPORTING_MIN_COHORT or 0 < rest < REPORTING_MIN_COHORT:
        return None
    return round(100.0 * numerator / denominator, 1)


def cell(value: Any, *, cohort: int | None = None, operational: bool = False) -> dict:
    if not operational and not qualifies(cohort):
        return {"figure": None, "suppressed": True}
    return {"figure": value, "suppressed": False}


def partition(buckets: Sequence[dict[str, Any]], *, operational: bool = False) -> list[dict]:
    """``buckets``: [{"label", "values": [..], "cohort": int}]. Returns rows with ``cells`` after primary + secondary suppression."""
    flags = [(not operational) and not qualifies(b["cohort"]) for b in buckets]
    if not operational and sum(flags) == 1:                    # secondary suppression: never leave exactly one hidden bucket
        visible = [(b["cohort"], i) for i, (b, f) in enumerate(zip(buckets, flags)) if not f]
        if visible:
            flags[min(visible)[1]] = True
    rows = []
    for b, hidden in zip(buckets, flags):
        cells = [{"figure": None, "suppressed": True} for _ in b["values"]] if hidden else [{"figure": v, "suppressed": False} for v in b["values"]]
        rows.append({"label": b["label"], "cells": cells})
    return rows
