"""05E (PRIV-DIFF): differencing attacks on cohort-suppressed Admin reports, the mitigation added, and the residual risk that remains. Offline.

Attack 1, NESTED WINDOWS: subtract a narrower standard window from a wider one (7d within 30d within 90d within all time).
Attack 2, TOTAL VERSUS BUCKETS: subtract the visible buckets of a partition from the visible total (or headline) and read the hidden remainder.
Both are tried against the W10.12 service and the 03E1 builder. Each test first shows the leak on the UNGUARDED computation (so the attack is real), then asserts the shipped
behaviour closes it. The cohort floor (REPORTING_MIN_COHORT = 5) and its existing rules are asserted unchanged."""

from __future__ import annotations

import itertools
import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

import tests.conftest  # noqa: F401  (isolation first)
from src.application import admin_permissions as perm
from src.persistence import AIUsageFact, Base, User, UserFeedback, make_session_factory
from src.reporting import differencing as DF
from src.reporting import report_builder as RB
from src.reporting import suppression as S
from src.reporting.definitions import REPORTING_MIN_COHORT
from src.reporting.service import ReportingService

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)
_SEQ = itertools.count(1)


@pytest.fixture()
def sf():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def svc(sf) -> ReportingService:
    return ReportingService(sf, clock=lambda: NOW)


def add_users(sf, n: int, age_days: float) -> list[int]:
    """n candidates registered ``age_days`` before NOW."""
    ids = []
    call = next(_SEQ)
    with sf() as s:
        for i in range(n):
            t = NOW - timedelta(days=age_days)
            u = User(subject=f"d{call}-{i}", provider="test", email=f"d{call}-{i}@example.test", platform_role="user", status="active", created_at=t, updated_at=t)
            s.add(u)
            s.flush()
            ids.append(u.id)
        s.commit()
    return ids


def add_usage(sf, user_ids: list[int], age_days: float, *, workflow="agent", model="model-a", calls=1) -> None:
    with sf() as s:
        for uid in user_ids:
            s.add(AIUsageFact(usage_key=f"k-{uuid.uuid4().hex}", user_id=uid, workflow=workflow, operation="x", model_id=model, model_calls=calls, cost_source="unavailable",
                              token_coverage="unknown", cost_coverage="unknown", occurred_at=NOW - timedelta(days=age_days), updated_at=NOW - timedelta(days=age_days)))
        s.commit()


def metric(report, section, mid):
    return next(m for m in next(x for x in report["sections"] if x["section_id"] == section)["metrics"] if m["metric_id"] == mid)


def table(report, section, tid):
    return next(t for t in next(x for x in report["sections"] if x["section_id"] == section)["tables"] if t["table_id"] == tid)


def unguarded(method):
    return method.__wrapped_unguarded__


# ===================================================================================================================== the floor itself is unchanged
def test_the_cohort_floor_and_the_existing_primary_rules_are_unchanged():
    assert REPORTING_MIN_COHORT == 5
    assert S.qualifies(5) and not S.qualifies(4) and not S.qualifies(None)
    assert S.metric("m", "m", 4, cohort=4)["state"] == "suppressed" and S.metric("m", "m", 5, cohort=5)["state"] == "available"
    assert S.rate(3, 6) is None and S.rate(0, 6) == 0.0 and S.rate(6, 6) == 100.0 and S.rate(3, 4) is None
    rows = S.partition([{"label": "a", "values": [9], "cohort": 9}, {"label": "b", "values": [2], "cohort": 2}, {"label": "c", "values": [7], "cohort": 7}])
    assert [r["cells"][0]["suppressed"] for r in rows] == [False, True, True]                   # exactly one hidden: the smallest visible is hidden too (unchanged)


# ===================================================================================================================== attack 1: nested windows
def test_attack_nested_windows_would_expose_a_small_group_without_the_guard(sf):
    add_users(sf, 6, age_days=3)                       # inside the 7d window
    add_users(sf, 3, age_days=20)                      # only inside 30d and wider: a group of 3, below the floor
    raw = unguarded(ReportingService.product)
    seven = metric(raw(svc(sf), "7d"), "product", "registrations")["figure"]
    thirty = metric(raw(svc(sf), "30d"), "product", "registrations")["figure"]
    assert (seven, thirty) == (6, 9) and thirty - seven == 3        # the attack: 9 - 6 = a hidden cohort of 3, each figure alone is above the floor


def test_nested_windows_the_wider_figure_is_suppressed_when_the_difference_is_a_small_group(sf):
    add_users(sf, 6, age_days=3)
    add_users(sf, 3, age_days=20)
    s = svc(sf)
    seven, thirty, ninety, everything = (metric(s.product(p), "product", "registrations") for p in ("7d", "30d", "90d", "all_time"))
    assert seven["figure"] == 6 and seven["state"] == "available"                       # the narrow window is untouched
    for wide in (thirty, ninety, everything):
        assert wide["figure"] is None and wide["state"] == "suppressed", wide           # no wider window can be subtracted from it
    # the shipped output offers NO pair of windows whose difference is a small non-zero group
    figures = [m["figure"] for m in (seven, thirty, ninety, everything) if m["figure"] is not None]
    assert all(not (0 < abs(a - b) < REPORTING_MIN_COHORT) for a, b in itertools.combinations(figures, 2))


def test_nested_windows_everything_stays_visible_when_every_complement_is_a_real_group_or_empty(sf):
    add_users(sf, 6, age_days=3)
    add_users(sf, 5, age_days=20)                       # complement of 7d inside 30d: exactly the floor, fine
    s = svc(sf)
    got = {p: metric(s.product(p), "product", "registrations") for p in ("7d", "30d", "90d", "all_time")}
    assert [got[p]["figure"] for p in ("7d", "30d", "90d", "all_time")] == [6, 11, 11, 11]      # 90d and all_time differ from 30d by ZERO: nothing hidden, nothing learned
    assert all(m["state"] == "available" for m in got.values())


def test_nested_windows_an_empty_complement_is_not_a_small_group(sf):
    add_users(sf, 7, age_days=2)
    s = svc(sf)
    assert [metric(s.product(p), "product", "registrations")["figure"] for p in ("7d", "30d", "90d", "all_time")] == [7, 7, 7, 7]


def test_nested_windows_property_no_pair_of_served_windows_exposes_a_small_group(sf):
    """Random registration histories: whatever the data, the served figures never differ by a small non-zero amount."""
    rng = random.Random(20261120)
    for _trial in range(12):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        db = make_session_factory(engine)
        for age, hi in ((3, 9), (20, 7), (60, 6), (200, 5)):
            add_users(db, rng.randint(0, hi), age_days=age)
        s = svc(db)
        figures = [metric(s.product(p), "product", "registrations")["figure"] for p in ("7d", "30d", "90d", "all_time")]
        visible = [f for f in figures if f is not None]
        assert all(not (0 < abs(a - b) < REPORTING_MIN_COHORT) for a, b in itertools.combinations(visible, 2)), figures
        assert all(f is None or f >= REPORTING_MIN_COHORT for f in figures)           # the primary floor still holds


def test_nested_windows_apply_to_partition_buckets_and_to_everything_derived_from_them(sf):
    a = add_users(sf, 9, age_days=1)
    add_usage(sf, a[:6], 2, model="model-a")             # 6 candidates on model-a inside 7d
    add_usage(sf, a[6:], 20, model="model-a")            # 3 more only inside 30d: the model-a complement is a group of 3
    add_usage(sf, a, 2, model="model-b", workflow="practice")          # model-b: same 9 in both windows (complement 0)
    raw = unguarded(ReportingService.ai_economics)

    def cells(report):
        return {r["label"]: r["cells"][0] for r in table(report, "ai_economics", "ai_by_model")["rows"]}
    assert cells(raw(svc(sf), "7d"))["model-a"]["figure"] == 6 and cells(raw(svc(sf), "30d"))["model-a"]["figure"] == 9      # the attack on a bucket: 9 - 6 = 3
    shipped = {p: svc(sf).ai_economics(p) for p in ("7d", "30d")}
    assert cells(shipped["7d"])["model-a"]["figure"] == 6
    assert cells(shipped["30d"])["model-a"]["suppressed"] and cells(shipped["30d"])["model-a"]["figure"] is None
    # a derived ranking is built from visible cells only, so the hidden bucket cannot reappear in it
    for tid in ("ai_rank_cost", "ai_rank_tokens"):
        assert "model-a" not in [r["label"] for r in table(shipped["30d"], "ai_economics", tid)["rows"]]


def test_nested_windows_cover_the_builder_and_its_own_feedback_aggregate(sf):
    people = add_users(sf, 9, age_days=1)
    with sf() as s:
        for i, uid in enumerate(people):
            age = 2 if i < 6 else 20                      # 6 candidates gave feedback within 7d, 3 more only within 30d
            s.add(UserFeedback(user_id=uid, surface="agent", target_id=f"t{i}", rating="helpful", category="accuracy", created_at=NOW - age * DAY, updated_at=NOW - age * DAY))
        s.commit()
    builder = RB.ReportBuilder(svc(sf))
    caps = perm.permissions_for_role("platform_admin")

    def preview(window, group=None):
        raw = {"report_id": "quality", "metric_ids": ["feedback"], "window": window}
        if group:
            raw["group_by"] = group
        plan = RB.validate_definition(RB.parse_definition(raw), caps, perm.REPORTS_READ)
        return builder.preview(plan)["metrics"][0]
    seven, thirty = preview("7d"), preview("30d")
    assert seven["value"] == 6 and seven["state"] == "ok"
    assert thirty["value"] is None and thirty["state"] == "suppressed"                    # 9 - 6 = 3 would have been readable
    g7, g30 = preview("7d", "feedback_category"), preview("30d", "feedback_category")
    assert [b["value"] for b in g7["buckets"]] == [6]
    assert all(b["value"] is None for b in g30["buckets"])                                # the bucket of the wider window is hidden too


def test_a_builder_previous_period_comparison_stays_individually_suppressed(sf):
    add_users(sf, 6, age_days=3)
    add_users(sf, 2, age_days=10)                         # the previous 7d period holds a group of 2
    plan = RB.validate_definition(RB.parse_definition({"report_id": "product", "metric_ids": ["registrations"], "window": "7d", "comparison": "previous_period"}),
                                  perm.permissions_for_role("platform_admin"), perm.REPORTS_READ)
    m = RB.ReportBuilder(svc(sf)).preview(plan)["metrics"][0]
    assert m["value"] == 6 and m["previous"]["value"] is None and m["previous"]["state"] == "suppressed"      # unchanged rule: a small previous cohort is never shown


def test_the_guard_leaves_the_seven_day_window_and_unknown_periods_alone(sf):
    from src.reporting.service import ReportingError

    assert DF.narrower("7d") == [] and DF.narrower("30d") == ["7d"] and DF.narrower("all_time") == ["7d", "30d", "90d"] and DF.narrower("bogus") == []
    add_users(sf, 6, age_days=1)
    assert metric(svc(sf).product("7d"), "product", "registrations")["figure"] == 6
    with pytest.raises(ReportingError):
        svc(sf).product("1d; DROP TABLE users")


def test_keys_to_hide_only_flags_visible_pairs_with_a_small_non_zero_difference():
    outer = {("metric", "a"): (9, True), ("metric", "b"): (9, True), ("metric", "c"): (9, False), ("metric", "d"): (12, True), ("cell", "t", "x"): (8, True)}
    inner = {"7d": {("metric", "a"): (6, True), ("metric", "b"): (6, False), ("metric", "c"): (6, True), ("metric", "d"): (6, True), ("cell", "t", "x"): (8, True)}}
    assert DF.keys_to_hide(outer, inner) == frozenset({("metric", "a")})
    # a: both visible, difference 3 -> hidden. b: the inner is hidden, so nothing can be subtracted. c: the outer is already hidden. d: difference 6, a real group.
    # x: difference zero, nothing learned.


# ===================================================================================================================== attack 2: total versus buckets
def test_attack_total_minus_visible_buckets_exposes_a_small_hidden_group_in_the_old_rule():
    buckets = [{"label": "big", "values": [20], "cohort": 20}, {"label": "mid", "values": [8], "cohort": 8}, {"label": "s1", "values": [1], "cohort": 1},
               {"label": "s2", "values": [1], "cohort": 1}, {"label": "s3", "values": [2], "cohort": 2}]
    total = sum(b["values"][0] for b in buckets)
    # the OLD rule hid only the three small buckets (hidden group 1 + 1 + 2 = 4, below the floor); reproduce it to show what a total minus the visible buckets gave
    old_hidden = [b for b in buckets if b["cohort"] < REPORTING_MIN_COHORT]
    visible = [b for b in buckets if b["cohort"] >= REPORTING_MIN_COHORT]
    assert total - sum(b["values"][0] for b in visible) == 4 and len(old_hidden) == 3 and sum(b["cohort"] for b in old_hidden) < REPORTING_MIN_COHORT


def test_total_minus_visible_buckets_is_never_a_small_group_after_the_fix():
    buckets = [{"label": "big", "values": [20], "cohort": 20}, {"label": "mid", "values": [8], "cohort": 8}, {"label": "s1", "values": [1], "cohort": 1},
               {"label": "s2", "values": [1], "cohort": 1}, {"label": "s3", "values": [2], "cohort": 2}]
    rows = S.partition(buckets)
    shown = {r["label"]: r["cells"][0] for r in rows}
    hidden = [b for b in buckets if shown[b["label"]]["suppressed"]]
    assert {b["label"] for b in hidden} >= {"s1", "s2", "s3"} and sum(b["cohort"] for b in hidden) >= REPORTING_MIN_COHORT
    assert shown["big"]["figure"] == 20                                         # the large bucket is still shown
    total = sum(b["values"][0] for b in buckets)
    remainder = total - sum(c["figure"] for c in shown.values() if not c["suppressed"])
    assert remainder >= REPORTING_MIN_COHORT


def test_partition_property_the_hidden_group_is_empty_or_at_least_the_floor_or_everything_is_hidden():
    rng = random.Random(7)
    for _ in range(500):
        buckets = [{"label": f"b{i}", "values": [c], "cohort": c} for i, c in enumerate(rng.randint(0, 14) for _ in range(rng.randint(1, 8)))]
        rows = S.partition(buckets)
        hidden = [b for b, r in zip(buckets, rows) if r["cells"][0]["suppressed"]]
        visible = [b for b, r in zip(buckets, rows) if not r["cells"][0]["suppressed"]]
        assert all(b["cohort"] >= REPORTING_MIN_COHORT for b in visible), buckets          # nothing below the floor is ever visible
        if hidden:
            assert sum(b["cohort"] for b in hidden) >= REPORTING_MIN_COHORT or not visible, (buckets, [b["label"] for b in hidden])
        assert [r["label"] for r in rows] == [b["label"] for b in buckets]


def test_operational_partitions_are_never_suppressed_by_the_new_rule():
    rows = S.partition([{"label": "a", "values": [1], "cohort": 1}, {"label": "b", "values": [1], "cohort": 1}, {"label": "c", "values": [30], "cohort": 30}], operational=True)
    assert [r["cells"][0]["suppressed"] for r in rows] == [False, False, False]


def test_total_versus_bucket_through_the_real_service_ai_economics(sf):
    heavy = add_users(sf, 12, age_days=1)
    add_usage(sf, heavy, 1, model="big-model", calls=2)
    for name, who in (("tiny-1", heavy[:1]), ("tiny-2", heavy[1:2]), ("tiny-3", heavy[2:4])):
        add_usage(sf, who, 1, model=name, calls=1)
    r = svc(sf).ai_economics("7d")
    by_model = {row["label"]: row["cells"][0] for row in table(r, "ai_economics", "ai_by_model")["rows"]}
    hidden_cohort = sum({"tiny-1": 1, "tiny-2": 1, "tiny-3": 2}[k] for k, c in by_model.items() if k in ("tiny-1", "tiny-2", "tiny-3") and c["suppressed"])
    assert all(by_model[k]["suppressed"] for k in ("tiny-1", "tiny-2", "tiny-3"))
    headline = metric(r, "ai_economics", "ai_calls")["figure"]
    visible_sum = sum(c["figure"] for c in by_model.values() if not c["suppressed"])
    assert headline is not None and hidden_cohort == 4
    # the headline minus the visible buckets is the remainder of the hidden models: it must not be a group of fewer than the floor
    assert headline - visible_sum >= REPORTING_MIN_COHORT or by_model["big-model"]["suppressed"]


# ===================================================================================================================== residual risk, stated as tests so the documentation stays true
def test_residual_risk_repeated_requests_at_different_moments_are_not_correlated(sf):
    """KNOWN, DOCUMENTED, NOT MITIGATED: windows are relative to the request time, and each request is checked only against the nested windows of ITS OWN clock. Two
    requests for the same window a moment apart can be subtracted. Mitigations that exist outside this module: the reports are aggregate-only, read-only,
    permission-gated and audited. If this test starts failing, the residual-risk text in src/reporting/differencing.py and the 05E evidence must change with it."""
    add_users(sf, 9, age_days=3)
    add_users(sf, 1, age_days=6.99)                       # one candidate registered just inside the 7d window
    early = ReportingService(sf, clock=lambda: NOW)
    later = ReportingService(sf, clock=lambda: NOW + timedelta(hours=1))        # an hour later that candidate has just fallen out of the 7d window
    a = metric(early.product("7d"), "product", "registrations")
    b = metric(later.product("7d"), "product", "registrations")
    assert (a["figure"], b["figure"]) == (10, 9)          # both above the floor, so both shown, and 10 - 9 = one identifiable registration time slice
    assert DF.NESTED_ORDER == ("7d", "30d", "90d", "all_time")


def test_the_new_documentation_claims_neither_anonymisation_nor_legal_compliance():
    from src.reporting import report_builder as _rb

    assert "not an anonymisation guarantee" in _rb.PRIVACY_NOTE
    assert "not anonymisation" in (DF.__doc__ or "").lower() and "not an anonymisation guarantee" in (S.__doc__ or "").lower()
    for doc in (DF.__doc__ or "", S.__doc__ or ""):
        low = doc.lower()
        for banned in ("gdpr compliant", "gdpr-compliant", "anonymous data", "legally compliant"):
            assert banned not in low
