"""A tiny throwaway SQLite session factory with the full schema, for API tests whose fake repository must still expose the DURABLE stores
(P10B-W10.11: the operator pause and feature flags are read from the database on every admission). Always under the system temp directory."""

from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence import Base


def durable_session_factory():
    path = Path(tempfile.mkdtemp(prefix="ask4mo_durable_")) / "stores.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


class DurableRepo:
    """Stands in for a repository wherever only ``session_factory`` is needed."""

    def __init__(self) -> None:
        self.session_factory = shared_session_factory()


_shared = None


def shared_session_factory():
    """One process-wide throwaway store (no pause or flag state is ever written to it by these tests)."""
    global _shared
    if _shared is None:
        _shared = durable_session_factory()
    return _shared
