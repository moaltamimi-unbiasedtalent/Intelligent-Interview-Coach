"""Migration runtime support (W12.4D-P5-B).

Alembic creates ``alembic_version.version_num`` as VARCHAR(32). Several of this project's revision identifiers are longer (for example
``0004_completed_interview_source_session`` is 39 characters), which SQLite ignores but PostgreSQL rejects (``value too long for type character varying(32)``), so a
fresh ``alembic upgrade head`` on PostgreSQL failed at revision 0004. ``widen_version_table`` creates the table with a wide column, or widens an existing narrow
one, before any migration runs. It is idempotent, changes no data and is a no-op on dialects that do not enforce the length."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION_COLUMN_WIDTH = 255


def widen_version_table(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(text(f"CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR({VERSION_COLUMN_WIDTH}) NOT NULL, "
                            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
    connection.execute(text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({VERSION_COLUMN_WIDTH})"))
    connection.commit()
