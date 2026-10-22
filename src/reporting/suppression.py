"""Minimum-cohort suppression (P10B-W10.12). An ENGINEERING privacy control, not an anonymisation guarantee and not a legal threshold.

* A candidate-derived cell is shown only when its DISTINCT-CANDIDATE cohort reaches ``REPORTING_MIN_COHORT``. A suppressed cell carries ``value = None`` and
  never the real count, a "<5" marker or a range.
* A rate is shown only when its DENOMINATOR cohort qualifies.
* Partitions (by model, plan, category...) get SECONDARY suppression: when exactly one bucket is suppressed the smallest remaining bucket is suppressed too,
  so a displayed grand total cannot reveal the single hidden bucket by subtraction. 05E (PRIV-DIFF) adds two mitigations (the residual risk that remains is
  documented in docs/production/execution/evidence/05E_EVIDENCE.md and ``src/reporting/differencing.py``):
  * when TWO OR MORE buckets are hidden, the smallest visible buckets are hidden as well until the hidden buckets together reach the floor, so "total minus visible
    buckets" is never a small hidden group (previously a total minus the visible buckets could equal 1 + 1 + 2);
  * a recorder / hider pair (``recording``, ``hiding``) lets ``differencing`` compare the same report across the nested standard windows and suppress a wider window
    whose difference from a narrower one is a small non-zero cohort. Neither hook changes anything unless ``differencing`` activates it.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Sequence

from src.reporting.definitions import (
    REPORTING_MIN_COHORT, STATE_AVAILABLE, STATE_NOT_CAPTURED, STATE_PARTIAL, STATE_SUPPRESSED, STATE_UNAVAILABLE,
)


# 05E (PRIV-DIFF): optional hooks used ONLY by ``src.reporting.differencing``. ``_REC`` collects (cohort, visible) per metric id and per partition bucket while a report is
# computed; ``_HIDE`` names keys that must be treated as below the floor. Both default to None, in which case nothing below changes behaviour.
_REC: ContextVar[dict | None] = ContextVar("reporting_cohort_recorder", default=None)
_HIDE: ContextVar[frozenset | None] = ContextVar("reporting_forced_suppression", default=None)


@contextmanager
def recording() -> Iterator[dict]:
    """Record ``{key: (cohort, visible)}`` for every non-operational metric and partition bucket produced inside the block (keys: ``("metric", id)`` and ``("cell", scope, label)``)."""
    store: dict = {}
    token = _REC.set(store)
    try:
        yield store
    finally:
        _REC.reset(token)


@contextmanager
def hiding(keys: frozenset) -> Iterator[None]:
    """Treat the named metrics / partition buckets as below the floor while a report is computed (so every derived figure, ranking and secondary suppression follows)."""
    token = _HIDE.set(frozenset(keys))
    try:
        yield
    finally:
        _HIDE.reset(token)


def _forced(key: tuple) -> bool:
    hide = _HIDE.get()
    return hide is not None and key in hide


def _note(key: tuple, cohort: int | None, visible: bool) -> None:
    rec = _REC.get()
    if rec is not None and cohort is not None:
        rec[key] = (int(cohort), bool(visible))


def qualifies(cohort: int | None) -> bool:
    return cohort is not None and cohort >= REPORTING_MIN_COHORT


def metric(metric_id: str, label: str, value: Any, *, cohort: int | None = None, unit: str = "count", coverage: str = "", note: str = "",
           partial: bool = False, state: str | None = None, operational: bool = False) -> dict:
    """One metric. ``cohort`` is the distinct-candidate count behind it (never returned). ``operational`` metrics skip candidate suppression."""
    if state is not None:                                      # explicit unavailable / not_captured
        return {"metric_id": metric_id, "label": label, "figure": None, "unit": unit, "state": state, "coverage": coverage, "note": note}
    if not operational and (not qualifies(cohort) or value is None or _forced(("metric", metric_id))):      # a None candidate value is a suppressed rate, never a quiet zero
        _note(("metric", metric_id), cohort, False)
        return {"metric_id": metric_id, "label": label, "figure": None, "unit": unit, "state": STATE_SUPPRESSED, "coverage": coverage, "note": note}
    if not operational:
        _note(("metric", metric_id), cohort, True)
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


def partition(buckets: Sequence[dict[str, Any]], *, operational: bool = False, scope: str | None = None) -> list[dict]:
    """``buckets``: [{"label", "values": [..], "cohort": int}]. Returns rows with ``cells`` after primary + secondary suppression.

    Secondary suppression (05E): (1) when exactly one bucket is hidden the smallest visible bucket is hidden too; (2) when the hidden buckets TOGETHER are still below the
    floor (two or more small buckets), the smallest visible buckets are hidden one by one until they reach it, so a displayed total minus the visible buckets is
    never a small group. ``scope`` (the table id) only names the buckets for ``differencing``; it never changes the result."""
    flags = [(not operational) and (not qualifies(b["cohort"]) or _forced(("cell", scope, b["label"]))) for b in buckets]
    if not operational and sum(flags) == 1:                    # secondary suppression: never leave exactly one hidden bucket
        visible = [(b["cohort"], i) for i, (b, f) in enumerate(zip(buckets, flags)) if not f]
        if visible:
            flags[min(visible)[1]] = True
    if not operational and sum(flags) >= 2:                    # 05E: a hidden group must itself be at least the floor, or total minus visible would expose it
        while sum(b["cohort"] for b, f in zip(buckets, flags) if f) < REPORTING_MIN_COHORT:
            visible = [(b["cohort"], i) for i, (b, f) in enumerate(zip(buckets, flags)) if not f]
            if not visible:
                break
            flags[min(visible)[1]] = True
    rows = []
    for b, hidden in zip(buckets, flags):
        cells = [{"figure": None, "suppressed": True} for _ in b["values"]] if hidden else [{"figure": v, "suppressed": False} for v in b["values"]]
        if not operational:
            _note(("cell", scope, b["label"]), b["cohort"], not hidden)
        rows.append({"label": b["label"], "cells": cells})
    return rows
