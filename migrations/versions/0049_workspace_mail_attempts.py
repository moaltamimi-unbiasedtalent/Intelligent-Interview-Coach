"""Allow bounded workspace mail-attempt categories without changing stored rows.

SQLite rebuilds are permitted only for explicitly opted-in disposable test databases.
PostgreSQL replaces the one check in place. No downgrade is performed automatically.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from alembic import op

revision = "0049_workspace_mail_attempts"
down_revision = "0048_agent_run_controls"
branch_labels = None
depends_on = None

OLD = "message_type IN ('email_verification', 'password_reset', 'account_notice', 'admin_test')"
NEW = "message_type IN ('email_verification', 'password_reset', 'account_notice', 'admin_test', 'workspace_invitation', 'ownership_transfer')"


def _require_disposable_sqlite(conn):
    databases = conn.exec_driver_sql("PRAGMA database_list").all()
    if any(row[1] not in ("main", "temp") for row in databases):
        raise RuntimeError("Attached SQLite databases are unsupported")
    path = next(row[2] for row in databases if row[1] == "main")
    if os.environ.get("ASK4MO_DISPOSABLE_SQLITE_MIGRATION") != "1":
        raise RuntimeError("SQLite migration requires explicit disposable database opt-in")
    if path:
        roots = (Path(tempfile.gettempdir()).resolve(), Path('/private/tmp').resolve())
        resolved = Path(path).resolve()
        if not any(resolved.is_relative_to(root) for root in roots):
            raise RuntimeError("SQLite migration refuses a database outside temporary storage")


def _sqlite_rebuild(conn, fault=None, *, source_check=OLD, target_check=NEW):
    """Rebuild a disposable table within the caller's transaction or refuse safely."""
    _require_disposable_sqlite(conn)
    if conn.exec_driver_sql("SELECT 1 FROM sqlite_temp_schema WHERE sql IS NOT NULL LIMIT 1").fetchone():
        raise RuntimeError("Temporary SQLite schema objects are unsupported")
    if conn.exec_driver_sql("PRAGMA writable_schema").scalar_one() or conn.exec_driver_sql("PRAGMA ignore_check_constraints").scalar_one():
        raise RuntimeError("Unsafe SQLite schema or CHECK settings are unsupported")
    # Read all object definitions before mutation. Incoming references and triggers
    # attached to other objects are refused rather than guessed or rewritten.
    objects = conn.exec_driver_sql("SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type, name").all()
    tables = [r[1] for r in objects if r[0] == 'table' and not r[1].startswith('sqlite_')]
    for stat_table in ('sqlite_stat1', 'sqlite_stat4'):
        if any(r[0] == 'table' and r[1] == stat_table for r in objects):
            if conn.exec_driver_sql(f"SELECT 1 FROM {stat_table} WHERE tbl='email_attempts' LIMIT 1").fetchone():
                raise RuntimeError("SQLite statistics for email_attempts are unsupported")
    if any(r[1] == '_ask4mo_email_attempts_new' for r in objects):
        raise RuntimeError("Temporary migration object already exists")
    table_sql = next(r[3] for r in objects if r[0] == 'table' and r[1] == 'email_attempts')
    if table_sql.count(source_check) != 1:
        raise RuntimeError("Unsupported email-attempt CHECK definition")
    if any(r[0] == 'trigger' and r[2] != 'email_attempts' and re.search(r'\bemail_attempts\b', r[3], re.I) for r in objects):
        raise RuntimeError("Unsupported external trigger dependency")
    quote = conn.dialect.identifier_preparer.quote
    for table in tables:
        if table != 'email_attempts':
            if any(row[2].lower() == 'email_attempts' for row in conn.exec_driver_sql(f"PRAGMA foreign_key_list({quote(table)})")):
                raise RuntimeError("Unsupported incoming foreign-key dependency")
    columns = conn.exec_driver_sql("PRAGMA table_xinfo(email_attempts)").all()
    if any(row[6] != 0 for row in columns):
        raise RuntimeError("Generated or hidden columns are unsupported")
    names = [r[1] for r in columns]
    cols = ', '.join(quote(n) for n in names)
    if conn.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
        raise RuntimeError("Existing foreign-key violation")
    before_rows = hashlib.sha256(repr(conn.exec_driver_sql(f"SELECT {cols} FROM email_attempts ORDER BY id").all()).encode()).hexdigest()
    before_fk = conn.exec_driver_sql("PRAGMA foreign_key_list(email_attempts)").all()
    sqlite_version = conn.exec_driver_sql("SELECT sqlite_version()").scalar_one()
    journal = conn.exec_driver_sql("PRAGMA journal_mode").scalar_one()
    # Include automatic, partial, expression and collation-bearing index metadata.
    def inventory():
        return {table: {
            'columns': conn.exec_driver_sql(f"PRAGMA table_xinfo({quote(table)})").all(),
            'foreign_keys': conn.exec_driver_sql(f"PRAGMA foreign_key_list({quote(table)})").all(),
            'indexes': sorted([(tuple(row[1:]), conn.exec_driver_sql(f"PRAGMA index_xinfo({quote(row[1])})").all())
                               for row in conn.exec_driver_sql(f"PRAGMA index_list({quote(table)})").all()]),
        } for table in tables}
    before_inventory = inventory()
    before_xinfo = columns
    legacy = conn.exec_driver_sql("PRAGMA legacy_alter_table").scalar_one()
    fk_mode = conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
    deferred_fk = conn.exec_driver_sql("PRAGMA defer_foreign_keys").scalar_one()
    recursive_triggers = conn.exec_driver_sql("PRAGMA recursive_triggers").scalar_one()
    sqlite_sequence = conn.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table' AND name='sqlite_sequence'").fetchone()
    sequences = conn.exec_driver_sql("SELECT name, seq FROM sqlite_sequence ORDER BY name").all() if sqlite_sequence else None
    seq = conn.exec_driver_sql("SELECT seq FROM sqlite_sequence WHERE name='email_attempts'").fetchone() if sqlite_sequence else None
    associated = [r for r in objects if r[2] == 'email_attempts' and r[0] in ('index', 'trigger')]
    renamed = re.sub(r'(?i)^CREATE\s+TABLE\s+(?:"email_attempts"|`email_attempts`|\[email_attempts\]|email_attempts)', 'CREATE TABLE "_ask4mo_email_attempts_new"', table_sql, count=1)
    if renamed == table_sql:
        raise RuntimeError("Unsupported table definition")
    if source_check == NEW and conn.exec_driver_sql("SELECT 1 FROM email_attempts WHERE message_type IN ('workspace_invitation', 'ownership_transfer') LIMIT 1").fetchone():
        raise RuntimeError("Refusing SQLite test downgrade while new message types exist")
    new_sql = renamed.replace(source_check, target_check)
    conn.exec_driver_sql("SAVEPOINT ask4mo_mail_rebuild")
    try:
        conn.exec_driver_sql(new_sql)
        conn.exec_driver_sql(f"INSERT INTO _ask4mo_email_attempts_new ({cols}) SELECT {cols} FROM email_attempts")
        conn.exec_driver_sql("DROP TABLE email_attempts")
        if fault:
            fault()
        conn.exec_driver_sql("PRAGMA legacy_alter_table=ON")
        conn.exec_driver_sql('ALTER TABLE _ask4mo_email_attempts_new RENAME TO email_attempts')
        for _, _, _, sql in associated:
            conn.exec_driver_sql(sql)
        if sqlite_sequence:
            if seq is None:
                conn.exec_driver_sql("DELETE FROM sqlite_sequence WHERE name='email_attempts'")
            else:
                updated = conn.exec_driver_sql("UPDATE sqlite_sequence SET seq=? WHERE name='email_attempts'", (seq[0],))
                if updated.rowcount == 0:
                    conn.exec_driver_sql("INSERT INTO sqlite_sequence(name, seq) VALUES ('email_attempts', ?)", (seq[0],))
        after_rows = hashlib.sha256(repr(conn.exec_driver_sql(f"SELECT {cols} FROM email_attempts ORDER BY id").all()).encode()).hexdigest()
        after_objects = conn.exec_driver_sql("SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type, name").all()
        expected_table = re.sub(
            r'(?i)^CREATE\s+TABLE\s+(?:"email_attempts"|`email_attempts`|\[email_attempts\]|email_attempts)',
            'CREATE TABLE "email_attempts"', table_sql.replace(source_check, target_check), count=1,
        )
        expected = [(t, n, tbl, expected_table if t == 'table' and n == 'email_attempts' else sql) for t, n, tbl, sql in objects]
        if after_rows != before_rows or list(after_objects) != expected or conn.exec_driver_sql("PRAGMA table_xinfo(email_attempts)").all() != before_xinfo or conn.exec_driver_sql("PRAGMA foreign_key_list(email_attempts)").all() != before_fk:
            raise RuntimeError("SQLite schema or data preservation check failed")
        if sqlite_sequence and conn.exec_driver_sql("SELECT name, seq FROM sqlite_sequence ORDER BY name").all() != sequences:
            raise RuntimeError("SQLite sequence state changed")
        if inventory() != before_inventory or conn.exec_driver_sql("SELECT sqlite_version()").scalar_one() != sqlite_version or conn.exec_driver_sql("PRAGMA journal_mode").scalar_one() != journal or conn.exec_driver_sql("PRAGMA defer_foreign_keys").scalar_one() != deferred_fk or conn.exec_driver_sql("PRAGMA recursive_triggers").scalar_one() != recursive_triggers:
            raise RuntimeError("SQLite table/index inventory changed")
        if conn.exec_driver_sql("PRAGMA foreign_key_check").fetchone() or conn.exec_driver_sql("PRAGMA integrity_check").scalar_one() != 'ok':
            raise RuntimeError("SQLite integrity verification failed")
    except BaseException:
        conn.exec_driver_sql("ROLLBACK TO SAVEPOINT ask4mo_mail_rebuild")
        conn.exec_driver_sql("RELEASE SAVEPOINT ask4mo_mail_rebuild")
        raise
    else:
        conn.exec_driver_sql("RELEASE SAVEPOINT ask4mo_mail_rebuild")
    finally:
        conn.exec_driver_sql(f"PRAGMA legacy_alter_table={int(legacy)}")
        if conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != fk_mode:
            raise RuntimeError("SQLite foreign-key setting changed")


def _require_revision(conn, expected):
    revisions = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
    if revisions != [expected]:
        raise RuntimeError("Unexpected Alembic revision; refusing mail-attempt migration")


def upgrade():
    conn = op.get_bind()
    _require_revision(conn, down_revision)
    if conn.dialect.name == 'sqlite':
        _require_disposable_sqlite(conn)
        if not conn.connection.driver_connection.in_transaction:
            conn.exec_driver_sql('BEGIN IMMEDIATE')
        _sqlite_rebuild(conn)
    elif conn.dialect.name == 'postgresql':
        op.drop_constraint('ck_email_attempts_type', 'email_attempts', type_='check')
        op.create_check_constraint('ck_email_attempts_type', 'email_attempts', NEW)
    else:
        raise RuntimeError('Unsupported database dialect')


def downgrade():
    # The owner's narrow exception is for explicit disposable SQLite test
    # round-trips only. PostgreSQL and all other environments remain forward-only.
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        raise RuntimeError("Production downgrade of mail-attempt categories is not supported")
    _require_disposable_sqlite(conn)
    _require_revision(conn, revision)
    if not conn.connection.driver_connection.in_transaction:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    _sqlite_rebuild(conn, source_check=NEW, target_check=OLD)
