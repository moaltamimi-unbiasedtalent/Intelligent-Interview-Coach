"""Disposable-only migration qualification for existing mail-attempt evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests._alembic_head import assert_chain
from tests.test_billing_f1_qualification import _alembic

REV = '0049_workspace_mail_attempts'
PREV = '0048_agent_run_controls'


def _module():
    spec = importlib.util.spec_from_file_location('mail_migration_0049', Path(__file__).resolve().parents[1] / 'migrations/versions/0049_workspace_mail_attempts.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _database(tmp_path, monkeypatch):
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, PREV)
    eng = create_engine(url)
    return cfg, eng


def test_upgrade_preserves_rows_trigger_view_indexes_constraints_and_foreign_keys(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (id,message_type,provider,status,created_at) VALUES (7,'email_verification','memory','captured','2020-01-01')"))
        c.execute(text('CREATE TABLE synthetic_trigger_log (id INTEGER)'))
        c.execute(text('CREATE TRIGGER synthetic_mail_trigger AFTER INSERT ON email_attempts BEGIN INSERT INTO synthetic_trigger_log VALUES (NEW.id); END'))
        c.execute(text('CREATE INDEX synthetic_mail_partial ON email_attempts(status) WHERE status = \'captured\''))
        c.execute(text('CREATE INDEX synthetic_mail_expression ON email_attempts(lower(provider))'))
        c.execute(text('CREATE UNIQUE INDEX synthetic_mail_unique ON email_attempts(provider, request_id) WHERE request_id IS NOT NULL'))
        c.execute(text('CREATE VIEW synthetic_mail_view AS SELECT id, message_type FROM email_attempts'))
        before = c.execute(text('SELECT * FROM email_attempts')).all()
        indexes = c.execute(text("SELECT name,sql FROM sqlite_schema WHERE type='index' AND tbl_name='email_attempts' ORDER BY name")).all()
        fk = c.exec_driver_sql('PRAGMA foreign_key_list(email_attempts)').all()
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    command.upgrade(cfg, REV)
    with eng.begin() as c:
        assert c.execute(text('SELECT * FROM email_attempts')).all() == before
        assert c.execute(text("SELECT name,sql FROM sqlite_schema WHERE type='index' AND tbl_name='email_attempts' ORDER BY name")).all() == indexes
        assert c.exec_driver_sql('PRAGMA foreign_key_list(email_attempts)').all() == fk
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        for typ in ('email_verification','password_reset','account_notice','admin_test','workspace_invitation','ownership_transfer'):
            c.execute(text("INSERT INTO email_attempts (message_type,provider,status,created_at) VALUES (:typ,'memory','captured','2020-01-01')"), {'typ':typ})
        assert c.execute(text('SELECT count(*) FROM synthetic_mail_view')).scalar_one() == 7
        assert c.execute(text('SELECT count(*) FROM synthetic_trigger_log')).scalar_one() == 6
        plan = c.exec_driver_sql("EXPLAIN QUERY PLAN SELECT * FROM email_attempts WHERE status = 'captured'").all()
        assert any('synthetic_mail_partial' in str(row) for row in plan)
        assert c.exec_driver_sql("SELECT count(*) FROM email_attempts INDEXED BY synthetic_mail_expression WHERE lower(provider)='memory'").scalar_one() == 7
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == REV
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (message_type,provider,status,request_id,created_at) VALUES ('admin_test','memory','captured','unique-request','2020-01-01')"))
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (message_type,provider,status,request_id,created_at) VALUES ('account_notice','memory','captured','unique-request','2020-01-01')"))
    for typ in ('not_a_type', ''):
        with pytest.raises(IntegrityError), eng.begin() as c:
            c.execute(text("INSERT INTO email_attempts (message_type,provider,status,created_at) VALUES (:typ,'memory','captured','2020-01-01')"), {'typ':typ})
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (message_type,provider,status,created_at) VALUES ('workspace_invitation','memory','bogus','2020-01-01')"))
    assert assert_chain(require=(REV,)) == REV


def test_forced_failure_after_drop_rolls_back_schema_data_and_revision(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (id,message_type,provider,status,created_at) VALUES (7,'email_verification','memory','captured','2020-01-01')"))
        c.execute(text('CREATE TRIGGER synthetic_trigger AFTER INSERT ON email_attempts BEGIN SELECT 1; END'))
        before = c.execute(text("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")).all()
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with pytest.raises(RuntimeError, match='forced failure'):
        with eng.begin() as c:
            c.exec_driver_sql('BEGIN IMMEDIATE')
            _module()._sqlite_rebuild(c, fault=lambda: (_ for _ in ()).throw(RuntimeError('forced failure')))
    with eng.connect() as c:
        assert c.execute(text("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")).all() == before
        assert c.execute(text('SELECT id,message_type FROM email_attempts')).all() == [(7,'email_verification')]
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_unsupported_incoming_reference_refuses_without_changes(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text('CREATE TABLE synthetic_dependency (id INTEGER REFERENCES email_attempts(id))'))
        before = c.execute(text("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")).all()
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with pytest.raises(RuntimeError, match='incoming foreign-key'):
        command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")).all() == before
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_sqlite_requires_disposable_opt_in(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    monkeypatch.delenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', raising=False)
    with pytest.raises(RuntimeError, match='disposable database opt-in'):
        command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_disposable_round_trip_refuses_new_category_evidence(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    command.upgrade(cfg, REV)
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (id,message_type,provider,status,created_at) VALUES (99,'workspace_invitation','memory','captured','2020-01-01')"))
        before = c.execute(text('SELECT * FROM email_attempts')).all()
        before_schema = c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all()
    with pytest.raises(RuntimeError, match='new message types exist'):
        command.downgrade(cfg, PREV)
    with eng.connect() as c:
        assert c.execute(text('SELECT * FROM email_attempts')).all() == before
        assert c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all() == before_schema
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == REV


def test_non_sqlite_downgrade_refuses_before_schema_change(monkeypatch):
    from types import SimpleNamespace
    mod = _module()
    monkeypatch.setattr(mod.op, 'get_bind', lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))
    with pytest.raises(RuntimeError, match='Production downgrade'):
        mod.downgrade()


def test_foreign_keys_enabled_and_autoincrement_sequence_preserved(monkeypatch):
    eng = create_engine('sqlite:///:memory:')
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with eng.connect() as c:
        c.exec_driver_sql('PRAGMA foreign_keys=ON')
        c.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('INSERT INTO users VALUES (1)')
        c.exec_driver_sql("CREATE TABLE email_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, message_type TEXT, user_id INTEGER REFERENCES users(id), CONSTRAINT ck_email_attempts_type CHECK (message_type IN ('email_verification', 'password_reset', 'account_notice', 'admin_test')))")
        c.exec_driver_sql("INSERT INTO email_attempts(id,message_type,user_id) VALUES (41,'email_verification',1)")
        c.exec_driver_sql("UPDATE sqlite_sequence SET seq=99 WHERE name='email_attempts'")
        c.commit()
        c.exec_driver_sql('BEGIN IMMEDIATE')
        with pytest.raises(RuntimeError, match='synthetic foreign-key failure'):
            _module()._sqlite_rebuild(c, fault=lambda: (_ for _ in ()).throw(RuntimeError('synthetic foreign-key failure')))
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert c.exec_driver_sql('SELECT id FROM email_attempts').scalar_one() == 41
        c.rollback()
        c.exec_driver_sql('BEGIN IMMEDIATE')
        _module()._sqlite_rebuild(c)
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert c.exec_driver_sql("SELECT seq FROM sqlite_sequence WHERE name='email_attempts'").scalar_one() == 99
        c.commit()
        c.exec_driver_sql("INSERT INTO email_attempts(message_type,user_id) VALUES ('ownership_transfer',1)")
        assert c.exec_driver_sql('SELECT max(id) FROM email_attempts').scalar_one() == 100
        with pytest.raises(IntegrityError):
            c.exec_driver_sql("INSERT INTO email_attempts(message_type,user_id) VALUES ('account_notice',999)")
        c.rollback()


def test_external_trigger_dependency_refuses_without_mutation(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text('CREATE TABLE external_source (id INTEGER)'))
        c.execute(text("CREATE TRIGGER external_mail_trigger AFTER INSERT ON external_source BEGIN SELECT count(*) FROM email_attempts; END"))
        before = c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all()
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with pytest.raises(RuntimeError, match='external trigger dependency'):
        command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all() == before
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_empty_autoincrement_table_keeps_sequence_high_water_mark(monkeypatch):
    eng = create_engine('sqlite:///:memory:')
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with eng.connect() as c:
        c.exec_driver_sql("CREATE TABLE email_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, message_type TEXT, CONSTRAINT ck_email_attempts_type CHECK (message_type IN ('email_verification', 'password_reset', 'account_notice', 'admin_test')))")
        c.exec_driver_sql("INSERT INTO email_attempts(id,message_type) VALUES (99,'email_verification')")
        c.exec_driver_sql('DELETE FROM email_attempts')
        c.commit()
        c.exec_driver_sql('BEGIN IMMEDIATE')
        _module()._sqlite_rebuild(c)
        assert c.exec_driver_sql("SELECT seq FROM sqlite_sequence WHERE name='email_attempts'").scalar_one() == 99
        c.commit()
        c.exec_driver_sql("INSERT INTO email_attempts(message_type) VALUES ('ownership_transfer')")
        assert c.exec_driver_sql('SELECT id FROM email_attempts').scalar_one() == 100


def test_revision_update_failure_rolls_back_rebuild(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (id,message_type,provider,status,created_at) VALUES (7,'email_verification','memory','captured','2020-01-01')"))
        c.execute(text("CREATE TRIGGER refuse_revision BEFORE UPDATE ON alembic_version BEGIN SELECT RAISE(ABORT, 'synthetic revision failure'); END"))
        before = c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all()
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with pytest.raises(IntegrityError, match='synthetic revision failure'):
        command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')).all() == before
        assert c.execute(text('SELECT id,message_type FROM email_attempts')).all() == [(7, 'email_verification')]
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_sqlite_path_outside_permitted_temporary_roots_refuses(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    mod = _module()
    monkeypatch.setattr(mod.tempfile, 'gettempdir', lambda: '/nonexistent/ask4mo-safety-root')
    with eng.connect() as c:
        with pytest.raises(RuntimeError, match='outside temporary storage'):
            mod._sqlite_rebuild(c)
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV


def test_temporary_schema_dependency_refuses_before_mutation(monkeypatch):
    eng = create_engine('sqlite:///:memory:')
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with eng.connect() as c:
        c.exec_driver_sql("CREATE TABLE email_attempts (id INTEGER PRIMARY KEY, message_type TEXT, CONSTRAINT ck_email_attempts_type CHECK (message_type IN ('email_verification', 'password_reset', 'account_notice', 'admin_test')))")
        c.exec_driver_sql('CREATE TEMP VIEW temp_mail_view AS SELECT * FROM main.email_attempts')
        before = c.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE name='email_attempts'").scalar_one()
        with pytest.raises(RuntimeError, match='Temporary SQLite schema objects'):
            _module()._sqlite_rebuild(c)
        assert c.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE name='email_attempts'").scalar_one() == before
        assert c.exec_driver_sql('SELECT count(*) FROM temp_mail_view').scalar_one() == 0


def test_table_statistics_refuse_without_mutation(tmp_path, monkeypatch):
    cfg, eng = _database(tmp_path, monkeypatch)
    with eng.begin() as c:
        c.execute(text("INSERT INTO email_attempts (id,message_type,provider,status,created_at) VALUES (8,'admin_test','memory','captured','2020-01-01')"))
        c.exec_driver_sql('ANALYZE email_attempts')
        before = c.execute(text("SELECT tbl,idx,stat FROM sqlite_stat1 WHERE tbl='email_attempts' ORDER BY idx")).all()
        assert before
    monkeypatch.setenv('ASK4MO_DISPOSABLE_SQLITE_MIGRATION', '1')
    with pytest.raises(RuntimeError, match='statistics for email_attempts are unsupported'):
        command.upgrade(cfg, REV)
    with eng.connect() as c:
        assert c.execute(text("SELECT tbl,idx,stat FROM sqlite_stat1 WHERE tbl='email_attempts' ORDER BY idx")).all() == before
        assert c.execute(text('SELECT id,message_type FROM email_attempts')).all() == [(8, 'admin_test')]
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == PREV
