"""Agent checkpoint saver selection (Sprint 4 Phase 8).

Chooses a LangGraph checkpointer for the HITL graph and keeps its configuration
deliberately explicit and PRIVATE:

- Preferred: an OFFICIAL persistent saver so a paused run survives another request,
  a browser refresh, application-service recreation and a process restart —
  ``SqliteSaver`` (dev) or ``PostgresSaver`` (production, optional [db] extra).
- Fallback: ``MemorySaver`` (transitional; interrupt/resume still work in-process
  but do NOT survive a restart).

**Fail-closed policy (pre-merge hardening).** When durability is explicitly
requested — an explicit ``AGENT_CHECKPOINT_DATABASE_URL`` / ``checkpoint_url``, or a
Postgres URL (production) — and the durable saver cannot be built, this raises
:class:`AgentConfigurationError` rather than silently downgrading to ``MemorySaver``
(which would pretend a durability that does not exist). Only an explicit transient
mode (a ``:memory:`` URL) or an unconfigured/dev sqlite file may degrade to
``MemorySaver``, and it is clearly reported (``durable=False``).

The checkpoint URL is never exposed through the API, /capabilities, events or logs.
The saver manages its OWN tables via ``setup()`` — separate from the Alembic-owned
application schema (never mixed, never modifies 0001/0002).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from src.agent.errors import AgentConfigurationError

__all__ = ["CheckpointerInfo", "build_checkpointer", "sqlite_path_from_url"]


@dataclass
class CheckpointerInfo:
    saver: Any
    kind: str          # "sqlite" | "postgres" | "memory"
    durable: bool      # survives process restart
    detail: str        # SAFE label only (never the URL/credentials)
    # A context manager whose lifetime this info owns (e.g. the Postgres saver CM),
    # kept referenced so it is not discarded and can be closed at shutdown.
    _resource: Any = field(default=None, repr=False)

    def close(self) -> None:
        """Release an owned resource (best-effort; safe to call more than once)."""
        res = self._resource
        self._resource = None
        if res is None:
            return
        try:
            exit_fn = getattr(res, "__exit__", None)
            if exit_fn is not None:
                exit_fn(None, None, None)
            else:
                close_fn = getattr(res, "close", None)
                if close_fn is not None:
                    close_fn()
        except Exception:  # noqa: BLE001 - shutdown cleanup must never raise
            pass


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

    Fails closed (raises :class:`AgentConfigurationError`) when durability is
    explicitly requested but cannot be provided; degrades to ``MemorySaver`` only for
    an explicit transient (``:memory:``) or an unconfigured/dev sqlite-file fallback.
    """
    url = _resolve_url(checkpoint_url, database_url)

    # Durability is EXPLICITLY requested via an explicit checkpoint URL (arg/env) or a
    # Postgres URL (production DBs must never be silently downgraded).
    explicit = bool(checkpoint_url or os.environ.get("AGENT_CHECKPOINT_DATABASE_URL"))
    scheme = urlsplit(url).scheme if url else ""
    require_durable = explicit or scheme.startswith("postgres")

    # Explicit transient mode: an in-memory URL always yields MemorySaver.
    sqlite_path = sqlite_path_from_url(url) if url else None
    if sqlite_path == ":memory:":
        return _memory("in-memory (explicit transient)")

    # Postgres (production) — official saver, optional dependency.
    if scheme.startswith("postgres"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            libpq = "postgresql://" + url.split("://", 1)[1]  # drop any +driver
            cm = PostgresSaver.from_conn_string(libpq)  # keep the CM; do not discard it
            saver = cm.__enter__()
            saver.setup()
            return CheckpointerInfo(saver=saver, kind="postgres", durable=True,
                                    detail="postgres saver", _resource=cm)
        except AgentConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed; never leak the URL
            raise AgentConfigurationError(
                "Durable agent checkpointing (PostgreSQL) is configured but unavailable."
            ) from exc

    # SQLite file — official saver on a dedicated file (not :memory:).
    if sqlite_path:
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            path = sqlite_path if sqlite_path.endswith("agent_checkpoints.sqlite") \
                else _derive_checkpoint_file(sqlite_path)
            conn = sqlite3.connect(path, check_same_thread=False)
            saver = SqliteSaver(conn)
            saver.setup()
            return CheckpointerInfo(saver=saver, kind="sqlite", durable=True,
                                    detail="sqlite saver", _resource=conn)
        except Exception as exc:  # noqa: BLE001
            if require_durable:
                raise AgentConfigurationError(
                    "Durable agent checkpointing (SQLite) is configured but unavailable."
                ) from exc
            return _memory("sqlite saver unavailable")

    # No usable configuration.
    if require_durable:
        raise AgentConfigurationError(
            "Durable agent checkpointing is configured but the URL is unsupported."
        )
    return _memory("in-memory (transient)")


def _memory(detail: str) -> CheckpointerInfo:
    from langgraph.checkpoint.memory import MemorySaver

    return CheckpointerInfo(saver=MemorySaver(), kind="memory", durable=False, detail=detail)
