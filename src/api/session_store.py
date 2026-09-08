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
        # session_id -> {"user_id": Any, "store": dict, "idem_key": str | None}
        self._sessions: "OrderedDict[str, dict]" = OrderedDict()
        # (user_id, idempotency_key) -> session_id. Same lifetime as the session it
        # points to (removed on eviction/discard); in-process only, like the store.
        self._idem: dict[tuple, str] = {}

    def _evict_locked(self) -> None:
        """Evict oldest sessions past the cap, cleaning their idempotency mappings."""
        while len(self._sessions) > self._max:
            _old_id, old_entry = self._sessions.popitem(last=False)
            key = old_entry.get("idem_key")
            if key is not None:
                self._idem.pop((old_entry["user_id"], key), None)

    def create(self, user_id: Any) -> str:
        """Create a fresh session for ``user_id`` and return its opaque id."""
        session_id = uuid.uuid4().hex
        with self._lock:
            self._sessions[session_id] = {"user_id": user_id, "store": {}, "idem_key": None}
            self._sessions.move_to_end(session_id)
            self._evict_locked()
        return session_id

    def create_or_get(self, user_id: Any, idempotency_key: str) -> tuple[str, bool]:
        """Return ``(session_id, created)`` for a user-scoped idempotency key.

        A repeat call with the same ``(user_id, idempotency_key)`` returns the SAME
        live session and ``created=False`` (so the caller must not re-run any
        generation). A different key — or a different user with the same key — yields
        a distinct session. Ownership is enforced by keying on ``user_id``; a key is
        never shared across users.
        """
        idem = (user_id, idempotency_key)
        with self._lock:
            existing = self._idem.get(idem)
            if existing is not None:
                entry = self._sessions.get(existing)
                if entry is not None and entry["user_id"] == user_id:
                    self._sessions.move_to_end(existing)  # LRU touch
                    return existing, False
                self._idem.pop(idem, None)  # stale (session was evicted)
            session_id = uuid.uuid4().hex
            self._sessions[session_id] = {"user_id": user_id, "store": {}, "idem_key": idempotency_key}
            self._idem[idem] = session_id
            self._sessions.move_to_end(session_id)
            self._evict_locked()
        return session_id, True

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
                key = entry.get("idem_key")
                if key is not None:
                    self._idem.pop((user_id, key), None)

    def __len__(self) -> int:  # pragma: no cover - trivial
        with self._lock:
            return len(self._sessions)
