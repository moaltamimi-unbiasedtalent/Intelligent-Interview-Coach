"""Nested-window differencing guard (05E, PRIV-DIFF). An ENGINEERING privacy control, not anonymisation and not a legal threshold.

THE ATTACK. Cohort suppression hides a figure whose distinct-candidate cohort is below ``REPORTING_MIN_COHORT``. The standard windows are NESTED (7d within 30d within
90d within all time). A reader allowed to read two windows of the same metric can subtract them: 30d = 9 and 7d = 6 are both above the floor, but 9 - 6 = 3 is the
cohort of the days outside the 7d window, a small group that suppression was meant to hide.

THE MITIGATION (this module). For one report and window, the same report is computed for every NARROWER standard window on the same clock, recording each metric's and
each partition bucket's distinct-candidate cohort. A figure of the requested window is then treated as below the floor (and the report is recomputed so every derived
figure, ranking and secondary suppression follows) when, for ANY narrower window in which both are visible, the cohort of the difference is a small non-zero number
(``0 < outer - inner < REPORTING_MIN_COHORT``). A difference of zero is not hidden: "nobody else" is not a small group. The narrower window stays visible; the wider
one is the figure that would expose the complement.

WHAT IS NOT PREVENTED (documented residual risk, stated in the Admin privacy note and in docs/production/execution/evidence/05E_EVIDENCE.md):
* Windows are relative to the request time. A reader who requests the SAME window at two different moments gets two slightly different windows and can difference
  them; each pair is checked only against the standard nested windows of one request, not against earlier calls. Mitigations outside this module: the reports
  are read-only, aggregate-only, permission-gated (``platform.reports.read``) and Admin-only, and Admin access is audited.
* Disjoint windows (the builder's ``previous_period`` comparison) are summed by the reader into a window that is not itself served (e.g. 30d minus the 7d minus the
  previous 7d); only the nested pairs are checked.
* Partitions whose buckets overlap (a candidate can use several workflows or models) make a hidden-bucket cohort sum an UPPER bound of the distinct hidden candidates.
* Cohort differences are exact for "event within window" cohorts, which is what every cohort metric here is; a metric defined differently must say so in its definition.
* The 03D1 Command Center computes its own tiles and is not covered by this guard (its figures are also cohort-suppressed).
* Several Admin readers can pool what each was shown; nothing technical prevents that.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from src.reporting import suppression as S
from src.reporting.definitions import DEFAULT_PERIOD, REPORTING_MIN_COHORT

# Narrow to wide. ``all_time`` contains every other window.
NESTED_ORDER: tuple[str, ...] = ("7d", "30d", "90d", "all_time")


def narrower(period: str | None) -> list[str]:
    p = period or DEFAULT_PERIOD
    return list(NESTED_ORDER[:NESTED_ORDER.index(p)]) if p in NESTED_ORDER else []


def keys_to_hide(outer: dict, inners: dict[str, dict]) -> frozenset:
    """Keys of ``outer`` whose difference from some narrower window is a small non-zero cohort (both figures visible)."""
    hide = set()
    for key, (c_out, visible_out) in outer.items():
        if not visible_out:
            continue
        for rec in inners.values():
            got = rec.get(key)
            if got is None:
                continue
            c_in, visible_in = got
            if visible_in and 0 < c_out - c_in < REPORTING_MIN_COHORT:
                hide.add(key)
                break
    return frozenset(hide)


def guarded(compute: Callable[[str], Any], period: str | None) -> Any:
    """Run ``compute(period)`` under the nested-window guard and return its (possibly recomputed) result. ``compute`` must be deterministic for one clock and call the
    ``suppression`` helpers for every cohort figure; it is called several times (once per narrower window, once recording, and once more only when something must be
    hidden)."""
    p = period or DEFAULT_PERIOD
    inner_periods = narrower(p)
    if not inner_periods:
        return compute(p)
    with S.recording() as outer_rec:
        result = compute(p)
    inners: dict[str, dict] = {}
    for q in inner_periods:
        with S.recording() as rec:
            compute(q)
        inners[q] = rec
    hide = keys_to_hide(outer_rec, inners)
    if not hide:
        return result
    with S.hiding(hide):
        return compute(p)


def guard_report(method: Callable) -> Callable:
    """Decorator for the public ``ReportingService`` report methods: ``method(self, period, *args, **kwargs)`` becomes nested-window guarded."""

    @wraps(method)
    def wrapper(self, period: str | None = None, *args, **kwargs):
        return guarded(lambda p: method(self, p, *args, **kwargs), period)

    wrapper.__wrapped_unguarded__ = method          # type: ignore[attr-defined]  (tests call the unguarded method to show what the attack would have seen)
    return wrapper
