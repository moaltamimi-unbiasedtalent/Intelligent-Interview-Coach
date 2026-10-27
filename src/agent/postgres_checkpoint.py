"""Official PostgreSQL saver connections without a retained dead session.

LangGraph 2.x accepts ConnectionPool, including the official NullConnectionPool.
Its saver serializes cursor use; max_size=1 preserves that connection bound.
Every cursor gets a new session. No graph/saver replacement or operation replay.
Imported only when PostgreSQL durability is explicitly requested.
"""

from __future__ import annotations
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import NullConnectionPool
from src.agent.errors import AgentCheckpointUnavailable
from src.backup_set.admission import SETTING

UNAVAILABLE = (
    "The assistant's saved state is temporarily unavailable. Please try again."
)
CONNECT_TIMEOUT = 2
STATEMENT_TIMEOUT_MS = 5000


def _configure(conn):
    try:
        conn.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(STATEMENT_TIMEOUT_MS),),
        )
        held = conn.execute(
            "SELECT current_setting(%s, true) AS held", (SETTING,)
        ).fetchone()
        if held["held"] == "on":
            raise AgentCheckpointUnavailable(UNAVAILABLE)
    except BaseException:
        # This NEW session has not been lent to a caller. Never close another
        # operation's borrowed connection, rebuild a graph, or reset a hold.
        conn.close()
        raise


class CheckpointPool(NullConnectionPool):
    @contextmanager
    def connection(self, timeout=None):
        try:
            with super().connection(timeout=timeout) as conn:
                yield conn
        except (psycopg.OperationalError, psycopg.InterfaceError):
            # No retry: writes may already have committed, and model/tool effects
            # must never be repeated because a checkpoint connection was lost.
            raise AgentCheckpointUnavailable(UNAVAILABLE) from None


def open_pool(libpq):
    return CheckpointPool(
        libpq,
        open=True,
        min_size=0,
        max_size=1,
        timeout=CONNECT_TIMEOUT,
        max_waiting=16,
        reconnect_timeout=CONNECT_TIMEOUT,
        num_workers=1,
        name="agent-checkpoints",
        configure=_configure,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "connect_timeout": CONNECT_TIMEOUT,
            "application_name": "ask4mo_agent_checkpoint",
            "keepalives": 1,
            "keepalives_idle": 2,
            "keepalives_interval": 1,
            "keepalives_count": 2,
            "tcp_user_timeout": 3000,
        },
    )
