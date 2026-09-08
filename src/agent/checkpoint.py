"""Agent checkpoint saver selection (Sprint 4 Phase 8).

Chooses a LangGraph checkpointer for the HITL graph and keeps its configuration
deliberately explicit and PRIVATE:

- Preferred: an OFFICIAL persistent saver so a paused run survives another request,
  a browser refresh, application-service recreation and a process restart —
  ``SqliteSaver`` (dev) or ``PostgresSaver`` (production, optional [db] extra).
- Fallback: ``MemorySaver`` (transitional; interrupt/resume still work in-process
  but do NOT survive a restart). This is used for ``:memory:`` and when a durable
  saver cannot be built safely.

The checkpoint URL is never exposed through the API, /capabilities, events or logs.
The saver manages its OWN tables via ``setup()`` — this is separate from the
Alembic-owned application schema (never mixed, never modifies 0001/0002).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

__all__ = ["CheckpointerInfo", "build_checkpointer", "sqlite_path_from_url"]


@dataclass
class CheckpointerInfo:
    saver: Any
    kind: str          # "sqlite" | "postgres" | "memory"
    durable: bool      # survives process restart
    detail: str        # SAFE label only (never the URL/credentials)


def _resolve_url(checkpoint_url: str | None, database_url: str | None) -> str | None:
    return (
        checkpoint_url
        or os.environ.get("AGENT_CHECKPOINT_DATABASE_URL")
        or database_url
        or os.environ.get("DATABASE_URL")
    )


def sqlite_path_from_url(url: str) -> str | None:
    """Return the filesystem path for a sqlite URL, or None if not sqlite.

    Accepts ``sqlite:///rel.db``, ``sqlite:////abs.db``, ``sqlite:///:memory:`` and a
    bare path. Returns ``":memory:"`` for in-memory (which the caller treats as
    non-durable).
    """
    if not url:
        return None
    if url.startswith("sqlite"):
        # sqlite:///path  or  sqlite+pysqlite:///path
        tail = url.split(":///", 1)[1] if ":///" in url else url.split("://", 1)[-1]
        return tail or ":memory:"
    if "://" not in url:  # a bare path
        return url
    return None


def _derive_checkpoint_file(db_path: str) -> str:
    """A checkpoint file SEPARATE from the Alembic-owned application DB file."""
    directory = os.path.dirname(os.path.abspath(db_path)) or "."
    return os.path.join(directory, "agent_checkpoints.sqlite")


def build_checkpointer(
    *, checkpoint_url: str | None = None, database_url: str | None = None
) -> CheckpointerInfo:
    """Build the best available checkpointer for the resolved configuration.

    Never raises: any failure to build a durable saver degrades safely to
    ``MemorySaver`` (transitional) rather than breaking the agent.
    """
    url = _resolve_url(checkpoint_url, database_url)

    # Postgres (production) — official saver, optional dependency.
    if url and urlsplit(url).scheme.startswith("postgres"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            libpq = "postgresql://" + url.split("://", 1)[1]  # drop any +driver
            saver = PostgresSaver.from_conn_string(libpq).__enter__()
            saver.setup()
            return CheckpointerInfo(saver=saver, kind="postgres", durable=True,
                                    detail="postgres saver")
        except Exception:  # noqa: BLE001 - fall back rather than crash the app
            return _memory("postgres saver unavailable")

    # SQLite (dev/default) — official saver on a dedicated file (not :memory:).
    sqlite_path = sqlite_path_from_url(url) if url else None
    if sqlite_path and sqlite_path != ":memory:":
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            # A dedicated checkpoint file, kept separate from the application DB.
            path = sqlite_path if sqlite_path.endswith("agent_checkpoints.sqlite") \
                else _derive_checkpoint_file(sqlite_path)
            conn = sqlite3.connect(path, check_same_thread=False)
            saver = SqliteSaver(conn)
            saver.setup()
            return CheckpointerInfo(saver=saver, kind="sqlite", durable=True,
                                    detail="sqlite saver")
        except Exception:  # noqa: BLE001
            return _memory("sqlite saver unavailable")

    return _memory("in-memory (transient)")


def _memory(detail: str) -> CheckpointerInfo:
    from langgraph.checkpoint.memory import MemorySaver

    return CheckpointerInfo(saver=MemorySaver(), kind="memory", durable=False, detail=detail)
