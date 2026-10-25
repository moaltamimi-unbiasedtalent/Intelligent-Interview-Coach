"""Persistent recovery quarantine, independent of restored application-table history.

A PostgreSQL database setting is installed on an unused empty target BEFORE restore.
pg_restore cannot overwrite it. Only an authorized operator reconciliation may reset
it; application images, startup and budget resume never do so.
"""
from sqlalchemy import text

RECOVERY_POLICY_VERSION = 1
SETTING = "ask4mo.recovery_pending"


def pending_session(session) -> bool:
    if session.get_bind().dialect.name != "postgresql":
        return False  # qualified operational recovery is PostgreSQL-only
    return session.execute(text("SELECT current_setting('ask4mo.recovery_pending', true)")).scalar() == "on"


def pending(session_factory) -> bool:
    with session_factory() as session:
        return pending_session(session)
