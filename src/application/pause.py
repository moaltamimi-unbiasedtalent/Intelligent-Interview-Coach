"""DURABLE operator pause (P10B-W10.11; closes SEC-W10-05).

Before W10.11 the pause switches were a process-local in-memory registry: a restart lost them and replicas disagreed (SEC-W10-05). The authority is now
the database: ``platform_pause_states`` holds one row per (environment, pausable capability). A row is an EXPLICIT pause or resume with an optimistic
``revision``; no row means "inherit the deployment baseline" (the ``PAUSED_CAPABILITIES`` environment seed, exactly the pre-W10.11 behaviour).

* Every admission decision reads the database (no cache), so a pause made by one process is seen by the next request on any other process.
* A failure to read the authoritative state is NEVER treated as "running": it raises ``PauseStateUnavailable`` and the protected request is refused
  (503, code ``platform_state_unavailable``) before any provider/model construction.
* The environment is decided by the SERVER (``API_ENV``); a request can never nominate another environment, and an unrecognised environment cannot
  mutate pause state.
* The pause set is a FIXED, bounded allow-list of capabilities (it is not a general feature-management system and not a worker kill switch).
* The reason is INTERNAL admin metadata (never returned to candidates).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.persistence import PlatformPauseState as PPS, utcnow

__all__ = [
    "PAUSABLE_CAPABILITIES", "PauseService", "PlatformPausedError", "PauseConflict", "PauseValidationError", "PauseUnsupportedEnvironment", "PauseStateUnavailable",
    "env_baseline", "MAX_REASON", "install", "uninstall", "check_paused",
]

# The FIXED set of capabilities an operator may pause. Bounded on purpose.
PAUSABLE_CAPABILITIES: tuple[str, ...] = (
    "realtime_voice",       # P7.5 realtime session creation
    "current_market",       # external market research (Adzuna / web)
    "ocr",                  # document OCR (potentially costly)
    "agent",                # Mo / agent LLM runs
    "public_registration",  # open verified-email registration
)
MAX_REASON = 200


class PauseConflict(Exception):
    """The expected revision is stale (another administrator changed this switch)."""


class PlatformPausedError(Exception):
    """A protected candidate operation was refused because its capability is paused. Carries no internal detail."""


class PauseValidationError(Exception):
    pass


class PauseUnsupportedEnvironment(Exception):
    """API_ENV is not a recognised environment, so pause state cannot be changed from this process."""


class PauseStateUnavailable(Exception):
    """The authoritative pause state could not be read. Callers must fail SAFE (refuse), never assume running."""


def env_baseline() -> set[str]:
    raw = os.environ.get("PAUSED_CAPABILITIES", "") or ""
    wanted = {c.strip() for c in raw.split(",") if c.strip()}
    return {c for c in wanted if c in PAUSABLE_CAPABILITIES}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class PauseService:
    def __init__(self, session_factory, *, environment: str | None = "from_process", clock: Callable[[], datetime] = utcnow) -> None:
        if environment == "from_process":
            from src.ai_admin.resolver import environment_name
            environment = environment_name()
        self.environment = environment             # None = unsupported (reads use the baseline; mutation refused)
        self._sf = session_factory
        self._clock = clock

    # ------------------------------------------------------------------ reads
    def _row(self, s, capability: str) -> PPS | None:
        return s.scalar(select(PPS).where(PPS.environment == (self.environment or "unsupported"), PPS.capability == capability))

    def is_paused(self, capability: str) -> bool:
        """Authoritative admission read. Raises ``PauseStateUnavailable`` if the store cannot be read (never defaults to running)."""
        if capability not in PAUSABLE_CAPABILITIES:
            raise ValueError(f"unknown pausable capability: {capability}")
        try:
            with self._sf() as s:
                row = self._row(s, capability)
                return bool(row.paused) if row is not None else capability in env_baseline()
        except Exception as exc:  # noqa: BLE001 - fixed category only; the cause is never surfaced
            raise PauseStateUnavailable("pause state unavailable") from exc

    def snapshot(self) -> dict[str, dict]:
        """{capability: state} for every pausable capability. Raises ``PauseStateUnavailable`` when the store is unreadable."""
        try:
            with self._sf() as s:
                rows = {r.capability: r for r in s.scalars(select(PPS).where(PPS.environment == (self.environment or "unsupported"))).all()}
        except Exception as exc:  # noqa: BLE001
            raise PauseStateUnavailable("pause state unavailable") from exc
        base = env_baseline()
        out: dict[str, dict] = {}
        for cap in PAUSABLE_CAPABILITIES:
            r = rows.get(cap)
            out[cap] = {
                "capability": cap, "paused": bool(r.paused) if r else cap in base, "source": "override" if r else "baseline",
                "baseline_paused": cap in base, "revision": r.revision if r else 0, "paused_at": _iso(r.paused_at) if r else None,
                "resumed_at": _iso(r.resumed_at) if r else None, "updated_at": _iso(r.updated_at) if r else None, "reason": r.reason if r else "",
            }
        return out

    def stats(self) -> dict:
        snap = self.snapshot()
        return {"environment": self.environment or "unsupported", "paused_count": sum(1 for v in snap.values() if v["paused"]),
                "paused": [c for c, v in snap.items() if v["paused"]], "durable": True}

    # ------------------------------------------------------------------ mutation (optimistic concurrency, same-transaction audit)
    def set_paused(self, capability: str, paused: bool, *, expected_revision: int, reason: Any, actor_user_id: int, audit: dict | None = None) -> dict:
        from src.admin_repository import _stage

        if capability not in PAUSABLE_CAPABILITIES:
            raise PauseValidationError("Unknown pausable capability.")
        if self.environment is None:
            raise PauseUnsupportedEnvironment("This deployment's environment is not recognised, so pause state cannot be changed here.")
        text = reason.strip() if isinstance(reason, str) else ""
        if not text or len(text) > MAX_REASON or "\x00" in text:
            raise PauseValidationError(f"A reason is required (up to {MAX_REASON} characters).")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise PauseValidationError("A valid expected revision is required.")
        now = self._clock()
        with self._sf() as s:
            row = self._row(s, capability)
            current = row.revision if row else 0
            if expected_revision != current:
                raise PauseConflict("This switch changed since you loaded it. Reload and review the current state before changing it.")
            before = bool(row.paused) if row else capability in env_baseline()
            if row is None:
                row = PPS(environment=self.environment, capability=capability, paused=paused, revision=1, updated_at=now, reason=text)
                s.add(row)
            else:
                res = s.execute(update(PPS).where(PPS.id == row.id, PPS.revision == current).values(paused=paused, revision=current + 1, updated_at=now, reason=text))
                if res.rowcount != 1:                                  # compare-and-swap lost a race
                    raise PauseConflict("This switch changed since you loaded it. Reload and review the current state before changing it.")
                s.refresh(row)
            if paused:
                row.paused_at, row.paused_by_user_id = now, actor_user_id
            else:
                row.resumed_at, row.resumed_by_user_id = now, actor_user_id
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise PauseConflict("This switch changed since you loaded it. Reload and review the current state before changing it.")
            _stage(s, {**audit, "target_id": capability} if audit else None, environment=self.environment, capability=capability, old_state="paused" if before else "running",
                   new_state="paused" if paused else "running", revision=row.revision)
            s.commit()
            return self.snapshot_one(capability)

    def snapshot_one(self, capability: str) -> dict:
        return self.snapshot()[capability]


# -- process-wide accessor for NON-request call sites (an agent tool runs inside a graph, with no request or dependency injection) -------------------
_installed: PauseService | None = None


def install(session_factory, *, environment: str | None = "from_process") -> PauseService:
    global _installed
    _installed = PauseService(session_factory, environment=environment)
    return _installed


def uninstall() -> None:
    global _installed
    _installed = None


def check_paused(capability: str) -> bool:
    """Pause check for call sites without a request. With the durable service installed (every API/worker process: ``build_repository``) the database
    is authoritative and an unreadable store counts as PAUSED (fail closed). Only a process with no database wiring at all (a bare unit test) falls
    back to the deployment baseline."""
    svc = _installed
    if svc is None:
        return capability in env_baseline()
    try:
        return svc.is_paused(capability)
    except PauseStateUnavailable:
        return True
