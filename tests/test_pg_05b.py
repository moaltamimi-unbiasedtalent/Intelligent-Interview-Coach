"""05B: the PostgreSQL-ONLY behaviours (job claim ``FOR UPDATE SKIP LOCKED``, the audit append-only trigger DDL, the encrypted secrets table, ``pg_dump``/``pg_restore``
through the backup set, and the migration rollback on PostgreSQL), executed ONLY against a DISPOSABLE PostgreSQL server named by ``TEST_DATABASE_URL``.

``TEST_DATABASE_URL`` is the URL of a throwaway server (administrator role, as in the other ``tests/test_pg_*.py`` modules, which use ``P5B_PG_ADMIN_URL``, also accepted).
Each module run creates and drops its OWN ``p5b_05b_*`` databases and never touches the database the URL names. The URL's database name must contain ``test`` (for example
``ask4mo_test``): anything else is refused as possibly not disposable and every test is SKIPPED with that reason. Without the variable every test is SKIPPED with an explicit
reason. These tests do not install, start or configure PostgreSQL and do not use Docker. Synthetic structural data only; no URL, password or row value is printed."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest

from tests._alembic_head import repository_head

ROOT = Path(__file__).resolve().parents[1]
ADMIN = os.environ.get("TEST_DATABASE_URL") or os.environ.get("P5B_PG_ADMIN_URL")


def _skip_reason() -> str | None:
    if not ADMIN:
        return "TEST_DATABASE_URL not set: no disposable PostgreSQL for this run (05B PostgreSQL-only paths NOT EXERCISED)"
    from sqlalchemy.engine import make_url

    u = make_url(ADMIN)
    if u.get_backend_name() != "postgresql":
        return "TEST_DATABASE_URL is not a PostgreSQL URL"
    if "test" not in (u.database or "").lower():
        return "TEST_DATABASE_URL does not name a database containing 'test': refusing, it may not be disposable"
    return None


REASON = _skip_reason()
pytestmark = pytest.mark.skipif(REASON is not None, reason=REASON or "")


def _libpq(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _create_db(prefix: str) -> tuple[str, str]:
    import psycopg

    name = f"{prefix}_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(_libpq(ADMIN), autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    return name, ADMIN.rsplit("/", 1)[0] + f"/{name}"


def _drop_db(name: str) -> None:
    import psycopg

    with psycopg.connect(_libpq(ADMIN), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "API_ENV": "test"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture(scope="module")
def pg():
    from sqlalchemy import create_engine

    name, url = _create_db("p5b_05b")
    out = _alembic(url, "upgrade", "head")
    assert out.returncode == 0, out.stderr[-800:]
    engine = create_engine(url, future=True)
    yield NS(url=url, engine=engine, name=name)
    engine.dispose()
    _drop_db(name)


@pytest.fixture()
def fresh_db():
    """An extra empty database for tests that restore into it or migrate it; dropped afterwards."""
    from sqlalchemy import create_engine

    made: list[str] = []
    engines: list = []

    def make(prefix: str, *, migrate: bool = False) -> NS:
        name, url = _create_db(prefix)
        made.append(name)
        if migrate:
            assert _alembic(url, "upgrade", "head").returncode == 0
        engine = create_engine(url, future=True)
        engines.append(engine)
        return NS(url=url, name=name, engine=engine)

    yield make
    for e in engines:
        e.dispose()
    for n in made:
        _drop_db(n)


def _sf(url: str):
    from src.persistence import make_engine, make_session_factory

    return make_session_factory(make_engine(url))


def _job_types():
    from pydantic import BaseModel, ConfigDict

    from src.jobs.registry import JobTypeDef

    class P(BaseModel):
        model_config = ConfigDict(extra="forbid")
        n: str = "x"

    return {"t": JobTypeDef(code="t", label="Test", payload_model=P, handler=lambda payload, ctx: None, summarize=lambda p: {"n": p.n}, idempotency="test",
                            max_attempts=3, lease_seconds=60, backoff_base_seconds=10, backoff_cap_seconds=40, admin_enqueue=True)}


# ======================================================================== H-PG-MULTI: job claim
def test_claim_is_exclusive_across_concurrent_workers_on_postgresql(pg):
    from src.jobs.service import JobService

    svc = JobService(_sf(pg.url), _job_types())
    total = 24
    for i in range(total):
        svc.enqueue("t", {"n": str(i)})
    claimed: list[int] = []
    lock = threading.Lock()

    def worker(wid: str):
        while True:
            job = svc.claim(wid)
            if job is None:
                return
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    assert not any(t.is_alive() for t in threads)
    assert len(claimed) == total and len(set(claimed)) == total        # every job exactly once: no double claim, none lost


def test_skip_locked_never_blocks_on_a_row_another_transaction_holds(pg):
    from sqlalchemy import text

    from src.jobs.service import JobService

    svc = JobService(_sf(pg.url), _job_types())
    for i in range(3):
        svc.enqueue("t", {"n": f"lock{i}"})
    holder = pg.engine.connect()
    tx = holder.begin()
    try:
        locked = holder.execute(text("SELECT id FROM jobs WHERE state = 'queued' ORDER BY available_at, id LIMIT 1 FOR UPDATE")).scalar()
        result: dict = {}

        def claim():
            result["job"] = svc.claim("blocked-or-not")

        t = threading.Thread(target=claim)
        t.start()
        t.join(15)
        assert not t.is_alive(), "claim blocked on a locked row: SKIP LOCKED is not in effect"
        assert result["job"] is not None and result["job"].id != locked      # it skipped the held row and took the next one
    finally:
        tx.rollback()
        holder.close()


# ======================================================================== H-PG-QUERY: audit trigger DDL
def test_audit_and_incident_triggers_exist_and_enforce_append_only_on_postgresql(pg):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from src.persistence import AuditEvent, User

    with pg.engine.connect() as c:
        triggers = {r[0] for r in c.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))}
        functions = {r[0] for r in c.execute(text("SELECT proname FROM pg_proc WHERE proname LIKE '%\\_guard'"))}
    assert {"trg_audit_events_guard", "trg_incident_events_guard"} <= triggers
    assert {"audit_events_guard", "incident_events_guard"} <= functions
    sf = _sf(pg.url)
    with sf() as s:
        u = User(subject=f"pg05b-{uuid.uuid4().hex[:8]}", provider="local", email=f"{uuid.uuid4().hex[:8]}@example.test")
        s.add(u)
        s.flush()
        ev = AuditEvent(actor_user_id=u.id, event_type="pg05b.test", target_type="t", target_id="1", result="success", context={"fields_changed": ["synthetic"]})
        s.add(ev)
        s.commit()
        uid, eid = u.id, ev.id
    with pytest.raises(DBAPIError, match="append-only"):
        with pg.engine.begin() as c:
            c.execute(text("UPDATE audit_events SET event_type = 'tampered' WHERE id = :i"), {"i": eid})
    with pytest.raises(DBAPIError, match="append-only"):
        with pg.engine.begin() as c:
            c.execute(text("DELETE FROM audit_events WHERE id = :i"), {"i": eid})
    with pytest.raises(DBAPIError, match="append-only"):
        with pg.engine.begin() as c:                                      # changing the context (JSON compared as text) is also refused
            c.execute(text("UPDATE audit_events SET context = CAST('{\"k\": \"other\"}' AS json) WHERE id = :i"), {"i": eid})
    with pg.engine.begin() as c:                                          # the one allowed change: the actor going to NULL (account anonymisation)
        c.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})     # the FK ON DELETE SET NULL performs exactly that UPDATE
    with pg.engine.connect() as c:
        row = c.execute(text("SELECT actor_user_id, event_type FROM audit_events WHERE id = :i"), {"i": eid}).one()
    assert row[0] is None and row[1] == "pg05b.test"


# ======================================================================== H-PG-SECRETS: encrypted secrets table
def test_managed_secrets_table_holds_only_ciphertext_and_enforces_its_constraints_on_postgresql(pg):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from src.secret_store import EncryptedDatabaseSecretStore, SecretStoreStale

    master = base64.b64encode(os.urandom(32)).decode()
    value = "pg05b-secret-" + uuid.uuid4().hex
    store = EncryptedDatabaseSecretStore(_sf(pg.url), master_key=master)
    name = "OPENROUTER_API_KEY"
    first = store.set(name, value, actor_user_id=None)
    assert first["revision"] == 1 and store.get_for_runtime(name).get_secret_value() == value
    with pg.engine.connect() as c:
        row = c.execute(text("SELECT ciphertext, nonce, revision FROM managed_secrets")).one()
        types = {r[0]: r[1] for r in c.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'managed_secrets'"))}
    assert value.encode() not in bytes(row[0]) and len(bytes(row[1])) == 12 and types["ciphertext"] == "bytea" and types["nonce"] == "bytea"
    assert store.set(name, value + "x", expected_revision=1)["revision"] == 2
    with pytest.raises(SecretStoreStale):
        store.set(name, "other", expected_revision=1)                          # optimistic concurrency holds on PostgreSQL
    with pytest.raises(IntegrityError):
        with pg.engine.begin() as c:
            c.execute(text("INSERT INTO managed_secrets (integration_code, slot, ciphertext, nonce, key_id, revision, created_at, updated_at) "
                           "SELECT integration_code, slot, ciphertext, nonce, key_id, 1, created_at, updated_at FROM managed_secrets LIMIT 1"))   # unique slot
    with pytest.raises(IntegrityError):
        with pg.engine.begin() as c:
            c.execute(text("UPDATE managed_secrets SET revision = 0"))          # ck_managed_secrets_revision
    wrong = EncryptedDatabaseSecretStore(_sf(pg.url), master_key=base64.b64encode(os.urandom(32)).decode())
    assert wrong.get_for_runtime(name) is None                                  # a wrong master key never yields a value


# ======================================================================== PG-09: pg_dump / pg_restore through the backup set
needs_pg_tools = pytest.mark.skipif(not (shutil.which("pg_dump") and shutil.which("pg_restore")), reason="pg_dump and pg_restore are not on PATH: backup-set PostgreSQL path NOT EXERCISED")


def _seed_docs(url: str, docs: Path) -> None:
    from src.persistence import CandidateDocument, DocumentVersion, User

    docs.mkdir(parents=True, exist_ok=True)
    with _sf(url)() as s:
        for n in range(2):
            u = User(subject=f"pg05b-doc-{uuid.uuid4().hex[:8]}", provider="local", email=f"{uuid.uuid4().hex[:8]}@example.test")
            s.add(u)
            s.flush()
            d = CandidateDocument(user_id=u.id, title=f"Synthetic {n}", category="other")
            s.add(d)
            s.flush()
            key = uuid.uuid4().hex * 2
            (docs / key).write_bytes(b"synthetic private document " + key.encode())
            s.add(DocumentVersion(document_id=d.id, version=1, original_filename="s.txt", storage_key=key, mime_type="text/plain", size_bytes=10))
        s.commit()


@needs_pg_tools
def test_backup_set_round_trips_through_pg_dump_and_pg_restore_and_refuses_unsafe_targets(fresh_db, tmp_path):
    from src.backup_set import engine as E

    src = fresh_db("p5b_05b_src", migrate=True)                                  # its own database: the shared one holds running jobs from the claim tests
    docs = tmp_path / "documents"
    _seed_docs(src.url, docs)
    out = tmp_path / "set"
    rep = E.create_set(E.Source(database_url=src.url, documents_dir=docs), out_dir=out, execute=True, api_env="test")
    assert rep.ok, rep.codes
    manifest = E.load_manifest(out)
    assert manifest["database"]["dialect"] == "postgresql" and manifest["database"]["schema_revision"] == repository_head() and E.verify_set(out).ok
    target = fresh_db("p5b_05b_restore")
    # refusals first: nothing is overwritten and nothing is restored into a database that is not clearly a restore target
    assert E.restore_set(out, target_root=tmp_path / "r0", execute=True, target_database_url=None).codes == ["target_database_url_required"]
    bad_name = target.url.rsplit("/", 1)[0] + "/ask4mo_production_like"
    assert "target_database_name_refused" in E.restore_set(out, target_root=tmp_path / "r0", execute=True, target_database_url=bad_name).codes
    ok = E.restore_set(out, target_root=tmp_path / "r1", execute=True, target_database_url=target.url)
    assert ok.ok, ok.codes
    assert E.table_counts(target.url) == manifest["database"]["row_counts"]
    again = E.restore_set(out, target_root=tmp_path / "r2", execute=True, target_database_url=target.url)
    assert not again.ok and "target_database_not_empty" in again.codes     # a second restore never overwrites the restored database


@needs_pg_tools
def test_restore_drill_record_on_postgresql_source(fresh_db, tmp_path):
    from src.backup_set import engine as E
    from src.backup_set.drill import run_drill

    src = fresh_db("p5b_05b_dsrc", migrate=True)
    docs = tmp_path / "documents"
    _seed_docs(src.url, docs)
    target = fresh_db("p5b_05b_drill")
    res = run_drill(E.Source(database_url=src.url, documents_dir=docs), work_dir=tmp_path / "work", record_dir=tmp_path / "records", label="pg", kind="offline_synthetic",
                    api_env="test", negative_checks=True, target_database_url=target.url)
    by = {c["id"]: c["result"] for c in res.record["checks"]}
    assert by["row_counts_match"] == "PASS" and by["schema_revision_matches"] == "PASS" and by["document_checksums_match"] == "PASS"
    assert (tmp_path / "records" / res.json_name).is_file()


# ======================================================================== PG-09: migration rollback on PostgreSQL (the FK branches SQLite skips)
def test_head_migration_downgrade_is_fail_closed_then_clean_then_reupgrades_on_postgresql(fresh_db):
    from sqlalchemy import inspect, text

    from src.backup_set import rollback as RB

    head, prev = RB.head_and_previous()
    suffix = head.split("_", 1)[1]
    if suffix not in RB.HEAD_SEEDERS:
        pytest.skip("no state seeder registered for the head revision: fail-closed refusal NOT EXERCISED on PostgreSQL")
    db = fresh_db("p5b_05b_roll", migrate=True)
    from src.persistence import User

    with _sf(db.url)() as s:
        u = User(subject=f"roll-{uuid.uuid4().hex[:8]}", provider="local", email=f"{uuid.uuid4().hex[:8]}@example.test")
        s.add(u)
        s.commit()
    RB.HEAD_SEEDERS[suffix][0](db.url)
    if suffix == "agent_run_controls":
        before = RB.protected_fingerprint(db.url)
        refused = _alembic(db.url, "downgrade", "-1")
        assert refused.returncode != 0 and "Run controls must be deliberately retired" in (refused.stderr + refused.stdout)
        assert RB.protected_fingerprint(db.url) == before
        with db.engine.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
        return  # Never delete protected rows to force a downgrade; new-target recovery is qualified separately.
    with db.engine.connect() as c:
        before = c.execute(text("SELECT count(*) FROM candidate_stories")).scalar()
    refused = _alembic(db.url, "downgrade", "-1")
    assert refused.returncode != 0 and "Refusing to downgrade" in (refused.stderr + refused.stdout)
    with db.engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == head and c.execute(text("SELECT count(*) FROM candidate_stories")).scalar() == before
    with db.engine.begin() as c:
        c.execute(text("DELETE FROM candidate_stories WHERE archived_at IS NOT NULL OR confirmed_at IS NOT NULL OR opportunity_id IS NOT NULL"))
    assert _alembic(db.url, "downgrade", "-1").returncode == 0
    with db.engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == prev
    assert _alembic(db.url, "upgrade", "head").returncode == 0
    with db.engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
    assert "users" in inspect(db.engine).get_table_names()
