"""TRANSITIONAL in-memory interview session store for the API.

The current persistence schema stores only *completed* interviews (via the
repository). In-progress interview state used to live in Streamlit's per-browser
``session_state``; the API has no equivalent, so this module bridges the gap with
a bounded, thread-safe, in-process store keyed by an opaque session id.

Limitations (documented on purpose):
- **In-process only** — not shared across workers/replicas; a multi-process
  deployment needs sticky routing or a shared store. Replaced when durable
  in-progress session persistence lands in a later phase.
- **Bounded** — oldest sessions are evicted past ``max_sessions`` (LRU).
- **User-scoped** — every access is checked against the owning user id, so one
  user can never touch another user's in-progress interview.

Completed interviews are still persisted durably through ``history_service``.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from typing import Any, MutableMapping

DEFAULT_MAX_SESSIONS = 500


class SessionNotFoundError(KeyError):
    """The session id is unknown, or is not owned by the requesting user."""


class InMemorySessionStore:
    """A bounded, thread-safe map of ``session_id -> (user_id, backing store)``."""

    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS) -> None:
        self._max = max_sessions
        self._lock = threading.Lock()
        # session_id -> {"user_id": Any, "store": dict}
        self._sessions: "OrderedDict[str, dict]" = OrderedDict()

    def create(self, user_id: Any) -> str:
        """Create a fresh session for ``user_id`` and return its opaque id."""
        session_id = uuid.uuid4().hex
        with self._lock:
            self._sessions[session_id] = {"user_id": user_id, "store": {}}
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)  # evict oldest
        return session_id

    def store_for(self, session_id: str, user_id: Any) -> MutableMapping[str, Any]:
        """Return the SessionManager backing store, enforcing ownership.

        Raises :class:`SessionNotFoundError` if the id is unknown or belongs to a
        different user (the two cases are indistinguishable to the caller on
        purpose, so ownership failures do not leak existence).
        """
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None or entry["user_id"] != user_id:
                raise SessionNotFoundError(session_id)
            self._sessions.move_to_end(session_id)  # LRU touch
            return entry["store"]

    def discard(self, session_id: str, user_id: Any) -> None:
        """Drop a session if it exists and is owned by ``user_id`` (no error)."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is not None and entry["user_id"] == user_id:
                self._sessions.pop(session_id, None)

    def __len__(self) -> int:  # pragma: no cover - trivial
        with self._lock:
            return len(self._sessions)
