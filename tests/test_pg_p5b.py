"""W12.4D-P5-B: PostgreSQL execution evidence for the P4-A quota counters/reservations and the P5-A Preparation Pack table. Runs ONLY against an ISOLATED, throwaway
PostgreSQL server named by ``P5B_PG_ADMIN_URL`` (a server created for the test run; never a developer database): each test module run creates and drops its own
database. Without that variable every test is skipped (CI without PostgreSQL), and the P5-B document records the result as NOT TESTED in that case.
Writes a machine-readable summary to ``P5B_PG_REPORT`` when set."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ADMIN = os.environ.get("P5B_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN, reason="P5B_PG_ADMIN_URL not set: no isolated PostgreSQL server for this run")
ROOT = Path(__file__).resolve().parents[1]
REPORT: dict = {}


def _write_report():
    path = os.environ.get("P5B_PG_REPORT")
    if path:
        Path(path).write_text(json.dumps(REPORT, indent=2, sort_keys=True))


@pytest.fixture(scope="module")
def pg():
    import psycopg
    from sqlalchemy import create_engine

    name = f"p5b_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = ADMIN.rsplit("/", 1)[0] + f"/{name}"
    env = {**os.environ, "DATABASE_URL": url, "API_ENV": "test"}
    out = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-800:]
    engine = create_engine(url, future=True)
    yield SimpleNamespace_(url=url, engine=engine, env=env)
    engine.dispose()
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    _write_report()


class SimpleNamespace_:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _factory(url):
    from src.persistence import make_engine, make_session_factory
    return make_session_factory(make_engine(url))


def _users(pg, n):
    from src.persistence import Opportunity, User
    sf = _factory(pg.url)
    with sf() as s:
        us = [User(subject=f"pg{uuid.uuid4().hex[:8]}", provider="local", email=f"{uuid.uuid4().hex[:8]}@x.test") for _ in range(n)]
        s.add_all(us)
        s.commit()
        ids = [u.id for u in us]
        opps = []
        for uid in ids:
            o = Opportunity(user_id=uid, title="t", target_role="r")
            s.add(o)
            s.flush()
            opps.append(o.id)
        s.commit()
    return sf, ids, opps


# ======================================================================== migrations
def test_the_full_migration_chain_upgrades_downgrades_one_step_and_reupgrades_on_postgresql(pg):
    from sqlalchemy import inspect, text
    insp = inspect(pg.engine)
    tables = set(insp.get_table_names())
    assert {"preparation_packs", "usage_quota_counters", "usage_quota_reservations", "ai_operation_events", "opportunities"} <= tables
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0035_knowledge_foundation"
        defs = {r[0]: r[1] for r in c.execute(text("select indexname, indexdef from pg_indexes where tablename = 'preparation_packs'"))}
    assert "WHERE ((status)::text = 'generating'::text)" in defs["uq_pack_one_generating"] and "UNIQUE" in defs["uq_pack_one_generating"]
    REPORT["migration_head"] = "0035_knowledge_foundation"
    REPORT["pack_partial_index_def"] = defs["uq_pack_one_generating"]
    for target in ("0033_usage_quotas", "head"):
        out = subprocess.run([sys.executable, "-m", "alembic", "downgrade" if target != "head" else "upgrade", target], cwd=ROOT, env=pg.env, capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr[-600:]
        names = set(inspect(pg.engine).get_table_names())
        assert ("preparation_packs" in names) == (target == "head")
        assert {"usage_quota_counters", "ai_operation_events"} <= names                      # a one-step downgrade leaves earlier migrations intact
    REPORT["migration_downgrade_reupgrade"] = "ok"


# ======================================================================== Pack table semantics
def test_pack_constraints_cascade_set_null_and_null_opportunity_semantics_on_postgresql(pg):
    from sqlalchemy import select, text
    from sqlalchemy.exc import IntegrityError
    from src.persistence import PreparationPack
    sf, (u1, u2), (o1, o2) = _users(pg, 2)

    def pack(**kw):
        base = dict(op_key=uuid.uuid4().hex, user_id=u1, opportunity_id=o1, revision=1, status="completed", schema_version="x")
        base.update(kw)
        return PreparationPack(**base)
    with sf() as s:
        s.add(pack(op_key="dup"))
        s.commit()
    for bad, label in ((pack(op_key="dup", revision=2), "op_key"), (pack(revision=1), "revision"), (pack(status="bogus", revision=9), "status")):
        with sf() as s:
            s.add(bad)
            with pytest.raises(IntegrityError):
                s.commit()
    with sf() as s:                                                            # one generating row per user and opportunity
        s.add(pack(status="generating", revision=2))
        s.commit()
        s.add(pack(status="generating", revision=3))
        with pytest.raises(IntegrityError):
            s.commit()
    with sf() as s:                                                            # ... but a different opportunity or user may generate at the same time
        s.add_all([pack(status="generating", opportunity_id=o2, user_id=u2, revision=1)])
        s.commit()
    with sf() as s:                                                            # NULL opportunity: PostgreSQL treats NULLs as distinct, so neither constraint binds
        s.add_all([pack(opportunity_id=None, status="generating", revision=1), pack(opportunity_id=None, status="generating", revision=1)])
        s.commit()
        REPORT["null_opportunity_rows_allowed"] = True
    with sf() as s:                                                            # SET NULL on opportunity delete; the Pack survives
        s.execute(text("delete from opportunities where id = :i"), {"i": o1})
        s.commit()
        rows = s.scalars(select(PreparationPack).where(PreparationPack.user_id == u1, PreparationPack.op_key == "dup")).all()
        assert rows and rows[0].opportunity_id is None
    with sf() as s:                                                            # CASCADE on user delete
        s.execute(text("delete from users where id = :i"), {"i": u2})
        s.commit()
        assert s.scalar(select(PreparationPack.id).where(PreparationPack.user_id == u2)) is None
    REPORT["pack_constraints"] = "ok"


# ======================================================================== Pack concurrency across processes
def test_pack_revision_allocation_and_single_generation_hold_across_processes_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.persistence import PreparationPack
    sf, (uid,), (oid,) = _users(pg, 1)
    script = textwrap.dedent(f'''
        import sys, time, json
        sys.path.insert(0, {str(ROOT)!r})
        from src.persistence import make_engine, make_session_factory
        from src.preparation_pack_repository import PreparationPackRepository
        repo = PreparationPackRepository(make_session_factory(make_engine({pg.url!r})))
        pid = sys.argv[1]; res = {{"created": 0, "in_progress": 0, "duplicate": 0, "errors": 0}}
        for n in range(6):
            try:
                outcome, row = repo.start(user_id={uid}, opportunity_id={oid}, op_key=f"p{{pid}}-{{n}}", schema_version="x")
                res[outcome] += 1
                if outcome == "created":
                    time.sleep(0.01)
                    repo.finish(row["id"], status="completed", content={{}}, generation=None)
            except Exception as exc:
                res["errors"] += 1; res.setdefault("error_types", []).append(type(exc).__name__)
        print(json.dumps(res))
    ''')
    procs = [subprocess.Popen([sys.executable, "-c", script, str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=pg.env) for i in range(6)]
    outs = [p.communicate(timeout=180) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-500:] for o in outs]
    tallies = [json.loads(o[0].strip().splitlines()[-1]) for o in outs]
    with sf() as s:
        revs = list(s.scalars(select(PreparationPack.revision).where(PreparationPack.user_id == uid)))
        gen = s.scalar(select(func.count()).select_from(PreparationPack).where(PreparationPack.user_id == uid, PreparationPack.status == "generating"))
    created = sum(t["created"] for t in tallies)
    assert gen == 0 and len(revs) == len(set(revs)) == created and sorted(revs) == list(range(1, created + 1)) and sum(t["errors"] for t in tallies) == 0
    REPORT["pack_concurrency"] = {"processes": 6, "attempts": 36, "created": created, "in_progress": sum(t["in_progress"] for t in tallies), "errors": 0, "revisions_unique_contiguous": True}


# ======================================================================== quota concurrency
def _quota_script(pg, uid, limit, ops, key_mode):
    return textwrap.dedent(f'''
        import sys, json
        sys.path.insert(0, {str(ROOT)!r})
        from src.application import usage_quota as UQ
        from src.persistence import make_engine, make_session_factory
        UQ.USAGE_QUOTAS_ENFORCED = True
        sf = make_session_factory(make_engine({pg.url!r}))
        pol = UQ.QuotaPolicy("synthetic-test", {{("basic", "practice_session"): UQ.Allowance({limit}, "month")}})
        class P:
            def plan_summary(self, u, **k): return {{"plan_code": "basic", "source": "fallback_default"}}
        svc = UQ.UsageQuotaService(sf, P(), policy=pol)
        pid = sys.argv[1]; res = {{"approved": 0, "denied": 0, "errors": 0}}
        for n in range({ops}):
            key = {key_mode!r}.format(pid=pid, n=n)
            try:
                if svc.reserve({uid}, "practice_session", key):
                    res["approved"] += 1
                    svc.commit(key) if n % 2 == 0 else None
            except UQ.QuotaExhausted:
                res["denied"] += 1
            except Exception as exc:
                res["errors"] += 1; res.setdefault("error_types", []).append(type(exc).__name__)
        print(json.dumps(res))
    ''')


def test_quota_admission_never_over_allocates_across_processes_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.persistence import UsageQuotaCounter, UsageQuotaReservation
    sf, (a, b), _ = _users(pg, 2)
    limit, procs_n, ops = 25, 8, 12
    procs = [subprocess.Popen([sys.executable, "-c", _quota_script(pg, a, limit, ops, "q{pid}-{n}"), str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=pg.env) for i in range(procs_n)]
    outs = [p.communicate(timeout=240) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-500:] for o in outs]
    t = [json.loads(o[0].strip().splitlines()[-1]) for o in outs]
    approved, denied, errors = (sum(x[k] for x in t) for k in ("approved", "denied", "errors"))
    with sf() as s:
        used = s.scalar(select(func.coalesce(func.sum(UsageQuotaCounter.used), 0)).where(UsageQuotaCounter.user_id == a))
        states = dict(s.execute(select(UsageQuotaReservation.state, func.count()).where(UsageQuotaReservation.user_id == a).group_by(UsageQuotaReservation.state)).all())
        other = s.scalar(select(func.coalesce(func.sum(UsageQuotaCounter.used), 0)).where(UsageQuotaCounter.user_id == b))
    assert errors == 0 and approved == limit and denied == procs_n * ops - limit and used == approved and sum(states.values()) == approved and other == 0
    REPORT["quota_concurrency_processes"] = {"processes": procs_n, "attempted": procs_n * ops, "approved": approved, "denied": denied, "db_errors": errors, "final_counter": used,
                                             "reservation_states": states, "allowance": limit, "other_user_counter": other}


def test_duplicate_operation_keys_across_processes_take_exactly_one_unit_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.persistence import UsageQuotaCounter, UsageQuotaReservation
    sf, (u,), _ = _users(pg, 1)
    procs = [subprocess.Popen([sys.executable, "-c", _quota_script(pg, u, 50, 5, "same-{n}"), str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=pg.env) for i in range(6)]
    outs = [p.communicate(timeout=240) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-500:] for o in outs]
    with sf() as s:
        used = s.scalar(select(func.coalesce(func.sum(UsageQuotaCounter.used), 0)).where(UsageQuotaCounter.user_id == u))
        rows = s.scalar(select(func.count()).select_from(UsageQuotaReservation).where(UsageQuotaReservation.user_id == u))
    assert used == 5 and rows == 5                                                     # 6 processes x 5 identical keys: five logical operations, five units
    REPORT["quota_duplicate_keys"] = {"processes": 6, "logical_operations": 5, "units": used, "reservations": rows}


def test_quota_threads_period_boundary_rollback_release_and_reaping_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.application import usage_quota as UQ
    from src.persistence import UsageQuotaCounter, UsageQuotaReservation
    UQ.USAGE_QUOTAS_ENFORCED = True
    try:
        sf, (u,), _ = _users(pg, 1)

        class P:
            def plan_summary(self, *a, **k):
                return {"plan_code": "basic", "source": "fallback_default"}
        before = datetime(2026, 10, 17, 10, 59, 30, tzinfo=timezone.utc)
        after = datetime(2026, 10, 17, 11, 0, 30, tzinfo=timezone.utc)
        pol = UQ.QuotaPolicy("synthetic-test", {("basic", "practice_session"): UQ.Allowance(4, "hour")})
        results = []
        gate = threading.Barrier(16)

        def work(i):
            svc = UQ.UsageQuotaService(sf, P(), policy=pol, now=lambda: before if i % 2 == 0 else after)
            gate.wait()
            try:
                results.append(("before" if i % 2 == 0 else "after", bool(svc.reserve(u, "practice_session", f"b{i}"))))
            except UQ.QuotaExhausted:
                results.append(("before" if i % 2 == 0 else "after", False))
        ts = [threading.Thread(target=work, args=(i,)) for i in range(16)]
        [x.start() for x in ts]; [x.join() for x in ts]
        ok_b = sum(1 for p, r in results if p == "before" and r)
        ok_a = sum(1 for p, r in results if p == "after" and r)
        assert ok_b == 4 and ok_a == 4                                                 # each UTC hour has its OWN allowance: exactly 4 each, never 5
        with sf() as s:
            periods = dict(s.execute(select(UsageQuotaCounter.period_start, UsageQuotaCounter.used).where(UsageQuotaCounter.user_id == u)).all())
        assert sorted(periods.values()) == [4, 4]
        svc = UQ.UsageQuotaService(sf, P(), policy=pol, now=lambda: after)
        with pytest.raises(UQ.QuotaExhausted):
            svc.reserve(u, "practice_session", "rolled-back")                          # denial rolls the reservation row back
        with sf() as s:
            assert s.scalar(select(UsageQuotaReservation.id).where(UsageQuotaReservation.op_key == "rolled-back")) is None
        with sf() as s:
            one = s.scalars(select(UsageQuotaReservation.op_key).where(UsageQuotaReservation.user_id == u, UsageQuotaReservation.state == "reserved")).first()
        assert svc.release(one) is True and svc.release(one) is False                  # an explicit release returns the unit exactly once
        with sf() as s:
            n_reserved = s.scalar(select(func.count()).select_from(UsageQuotaReservation).where(UsageQuotaReservation.user_id == u, UsageQuotaReservation.state == "reserved"))
        late = after + UQ.RESERVATION_TTL + timedelta(seconds=1)
        reaped = UQ.UsageQuotaService(sf, P(), policy=pol, now=lambda: late).reap_expired()
        with sf() as s:
            used = s.scalar(select(func.coalesce(func.sum(UsageQuotaCounter.used), 0)).where(UsageQuotaCounter.user_id == u))
        assert reaped == n_reserved and used == 8 - 1 - reaped                          # 8 approved, 1 released explicitly, every still-reserved row reaped back
        REPORT["quota_threads_boundary"] = {"threads": 16, "approved_before_boundary": ok_b, "approved_after_boundary": ok_a, "reaped": reaped, "reserved_before_reap": n_reserved}
    finally:
        UQ.USAGE_QUOTAS_ENFORCED = False


def test_a_running_operation_keeps_its_quota_reservation_alive_and_a_crashed_one_is_recovered_on_postgresql(pg, monkeypatch):
    import time
    from sqlalchemy import select
    from src.application import usage_quota as UQ
    from src.application.lease import Heartbeat
    from src.persistence import UsageQuotaCounter, UsageQuotaReservation
    monkeypatch.setattr(UQ, "USAGE_QUOTAS_ENFORCED", True)
    monkeypatch.setattr(UQ, "RESERVATION_TTL", timedelta(seconds=1))
    sf, (u,), _ = _users(pg, 1)

    class P:
        def plan_summary(self, *a, **k):
            return {"plan_code": "basic", "source": "fallback_default"}
    pol = UQ.QuotaPolicy("synthetic-test", {("basic", "practice_session"): UQ.Allowance(5, "month")})
    svc = UQ.UsageQuotaService(sf, P(), policy=pol)
    svc.reserve(u, "practice_session", "alive")
    svc.reserve(u, "practice_session", "crashed")
    with Heartbeat(lambda: svc.renew("alive"), 0.2):
        time.sleep(2.2)                                                                # longer than the (shortened) lease: only the heartbeat keeps "alive" alive
        recovered = svc.reap_expired()
    assert recovered == 1
    with sf() as s:
        states = dict(s.execute(select(UsageQuotaReservation.op_key, UsageQuotaReservation.state).where(UsageQuotaReservation.user_id == u)).all())
        used = s.scalar(select(UsageQuotaCounter.used).where(UsageQuotaCounter.user_id == u))
    assert states == {"alive": "reserved", "crashed": "released"} and used == 1
    assert svc.commit("crashed") is False and svc.commit("alive") is True               # a late result for a recovered reservation cannot re-finalize it
    REPORT["quota_lease_recovery"] = {"alive_kept": True, "crashed_recovered": True, "late_commit_refused": True}
