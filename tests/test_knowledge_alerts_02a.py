"""02A part 2: knowledge health alerts through the EXISTING in-app alert mechanism, migration 0040 and the unchanged Admin permission matrix. Offline."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select, text

from src.admin_security import definitions as D
from src.admin_security.alerts import AlertService
from src.knowledge_admin import alerts as KA
from src.knowledge_admin import policy as P
from src.persistence import ALERT_CATEGORIES, AdminNotification, Job, KnowledgeSourceVersion
from tests._alembic_head import assert_chain
from tests._knowledge_env_02a import Process, hosted_temp

ROOT = Path(__file__).resolve().parents[1]


def alert_rows(p: Process):
    with p.sf() as s:
        return {r.category + "|" + r.dedupe_key: r for r in s.scalars(select(AdminNotification)).all()}


def states(p: Process):
    with p.sf() as s:
        return {r.category: (r.state, r.occurrence_count) for r in s.scalars(select(AdminNotification)).all()}


def test_categories_are_code_defined_in_one_place_and_match_the_database_constraint():
    assert set(D.ALERT_DEFINITIONS) == set(ALERT_CATEGORIES)
    assert set(KA.CATEGORIES) <= set(ALERT_CATEGORIES)
    for c in KA.CATEGORIES:
        assert D.ALERT_DEFINITIONS[c]["source_type"] == "knowledge" and len(c) <= 32
    assert not (set(D.ALERT_NOT_IMPLEMENTED) & set(ALERT_CATEGORIES))


def test_lost_collection_alert_is_raised_deduplicated_and_resolved_when_the_condition_clears(tmp_path):
    p = Process(tmp_path / "env", alerts=True)
    try:
        p.to_active()
        p.guard.check(fresh=True)
        assert KA.COLLECTION_LOST not in states(p)                                   # healthy: no alert
        p.store.reset()                                                              # the collection is lost
        p.guard.check(fresh=True)
        p.guard.check(fresh=True)
        p.guard.check(fresh=True)                                                    # a flapping check must not stack rows or inflate the count
        st = states(p)
        assert st[KA.COLLECTION_LOST] == ("active", 1)
        assert [k for k in alert_rows(p) if k.startswith(KA.COLLECTION_LOST)] == [f"{KA.COLLECTION_LOST}|{KA.COLLECTION_LOST}"]     # one row, stable dedupe key
        p.svc.request_reindex(p.sf().scalar(select(KnowledgeSourceVersion.public_id)), actor_user_id=1)
        p.drain()                                                                    # the repair
        p.guard.check(fresh=True)
        assert states(p)[KA.COLLECTION_LOST][0] == "resolved"
        p.store.reset()                                                              # it recurs: the SAME row reopens
        p.guard.check(fresh=True)
        assert states(p)[KA.COLLECTION_LOST][0] == "active" and len([k for k in alert_rows(p) if k.startswith(KA.COLLECTION_LOST)]) == 1
    finally:
        p.close()


def test_missing_source_files_alert(tmp_path):
    p = Process(tmp_path / "env", alerts=True)
    try:
        p.to_active()
        for f in (tmp_path / "env" / "private").iterdir():
            f.unlink()
        p.guard.check(fresh=True)
        assert states(p)[KA.FILES_MISSING][0] == "active"
    finally:
        p.close()


def test_identity_mismatch_alert_names_no_field_values_and_no_paths(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", worker_data_root=tmp_path / "other", alerts=True)
    try:
        p.worker.run_once()
        p.guard.check(fresh=True)
        row = alert_rows(p)[f"{KA.IDENTITY_MISMATCH}|{KA.IDENTITY_MISMATCH}"]
        assert row.state == "active" and row.severity == "high" and row.source_type == "knowledge"
        blob = " ".join(str(v) for v in (row.title, row.source_id, row.dedupe_key))
        assert str(tmp_path) not in blob and "/" not in blob
    finally:
        p.close()


def test_failed_knowledge_job_uses_the_existing_job_failed_category_once_per_job_type(tmp_path):
    p = Process(tmp_path / "env", alerts=True)
    try:
        r = p.to_review()
        v = r["version_public_id"]
        p.svc.approve(v, actor_user_id=1)
        p.svc.request_index(v, actor_user_id=1)
        with p.sf() as s:                                                           # the stored file disappears: the index job fails permanently
            key = s.execute(select(KnowledgeSourceVersion.storage_key)).scalar()
        (Path(p.docs._root) / key).unlink()
        p.drain()
        with p.sf() as s:
            assert s.scalars(select(Job).where(Job.job_type == P.JOB_INDEX, Job.state == "failed")).all()
        p.guard.check(fresh=True)
        p.guard.check(fresh=True)
        keys = [k for k in alert_rows(p) if k.startswith("job_failed")]
        assert keys.count(f"job_failed|job_failed:{P.JOB_INDEX}") == 1 and len(keys) == len(set(keys))
        assert not [k for k in alert_rows(p) if k.startswith("knowledge_") and "job" in k]      # no second, parallel category for the same condition
    finally:
        p.close()


def test_embedding_incompatibility_mechanism_for_02b(tmp_path):
    p = Process(tmp_path / "env")
    try:
        KA.observe_embedding_incompatibility(p.sf, ["model", "dimensions"])
        assert states(p)[KA.EMBEDDING_MISMATCH][0] == "active"
        KA.observe_embedding_incompatibility(p.sf, [])
        assert states(p)[KA.EMBEDDING_MISMATCH][0] == "resolved"
    finally:
        p.close()


def test_alert_emission_never_raises_and_never_changes_the_observed_outcome(tmp_path):
    p = Process(tmp_path / "env")
    try:
        class Boom:
            environment = "development"
            findings = None                     # iterating raises
        assert KA.observe_guard_report(p.sf, Boom()) == []
        def broken():
            raise RuntimeError("db down")
        assert KA.observe_guard_report(broken, p.guard.check(fresh=True)) == []
    finally:
        p.close()


def test_alerts_are_listed_by_the_existing_admin_alert_service_in_app_only(tmp_path):
    p = Process(tmp_path / "env", alerts=True)
    try:
        p.to_active()
        p.store.reset()
        p.guard.check(fresh=True)
        listing = AlertService(p.sf).list()
        assert listing["delivery"] == "in_app_only" and KA.COLLECTION_LOST in listing["categories"]
        item = next(i for i in listing["items"] if i["category"] == KA.COLLECTION_LOST)
        assert item["title"] == D.ALERT_DEFINITIONS[KA.COLLECTION_LOST]["title"] and item["state"] == "active"
        src = (ROOT / "src/knowledge_admin/alerts.py").read_text()
        for banned in ("smtplib", "requests", "httpx", "urllib", "slack", "webhook", "twilio", "pagerduty"):
            assert banned not in src.lower(), banned
    finally:
        p.close()


# ===================================================================== migration 0040
def _alembic(tmp_path, monkeypatch):
    from tests.test_billing_f1_qualification import _alembic as a
    return a(tmp_path, monkeypatch)


def test_migration_0040_accepts_the_new_categories_keeps_the_old_and_is_the_single_head(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError

    cfg, url = _alembic(tmp_path, monkeypatch)
    assert ScriptDirectory.from_config(cfg).get_heads() == [assert_chain(require=("0040_knowledge_alert_categories",))]   # one head, 0040 in the chain (later revisions may sit above it)
    command.upgrade(cfg, "0040_knowledge_alert_categories")
    eng = create_engine(url)
    ins = ("insert into admin_notifications (public_id, category, severity, dedupe_key, state, source_type, title, occurrence_count, first_seen_at, last_seen_at, created_at, updated_at, revision) "
           "values (:p, :c, 'high', :k, 'active', 'knowledge', 't', 1, '2026-01-01', '2026-01-01', '2026-01-01', '2026-01-01', 0)")
    with eng.begin() as c:
        for i, cat in enumerate(("job_failed",) + KA.CATEGORIES):
            c.execute(text(ins), {"p": f"p{i}", "c": cat, "k": f"k{i}"})
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(text(ins), {"p": "px", "c": "not_a_category", "k": "kx"})


REV_0040 = "0040_knowledge_alert_categories"


def test_migration_0040_downgrade_is_fail_closed_and_data_preserving(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine

    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0040_knowledge_alert_categories")
    eng = create_engine(url)
    ins = ("insert into admin_notifications (public_id, category, severity, dedupe_key, state, source_type, title, occurrence_count, first_seen_at, last_seen_at, created_at, updated_at, revision) "
           "values ('p1', :c, 'high', 'k1', 'active', 'knowledge', 't', 1, '2026-01-01', '2026-01-01', '2026-01-01', '2026-01-01', 0)")
    with eng.begin() as c:
        c.execute(text(ins), {"c": KA.COLLECTION_LOST})
    with pytest.raises(RuntimeError, match="Refusing to downgrade 0040_knowledge_alert_categories"):
        command.downgrade(cfg, "0039_speech_governance")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from admin_notifications")).scalar() == 1            # nothing was deleted
        assert c.execute(text("select version_num from alembic_version")).scalar() == REV_0040       # the fixed historical revision under test, not the head
    with eng.begin() as c:
        c.execute(text("delete from admin_notifications"))
    command.downgrade(cfg, "0039_speech_governance")
    with eng.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0039_speech_governance"
    command.upgrade(cfg, "0040_knowledge_alert_categories")                                           # and it re-applies


# ===================================================================== Admin permission matrix unchanged
def test_admin_permission_registry_and_knowledge_routes_are_unchanged_by_02a():
    from src.api.admin_route_invariant import admin_routes
    from src.application import admin_permissions as perm

    assert len(perm.PERMISSIONS) == 44                                                             # no permission was added by 02A
    mine = {(m, r.path): tuple(sorted(r.permissions)) for r in admin_routes() if r.path.startswith("/admin/knowledge") for m in r.methods}
    reads = {k for k, v in mine.items() if v == (perm.KNOWLEDGE_READ,)}
    assert ("GET", "/admin/knowledge/readiness") in reads and ("GET", "/admin/knowledge/active") in reads
    assert mine[("POST", "/admin/knowledge/versions/{version_id}/reindex")] == (perm.KNOWLEDGE_MANAGE,)
    assert mine[("POST", "/admin/knowledge/versions/{version_id}/replace")] == (perm.KNOWLEDGE_APPROVE,)
    assert all(v for v in mine.values())
