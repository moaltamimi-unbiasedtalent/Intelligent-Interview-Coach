"""Alembic migration environment.

The database URL comes from the ``DATABASE_URL`` environment variable (falling
back to the app default), so no credentials are stored in the repo. Target
metadata is the app's SQLAlchemy models, so autogenerate stays in sync.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from src import constants
from src.persistence import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return os.environ.get("DATABASE_URL") or constants.DEFAULT_DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_version_table_width(connection) -> None:
    """Guarantee a wide-enough ``alembic_version.version_num`` on PostgreSQL.

    Alembic creates ``alembic_version.version_num`` as ``VARCHAR(32)`` by default.
    Revision ids in this project can exceed that (``0004_completed_interview_source_session``
    is 39 characters), which is invisible on SQLite (no length enforcement) but fails
    on PostgreSQL with ``StringDataRightTruncation`` as soon as that revision is applied.
    Pre-create/upgrade the column so fresh AND already-migrated Postgres databases work.
    No-op on every other dialect.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version ("
        "version_num VARCHAR(255) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    connection.exec_driver_sql(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
    )
    connection.commit()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        _ensure_version_table_width(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
